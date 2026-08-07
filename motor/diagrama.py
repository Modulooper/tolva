"""Diagrama del modelo en Mermaid, generado del catálogo semántico.

No es un fichero que alguien mantenga: se lee de `/catalogo/*.json` en cada
llamada, así que no puede enseñar un modelo que ya no existe. Mermaid se
renderiza nativo en el chat, en GitHub y en Obsidian, sin herramientas ni
imágenes de por medio.

El catálogo es la fuente porque es donde vive la semántica —qué es cada tabla,
qué campos se relacionan y por qué— que el esquema físico no sabe. A cambio,
puede separarse de la realidad, así que `desajustes()` compara con el almacén
y avisa: un diagrama desactualizado es peor que ninguno, porque te lo crees.
"""

TIPOS_MERMAID = {
    "uuid": "string",
    "varchar": "string",
    "integer": "int",
    "double": "float",
    "boolean": "bool",
    "date": "date",
    "timestamp": "datetime",
}

TABLAS_SISTEMA_PREFIJO = "_"


def _entidades(con_ejemplos: bool = False):
    from . import catalogo

    return [
        catalogo.cargar_entidad(nombre)
        for nombre in catalogo.listar_entidades(con_ejemplos=con_ejemplos)
    ]


def mermaid(completo: bool = False, con_ejemplos: bool = False) -> str:
    """Diagrama entidad-relación. Sin `completo`, oculta los campos marcados
    como `sistema` (created_at, updated_at, ejecucion_id): están en todas las
    tablas y tapan lo que se quiere ver. Sin `con_ejemplos`, deja fuera el
    dominio de ejemplo: el diagrama es del modelo, no del material de prueba."""
    entidades = _entidades(con_ejemplos)
    lineas = ["erDiagram"]
    relaciones = []

    for entidad in entidades:
        # Solo las relaciones declaradas marcan clave ajena. Deducirlo del
        # sufijo "_id" da falsos positivos: previ_transporte.oracle_carrier_id
        # es un código del sistema de origen, no una FK a ninguna tabla.
        claves_ajenas = {r["campo"] for r in entidad.get("relaciones", [])}

        lineas.append(f"    {entidad['tabla']} {{")
        for campo, meta in entidad["campos"].items():
            if meta.get("sistema") and campo != "id" and not completo:
                continue
            tipo = TIPOS_MERMAID.get(meta["tipo"], meta["tipo"])
            marca = "PK" if campo == "id" else ("FK" if campo in claves_ajenas else "")
            lineas.append(f"        {tipo} {campo} {marca}".rstrip())
        lineas.append("    }")

        for relacion in entidad.get("relaciones", []):
            campo = entidad["campos"].get(relacion["campo"], {})
            # Obligatoria: toda fila tiene destino. Opcional: puede no tenerlo.
            cardinalidad = "}|--||" if campo.get("obligatorio") else "}o--||"
            relaciones.append(
                f"    {entidad['tabla']} {cardinalidad} "
                f"{relacion['entidad_destino']} : {relacion['campo']}"
            )

    return "\n".join(lineas + relaciones)


def resumen(con_ejemplos: bool = False) -> list:
    """(tabla, descripción, nº de campos) de cada entidad del catálogo."""
    return [
        (e["tabla"], e.get("descripcion", ""), len(e["campos"]))
        for e in _entidades(con_ejemplos)
    ]


def cargas_declaradas(con_ejemplos: bool = False) -> list:
    """(carga, tabla destino, para qué se hace) de cada definición de carga.

    Va junto al diagrama porque el modelo no se entiende solo mirando tablas:
    la mitad de las filas entran por una carga, y saber de qué fichero vienen
    y para qué se cargan explica el esquema tanto como las relaciones.
    """
    from . import cargas, catalogo

    declaradas = []
    for ruta in cargas.listar_definiciones():
        definicion = cargas.cargar(str(ruta))
        if not con_ejemplos:
            # Una carga es de ejemplo si lo es la tabla en la que escribe.
            destino = catalogo.cargar_por_tabla(definicion.get("tabla_destino", ""))
            if destino and destino.get("ejemplo"):
                continue
        declaradas.append(
            (
                definicion["nombre"],
                definicion.get("tabla_destino", ""),
                definicion.get("descripcion", ""),
            )
        )
    return declaradas


def desajustes(con) -> list:
    """Dónde se han separado el catálogo y el almacén.

    Aquí las entidades de ejemplo entran **siempre**, y no por capricho: si se
    ocultasen y alguien hubiera migrado con `--con-ejemplos`, sus tablas
    aparecerían como 'existe en el almacén y no tiene ficha de catálogo'. Se
    miran las dos, y lo único que se calla es la queja simétrica —una ficha de
    ejemplo sin tabla— porque esas migraciones son opt-in y no tenerlas
    aplicadas es lo normal, no un desajuste.
    """
    entidades = _entidades(con_ejemplos=True)
    avisos = []

    tablas_reales = {
        f[0]
        for f in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }
    vistas = {
        f[0] for f in con.execute("SELECT view_name FROM duckdb_views() WHERE internal = false").fetchall()
    }
    tablas_reales -= vistas
    catalogadas = {e["tabla"] for e in entidades}

    for tabla in sorted(tablas_reales - catalogadas):
        if not tabla.startswith(TABLAS_SISTEMA_PREFIJO):
            avisos.append(f"la tabla '{tabla}' existe en el almacén y no tiene ficha de catálogo")

    for entidad in entidades:
        tabla = entidad["tabla"]
        if tabla not in tablas_reales:
            if not entidad.get("ejemplo"):
                avisos.append(f"el catálogo describe '{tabla}', que no existe en el almacén")
            continue
        columnas = {
            f[0]
            for f in con.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = ?", [tabla]
            ).fetchall()
        }
        for campo in entidad["campos"]:
            if campo not in columnas:
                avisos.append(f"'{tabla}.{campo}' está en el catálogo y no en la tabla")
        for columna in sorted(columnas - set(entidad["campos"])):
            avisos.append(f"'{tabla}.{columna}' está en la tabla y no en el catálogo")

    return avisos


def vistas_de_consumo(con, con_ejemplos: bool = False) -> list:
    """Las vistas del almacén. Las del dominio de ejemplo se ocultan igual que
    sus tablas: se reconocen porque cuelgan del nombre de una entidad marcada
    como `ejemplo` (`demo_venta` -> `demo_venta_consumo`)."""
    from . import catalogo

    todas = sorted(
        f[0]
        for f in con.execute("SELECT view_name FROM duckdb_views() WHERE internal = false").fetchall()
    )
    if con_ejemplos:
        return todas
    de_ejemplo = tuple(
        catalogo.cargar_entidad(n)["tabla"]
        for n in catalogo.listar_entidades(con_ejemplos=True)
        if catalogo.es_ejemplo(n)
    )
    return [v for v in todas if not v.startswith(de_ejemplo)] if de_ejemplo else todas
