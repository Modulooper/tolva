"""Perfilado de ficheros de muestra para la conversación de definición de carga.

No decide nada por sí solo: da evidencia de código (tipos aparentes, nulos,
cardinalidad, valores de muestra) y cruza las cabeceras del fichero contra
los sinónimos del catálogo para sugerir candidatos de campo destino.
"""

import csv
import re
from pathlib import Path

from . import catalogo

MUESTRA_VALORES = 5
_FECHA_RE = re.compile(r"^\s*\d{1,4}[/\-.]\d{1,4}[/\-.]\d{1,4}\s*$")


def _es_entero(v) -> bool:
    try:
        int(str(v).strip())
        return True
    except ValueError:
        return False


def _es_double_en(v) -> bool:
    try:
        float(str(v).strip())
        return True
    except ValueError:
        return False


def _es_double_es(v) -> bool:
    try:
        float(str(v).strip().replace(".", "").replace(",", "."))
        return True
    except ValueError:
        return False


def _parece_fecha(v) -> bool:
    return bool(_FECHA_RE.match(str(v).strip()))


def _tipo_aparente(valores: list) -> str:
    no_vacios = [v for v in valores if v is not None and str(v).strip() != ""]
    if not no_vacios:
        return "desconocido (todo vacío)"
    if all(_parece_fecha(v) for v in no_vacios):
        return "fecha (candidato date_format)"
    if all(_es_entero(v) for v in no_vacios):
        return "integer"
    if all(_es_double_en(v) for v in no_vacios):
        return "double"
    if all(_es_double_es(v) for v in no_vacios):
        return "double (formato_numerico: es)"
    return "varchar"


def _leer_muestra_csv(ruta: Path, delimitador: str, fila_cabecera: int, encoding: str):
    with ruta.open(encoding=encoding, newline="") as f:
        filas = list(csv.reader(f, delimiter=delimitador))
    if len(filas) < fila_cabecera:
        raise ValueError(f"el fichero tiene {len(filas)} filas, menos que fila_cabecera={fila_cabecera}")
    cabecera = filas[fila_cabecera - 1]
    datos = filas[fila_cabecera:]
    return cabecera, datos


def _leer_muestra_excel(ruta: Path, hoja, fila_cabecera: int):
    import openpyxl

    wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    if isinstance(hoja, str) and hoja:
        ws = wb[hoja]
    elif isinstance(hoja, int):
        ws = wb.worksheets[hoja]
    else:
        ws = wb.active
    filas = list(ws.iter_rows(values_only=True))
    if len(filas) < fila_cabecera:
        raise ValueError(f"el fichero tiene {len(filas)} filas, menos que fila_cabecera={fila_cabecera}")
    cabecera = [str(c) if c is not None else "" for c in filas[fila_cabecera - 1]]
    datos = filas[fila_cabecera:]
    return cabecera, datos


def perfilar(
    ruta,
    formato: str = None,
    delimitador: str = ",",
    encoding: str = "utf-8-sig",
    hoja=None,
    fila_cabecera: int = 1,
) -> dict:
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"no existe el fichero: {ruta}")

    if formato is None:
        formato = "excel" if ruta.suffix.lower() in (".xlsx", ".xlsm", ".xls") else "csv"

    if formato == "csv":
        cabecera, filas = _leer_muestra_csv(ruta, delimitador, fila_cabecera, encoding)
    else:
        cabecera, filas = _leer_muestra_excel(ruta, hoja, fila_cabecera)

    entidades = [catalogo.cargar_entidad(n) for n in catalogo.listar_entidades()]

    columnas = []
    for i, nombre_columna in enumerate(cabecera):
        valores = [fila[i] if i < len(fila) else None for fila in filas]
        no_vacios = [v for v in valores if v is not None and str(v).strip() != ""]
        distintos = list(dict.fromkeys(str(v) for v in no_vacios))

        sugerencias = []
        if nombre_columna:
            for entidad in entidades:
                campo = catalogo.buscar_por_sinonimo(entidad, nombre_columna)
                if campo:
                    sugerencias.append(f"{entidad['tabla']}.{campo}")

        columnas.append(
            {
                "columna": nombre_columna or f"(sin nombre, posición {i + 1})",
                "tipo_aparente": _tipo_aparente(valores),
                "filas_totales": len(valores),
                "nulos": len(valores) - len(no_vacios),
                "cardinalidad": len(distintos),
                "muestra_valores": distintos[:MUESTRA_VALORES],
                "sugerencias_catalogo": sugerencias,
            }
        )

    return {"fichero": str(ruta), "formato": formato, "filas_leidas": len(filas), "columnas": columnas}
