"""CLI: db migrar/consultar | etl definir/validar/dry-run/ejecutar/estado/exportar |
ticket crear/listar/editar/borrar | proceso analizar."""

import argparse
import json
import sys
from datetime import date

import duckdb

from . import cargas, db, export, motor_etl, perfil, solapamiento, tickets


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


def _cmd_etl_definir(args: argparse.Namespace) -> int:
    try:
        resultado = perfil.perfilar(
            args.fichero,
            formato=args.formato,
            delimitador=args.delimitador,
            encoding=args.encoding,
            hoja=args.hoja,
            fila_cabecera=args.fila_cabecera,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return 0

    print(f"Fichero: {resultado['fichero']}  formato={resultado['formato']}  filas_leidas={resultado['filas_leidas']}")
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
    return 0


def _cmd_etl_dry_run(args: argparse.Namespace) -> int:
    try:
        resultado = motor_etl.dry_run_carga(args.carga)
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


def _cmd_etl_ejecutar(args: argparse.Namespace) -> int:
    try:
        resultado = motor_etl.ejecutar_carga(args.carga, forzar=args.forzar)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for fr in resultado["ficheros"]:
        if fr["estado"] == "OMITIDO":
            print(f"{fr['fichero']}: OMITIDO ({fr['motivo']})")
        else:
            print(
                f"{fr['fichero']}: {fr['estado']} "
                f"(leídas={fr['filas_leidas']} ok={fr['filas_ok']} rechazadas={fr['filas_rechazadas']})"
            )
    if not resultado["ficheros"]:
        print("No hay ficheros que coincidan con el patrón.")
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


def _cmd_ticket_crear(args: argparse.Namespace) -> int:
    con = db.conectar()
    try:
        try:
            ticket_id = tickets.crear(
                con, args.cliente, args.persona, args.concepto, args.importe, args.fecha, args.descripcion
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Ticket creado: {ticket_id}")
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

    etl_parser = subparsers.add_parser("etl", help="Operaciones sobre cargas ETL")
    etl_sub = etl_parser.add_subparsers(dest="command", required=True)
    definir_parser = etl_sub.add_parser("definir", help="Perfila un fichero de muestra")
    definir_parser.add_argument("fichero")
    definir_parser.add_argument("--formato", choices=["csv", "excel"], default=None)
    definir_parser.add_argument("--delimitador", default=",")
    definir_parser.add_argument("--encoding", default="utf-8-sig")
    definir_parser.add_argument("--hoja", default=None)
    definir_parser.add_argument("--fila-cabecera", type=int, default=1, dest="fila_cabecera")
    definir_parser.add_argument("--json", action="store_true", help="Salida en JSON")
    validar_parser = etl_sub.add_parser("validar", help="Valida una definición de carga")
    validar_parser.add_argument("carga")
    dry_run_parser = etl_sub.add_parser("dry-run", help="Ejecuta sin escribir en el almacén")
    dry_run_parser.add_argument("carga")
    ejecutar_parser = etl_sub.add_parser("ejecutar", help="Ejecuta una carga")
    ejecutar_parser.add_argument("carga")
    ejecutar_parser.add_argument("--forzar", action="store_true", help="Reprocesa aunque el hash ya esté OK")
    etl_sub.add_parser("estado", help="Últimas ejecuciones registradas")
    exportar_parser = etl_sub.add_parser("exportar", help="Exporta una vista de consumo a /export")
    exportar_parser.add_argument("vista")

    ticket_parser = subparsers.add_parser("ticket", help="CRUD de tickets de gasto")
    ticket_sub = ticket_parser.add_subparsers(dest="command", required=True)

    crear_parser = ticket_sub.add_parser("crear", help="Crea un ticket")
    crear_parser.add_argument("--cliente", required=True)
    crear_parser.add_argument("--persona", required=True)
    crear_parser.add_argument("--concepto", required=True, choices=list(tickets.CONCEPTOS_VALIDOS))
    crear_parser.add_argument("--importe", required=True, type=float)
    crear_parser.add_argument("--fecha", required=True, type=date.fromisoformat)
    crear_parser.add_argument("--descripcion", default=None)

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

    if args.namespace == "etl":
        if args.command == "definir":
            return _cmd_etl_definir(args)
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

    if args.namespace == "ticket":
        if args.command == "crear":
            return _cmd_ticket_crear(args)
        if args.command == "listar":
            return _cmd_ticket_listar(args)
        if args.command == "editar":
            return _cmd_ticket_editar(args)
        if args.command == "borrar":
            return _cmd_ticket_borrar(args)

    if args.namespace == "proceso":
        if args.command == "analizar":
            return _cmd_proceso_analizar(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
