"""Conexión al almacén DuckDB y runner de migraciones."""

import hashlib
import time
from pathlib import Path

import duckdb

from . import entorno, rutas

ROOT = Path(__file__).resolve().parent.parent
# Se resuelve al importar: la ruta de los datos es configuración del entorno,
# no algo que cambie a mitad de ejecución. Ver motor/entorno.py.
DB_PATH = entorno.datos_dir() / "almacen.duckdb"
MIGRACIONES_DIR = ROOT / "migraciones"


def conectar(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def _asegurar_tabla_migraciones(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SEQUENCE IF NOT EXISTS seq_migraciones START 1")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS _migraciones (
            id BIGINT PRIMARY KEY DEFAULT nextval('seq_migraciones'),
            nombre_fichero VARCHAR NOT NULL UNIQUE,
            checksum VARCHAR NOT NULL,
            aplicada_en TIMESTAMP NOT NULL DEFAULT current_timestamp
        )
        """
    )


def _aplicadas(con: duckdb.DuckDBPyConnection) -> set:
    filas = con.execute("SELECT nombre_fichero FROM _migraciones").fetchall()
    return {fila[0] for fila in filas}


def _pendientes(migraciones_dir: Path, aplicadas: set, con_ejemplos: bool = False) -> list:
    # Núcleo primero y capa propia después: una migración propia puede
    # apoyarse en tablas del framework, nunca al revés (ver motor/rutas.py).
    ficheros = rutas.ficheros("migraciones", "*.sql", migraciones_dir, con_ejemplos=con_ejemplos)
    return [f for f in ficheros if f.name not in aplicadas]


def migrar(db_path: Path = DB_PATH, migraciones_dir: Path = MIGRACIONES_DIR,
           con_ejemplos: bool = False) -> list:
    """Aplica las migraciones pendientes en orden. Devuelve los nombres aplicados.

    Las de la capa `ejemplos/` solo entran con `con_ejemplos=True`: son datos
    dummy de un dominio inventado y nadie debe encontrárselos sin pedirlos.
    Una vez aplicadas quedan en `_migraciones` como cualquier otra, así que un
    `migrar` normal posterior no las deshace ni las vuelve a aplicar.
    """
    con = conectar(db_path)
    try:
        _asegurar_tabla_migraciones(con)
        aplicadas = _aplicadas(con)
        pendientes = _pendientes(migraciones_dir, aplicadas, con_ejemplos)
        resultado = []
        for fichero in pendientes:
            sql = fichero.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            con.execute("BEGIN TRANSACTION")
            try:
                con.execute(sql)
                con.execute(
                    "INSERT INTO _migraciones (nombre_fichero, checksum) VALUES (?, ?)",
                    [fichero.name, checksum],
                )
                con.execute("COMMIT")
            except Exception as exc:
                con.execute("ROLLBACK")
                raise RuntimeError(f"Error aplicando migración {fichero.name}: {exc}") from exc
            resultado.append(fichero.name)
        return resultado
    finally:
        con.close()


def consultar(sql: str, db_path: Path = DB_PATH):
    """Ejecuta una consulta SQL. Devuelve (columnas, filas). Queda registrada
    en `_consultas` (ver `motor/consultas.py`)."""
    from . import consultas

    con = conectar(db_path)
    inicio = time.perf_counter()
    try:
        try:
            cursor = con.execute(sql)
            columnas = [d[0] for d in cursor.description] if cursor.description else []
            filas = cursor.fetchall()
        except Exception as exc:
            consultas.registrar(
                con, sql, "consulta", duracion=time.perf_counter() - inicio,
                estado="ERROR", error=str(exc),
            )
            raise
        consultas.registrar(
            con, sql, "consulta", filas=len(filas), duracion=time.perf_counter() - inicio
        )
        return columnas, filas
    finally:
        con.close()
