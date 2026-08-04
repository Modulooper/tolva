"""Catálogo semántico: fuente de verdad de entidades y campos del modelo.

Se lee antes de proponer cualquier tabla nueva o mapping. Sirve a la
entrevista de creación de procesos, a la validación de cargas y a la
consulta. Un fichero por entidad en `/catalogo/<tabla>.json`.
"""

import json
from pathlib import Path

import jsonschema

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
    },
    "required": ["entidad", "tabla", "descripcion", "campos"],
    "additionalProperties": False,
}


def listar_entidades() -> list:
    return sorted(p.stem for p in CATALOGO_DIR.glob("*.json"))


def cargar_entidad(nombre: str) -> dict:
    ruta = CATALOGO_DIR / f"{nombre}.json"
    if not ruta.exists():
        raise FileNotFoundError(f"no hay entrada de catálogo para '{nombre}'")
    entidad = json.loads(ruta.read_text(encoding="utf-8"))
    jsonschema.validate(entidad, SCHEMA_ENTIDAD)
    return entidad


def cargar_por_tabla(tabla: str):
    """Busca la entidad del catálogo cuya tabla coincide. None si no existe."""
    for nombre in listar_entidades():
        entidad = cargar_entidad(nombre)
        if entidad.get("tabla") == tabla:
            return entidad
    return None


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
