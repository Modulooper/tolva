"""CLI: db migrar/consultar | etl definir/validar/dry-run/ejecutar/estado/exportar |
ticket crear/listar/editar/borrar | idea crear/listar/editar/borrar | proceso analizar."""

import argparse
import json
import sys
from datetime import date

import duckdb

from . import (
    cargas,
    consultas,
    db,
    diagrama,
    documentos,
    esquema,
    export,
    ideas,
    motor_etl,
    perfil,
    salidas,
    solapamiento,
    tickets,
    validaciones,
)


def _imprimir_tabla(columnas, filas) -> None:
    if not columnas:
        print("OK (sin resultado tabular)")
        return
    filas_str = [[str(v) if v is not None else "" for v in fila] for fila in filas]
    anchos = [len(c) for c in columnas]
    for fila in filas_str:
        for i, val in enumerate(fila):
            anchos[i] = max(anchos[i], len(val))
    print("  ".join(c.ljust(anchos[i]) for i, c in enumerate(columnas)))
    print("  ".join("-" * a for a in anchos))
    for fila in filas_str:
        print("  ".join(val.ljust(anchos[i]) for i, val in enumerate(fila)))
    print(f"({len(filas)} filas)")


def _cmd_db_migrar(_args: argparse.Namespace) -> int:
    try:
        aplicadas = db.migrar()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not aplicadas:
        print("No hay migraciones pendientes.")
    else:
        for nombre in aplicadas:
            print(f"Aplicada: {nombre}")
    return 0


def _cmd_db_consultar(args: argparse.Namespace) -> int:
    try:
        columnas, filas = db.consultar(args.sql)
    except duckdb.Error as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _imprimir_tabla(columnas, filas)
    return 0


def _cmd_db_uso(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        informe = consultas.analizar_uso(con, minimo_repeticiones=args.minimo)
    finally:
        con.close()

    print(f"Consultas registradas (OK): {informe['total_registradas']}")
    if informe["errores"]:
        print(f"Consultas con error: {informe['errores']}")

    print("\nUso por objeto:")
    if informe["uso_por_objeto"]:
        for objeto, veces in informe["uso_por_objeto"]:
            print(f"  {objeto}: {veces}")
    else:
        print("  (todavía no hay consultas registradas)")

    if informe["sin_uso"]:
        print("\nSin uso registrado (candidatas a revisar):")
        for objeto in informe["sin_uso"]:
            print(f"  {objeto}")

    if informe["recurrentes"]:
        print(f"\nConsultas recurrentes (>= {args.minimo} veces) — candidatas a vista de consumo:")
        for r in informe["recurrentes"]:
            print(f"  [{r['tablas']}] x{r['veces']}")
            print(f"    ej: {r['ejemplo'][:110]}")

    if informe["lentas"]:
        print("\nMás lentas:")
        for sql, origen, objeto, filas, duracion in informe["lentas"]:
            etiqueta = objeto or sql[:60]
            print(f"  {duracion*1000:.1f} ms  ({origen}, {filas} filas)  {etiqueta}")
    return 0


def _avisar_muestreo(resultado: dict) -> None:
    if resultado.get("muestreado"):
        print(
            f"AVISO: MUESTRA de {resultado['filas_leidas']} filas; el fichero tiene más.\n"
            "  Los tipos inferidos NO están garantizados para el resto: basta un decimal\n"
            "  con coma o un valor no numérico más allá de la muestra para que el tipo real\n"
            "  sea otro. Repite sin --limite antes de dar el esquema por bueno."
        )


def _cmd_etl_esquema(args: argparse.Namespace) -> int:
    try:
        perfilado = perfil.perfilar(
            args.fichero,
            formato=args.formato,
            delimitador=args.delimitador,
            encoding=args.encoding,
            hoja=args.hoja,
            fila_cabecera=args.fila_cabecera,
            limite=args.limite,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    propuesta = esquema.proponer(perfilado, args.tabla)

    if args.json:
        print(json.dumps(propuesta, indent=2, ensure_ascii=False))
        return 0

    print(f"Borrador de esquema para '{args.tabla}' ({propuesta['filas_analizadas']} filas analizadas)")
    _avisar_muestreo(perfilado)
    print("\n-- BORRADOR, revisa los avisos antes de convertirlo en migración --")
    print(propuesta["ddl"])

    dudosas = [c for c in propuesta["columnas"] if c["avisos"]]
    if dudosas:
        print("\nColumnas que necesitan decisión tuya:")
        for c in dudosas:
            print(f"\n  {c['nombre']}  (origen: {c['origen']}, inferido {c['tipo']})")
            print(f"    muestra: {c['muestra']}")
            for aviso in c["avisos"]:
                print(f"    - {aviso}")

    sin_nulos = [c["nombre"] for c in propuesta["columnas"] if c["notas"]]
    if sin_nulos:
        print(f"\nSin nulos en lo analizado (candidatas a NOT NULL): {', '.join(sin_nulos)}")

    print(
        "\nLa inferencia acierta el tipo de almacenamiento, no la semántica: "
        "revisa identificadores,\nceros a la izquierda y fechas disfrazadas de número. "
        "Con --json sale también la entrada\nde catálogo para /catalogo/<tabla>.json."
    )
    return 0


def _cmd_etl_definir(args: argparse.Namespace) -> int:
    try:
        resultado = perfil.perfilar(
            args.fichero,
            formato=args.formato,
            delimitador=args.delimitador,
            encoding=args.encoding,
            hoja=args.hoja,
            fila_cabecera=args.fila_cabecera,
            limite=args.limite,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return 0

    print(f"Fichero: {resultado['fichero']}  formato={resultado['formato']}  filas_leidas={resultado['filas_leidas']}")
    _avisar_muestreo(resultado)
    for c in resultado["columnas"]:
        print(f"\n- {c['columna']}")
        print(f"    tipo aparente: {c['tipo_aparente']}")
        print(f"    nulos: {c['nulos']}/{c['filas_totales']}   cardinalidad: {c['cardinalidad']}")
        print(f"    muestra: {c['muestra_valores']}")
        if c["sugerencias_catalogo"]:
            print(f"    sugerencia catálogo: {c['sugerencias_catalogo']}")
    return 0


def _cmd_etl_validar(args: argparse.Namespace) -> int:
    try:
        definicion = cargas.cargar(args.carga)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    con = db.conectar()
    try:
        errores = cargas.validar(definicion, con)
    finally:
        con.close()
    if errores:
        for error in errores:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: definición válida")
    print(f"\n{definicion['nombre']}: {definicion['descripcion']}")
    for aviso in cargas.avisos(definicion):
        print(f"AVISO: {aviso}")
    return 0


def _cmd_etl_dry_run(args: argparse.Namespace) -> int:
    try:
        resultado = motor_etl.dry_run_carga(args.carga, valores_parametros=_parametros_de(args))
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for fr in resultado["ficheros"]:
        print(
            f"{fr['fichero']}: leídas={fr['filas_leidas']} "
            f"ok={fr['filas_ok']} rechazadas={fr['filas_rechazadas']}"
        )
        if fr["columnas_extra"]:
            print(f"  columnas no declaradas: {fr['columnas_extra']}")
        for fila in fr["muestra_validas"]:
            print(f"  OK: {fila}")
        for num_fila, motivo, campo, raw in fr["muestra_rechazos"]:
            print(f"  RECHAZO fila {num_fila} [{campo}]: {motivo} -- {raw}")
    if not resultado["ficheros"]:
        print("No hay ficheros que coincidan con el patrón.")
    return 0


def _parametros_de(args: argparse.Namespace) -> dict:
    """Convierte los --parametro nombre=valor en un diccionario."""
    valores = {}
    for crudo in args.parametro or []:
        if "=" not in crudo:
            raise ValueError(f"--parametro espera 'nombre=valor', recibido '{crudo}'")
        nombre, valor = crudo.split("=", 1)
        valores[nombre.strip()] = valor
    return valores


def _cmd_etl_ejecutar(args: argparse.Namespace) -> int:
    try:
        resultado = motor_etl.ejecutar_carga(
            args.carga, forzar=args.forzar, valores_parametros=_parametros_de(args)
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for fr in resultado["ficheros"]:
        if fr["estado"] == "OMITIDO":
            print(f"{fr['fichero']}: OMITIDO ({fr['motivo']})")
            continue

        print(
            f"{fr['fichero']}: {fr['estado']} "
            f"(leídas={fr['filas_leidas']} ok={fr['filas_ok']} rechazadas={fr['filas_rechazadas']})"
        )

        stops = validaciones.disparadas(fr.get("validaciones", []), "stop")
        alarmas = validaciones.disparadas(fr.get("validaciones", []), "alarma")
        for r in stops + alarmas:
            print(validaciones.formatear(r))

        if fr["estado"] == "ERROR":
            print("  Carga ABORTADA: la tabla destino no se ha modificado.")
            print(f"  Ejecución {fr['ejecucion_id']} registrada. Detalle completo:")
            print(
                f"    db consultar \"SELECT * FROM _validaciones_disparadas "
                f"WHERE ejecucion_id = {fr['ejecucion_id']}\""
            )
            if fr.get("tabla_hall"):
                print(
                    f"  Los datos entrantes quedan en '{fr['tabla_hall']}' para inspeccionarlos "
                    "(hasta la siguiente carga)."
                )
        else:
            print(
                f"  promovidas={fr['filas_promovidas']} "
                f"sustituidas={fr['filas_sustituidas']} (borradas por singularidad antes de insertar)"
            )
            for s in fr.get("salidas", []):
                print(f"  salida '{s['nombre']}' ({s['filas']} filas): {s['fichero']}")
    if not resultado["ficheros"]:
        print("No hay ficheros que coincidan con el patrón.")
    return 1 if resultado["estado"] == "ERROR" else 0


def _cmd_etl_salida(args: argparse.Namespace) -> int:
    try:
        definicion = cargas.cargar(args.carga)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    declaradas = definicion.get("salidas", [])
    if args.nombre:
        declaradas = [s for s in declaradas if s["nombre"] == args.nombre]
        if not declaradas:
            print(f"ERROR: la carga '{args.carga}' no declara una salida '{args.nombre}'", file=sys.stderr)
            return 1
    if not declaradas:
        print(f"La carga '{args.carga}' no declara salidas.")
        return 0

    con = db.conectar()
    try:
        ultima = con.execute(
            "SELECT max(id) FROM _ejecuciones WHERE carga = ? AND estado = 'OK'",
            [definicion["nombre"]],
        ).fetchone()[0]
        contexto = {"carga": definicion["nombre"], "ejecucion_id": ultima}
        for salida in declaradas:
            try:
                resultado = salidas.generar(con, salida, contexto)
            except Exception as exc:
                print(f"ERROR en salida '{salida['nombre']}': {exc}", file=sys.stderr)
                return 1
            print(f"salida '{resultado['nombre']}' ({resultado['filas']} filas): {resultado['fichero']}")
    finally:
        con.close()
    return 0


def _cmd_etl_exportar(args: argparse.Namespace) -> int:
    try:
        resultado = export.exportar(args.vista)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Vista '{resultado['vista']}' exportada ({resultado['filas']} filas):")
    print(f"  {resultado['parquet']}")
    print(f"  {resultado['csv']}")
    return 0


def _cmd_etl_estado(_args: argparse.Namespace) -> int:
    columnas, filas = db.consultar(
        "SELECT id, carga, fichero, fecha, filas_leidas, filas_ok, filas_rechazadas, estado "
        "FROM _ejecuciones ORDER BY fecha DESC LIMIT 20"
    )
    _imprimir_tabla(columnas, filas)
    return 0


def _avisar_alarmas(resultados) -> None:
    for r in validaciones.disparadas(resultados or [], "alarma"):
        print(validaciones.formatear(r))


def _cmd_ticket_crear(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        try:
            ticket_id, resultados = tickets.crear(
                con, args.cliente, args.persona, args.concepto, args.importe, args.fecha,
                args.descripcion, args.documento,
            )
        except validaciones.StopError as exc:
            print(f"ERROR: no se creó el ticket.\n{exc}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Ticket creado: {ticket_id}")
        _avisar_alarmas(resultados)
        return 0
    finally:
        con.close()


def _cmd_ticket_listar(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        columnas, filas = tickets.listar(
            con, cliente=args.cliente, persona=args.persona, concepto=args.concepto,
            desde=args.desde, hasta=args.hasta,
        )
    finally:
        con.close()
    _imprimir_tabla(columnas, filas)
    return 0


def _cmd_ticket_editar(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        try:
            tickets.editar(
                con, args.id, concepto=args.concepto, descripcion=args.descripcion,
                importe=args.importe, fecha=args.fecha,
            )
        except validaciones.StopError as exc:
            print(f"ERROR: no se actualizó el ticket.\n{exc}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print("Ticket actualizado.")
        return 0
    finally:
        con.close()


def _cmd_ticket_borrar(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        try:
            tickets.borrar(con, args.id)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print("Ticket borrado.")
        return 0
    finally:
        con.close()


def _cmd_idea_crear(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        try:
            idea_id, resultados = ideas.crear(
                con, args.persona, args.texto, cliente=args.cliente, estado=args.estado,
                fecha=args.fecha, documento=args.documento,
            )
        except validaciones.StopError as exc:
            print(f"ERROR: no se creó la idea.\n{exc}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Idea creada: {idea_id}")
        _avisar_alarmas(resultados)
        return 0
    finally:
        con.close()


def _cmd_idea_listar(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        columnas, filas = ideas.listar(
            con, persona=args.persona, cliente=args.cliente, estado=args.estado,
            desde=args.desde, hasta=args.hasta,
        )
    finally:
        con.close()
    _imprimir_tabla(columnas, filas)
    return 0


def _cmd_idea_editar(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        try:
            ideas.editar(
                con, args.id, texto=args.texto, cliente=args.cliente,
                estado=args.estado, fecha=args.fecha,
            )
        except validaciones.StopError as exc:
            print(f"ERROR: no se actualizó la idea.\n{exc}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print("Idea actualizada.")
        return 0
    finally:
        con.close()


def _cmd_idea_borrar(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        try:
            ideas.borrar(con, args.id)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print("Idea borrada.")
        return 0
    finally:
        con.close()


def _cmd_db_diagrama(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        avisos = diagrama.desajustes(con)
        vistas = diagrama.vistas_de_consumo(con)
    finally:
        con.close()

    # Con la valla de ```mermaid se renderiza tal cual en el chat, en GitHub y
    # en Obsidian; en un terminal es texto inocuo.
    print("```mermaid")
    print(diagrama.mermaid(completo=args.completo))
    print("```")

    print("\n| tabla | qué es | campos |")
    print("|---|---|---|")
    for tabla, descripcion, campos in diagrama.resumen():
        print(f"| `{tabla}` | {descripcion} | {campos} |")

    declaradas = diagrama.cargas_declaradas()
    if declaradas:
        print("\n### Cómo entran los datos\n")
        for nombre, destino, descripcion in declaradas:
            # Flecha ASCII a propósito: la consola de Windows va en cp1252 y
            # una flecha U+2192 revienta el comando con UnicodeEncodeError.
            print(f"**`{nombre}` -> `{destino}`** — {descripcion}\n")

    if vistas:
        print("\nVistas de consumo: " + ", ".join(f"`{v}`" for v in vistas))
    if not args.completo:
        print("\n(campos de sistema ocultos; `--completo` los muestra)")
    for aviso in avisos:
        print(f"AVISO: {aviso}")
    return 0


def _cmd_documento_adjuntar(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        try:
            hash_doc = documentos.adjuntar(con, args.tabla, args.id, args.ruta, args.tag)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Documento adjuntado a {args.tabla} {args.id}: {hash_doc[:12]}… (tag '{args.tag or documentos.TAG_ORIGEN}')")
        return 0
    finally:
        con.close()


def _cmd_documento_listar(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        if args.tabla and args.id:
            columnas, filas = documentos.de_fila(con, args.tabla, args.id)
        elif args.ejecucion:
            columnas, filas = documentos.de_ejecucion(con, args.ejecucion)
        else:
            columnas, filas = documentos.listar(con)
    finally:
        con.close()
    _imprimir_tabla(columnas, filas)
    return 0


def _cmd_documento_purgar(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        candidatos = documentos.purgar(con, aplicar=args.aplicar)
    finally:
        con.close()
    if not candidatos:
        print("Nada que purgar: todos los documentos los conserva algún proceso.")
        return 0
    liberado = sum(fila[2] for fila in candidatos) / 1024 / 1024
    verbo = "Purgados" if args.aplicar else "Se purgarían"
    print(f"{verbo} {len(candidatos)} documentos ({liberado:.1f} MB)")
    _imprimir_tabla(["hash", "nombre", "bytes", "ruta"], candidatos)
    if not args.aplicar:
        print("\nEn seco. Repite con --aplicar para liberar los bytes.")
        print("La ficha de cada documento se conserva: solo se vacía el contenido.")
    return 0


def _cmd_proceso_analizar(args: argparse.Namespace) -> int:
    valores = [v.strip() for v in args.valores.split(",")] if args.valores else []

    resultado = {
        "campo": args.campo,
        "coincidencias_por_nombre": solapamiento.coincidencias_por_nombre(args.campo),
    }
    if valores:
        resultado["cardinalidad"] = solapamiento.cardinalidad(valores)
        con = db.conectar()
        try:
            resultado["candidatos_fk"] = solapamiento.candidatos_fk(con, valores, umbral=args.umbral)
        finally:
            con.close()

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return 0

    print(f"Campo propuesto: {resultado['campo']}")
    if resultado["coincidencias_por_nombre"]:
        print("Coincidencias por nombre/sinónimo en el catálogo:")
        for c in resultado["coincidencias_por_nombre"]:
            print(f"  - {c['tabla']}.{c['campo']}")
    else:
        print("Sin coincidencias por nombre/sinónimo en el catálogo.")

    if valores:
        card = resultado["cardinalidad"]
        print(
            f"\nCardinalidad de los valores propuestos: {card['distintos']} distintos "
            f"de {card['total']} (ratio unicidad {card['ratio_unicidad']:.2f})"
        )
        if resultado["candidatos_fk"]:
            print(f"Candidatos a clave foránea (umbral {args.umbral}):")
            for c in resultado["candidatos_fk"]:
                print(
                    f"  - {c['tabla']}.{c['columna']}: {c['coinciden']}/{c['total_propuestos']} "
                    f"coinciden (ratio {c['ratio']:.2f}) -> {c['valores_coincidentes']}"
                )
        else:
            print(f"Sin candidatos a clave foránea por encima del umbral ({args.umbral}).")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="motor")
    subparsers = parser.add_subparsers(dest="namespace", required=True)

    db_parser = subparsers.add_parser("db", help="Operaciones sobre el almacén DuckDB")
    db_sub = db_parser.add_subparsers(dest="command", required=True)
    db_sub.add_parser("migrar", help="Aplica migraciones pendientes")
    consultar_parser = db_sub.add_parser("consultar", help="Ejecuta SQL y muestra el resultado")
    consultar_parser.add_argument("sql")
    diagrama_parser = db_sub.add_parser("diagrama", help="Diagrama Mermaid del modelo, desde el catálogo")
    diagrama_parser.add_argument("--completo", action="store_true",
                                 help="Incluye también los campos de sistema")
    uso_parser = db_sub.add_parser("uso", help="Uso real del almacén según las consultas registradas")
    uso_parser.add_argument("--minimo", type=int, default=3, help="Repeticiones para considerar recurrente")

    etl_parser = subparsers.add_parser("etl", help="Operaciones sobre cargas ETL")
    etl_sub = etl_parser.add_subparsers(dest="command", required=True)
    definir_parser = etl_sub.add_parser("definir", help="Perfila un fichero de muestra")
    definir_parser.add_argument("fichero")
    definir_parser.add_argument("--formato", choices=["csv", "excel"], default=None)
    definir_parser.add_argument("--delimitador", default=",")
    definir_parser.add_argument("--encoding", default="utf-8-sig")
    definir_parser.add_argument("--hoja", default=None)
    definir_parser.add_argument("--fila-cabecera", type=int, default=1, dest="fila_cabecera")
    definir_parser.add_argument("--limite", type=int, default=None,
                                help="Analiza solo las primeras N filas (mas rapido, tipos no garantizados)")
    definir_parser.add_argument("--json", action="store_true", help="Salida en JSON")

    esquema_parser = etl_sub.add_parser("esquema", help="Borrador de CREATE TABLE a partir del perfil")
    esquema_parser.add_argument("fichero")
    esquema_parser.add_argument("--tabla", required=True)
    esquema_parser.add_argument("--formato", choices=["csv", "excel"], default=None)
    esquema_parser.add_argument("--delimitador", default=",")
    esquema_parser.add_argument("--encoding", default="utf-8-sig")
    esquema_parser.add_argument("--hoja", default=None)
    esquema_parser.add_argument("--fila-cabecera", type=int, default=1, dest="fila_cabecera")
    esquema_parser.add_argument("--limite", type=int, default=None)
    esquema_parser.add_argument("--json", action="store_true")
    validar_parser = etl_sub.add_parser("validar", help="Valida una definición de carga")
    validar_parser.add_argument("carga")
    dry_run_parser = etl_sub.add_parser("dry-run", help="Ejecuta sin escribir en el almacén")
    dry_run_parser.add_argument("carga")
    dry_run_parser.add_argument("--parametro", action="append", metavar="NOMBRE=VALOR",
                                help="Valor de un parámetro declarado por la carga (repetible)")
    ejecutar_parser = etl_sub.add_parser("ejecutar", help="Ejecuta una carga")
    ejecutar_parser.add_argument("carga")
    ejecutar_parser.add_argument("--forzar", action="store_true", help="Reprocesa aunque el hash ya esté OK")
    ejecutar_parser.add_argument("--parametro", action="append", metavar="NOMBRE=VALOR",
                                help="Valor de un parámetro declarado por la carga (repetible)")
    etl_sub.add_parser("estado", help="Últimas ejecuciones registradas")
    exportar_parser = etl_sub.add_parser("exportar", help="Exporta una vista de consumo a /export")
    exportar_parser.add_argument("vista")
    salida_parser = etl_sub.add_parser("salida", help="Genera las salidas declaradas por una carga")
    salida_parser.add_argument("carga")
    salida_parser.add_argument("--nombre", default=None, help="Genera solo la salida con ese nombre")

    ticket_parser = subparsers.add_parser("ticket", help="CRUD de tickets de gasto")
    ticket_sub = ticket_parser.add_subparsers(dest="command", required=True)

    crear_parser = ticket_sub.add_parser("crear", help="Crea un ticket")
    crear_parser.add_argument("--cliente", required=True)
    crear_parser.add_argument("--persona", required=True)
    crear_parser.add_argument("--concepto", required=True, choices=list(tickets.CONCEPTOS_VALIDOS))
    crear_parser.add_argument("--importe", required=True, type=float)
    crear_parser.add_argument("--fecha", required=True, type=date.fromisoformat)
    crear_parser.add_argument("--descripcion", default=None)
    crear_parser.add_argument("--documento", default=None, help="Justificante del que salen los datos (foto, pdf)")

    listar_parser = ticket_sub.add_parser("listar", help="Lista tickets")
    listar_parser.add_argument("--cliente", default=None)
    listar_parser.add_argument("--persona", default=None)
    listar_parser.add_argument("--concepto", default=None, choices=list(tickets.CONCEPTOS_VALIDOS))
    listar_parser.add_argument("--desde", default=None, type=date.fromisoformat)
    listar_parser.add_argument("--hasta", default=None, type=date.fromisoformat)

    editar_parser = ticket_sub.add_parser("editar", help="Edita un ticket")
    editar_parser.add_argument("id")
    editar_parser.add_argument("--concepto", default=None, choices=list(tickets.CONCEPTOS_VALIDOS))
    editar_parser.add_argument("--importe", default=None, type=float)
    editar_parser.add_argument("--fecha", default=None, type=date.fromisoformat)
    editar_parser.add_argument("--descripcion", default=None)

    borrar_parser = ticket_sub.add_parser("borrar", help="Borra un ticket")
    borrar_parser.add_argument("id")

    idea_parser = subparsers.add_parser("idea", help="CRUD de ideas sueltas")
    idea_sub = idea_parser.add_subparsers(dest="command", required=True)

    idea_crear_parser = idea_sub.add_parser("crear", help="Crea una idea")
    idea_crear_parser.add_argument("--persona", required=True)
    idea_crear_parser.add_argument("--texto", required=True)
    idea_crear_parser.add_argument("--cliente", default=None)
    idea_crear_parser.add_argument("--estado", default=None, choices=list(ideas.ESTADOS_VALIDOS))
    idea_crear_parser.add_argument("--fecha", default=None, type=date.fromisoformat)
    idea_crear_parser.add_argument("--documento", default=None, help="Fichero de origen de la idea")

    idea_listar_parser = idea_sub.add_parser("listar", help="Lista ideas")
    idea_listar_parser.add_argument("--persona", default=None)
    idea_listar_parser.add_argument("--cliente", default=None)
    idea_listar_parser.add_argument("--estado", default=None, choices=list(ideas.ESTADOS_VALIDOS))
    idea_listar_parser.add_argument("--desde", default=None, type=date.fromisoformat)
    idea_listar_parser.add_argument("--hasta", default=None, type=date.fromisoformat)

    idea_editar_parser = idea_sub.add_parser("editar", help="Edita una idea")
    idea_editar_parser.add_argument("id")
    idea_editar_parser.add_argument("--texto", default=None)
    idea_editar_parser.add_argument("--cliente", default=None)
    idea_editar_parser.add_argument("--estado", default=None, choices=list(ideas.ESTADOS_VALIDOS))
    idea_editar_parser.add_argument("--fecha", default=None, type=date.fromisoformat)

    idea_borrar_parser = idea_sub.add_parser("borrar", help="Borra una idea")
    idea_borrar_parser.add_argument("id")

    documento_parser = subparsers.add_parser("documento", help="Documentos archivados y su historial")
    documento_sub = documento_parser.add_subparsers(dest="command", required=True)

    adjuntar_parser = documento_sub.add_parser("adjuntar", help="Adjunta un fichero a un registro")
    adjuntar_parser.add_argument("tabla", help="Tabla del registro (ticket, idea...)")
    adjuntar_parser.add_argument("id", help="Id del registro")
    adjuntar_parser.add_argument("ruta", help="Ruta del fichero a archivar")
    adjuntar_parser.add_argument("--tag", default=None, help="Etiqueta del documento (p.ej. 'justificante pago')")

    doc_listar_parser = documento_sub.add_parser("listar", help="Lista documentos archivados")
    doc_listar_parser.add_argument("--tabla", default=None, help="Con --id, documentos de ese registro")
    doc_listar_parser.add_argument("--id", default=None, help="Id del registro")
    doc_listar_parser.add_argument("--ejecucion", default=None, type=int, help="Documentos de una ejecución")

    purgar_parser = documento_sub.add_parser("purgar", help="Libera los bytes que ningún proceso conserva")
    purgar_parser.add_argument("--aplicar", action="store_true", help="Borra de verdad (por defecto va en seco)")

    proceso_parser = subparsers.add_parser("proceso", help="Análisis de solapamiento para entidades nuevas")
    proceso_sub = proceso_parser.add_subparsers(dest="command", required=True)
    analizar_parser = proceso_sub.add_parser("analizar", help="Comprueba solapamiento de un campo propuesto")
    analizar_parser.add_argument("--campo", required=True, help="Nombre de campo propuesto")
    analizar_parser.add_argument("--valores", default=None, help="Valores de ejemplo separados por coma")
    analizar_parser.add_argument("--umbral", type=float, default=0.5)
    analizar_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.namespace == "db":
        if args.command == "migrar":
            return _cmd_db_migrar(args)
        if args.command == "consultar":
            return _cmd_db_consultar(args)
        if args.command == "uso":
            return _cmd_db_uso(args)
        if args.command == "diagrama":
            return _cmd_db_diagrama(args)

    if args.namespace == "etl":
        if args.command == "definir":
            return _cmd_etl_definir(args)
        if args.command == "esquema":
            return _cmd_etl_esquema(args)
        if args.command == "validar":
            return _cmd_etl_validar(args)
        if args.command == "dry-run":
            return _cmd_etl_dry_run(args)
        if args.command == "ejecutar":
            return _cmd_etl_ejecutar(args)
        if args.command == "estado":
            return _cmd_etl_estado(args)
        if args.command == "exportar":
            return _cmd_etl_exportar(args)
        if args.command == "salida":
            return _cmd_etl_salida(args)

    if args.namespace == "ticket":
        if args.command == "crear":
            return _cmd_ticket_crear(args)
        if args.command == "listar":
            return _cmd_ticket_listar(args)
        if args.command == "editar":
            return _cmd_ticket_editar(args)
        if args.command == "borrar":
            return _cmd_ticket_borrar(args)

    if args.namespace == "idea":
        if args.command == "crear":
            return _cmd_idea_crear(args)
        if args.command == "listar":
            return _cmd_idea_listar(args)
        if args.command == "editar":
            return _cmd_idea_editar(args)
        if args.command == "borrar":
            return _cmd_idea_borrar(args)

    if args.namespace == "documento":
        if args.command == "adjuntar":
            return _cmd_documento_adjuntar(args)
        if args.command == "listar":
            return _cmd_documento_listar(args)
        if args.command == "purgar":
            return _cmd_documento_purgar(args)

    if args.namespace == "proceso":
        if args.command == "analizar":
            return _cmd_proceso_analizar(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
