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
            "formato_numerico": {"enum": ["en", "es"]},
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
    "parametro": {
        "type": "object",
        "properties": {"tipo": {"const": "parametro"}, "nombre": {"type": "string", "minLength": 1}},
        "required": ["tipo", "nombre"],
        "additionalProperties": False,
    },
    # Un dato de cabecera: la sucursal en B5, el mes en B6. No está en ninguna
    # columna, así que no tiene `origen`; se lee una vez al abrir el fichero y
    # se reparte igual a todas las filas, como `const` o `parametro`.
    "celda": {
        "type": "object",
        "properties": {
            "tipo": {"const": "celda"},
            # Referencia de Excel de toda la vida: columna y fila, sin $.
            "referencia": {"type": "string", "pattern": "^[A-Za-z]{1,3}[1-9][0-9]{0,6}$"},
        },
        "required": ["tipo", "referencia"],
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


def _normalizar_numero(texto: str, formato_numerico: str) -> str:
    if formato_numerico == "es":
        return texto.replace(".", "").replace(",", ".")
    return texto


def _aplicar_cast(valor, params, contexto):
    if valor is None or str(valor).strip() == "":
        return None
    tipo_destino = params["tipo_destino"]
    texto = str(valor).strip()
    formato_numerico = params.get("formato_numerico", "en")
    if tipo_destino == "varchar":
        return texto
    if tipo_destino == "integer":
        return int(float(_normalizar_numero(texto, formato_numerico)))
    if tipo_destino == "double":
        return float(_normalizar_numero(texto, formato_numerico))
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


def _aplicar_parametro(valor, params, contexto):
    """Como const, pero el valor se resuelve al ejecutar la carga en vez de
    estar escrito en la definición."""
    return contexto.get("parametros", {}).get(params["nombre"])


def _aplicar_celda(valor, params, contexto):
    """El valor de una celda fija del propio fichero.

    A diferencia de `parametro`, que hay que teclear al lanzar la carga, esto
    lo lee del sitio donde ya está. El dato venía en el fichero: pedirlo
    aparte es invitar a que alguien escriba una sucursal por otra.
    """
    celdas = contexto.get("celdas")
    if celdas is None or params["referencia"] not in celdas:
        raise ValueError(
            f"no se pudo leer la celda {params['referencia']} del fichero "
            f"(la operación 'celda' solo funciona con formato excel)"
        )
    return celdas[params["referencia"]]


def _aplicar_date_format(valor, params, contexto):
    return fechas.aplicar_fecha(valor, contexto["resolucion_fecha"])


APLICAR = {
    "rename": _aplicar_rename,
    "trim": _aplicar_trim,
    "cast": _aplicar_cast,
    "const": _aplicar_const,
    "parametro": _aplicar_parametro,
    "celda": _aplicar_celda,
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
