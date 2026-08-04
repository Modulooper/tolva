"""Carga, valida y resuelve definiciones de carga (`/cargas/<nombre>.json`)."""

import json
from pathlib import Path

import jsonschema

from . import catalogo, operaciones

ROOT = Path(__file__).resolve().parent.parent
CARGAS_DIR = ROOT / "cargas"

SCHEMA_DEFINICION = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string", "minLength": 1},
        "carpeta": {"type": "string", "minLength": 1},
        "patron": {"type": "string", "minLength": 1},
        "formato": {"enum": ["csv", "excel"]},
        "delimitador": {"type": "string", "minLength": 1},
        "encoding": {"type": "string", "minLength": 1},
        "hoja": {"type": ["string", "integer", "null"]},
        "fila_cabecera": {"type": "integer", "minimum": 1},
        "tabla_destino": {"type": "string", "minLength": 1},
        "clave_upsert": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "mapping": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "origen": {"type": "string"},
                    "destino": {"type": "string", "minLength": 1},
                    "operaciones": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["destino", "operaciones"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "nombre",
        "carpeta",
        "patron",
        "formato",
        "fila_cabecera",
        "tabla_destino",
        "clave_upsert",
        "mapping",
    ],
    "additionalProperties": False,
}


def ruta_definicion(nombre_o_ruta: str) -> Path:
    p = Path(nombre_o_ruta)
    if p.suffix == ".json" and p.exists():
        return p
    return CARGAS_DIR / f"{nombre_o_ruta}.json"


def carpeta_entrada(definicion: dict) -> Path:
    carpeta = Path(definicion["carpeta"])
    return carpeta if carpeta.is_absolute() else ROOT / carpeta


def cargar(nombre_o_ruta: str) -> dict:
    ruta = ruta_definicion(nombre_o_ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"no existe la definición de carga: {ruta}")
    return json.loads(ruta.read_text(encoding="utf-8"))


def validar(definicion: dict, con=None) -> list:
    """Devuelve la lista de errores encontrados (vacía si es válida). No lanza excepción."""
    errores = []
    try:
        jsonschema.validate(definicion, SCHEMA_DEFINICION)
    except jsonschema.ValidationError as exc:
        errores.append(f"estructura inválida: {exc.message}")
        return errores

    if definicion["formato"] == "csv" and "delimitador" not in definicion:
        errores.append("formato 'csv' requiere 'delimitador'")

    destinos = []
    for campo in definicion["mapping"]:
        destinos.append(campo["destino"])
        if "origen" not in campo and not any(
            op.get("tipo") == "const" for op in campo.get("operaciones", [])
        ):
            errores.append(f"campo '{campo['destino']}' no tiene 'origen' ni una operación 'const'")
        for op in campo.get("operaciones", []):
            try:
                operaciones.validar_operacion(op)
            except ValueError as exc:
                errores.append(f"campo '{campo['destino']}': {exc}")

    if len(set(destinos)) != len(destinos):
        errores.append("hay campos destino duplicados en el mapping")

    for clave in definicion["clave_upsert"]:
        if clave not in destinos:
            errores.append(f"clave de upsert '{clave}' no está en el mapping")

    errores.extend(catalogo.validar_mapping_contra_catalogo(definicion["tabla_destino"], destinos))

    if con is not None:
        tabla = definicion["tabla_destino"]
        filas = con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            [tabla],
        ).fetchall()
        columnas_tabla = {f[0] for f in filas}
        if not columnas_tabla:
            errores.append(f"la tabla destino '{tabla}' no existe en el almacén")
        else:
            for destino in destinos:
                if destino not in columnas_tabla:
                    errores.append(f"campo destino '{destino}' no existe en la tabla '{tabla}'")

    return errores
