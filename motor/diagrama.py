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


def _entidades():
    from . import catalogo

    return [catalogo.cargar_entidad(nombre) for nombre in catalogo.listar_entidades()]


def mermaid(completo: bool = False) -> str:
    """Diagrama entidad-relación. Sin `completo`, oculta los campos marcados
    como `sistema` (created_at, updated_at, ejecucion_id): están en todas las
    tablas y tapan lo que se quiere ver."""
    entidades = _entidades()
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


def resumen() -> list:
    """(tabla, descripción, nº de campos) de cada entidad del catálogo."""
    return [
        (e["tabla"], e.get("descripcion", ""), len(e["campos"]))
        for e in _entidades()
    ]


def cargas_declaradas() -> list:
    """(carga, tabla destino, para qué se hace) de cada definición de carga.

    Va junto al diagrama porque el modelo no se entiende solo mirando tablas:
    la mitad de las filas entran por una carga, y saber de qué fichero vienen
    y para qué se cargan explica el esquema tanto como las relaciones.
    """
    from . import cargas

    declaradas = []
    for ruta in cargas.listar_definiciones():
        definicion = cargas.cargar(str(ruta))
        declaradas.append(
            (
                definicion["nombre"],
                definicion.get("tabla_destino", ""),
                definicion.get("descripcion", ""),
            )
        )
    return declaradas


def desajustes(con) -> list:
    """Dónde se han separado el catálogo y el almacén."""
    entidades = _entidades()
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


def vistas_de_consumo(con) -> list:
    return sorted(
        f[0]
        for f in con.execute("SELECT view_name FROM duckdb_views() WHERE internal = false").fetchall()
    )
