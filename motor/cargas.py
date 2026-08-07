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

from . import catalogo, historial, operaciones, parametros, rutas, salidas, validaciones

ROOT = Path(__file__).resolve().parent.parent
CARGAS_DIR = ROOT / "cargas"

# Momentos del ciclo de vida en los que puede engancharse una acción o
# capturarse una variable. `tras_promover` es el único desde el que se ve el
# resultado real de la escritura: `tras_validar` corre antes de tocar el
# destino, así que desde ahí solo se ve el estado anterior más la hall.
MOMENTOS = ["antes", "tras_validar", "tras_promover", "al_fallar"]

# Nombres que el motor pone siempre. `promovidas` y `borradas` solo existen a
# partir de `tras_promover`; usarlos antes falla, que es mejor que un nulo.
VARIABLES_DE_SISTEMA = ["ejecucion_id", "carga", "fichero", "hash_fichero",
                        "promovidas", "borradas"]


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
                    "momento": {"enum": MOMENTOS},
                    "sql": {"type": "string", "minLength": 1},
                },
                "required": ["momento", "sql"],
                "additionalProperties": False,
            },
        },
        # Valores calculados durante la carga y fijados en el momento en que se
        # capturan. Cada columna de la fila resultante pasa a ser `$v_<columna>`.
        "variables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "momento": {"enum": MOMENTOS},
                    "sql": {"type": "string", "minLength": 1},
                    "descripcion": {"type": "string"},
                },
                "required": ["sql"],
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
    encontrada = rutas.resolver("cargas", f"{nombre_o_ruta}.json", CARGAS_DIR)
    # Si no está en ninguna capa se devuelve la del núcleo: quien llama ya
    # comprueba la existencia y da el mensaje de "no existe la definición".
    return encontrada if encontrada is not None else CARGAS_DIR / f"{nombre_o_ruta}.json"


def listar_definiciones() -> list:
    """Rutas de todas las definiciones, núcleo y capa propia."""
    return rutas.ficheros("cargas", "*.json", CARGAS_DIR)


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


def _todos_los_sql(definicion: dict):
    """Todos los SQL de una definición, vengan de donde vengan."""
    for accion in definicion.get("acciones", []):
        yield accion["sql"]
    for variable in definicion.get("variables", []):
        yield variable["sql"]
    for validacion in definicion.get("validaciones", []):
        yield validacion["sql"]
    for salida in definicion.get("salidas", []):
        yield salida["sql"]
    if "transformacion_sql" in definicion:
        yield definicion["transformacion_sql"]


def _parametros_usados_en_sql(definicion: dict) -> set:
    from . import sustitucion

    usados = set()
    for sql in _todos_los_sql(definicion):
        usados |= {
            n[2:] for n in sustitucion.nombres_usados(sql) if n.startswith("p_")
        }
    return usados


def _errores_de_variables(definicion: dict) -> list:
    """Que toda `$variable` usada en un SQL exista, sin ejecutar nada.

    Una errata en `$v_totl` no se descubriría hasta que la carga corre, y
    posiblemente en el peor momento: dentro de una acción que ya ha escrito
    media tabla. Aquí se caza al validar la definición.

    También se comprueba el orden: una variable capturada en `tras_promover`
    no puede usarse en algo que corre en `tras_validar`, y `$promovidas` y
    `$borradas` no existen hasta que hay promoción.
    """
    from . import sustitucion

    orden = {m: i for i, m in enumerate(MOMENTOS)}
    # `al_fallar` sucede en la rama del stop, antes de promover: lo que se ve
    # ahí es lo mismo que en `tras_validar`.
    orden["al_fallar"] = orden["tras_validar"]

    declaradas_en = {}  # nombre de variable -> primer momento en que existe
    for variable in definicion.get("variables", []):
        momento = variable.get("momento", "tras_validar")
        # No se puede saber qué columnas devuelve un SELECT sin ejecutarlo, así
        # que lo declarado no se puede verificar aquí; lo que sí se sabe es a
        # partir de cuándo estarán disponibles las que produzca.
        declaradas_en.setdefault(momento, []).append(variable["sql"])

    parametros_ = {f"p_{p['nombre']}" for p in definicion.get("parametros", [])}
    tardias = {"promovidas", "borradas"}

    def disponibles(momento):
        nombres = set(VARIABLES_DE_SISTEMA) - tardias | parametros_
        if orden.get(momento, 0) >= orden["tras_promover"]:
            nombres |= tardias
        return nombres

    errores = []

    def revisar(sql, momento, donde):
        usados = set(sustitucion.nombres_usados(sql))
        # Las `v_` no se pueden comprobar por nombre (dependen del resultado de
        # un SELECT), pero sí que haya alguna variable declarada antes.
        propias = {u for u in usados if u.startswith("v_")}
        if propias and not any(
            orden.get(m, 0) <= orden.get(momento, 0) for m in declaradas_en
        ):
            errores.append(
                f"{donde} usa {sorted('$' + p for p in propias)} pero la carga no "
                f"declara ninguna variable disponible en el momento '{momento}'"
            )
        for nombre in sorted(usados - propias - disponibles(momento)):
            if nombre in tardias:
                errores.append(
                    f"{donde} usa ${nombre}, que no existe hasta 'tras_promover' "
                    f"(este SQL corre en '{momento}')"
                )
            else:
                errores.append(
                    f"{donde} usa una variable no definida: ${nombre}. "
                    f"Disponibles: {', '.join('$' + n for n in sorted(disponibles(momento)))}"
                )

    for accion in definicion.get("acciones", []):
        revisar(accion["sql"], accion["momento"], f"la acción '{accion['momento']}'")
    for variable in definicion.get("variables", []):
        momento = variable.get("momento", "tras_validar")
        revisar(variable["sql"], momento, f"la variable de '{momento}'")
    for validacion in definicion.get("validaciones", []):
        revisar(validacion["sql"], "tras_validar", f"la validación '{validacion['nombre']}'")
    if "transformacion_sql" in definicion:
        revisar(definicion["transformacion_sql"], "tras_validar", "transformacion_sql")
    for salida in definicion.get("salidas", []):
        revisar(salida["sql"], "tras_promover", f"la salida '{salida['nombre']}'")

    return errores


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
        # Las tres operaciones que producen un valor sin leer una columna:
        # escrito en la definición, tecleado al lanzar, o leído de una celda
        # suelta del propio fichero.
        if "origen" not in campo and not tipos_op & {"const", "parametro", "celda"}:
            errores.append(
                f"campo '{campo['destino']}' no tiene 'origen' ni una operación "
                f"'const', 'parametro' o 'celda'"
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

    # Un parámetro también puede usarse solo en el SQL de la carga (`$p_x`),
    # sin llegar a ninguna columna: filtrar la transformación por la tienda es
    # tan legítimo como escribirla en una fila.
    parametros_usados |= _parametros_usados_en_sql(definicion)

    for huerfano in sorted(parametros_declarados - parametros_usados):
        errores.append(
            f"el parámetro '{huerfano}' está declarado y no lo usa ni el mapping ni ningún SQL"
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

    errores.extend(_errores_de_variables(definicion))

    if definicion["formato"] != "excel":
        celdas = [
            op["referencia"]
            for campo in definicion.get("mapping", [])
            for op in campo.get("operaciones", [])
            if op.get("tipo") == "celda"
        ]
        if celdas:
            errores.append(
                f"la operación 'celda' ({', '.join(celdas)}) requiere formato 'excel': "
                f"un CSV no tiene celdas con posición"
            )

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
