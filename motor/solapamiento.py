"""Comprobaciones de código para detectar solapamiento entre una entidad
nueva propuesta y el modelo de datos existente (catálogo + almacén).

Usado por la skill `crear-proceso` antes de proponer ninguna tabla: la
detección de solapamiento se apoya en evidencia de datos, no solo en
criterio del modelo.
"""

from . import catalogo


def coincidencias_por_nombre(nombre_campo: str) -> list:
    """Cruza un nombre de campo propuesto contra nombres canónicos y
    sinónimos de TODAS las entidades del catálogo."""
    coincidencias = []
    for nombre_entidad in catalogo.listar_entidades():
        entidad = catalogo.cargar_entidad(nombre_entidad)
        campo = catalogo.buscar_por_sinonimo(entidad, nombre_campo)
        if campo:
            coincidencias.append({"tabla": entidad["tabla"], "campo": campo})
    return coincidencias


def _valores_existentes(con, tabla: str, columna: str) -> set:
    filas = con.execute(f"SELECT DISTINCT {columna} FROM {tabla} WHERE {columna} IS NOT NULL").fetchall()
    return {str(f[0]).strip().lower() for f in filas}


def solapamiento_de_valores(con, valores_propuestos: list, tabla: str, columna: str) -> dict:
    """Compara un conjunto de valores propuestos contra los valores reales de
    una columna existente. Devuelve evidencia cuantitativa, no una opinión."""
    existentes = _valores_existentes(con, tabla, columna)
    propuestos = {str(v).strip().lower() for v in valores_propuestos if v and str(v).strip()}
    if not propuestos:
        return {"tabla": tabla, "columna": columna, "coinciden": 0, "total_propuestos": 0, "ratio": 0.0}
    coinciden = propuestos & existentes
    return {
        "tabla": tabla,
        "columna": columna,
        "coinciden": len(coinciden),
        "total_propuestos": len(propuestos),
        "ratio": len(coinciden) / len(propuestos),
        "valores_coincidentes": sorted(coinciden)[:10],
    }


def candidatos_fk(con, valores_propuestos: list, umbral: float = 0.5) -> list:
    """Recorre los campos varchar no-sistema de todas las entidades del
    catálogo buscando solapamiento de valores por encima del umbral.
    Candidatos a clave foránea, ordenados por ratio de coincidencia."""
    candidatos = []
    for nombre_entidad in catalogo.listar_entidades():
        entidad = catalogo.cargar_entidad(nombre_entidad)
        tabla = entidad["tabla"]
        for campo, meta in entidad.get("campos", {}).items():
            if meta.get("tipo") != "varchar" or meta.get("sistema"):
                continue
            resultado = solapamiento_de_valores(con, valores_propuestos, tabla, campo)
            if resultado["total_propuestos"] > 0 and resultado["ratio"] >= umbral:
                candidatos.append(resultado)
    return sorted(candidatos, key=lambda r: r["ratio"], reverse=True)


def cardinalidad(valores: list) -> dict:
    """Da evidencia de si un conjunto de valores se parece más a una
    categoría cerrada (pocos distintos) o a una entidad propia (muchos)."""
    no_vacios = [str(v).strip() for v in valores if v is not None and str(v).strip() != ""]
    distintos = set(no_vacios)
    return {
        "total": len(no_vacios),
        "distintos": len(distintos),
        "ratio_unicidad": (len(distintos) / len(no_vacios)) if no_vacios else 0.0,
    }
