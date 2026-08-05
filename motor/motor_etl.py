"""Orquestador del motor ETL: escaneo, mapping fila a fila, promoción, rechazos.

Ningún registro pasa por el modelo. La definición de carga (ya revisada por
el usuario) es lo único que decide cómo se transforma cada columna.

Las cargas de fichero no hacen upsert fila a fila: promueven en bloque
(borrado de las combinaciones de `campos_singularidad` presentes en los datos
nuevos + inserción masiva). Ver `motor/cargas.py` para las dos formas de
carga (directa y con tabla hall).
"""

import csv
import getpass
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from . import cargas, db, operaciones


def _hash_fichero(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _leer_csv(ruta: Path, delimitador: str, fila_cabecera: int, encoding: str):
    with ruta.open(encoding=encoding, newline="") as f:
        filas = list(csv.reader(f, delimiter=delimitador))
    cabecera = filas[fila_cabecera - 1]
    datos = filas[fila_cabecera:]
    return cabecera, [dict(zip(cabecera, fila)) for fila in datos]


def _leer_excel(ruta: Path, hoja, fila_cabecera: int):
    import openpyxl

    wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    if isinstance(hoja, str) and hoja:
        ws = wb[hoja]
    elif isinstance(hoja, int):
        ws = wb.worksheets[hoja]
    else:
        ws = wb.active
    filas = list(ws.iter_rows(values_only=True))
    cabecera = [str(c) if c is not None else "" for c in filas[fila_cabecera - 1]]
    datos = filas[fila_cabecera:]
    return cabecera, [dict(zip(cabecera, fila)) for fila in datos]


def leer_fichero(ruta: Path, definicion: dict):
    if definicion["formato"] == "csv":
        return _leer_csv(
            ruta,
            definicion.get("delimitador", ","),
            definicion["fila_cabecera"],
            definicion.get("encoding", "utf-8-sig"),
        )
    return _leer_excel(ruta, definicion.get("hoja"), definicion["fila_cabecera"])


@dataclass
class ResultadoProceso:
    filas_leidas: int
    validas: list
    rechazadas: list  # tuplas (num_fila, motivo, campo_implicado, contenido_raw)
    columnas_extra: set


def procesar_filas(cabecera: list, filas: list, definicion: dict) -> ResultadoProceso:
    mapping = definicion["mapping"]
    origenes_declarados = {c["origen"] for c in mapping if "origen" in c}
    columnas_extra = {c for c in cabecera if c and c not in origenes_declarados}

    contextos = {}
    for campo in mapping:
        if "origen" not in campo:
            contextos[campo["destino"]] = {}
            continue
        valores_columna = [fila.get(campo["origen"]) for fila in filas]
        contextos[campo["destino"]] = operaciones.preparar_contexto(campo, valores_columna)

    validas, rechazadas = [], []
    for i, fila in enumerate(filas, start=definicion["fila_cabecera"] + 1):
        registro = {}
        error = None
        for campo in mapping:
            valor_origen = fila.get(campo["origen"]) if "origen" in campo else None
            try:
                registro[campo["destino"]] = operaciones.aplicar_cadena(
                    valor_origen, campo.get("operaciones", []), contextos[campo["destino"]]
                )
            except Exception as exc:
                error = (str(exc), campo["destino"])
                break
        if error:
            motivo, campo_implicado = error
            rechazadas.append(
                (i, motivo, campo_implicado, json.dumps(fila, default=str, ensure_ascii=False))
            )
            continue
        if columnas_extra:
            registro.setdefault(
                "extra_fields",
                json.dumps({c: fila.get(c) for c in columnas_extra}, default=str, ensure_ascii=False),
            )
        validas.append(registro)

    return ResultadoProceso(len(filas), validas, rechazadas, columnas_extra)


def _insertar_bloque(con, tabla: str, filas: list) -> None:
    """Inserción masiva vía DataFrame.

    DuckDB es columnar: una sentencia INSERT por fila (o una sola sentencia con
    miles de tuplas) es un antipatrón que degrada de forma no lineal — medido:
    1.000 filas por SQL tardan ~13s, mientras que 500.000 vía DataFrame tardan
    ~0,35s. Todo lo que escriba volumen en el almacén pasa por aquí.
    """
    if not filas:
        return
    import pandas as pd

    columnas = sorted({c for fila in filas for c in fila.keys()})
    df = pd.DataFrame(filas, columns=columnas)
    con.register("_bloque_entrante", df)
    try:
        con.execute(f"INSERT INTO {tabla} ({', '.join(columnas)}) SELECT * FROM _bloque_entrante")
    finally:
        con.unregister("_bloque_entrante")


def _borrar_combinaciones(con, tabla: str, campos_singularidad: list, filas: list) -> int:
    """Borra de `tabla` las filas cuya combinación de campos_singularidad aparezca
    en `filas`. Devuelve cuántas se borraron.

    Sin campos_singularidad la carga es acumulativa pura: no borra nada.
    """
    if not campos_singularidad or not filas:
        return 0
    import pandas as pd

    combinaciones = pd.DataFrame(
        [{c: fila.get(c) for c in campos_singularidad} for fila in filas]
    ).drop_duplicates()
    con.register("_combinaciones_entrantes", combinaciones)
    try:
        condicion = " AND ".join(f"t.{c} IS NOT DISTINCT FROM e.{c}" for c in campos_singularidad)
        borradas = con.execute(
            f"SELECT count(*) FROM {tabla} t "
            f"WHERE EXISTS (SELECT 1 FROM _combinaciones_entrantes e WHERE {condicion})"
        ).fetchone()[0]
        con.execute(
            f"DELETE FROM {tabla} t "
            f"WHERE EXISTS (SELECT 1 FROM _combinaciones_entrantes e WHERE {condicion})"
        )
    finally:
        con.unregister("_combinaciones_entrantes")
    return borradas


def _cargar_hall(con, tabla_hall: str, filas: list) -> None:
    """La hall es siempre foto completa: se vacía entera y se recarga."""
    con.execute(f"DELETE FROM {tabla_hall}")
    _insertar_bloque(con, tabla_hall, filas)


def _promover(con, tabla_destino: str, campos_singularidad: list, filas: list) -> int:
    """Borra en bloque las combinaciones de singularidad presentes en `filas` e
    inserta `filas`. Sin campos_singularidad, solo acumula."""
    borradas = _borrar_combinaciones(con, tabla_destino, campos_singularidad, filas)
    _insertar_bloque(con, tabla_destino, filas)
    return borradas


def _promover_desde_sql(con, tabla_destino: str, campos_singularidad: list, sql_origen: str) -> tuple:
    """Promoción sin pasar los datos por Python: el borrado y la inserción se
    resuelven dentro del motor a partir del SELECT de transformación.

    Traer las filas transformadas a Python solo para reinsertarlas obligaría a
    materializarlas dos veces (fetchall + DataFrame); DuckDB puede hacer todo
    el trayecto hall -> destino internamente.
    """
    con.execute(f"CREATE OR REPLACE TEMP TABLE _transformadas AS {sql_origen}")
    promovidas = con.execute("SELECT count(*) FROM _transformadas").fetchone()[0]
    columnas = [f[0] for f in con.execute("DESCRIBE _transformadas").fetchall()]

    borradas = 0
    if campos_singularidad:
        condicion = " AND ".join(f"t.{c} IS NOT DISTINCT FROM e.{c}" for c in campos_singularidad)
        existe = f"EXISTS (SELECT 1 FROM _transformadas e WHERE {condicion})"
        borradas = con.execute(f"SELECT count(*) FROM {tabla_destino} t WHERE {existe}").fetchone()[0]
        con.execute(f"DELETE FROM {tabla_destino} t WHERE {existe}")

    con.execute(
        f"INSERT INTO {tabla_destino} ({', '.join(columnas)}) SELECT {', '.join(columnas)} FROM _transformadas"
    )
    con.execute("DROP TABLE _transformadas")
    return promovidas, borradas


def _validar_o_lanzar(definicion: dict, con) -> None:
    errores = cargas.validar(definicion, con)
    if errores:
        raise ValueError("definición inválida: " + "; ".join(errores))


def dry_run_carga(nombre_carga: str, db_path=None) -> dict:
    """Ejecuta sin escribir nada en el almacén. Devuelve resultado y rechazos."""
    definicion = cargas.cargar(nombre_carga)
    con = db.conectar(db_path or db.DB_PATH)
    try:
        _validar_o_lanzar(definicion, con)
        carpeta = cargas.carpeta_entrada(definicion)
        ficheros = sorted(carpeta.glob(definicion["patron"]))
        resultados = []
        for ruta in ficheros:
            cabecera, filas = leer_fichero(ruta, definicion)
            resultado = procesar_filas(cabecera, filas, definicion)
            resultados.append(
                {
                    "fichero": ruta.name,
                    "filas_leidas": resultado.filas_leidas,
                    "filas_ok": len(resultado.validas),
                    "filas_rechazadas": len(resultado.rechazadas),
                    "muestra_validas": resultado.validas[:5],
                    "muestra_rechazos": resultado.rechazadas[:5],
                    "columnas_extra": sorted(resultado.columnas_extra),
                }
            )
        return {"carga": definicion["nombre"], "ficheros": resultados}
    finally:
        con.close()


def _procesar_fichero(con, definicion: dict, ruta: Path, forzar: bool) -> dict:
    hash_fichero = _hash_fichero(ruta)
    nombre_carga = definicion["nombre"]

    if not forzar:
        ya_ok = con.execute(
            "SELECT count(*) FROM _ejecuciones WHERE carga = ? AND hash_fichero = ? AND estado = 'OK'",
            [nombre_carga, hash_fichero],
        ).fetchone()[0]
        if ya_ok:
            return {"fichero": ruta.name, "estado": "OMITIDO", "motivo": "ya procesado (mismo hash)"}

    inicio = time.perf_counter()
    cabecera, filas = leer_fichero(ruta, definicion)
    resultado = procesar_filas(cabecera, filas, definicion)
    # Si se llega aquí, el fichero se leyó y procesó fila a fila sin excepción:
    # las filas inválidas quedan en _rechazos, no convierten la ejecución en un fallo.
    estado = "OK"

    campos_singularidad = definicion.get("campos_singularidad", [])

    con.execute("BEGIN TRANSACTION")
    try:
        if cargas.usa_hall(definicion):
            # 1) la hall se sustituye entera con lo que trae el fichero,
            # 2) la transformación SQL (la T) produce las filas finales,
            # 3) esas filas se promueven a la tabla destino sin salir del motor.
            _cargar_hall(con, definicion["tabla_hall"], resultado.validas)
            promovidas, borradas = _promover_desde_sql(
                con, definicion["tabla_destino"], campos_singularidad, definicion["transformacion_sql"]
            )
        else:
            promovidas = len(resultado.validas)
            borradas = _promover(
                con, definicion["tabla_destino"], campos_singularidad, resultado.validas
            )
        ejecucion_id = con.execute(
            """INSERT INTO _ejecuciones
               (carga, fichero, hash_fichero, filas_leidas, filas_ok, filas_rechazadas, estado, duracion, usuario)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            [
                nombre_carga,
                ruta.name,
                hash_fichero,
                resultado.filas_leidas,
                len(resultado.validas),
                len(resultado.rechazadas),
                estado,
                time.perf_counter() - inicio,
                getpass.getuser(),
            ],
        ).fetchone()[0]
        _insertar_bloque(
            con,
            "_rechazos",
            [
                {
                    "ejecucion_id": ejecucion_id,
                    "num_fila": num_fila,
                    "motivo": motivo,
                    "campo_implicado": campo,
                    "contenido_raw": raw,
                }
                for num_fila, motivo, campo, raw in resultado.rechazadas
            ],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    if resultado.columnas_extra:
        print(f"AVISO: columnas no declaradas en '{ruta.name}': {sorted(resultado.columnas_extra)}")

    return {
        "fichero": ruta.name,
        "estado": estado,
        "filas_leidas": resultado.filas_leidas,
        "filas_ok": len(resultado.validas),
        "filas_rechazadas": len(resultado.rechazadas),
        "filas_promovidas": promovidas,
        "filas_sustituidas": borradas,
    }


def ejecutar_carga(nombre_carga: str, forzar: bool = False, db_path=None) -> dict:
    definicion = cargas.cargar(nombre_carga)
    con = db.conectar(db_path or db.DB_PATH)
    try:
        _validar_o_lanzar(definicion, con)
        carpeta = cargas.carpeta_entrada(definicion)
        ficheros = sorted(carpeta.glob(definicion["patron"]))
        resumen = [_procesar_fichero(con, definicion, ruta, forzar) for ruta in ficheros]
        return {"carga": definicion["nombre"], "ficheros": resumen}
    finally:
        con.close()
