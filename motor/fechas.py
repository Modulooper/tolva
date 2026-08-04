"""Resolución de columnas de fecha: ambigüedad día/mes y seriales de Excel.

El parseo de fechas nunca se delega al modelo. `resolver_formato_columna` se
ejecuta una vez por columna, sobre todos los valores, antes de procesar filas.
"""

import re
from datetime import date, datetime, timedelta

EPOCH_1900 = date(1899, 12, 30)  # compensa el bug del año bisiesto 1900 de Excel
EPOCH_1904 = date(1904, 1, 1)

SERIAL_MIN = 1
SERIAL_MAX = 60000  # rango plausible para fechas de negocio (~hasta el año 2064)

_COMPONENTES_RE = re.compile(r"^\s*(\d{1,4})[/\-.](\d{1,4})[/\-.](\d{1,4})\s*$")

PARES_AMBIGUOS = [
    ("%d/%m/%Y", "%m/%d/%Y"),
    ("%d/%m/%y", "%m/%d/%y"),
    ("%d-%m-%Y", "%m-%d-%Y"),
    ("%d-%m-%y", "%m-%d-%y"),
]


class FechaAmbiguaError(ValueError):
    pass


def es_serial_excel(valor) -> bool:
    if isinstance(valor, bool):
        return False
    if isinstance(valor, (int, float)):
        return SERIAL_MIN <= valor <= SERIAL_MAX
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto or _COMPONENTES_RE.match(texto):
            return False
        try:
            numero = float(texto)
        except ValueError:
            return False
        return SERIAL_MIN <= numero <= SERIAL_MAX
    return False


def serial_a_fecha(valor, epoch: str = "1900") -> date:
    base = EPOCH_1900 if epoch == "1900" else EPOCH_1904
    return base + timedelta(days=float(valor))


def _componentes(valor: str):
    m = _COMPONENTES_RE.match(valor)
    if not m:
        return None
    return tuple(int(g) for g in m.groups())


def resolver_ambiguedad_dia_mes(valores_columna: list, formato_dm: str, formato_md: str) -> str:
    """Decide entre un formato día/mes y uno mes/día según evidencia sobre TODA la columna.

    Si algún valor tiene primer componente > 12, ese componente solo puede ser día.
    Si algún valor tiene segundo componente > 12, ese componente solo puede ser mes.
    Evidencia contradictoria o ausente -> falla explícitamente, no se adivina.
    """
    evidencia_dm = False
    evidencia_md = False
    for valor in valores_columna:
        if valor is None or not isinstance(valor, str) or not valor.strip():
            continue
        comp = _componentes(valor)
        if comp is None:
            continue
        primero, segundo, _ = comp
        if primero > 12:
            evidencia_dm = True
        if segundo > 12:
            evidencia_md = True

    if evidencia_dm and evidencia_md:
        raise FechaAmbiguaError(
            "Evidencia contradictoria: la columna tiene valores que solo pueden ser "
            "día/mes y otros que solo pueden ser mes/día. Formato irresoluble por evidencia; "
            "confirma el formato explícitamente (un único formato en 'formatos')."
        )
    if evidencia_dm:
        return formato_dm
    if evidencia_md:
        return formato_md
    raise FechaAmbiguaError(
        f"No hay evidencia suficiente en la columna para distinguir entre "
        f"'{formato_dm}' y '{formato_md}'. Confirma el formato explícitamente "
        "(un único formato en 'formatos')."
    )


def _formato_valido_para_columna(valores, formato) -> bool:
    for v in valores:
        try:
            datetime.strptime(str(v).strip(), formato)
        except ValueError:
            return False
    return True


def resolver_formato_columna(valores_columna: list, candidatos: list, epoch_excel: str = "1900") -> dict:
    """Determina cómo interpretar una columna de fechas antes de procesar fila a fila.

    Devuelve {"modo": "serial", "epoch": ...} o {"modo": "formato", "formato": "%d/%m/%Y"}.
    """
    no_vacios = [v for v in valores_columna if v is not None and str(v).strip() != ""]

    if no_vacios and all(es_serial_excel(v) for v in no_vacios):
        return {"modo": "serial", "epoch": epoch_excel}

    if len(candidatos) == 1:
        return {"modo": "formato", "formato": candidatos[0]}

    par = tuple(candidatos)
    par_inverso = tuple(reversed(candidatos))
    if len(candidatos) == 2 and (par in PARES_AMBIGUOS or par_inverso in PARES_AMBIGUOS):
        formato_dm, formato_md = par if par in PARES_AMBIGUOS else par_inverso
        formato_resuelto = resolver_ambiguedad_dia_mes(no_vacios, formato_dm, formato_md)
        return {"modo": "formato", "formato": formato_resuelto}

    for candidato in candidatos:
        if _formato_valido_para_columna(no_vacios, candidato):
            return {"modo": "formato", "formato": candidato}

    raise FechaAmbiguaError(f"Ningún formato candidato {candidatos} es válido para toda la columna.")


def aplicar_fecha(valor, resolucion: dict):
    """Parsea un valor individual según la resolución ya calculada para su columna."""
    if valor is None or str(valor).strip() == "":
        return None
    if resolucion["modo"] == "serial":
        if not es_serial_excel(valor):
            raise ValueError(f"'{valor}' no es un serial de Excel plausible")
        return serial_a_fecha(valor, resolucion["epoch"])
    return datetime.strptime(str(valor).strip(), resolucion["formato"]).date()
