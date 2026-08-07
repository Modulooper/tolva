"""Catálogo semántico: fuente de verdad de entidades y campos del modelo.

Se lee antes de proponer cualquier tabla nueva o mapping. Sirve a la
entrevista de creación de procesos, a la validación de cargas y a la
consulta. Un fichero por entidad en `/catalogo/<tabla>.json`.
"""

import json
from pathlib import Path

import jsonschema

from . import historial, rutas, validaciones

ROOT = Path(__file__).resolve().parent.parent
CATALOGO_DIR = ROOT / "catalogo"

SCHEMA_ENTIDAD = {
    "type": "object",
    "properties": {
        "entidad": {"type": "string", "minLength": 1},
        "tabla": {"type": "string", "minLength": 1},
        "descripcion": {"type": "string"},
        "campos": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "tipo": {"enum": ["uuid", "varchar", "integer", "double", "boolean", "date", "timestamp"]},
                    "obligatorio": {"type": "boolean"},
                    "sistema": {"type": "boolean"},
                    "descripcion": {"type": "string"},
                    "sinonimos": {"type": "array", "items": {"type": "string"}},
                    "validacion": {"type": "object"},
                },
                "required": ["tipo", "obligatorio", "descripcion"],
                "additionalProperties": False,
            },
        },
        # Con qué columna se nombra a una de estas en lenguaje humano, para
        # poder referirse a ella sin el uuid (`--set demo_libro="El jardín de
        # arena"`). Por defecto `nombre` si la entidad lo tiene; se declara
        # cuando la etiqueta es otra cosa, como `titulo`.
        "etiqueta": {"type": "string", "minLength": 1},
        # Marca las entidades del dominio de ejemplo (`ejemplos/`). Quien
        # recorre el catálogo las ignora por defecto: sin esto, los datos
        # dummy contaminarían el análisis de solapamiento y las sugerencias
        # de campo destino al perfilar un fichero real.
        "ejemplo": {"type": "boolean"},
        "historial": historial.SCHEMA_HISTORIAL,
        "relaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "campo": {"type": "string"},
                    "entidad_destino": {"type": "string"},
                    "campo_destino": {"type": "string"},
                    "tipo": {"type": "string"},
                },
                "required": ["campo", "entidad_destino"],
                "additionalProperties": False,
            },
        },
        # Invariantes de la tabla: se comprueban en cualquier escritura, venga
        # de una carga o del CLI, para que la regla no dependa de por dónde
        # entren los datos.
        "validaciones": {"type": "array", "items": validaciones.SCHEMA_VALIDACION},
    },
    "required": ["entidad", "tabla", "descripcion", "campos"],
    "additionalProperties": False,
}


def listar_entidades(con_ejemplos: bool = False) -> list:
    """Entidades del catálogo, **sin las de ejemplo** salvo que se pidan.

    El defecto es ocultarlas a propósito. Todo lo que recorre el catálogo
    entero saca conclusiones de lo que encuentra —candidatos a clave foránea,
    campos destino sugeridos, el diagrama del modelo— y un dominio dummy
    metido ahí produce respuestas falsas sobre datos reales. Solo pide
    `con_ejemplos=True` la maquinaria que necesita resolver una entidad
    concreta por su tabla (`cargar_por_tabla`), porque ahí no se está
    infiriendo nada: se está buscando algo que ya se sabe que existe.
    """
    nombres = rutas.nombres("catalogo", "*.json", CATALOGO_DIR)
    if con_ejemplos:
        return nombres
    return [n for n in nombres if not es_ejemplo(n)]


def es_ejemplo(nombre: str) -> bool:
    """Si la entidad pertenece al dominio de ejemplo. Una ficha ilegible o
    inválida no se considera de ejemplo: mejor que se vea y falle donde toca."""
    try:
        return bool(cargar_entidad(nombre).get("ejemplo", False))
    except (FileNotFoundError, json.JSONDecodeError, jsonschema.ValidationError):
        return False


def cargar_entidad(nombre: str) -> dict:
    ruta = rutas.resolver("catalogo", f"{nombre}.json", CATALOGO_DIR)
    if ruta is None:
        raise FileNotFoundError(f"no hay entrada de catálogo para '{nombre}'")
    entidad = json.loads(ruta.read_text(encoding="utf-8"))
    jsonschema.validate(entidad, SCHEMA_ENTIDAD)
    return entidad


def cargar_por_tabla(tabla: str):
    """Busca la entidad del catálogo cuya tabla coincide. None si no existe.

    Mira también las de ejemplo: aquí no se infiere nada, se resuelve una
    tabla concreta que alguien ya ha nombrado (la destino de una carga, por
    ejemplo), y ocultarla solo produciría un 'no tiene entrada en el
    catálogo' incomprensible.
    """
    for nombre in listar_entidades(con_ejemplos=True):
        entidad = cargar_entidad(nombre)
        if entidad.get("tabla") == tabla:
            return entidad
    return None


def validaciones_de_tabla(tabla: str) -> list:
    """Invariantes declarados en el catálogo para esa tabla ([] si no hay)."""
    try:
        entidad = cargar_por_tabla(tabla)
    except jsonschema.ValidationError:
        return []
    return entidad.get("validaciones", []) if entidad else []


def campos_declarados(entidad: dict) -> set:
    return set(entidad.get("campos", {}).keys())


def buscar_por_sinonimo(entidad: dict, nombre_origen: str):
    """Devuelve el nombre canónico del campo cuyo sinónimo coincide (case-insensitive), o None."""
    objetivo = nombre_origen.strip().lower()
    for campo, meta in entidad.get("campos", {}).items():
        if campo.lower() == objetivo:
            return campo
        if any(s.strip().lower() == objetivo for s in meta.get("sinonimos", [])):
            return campo
    return None


def validar_mapping_contra_catalogo(tabla_destino: str, destinos: list) -> list:
    """Errores si la tabla no tiene entrada de catálogo, o si algún campo del
    mapping no está declarado en ella. Se usa desde `cargas.validar`."""
    try:
        entidad = cargar_por_tabla(tabla_destino)
    except jsonschema.ValidationError as exc:
        return [f"catálogo de '{tabla_destino}' inválido: {exc.message}"]
    if entidad is None:
        return [f"la tabla destino '{tabla_destino}' no tiene entrada en el catálogo (/catalogo)"]
    campos = campos_declarados(entidad)
    errores = []
    for destino in destinos:
        if destino not in campos:
            errores.append(
                f"campo '{destino}' no está declarado en el catálogo de '{tabla_destino}' "
                f"(campos válidos: {sorted(campos)})"
            )
    return errores
