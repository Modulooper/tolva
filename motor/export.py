"""Export de vistas de consumo a /export en parquet y CSV.

DuckDB bloquea el fichero de base de datos en escritura mientras hay una
conexión abierta. La conexión se cierra explícitamente al terminar el
export para que Excel/Power BI puedan leer los ficheros sin conflicto.
"""

from pathlib import Path

from . import db

ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = ROOT / "export"


def vistas_disponibles(con) -> list:
    # table_catalog != 'system' excluye las vistas internas de DuckDB
    # (duckdb_*, pg_catalog, sqlite_master...), que también viven en 'main'.
    filas = con.execute(
        "SELECT table_name FROM information_schema.views "
        "WHERE table_schema = 'main' AND table_catalog != 'system' ORDER BY 1"
    ).fetchall()
    return [f[0] for f in filas]


def exportar(nombre_vista: str, db_path=None) -> dict:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = db.conectar(db_path or db.DB_PATH)
    try:
        disponibles = vistas_disponibles(con)
        if nombre_vista not in disponibles:
            raise ValueError(f"la vista '{nombre_vista}' no existe (vistas disponibles: {disponibles})")

        ruta_parquet = EXPORT_DIR / f"{nombre_vista}.parquet"
        ruta_csv = EXPORT_DIR / f"{nombre_vista}.csv"

        con.execute(f"COPY (SELECT * FROM {nombre_vista}) TO '{ruta_parquet.as_posix()}' (FORMAT PARQUET)")
        con.execute(f"COPY (SELECT * FROM {nombre_vista}) TO '{ruta_csv.as_posix()}' (FORMAT CSV, HEADER)")

        filas = con.execute(f"SELECT count(*) FROM {nombre_vista}").fetchone()[0]
    finally:
        # Cierre explícito: mientras esta conexión viva, DuckDB mantiene el
        # fichero almacen.duckdb bloqueado en escritura, lo que impediría a
        # cualquier otro proceso (otra ejecución del motor, un cliente que
        # se conecte directo al .duckdb) acceder al almacén en paralelo.
        con.close()

    return {"vista": nombre_vista, "filas": filas, "parquet": str(ruta_parquet), "csv": str(ruta_csv)}
