"""Conexión al almacén DuckDB y runner de migraciones."""

import hashlib
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "datos" / "almacen.duckdb"
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


def _pendientes(migraciones_dir: Path, aplicadas: set) -> list:
    ficheros = sorted(migraciones_dir.glob("*.sql"))
    return [f for f in ficheros if f.name not in aplicadas]


def migrar(db_path: Path = DB_PATH, migraciones_dir: Path = MIGRACIONES_DIR) -> list:
    """Aplica las migraciones pendientes en orden. Devuelve los nombres aplicados."""
    con = conectar(db_path)
    try:
        _asegurar_tabla_migraciones(con)
        aplicadas = _aplicadas(con)
        pendientes = _pendientes(migraciones_dir, aplicadas)
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
    """Ejecuta una consulta SQL. Devuelve (columnas, filas)."""
    con = conectar(db_path)
    try:
        cursor = con.execute(sql)
        columnas = [d[0] for d in cursor.description] if cursor.description else []
        filas = cursor.fetchall()
        return columnas, filas
    finally:
        con.close()
