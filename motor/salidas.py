"""Salidas: ficheros de resultado generados a partir de un SELECT.

Una salida es un `SELECT` (sobre cualquier tabla o vista del almacén) volcado
a un fichero cuyo nombre se compone con la fecha y datos de la ejecución, por
ejemplo `20260805_previ_ok.xlsx`.

Se declaran en la definición de carga y se generan al terminar una carga
correcta, o se piden a mano con `etl salida`. A diferencia de
`etl exportar <vista>`, que vuelca una vista de consumo a un nombre fijo en
parquet y CSV, aquí el SQL y el nombre son libres.
"""

from datetime import datetime
from pathlib import Path

from . import entorno

ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = entorno.ruta("export")

FORMATOS = {".csv": "csv", ".parquet": "parquet", ".xlsx": "xlsx"}

SCHEMA_SALIDA = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string", "minLength": 1},
        "fichero": {"type": "string", "minLength": 1},
        "sql": {"type": "string", "minLength": 1},
        "carpeta": {"type": "string", "minLength": 1},
    },
    "required": ["nombre", "fichero", "sql"],
    "additionalProperties": False,
}


def formato_de(nombre_fichero: str) -> str:
    sufijo = Path(nombre_fichero).suffix.lower()
    if sufijo not in FORMATOS:
        raise ValueError(
            f"extensión '{sufijo}' no soportada en salidas (usa {', '.join(sorted(FORMATOS))})"
        )
    return FORMATOS[sufijo]


def resolver_nombre(plantilla: str, contexto: dict, momento: datetime = None) -> str:
    """Compone el nombre del fichero.

    Admite marcas de fecha de strftime (`%Y%m%d` -> 20260805) y campos entre
    llaves del contexto de la ejecución (`{carga}`, `{ejecucion_id}`).
    """
    momento = momento or datetime.now()
    return momento.strftime(plantilla).format(**contexto)


def _escribir_xlsx(con, sql: str, ruta: Path, valores: list = None) -> None:
    """Escribe xlsx con la extensión `excel` de DuckDB, que resuelve el volcado
    dentro del motor. Si no está disponible (por ejemplo, sin red para
    instalarla la primera vez), se recurre a openpyxl, que ya es dependencia
    del proyecto pero pasa las filas por Python.

    `sql` llega ya con sus marcadores y `valores` con lo que enlazar."""
    valores = valores or []
    try:
        con.execute("INSTALL excel; LOAD excel;")
        # HEADER true es obligatorio aquí: sin él la primera fila del fichero ya
        # es un dato y quien lo abra en Excel no sabe qué columna es cada cosa.
        con.execute(
            f"COPY ({sql}) TO '{ruta.as_posix()}' (FORMAT xlsx, HEADER true)", valores
        )
        return
    except Exception:
        pass

    import openpyxl

    cursor = con.execute(sql, valores)
    columnas = [d[0] for d in cursor.description]
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet()
    ws.append(columnas)
    for fila in cursor.fetchall():
        ws.append(list(fila))
    wb.save(ruta)


def generar(con, salida: dict, contexto: dict = None) -> dict:
    """Genera una salida. Devuelve la ruta y el número de filas escritas.

    El mismo `contexto` sirve para las dos cosas: las llaves del nombre de
    fichero (`{carga}`) y las variables del SQL (`$p_tienda`). Son sintaxis
    distintas a propósito, porque el nombre de fichero se compone pegando
    texto y el SQL nunca.
    """
    from . import sustitucion

    contexto = contexto or {}
    nombre_fichero = resolver_nombre(salida["fichero"], contexto)
    formato = formato_de(nombre_fichero)

    carpeta = Path(salida.get("carpeta", EXPORT_DIR))
    if not carpeta.is_absolute():
        carpeta = ROOT / carpeta
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre_fichero

    # Se resuelve una vez y se reutiliza: el SQL entra en tres sentencias
    # distintas (contar, copiar, volcar) y las tres necesitan los mismos
    # valores enlazados en el mismo orden.
    sql, valores = sustitucion.resolver(salida["sql"], contexto)
    filas = con.execute(f"SELECT count(*) FROM ({sql})", valores).fetchone()[0]

    if formato == "csv":
        con.execute(f"COPY ({sql}) TO '{ruta.as_posix()}' (FORMAT CSV, HEADER)", valores)
    elif formato == "parquet":
        con.execute(f"COPY ({sql}) TO '{ruta.as_posix()}' (FORMAT PARQUET)", valores)
    else:
        _escribir_xlsx(con, sql, ruta, valores)

    return {"nombre": salida["nombre"], "fichero": str(ruta), "filas": filas, "formato": formato}


def generar_todas(con, definicion: dict, contexto: dict = None) -> list:
    return [generar(con, salida, contexto) for salida in definicion.get("salidas", [])]
