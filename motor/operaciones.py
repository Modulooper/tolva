"""Vocabulario cerrado de operaciones del motor ETL.

Una definición de carga que use un tipo no registrado aquí se rechaza al
validarse, no en ejecución. Para añadir una operación: registrar su JSON
Schema en SCHEMAS y su función en APLICAR.
"""

from datetime import datetime

import jsonschema

from . import fechas

SCHEMAS = {
    "rename": {
        "type": "object",
        "properties": {"tipo": {"const": "rename"}},
        "required": ["tipo"],
        "additionalProperties": False,
    },
    "trim": {
        "type": "object",
        "properties": {"tipo": {"const": "trim"}},
        "required": ["tipo"],
        "additionalProperties": False,
    },
    "cast": {
        "type": "object",
        "properties": {
            "tipo": {"const": "cast"},
            "tipo_destino": {"enum": ["varchar", "integer", "double", "boolean", "date"]},
        },
        "required": ["tipo", "tipo_destino"],
        "additionalProperties": False,
    },
    "const": {
        "type": "object",
        "properties": {"tipo": {"const": "const"}, "valor": {}},
        "required": ["tipo", "valor"],
        "additionalProperties": False,
    },
    "date_format": {
        "type": "object",
        "properties": {
            "tipo": {"const": "date_format"},
            "formatos": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "epoch_excel": {"enum": ["1900", "1904"]},
        },
        "required": ["tipo", "formatos"],
        "additionalProperties": False,
    },
}

_BOOLEANOS_VERDADEROS = {"true", "1", "si", "sí", "yes", "verdadero"}
_BOOLEANOS_FALSOS = {"false", "0", "no", "falso"}


def _aplicar_rename(valor, params, contexto):
    return valor


def _aplicar_trim(valor, params, contexto):
    if valor is None:
        return None
    return str(valor).strip()


def _aplicar_cast(valor, params, contexto):
    if valor is None or str(valor).strip() == "":
        return None
    tipo_destino = params["tipo_destino"]
    texto = str(valor).strip()
    if tipo_destino == "varchar":
        return texto
    if tipo_destino == "integer":
        return int(float(texto))
    if tipo_destino == "double":
        return float(texto)
    if tipo_destino == "boolean":
        texto_l = texto.lower()
        if texto_l in _BOOLEANOS_VERDADEROS:
            return True
        if texto_l in _BOOLEANOS_FALSOS:
            return False
        raise ValueError(f"'{valor}' no es interpretable como boolean")
    if tipo_destino == "date":
        return datetime.fromisoformat(texto).date()
    raise ValueError(f"tipo_destino desconocido: {tipo_destino}")


def _aplicar_const(valor, params, contexto):
    return params["valor"]


def _aplicar_date_format(valor, params, contexto):
    return fechas.aplicar_fecha(valor, contexto["resolucion_fecha"])


APLICAR = {
    "rename": _aplicar_rename,
    "trim": _aplicar_trim,
    "cast": _aplicar_cast,
    "const": _aplicar_const,
    "date_format": _aplicar_date_format,
}


def validar_operacion(op: dict) -> None:
    tipo = op.get("tipo")
    if tipo not in SCHEMAS:
        raise ValueError(f"operación no registrada en el vocabulario: '{tipo}'")
    try:
        jsonschema.validate(op, SCHEMAS[tipo])
    except jsonschema.ValidationError as exc:
        raise ValueError(f"operación '{tipo}' inválida: {exc.message}") from exc


def preparar_contexto(campo_mapping: dict, valores_columna: list) -> dict:
    """Precomputa lo necesario a nivel de columna (p.ej. resolución de fecha)
    antes de procesar filas, para no repetir el análisis por cada valor."""
    contexto = {}
    for op in campo_mapping.get("operaciones", []):
        if op["tipo"] == "date_format":
            contexto["resolucion_fecha"] = fechas.resolver_formato_columna(
                valores_columna, op["formatos"], op.get("epoch_excel", "1900")
            )
    return contexto


def aplicar_cadena(valor, operaciones_campo: list, contexto: dict):
    for op in operaciones_campo:
        valor = APLICAR[op["tipo"]](valor, op, contexto)
    return valor
