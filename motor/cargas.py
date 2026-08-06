"""Carga, valida y resuelve definiciones de carga (`/cargas/<nombre>.json`).

Dos formas de carga:
- Directa: el mapping produce las filas finales, que se promueven a
  `tabla_destino`.
- Con hall: el mapping produce filas de staging que sustituyen entera la
  tabla `tabla_hall` (siempre "borra todo y carga lo nuevo", sin
  singularidad); `transformacion_sql` es un SELECT sobre esa hall (con joins
  a otras tablas si hace falta) que produce las filas finales a promover.

En ambos casos, la promoción a `tabla_destino` usa `campos_singularidad`:
sin campos, acumula sin más; con campos, borra en bloque las combinaciones
de esos campos presentes en las filas nuevas antes de insertar (ver
`motor/motor_etl.py::_promover`). No hay upsert fila a fila para cargas de
fichero — eso queda para las acciones puntuales del CLI conversacional
(`ticket editar`, `idea editar`...).
"""

import json
from pathlib import Path

import jsonschema

from . import catalogo, historial, operaciones, parametros, salidas, validaciones

ROOT = Path(__file__).resolve().parent.parent
CARGAS_DIR = ROOT / "cargas"

SCHEMA_DEFINICION = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string", "minLength": 1},
        # No es un rótulo: es para qué se hace esta carga y qué trae el fichero.
        # El mapping ya dice a qué columna va cada cosa; esto dice lo que el
        # mapping no puede — de dónde sale el fichero, qué es una fila, qué
        # significa volver a subirlo. El mínimo corta los "Carga de bancos".
        "descripcion": {"type": "string", "minLength": 40},
        "carpeta": {"type": "string", "minLength": 1},
        "patron": {"type": "string", "minLength": 1},
        "formato": {"enum": ["csv", "excel"]},
        "delimitador": {"type": "string", "minLength": 1},
        "encoding": {"type": "string", "minLength": 1},
        "hoja": {"type": ["string", "integer", "null"]},
        "fila_cabecera": {"type": "integer", "minimum": 1},
        "tabla_destino": {"type": "string", "minLength": 1},
        "tabla_hall": {"type": "string", "minLength": 1},
        "transformacion_sql": {"type": "string", "minLength": 1},
        "campos_singularidad": {"type": "array", "items": {"type": "string"}},
        "validaciones": {"type": "array", "items": validaciones.SCHEMA_VALIDACION},
        "salidas": {"type": "array", "items": salidas.SCHEMA_SALIDA},
        "historial": historial.SCHEMA_HISTORIAL,
        "parametros": {"type": "array", "items": parametros.SCHEMA_PARAMETRO},
        "acciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "momento": {"enum": ["antes", "tras_validar", "al_fallar"]},
                    "sql": {"type": "string", "minLength": 1},
                },
                "required": ["momento", "sql"],
                "additionalProperties": False,
            },
        },
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
        "descripcion",
        "carpeta",
        "patron",
        "formato",
        "fila_cabecera",
        "tabla_destino",
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


def usa_hall(definicion: dict) -> bool:
    return "tabla_hall" in definicion


def avisos(definicion: dict) -> list:
    """Cosas que no invalidan la definición pero conviene mirar antes de cargar.

    Hoy solo una, y es la que más caro sale: un parámetro obligatorio que no
    entra en la singularidad. Si la tienda no forma parte de la clave que se
    borra, recargar el fichero de una tienda se lleva por delante las filas de
    las demás. No es error porque hay casos legítimos (un comentario no
    identifica nada), pero conviene verlo.
    """
    campos_singularidad = definicion.get("campos_singularidad", [])
    if not campos_singularidad:
        # Sin singularidad la carga es acumulativa a propósito: no borra nada.
        return []

    destino_de = {}
    for campo in definicion.get("mapping", []):
        for op in campo.get("operaciones", []):
            if op.get("tipo") == "parametro":
                destino_de[op["nombre"]] = campo["destino"]

    avisos_ = []
    for parametro in parametros.declarados(definicion):
        if not parametro.get("obligatorio"):
            continue
        destino = destino_de.get(parametro["nombre"])
        if destino and destino not in campos_singularidad:
            avisos_.append(
                f"el parámetro obligatorio '{parametro['nombre']}' llega a '{destino}', "
                f"que no está en campos_singularidad {campos_singularidad}: al recargar, "
                f"el fichero de un valor borrará las filas de los demás"
            )
    return avisos_


def validar(definicion: dict, con=None) -> list:
    """Devuelve la lista de errores encontrados (vacía si es válida). No lanza excepción."""
    errores = []
    try:
        jsonschema.validate(definicion, SCHEMA_DEFINICION)
    except jsonschema.ValidationError as exc:
        # Sin la ruta, un "'Carga de bancos' is too short" no dice qué campo
        # hay que arreglar. jsonschema la trae en json_path ($.descripcion).
        ubicacion = exc.json_path.removeprefix("$.") if exc.json_path != "$" else ""
        errores.append(
            f"estructura inválida{f' en {ubicacion}' if ubicacion else ''}: {exc.message}"
        )
        return errores

    if definicion["formato"] == "csv" and "delimitador" not in definicion:
        errores.append("formato 'csv' requiere 'delimitador'")

    tiene_hall = "tabla_hall" in definicion
    tiene_transform = "transformacion_sql" in definicion
    if tiene_hall != tiene_transform:
        errores.append("'tabla_hall' y 'transformacion_sql' van siempre juntos, o ninguno de los dos")

    parametros_declarados = parametros.nombres(definicion)
    parametros_usados = set()

    destinos = []
    for campo in definicion["mapping"]:
        destinos.append(campo["destino"])
        tipos_op = {op.get("tipo") for op in campo.get("operaciones", [])}
        if "origen" not in campo and not tipos_op & {"const", "parametro"}:
            errores.append(
                f"campo '{campo['destino']}' no tiene 'origen' ni una operación 'const' o 'parametro'"
            )
        for op in campo.get("operaciones", []):
            try:
                operaciones.validar_operacion(op)
            except ValueError as exc:
                errores.append(f"campo '{campo['destino']}': {exc}")
            if op.get("tipo") == "parametro":
                parametros_usados.add(op["nombre"])
                if op["nombre"] not in parametros_declarados:
                    errores.append(
                        f"campo '{campo['destino']}': usa el parámetro '{op['nombre']}', "
                        f"que no está en 'parametros' {sorted(parametros_declarados) or '(vacío)'}"
                    )

    for huerfano in sorted(parametros_declarados - parametros_usados):
        errores.append(
            f"el parámetro '{huerfano}' está declarado pero no lo usa ningún campo del mapping"
        )

    if len(set(destinos)) != len(destinos):
        errores.append("hay campos destino duplicados en el mapping")

    nombres_validacion = [v["nombre"] for v in definicion.get("validaciones", [])]
    if len(set(nombres_validacion)) != len(nombres_validacion):
        errores.append("hay validaciones con el mismo 'nombre'")

    for salida in definicion.get("salidas", []):
        try:
            salidas.formato_de(salida["fichero"])
        except ValueError as exc:
            errores.append(f"salida '{salida['nombre']}': {exc}")

    campos_singularidad = definicion.get("campos_singularidad", [])

    if tiene_hall:
        # El mapping alimenta la tabla_hall, no tabla_destino directamente.
        errores.extend(catalogo.validar_mapping_contra_catalogo(definicion["tabla_hall"], destinos))
    else:
        errores.extend(catalogo.validar_mapping_contra_catalogo(definicion["tabla_destino"], destinos))
        for clave in campos_singularidad:
            if clave not in destinos:
                errores.append(f"campo de singularidad '{clave}' no está en el mapping")

    if con is not None:
        tabla_mapping = definicion["tabla_hall"] if tiene_hall else definicion["tabla_destino"]
        filas = con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            [tabla_mapping],
        ).fetchall()
        columnas_tabla = {f[0] for f in filas}
        if not columnas_tabla:
            errores.append(f"la tabla '{tabla_mapping}' no existe en el almacén")
        else:
            for destino in destinos:
                if destino not in columnas_tabla:
                    errores.append(f"campo destino '{destino}' no existe en la tabla '{tabla_mapping}'")

        if tiene_hall and not errores:
            try:
                columnas_salida = [
                    fila[0] for fila in con.execute(f"DESCRIBE {definicion['transformacion_sql']}").fetchall()
                ]
            except Exception as exc:
                errores.append(f"'transformacion_sql' inválida: {exc}")
            else:
                errores.extend(
                    catalogo.validar_mapping_contra_catalogo(definicion["tabla_destino"], columnas_salida)
                )
                for clave in campos_singularidad:
                    if clave not in columnas_salida:
                        errores.append(
                            f"campo de singularidad '{clave}' no está entre las columnas de 'transformacion_sql'"
                        )

    return errores
