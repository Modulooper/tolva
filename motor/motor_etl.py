"""Orquestador del motor ETL: escaneo, mapping fila a fila, upsert, rechazos.

Ningún registro pasa por el modelo. La definición de carga (ya revisada por
el usuario) es lo único que decide cómo se transforma cada columna.
"""

import csv
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


def _upsert(con, tabla: str, clave_upsert: list, filas: list) -> None:
    if not filas:
        return
    columnas = sorted({c for fila in filas for c in fila.keys()})
    lista_cols = ", ".join(columnas)
    placeholders = ", ".join("?" for _ in columnas)
    actualizables = [c for c in columnas if c not in clave_upsert]
    conflicto = ", ".join(clave_upsert)
    if actualizables:
        set_clause = ", ".join(f"{c} = excluded.{c}" for c in actualizables)
        sql = (
            f"INSERT INTO {tabla} ({lista_cols}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflicto}) DO UPDATE SET {set_clause}"
        )
    else:
        sql = (
            f"INSERT INTO {tabla} ({lista_cols}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflicto}) DO NOTHING"
        )
    for fila in filas:
        con.execute(sql, [fila.get(c) for c in columnas])


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

    con.execute("BEGIN TRANSACTION")
    try:
        _upsert(con, definicion["tabla_destino"], definicion["clave_upsert"], resultado.validas)
        ejecucion_id = con.execute(
            """INSERT INTO _ejecuciones
               (carga, fichero, hash_fichero, filas_leidas, filas_ok, filas_rechazadas, estado, duracion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            [
                nombre_carga,
                ruta.name,
                hash_fichero,
                resultado.filas_leidas,
                len(resultado.validas),
                len(resultado.rechazadas),
                estado,
                time.perf_counter() - inicio,
            ],
        ).fetchone()[0]
        for num_fila, motivo, campo, raw in resultado.rechazadas:
            con.execute(
                """INSERT INTO _rechazos (ejecucion_id, num_fila, motivo, campo_implicado, contenido_raw)
                   VALUES (?, ?, ?, ?, ?)""",
                [ejecucion_id, num_fila, motivo, campo, raw],
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
