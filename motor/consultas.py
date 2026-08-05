"""Registro de consultas al almacén y análisis de uso.

Qué se consulta y se extrae queda en `_consultas`. El análisis responde a
tres preguntas: qué tablas/vistas se usan de verdad (y cuáles no las toca
nadie), qué consultas se repiten (candidatas a vista de consumo) y cuáles
tardan.

No propone índices: medido sobre 497.383 filas, un índice no mejora la
consulta de punto ni el agregado, y empeora el filtro por texto (ver
`_decisiones`, migración 011). DuckDB es columnar y ya mantiene zonemaps
automáticos en todas las columnas.

Las tablas referenciadas por una consulta se extraen del AST que devuelve el
propio DuckDB (`json_serialize_sql`), no con expresiones regulares: igual que
el parseo de fechas, se resuelve por evidencia y no por adivinación.
"""

import getpass
import json

# Tablas de sistema: se excluyen del análisis de uso para que las propias
# consultas de mantenimiento no aparezcan como "uso del modelo".
TABLAS_SISTEMA = ("_consultas", "_ejecuciones", "_rechazos", "_decisiones", "_migraciones")


def registrar(con, sql: str, origen: str, objeto=None, filas=None, duracion=None,
              estado: str = "OK", error=None) -> None:
    """Registra una consulta. Nunca hace fallar a quien la llama: el registro
    es observabilidad, no puede tumbar la operación que estaba en curso."""
    try:
        con.execute(
            """INSERT INTO _consultas (sql, origen, objeto, filas, duracion, estado, error, usuario)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [sql, origen, objeto, filas, duracion, estado, error, getpass.getuser()],
        )
    except Exception:
        pass


def _recorrer(nodo, encontradas: set) -> None:
    """Recorre el AST acumulando los nombres de BASE_TABLE a cualquier
    profundidad (joins, subconsultas, CTEs)."""
    if isinstance(nodo, dict):
        if nodo.get("type") == "BASE_TABLE" and nodo.get("table_name"):
            encontradas.add(nodo["table_name"])
        for valor in nodo.values():
            _recorrer(valor, encontradas)
    elif isinstance(nodo, list):
        for elemento in nodo:
            _recorrer(elemento, encontradas)


def tablas_de(con, sql: str) -> list:
    """Tablas/vistas referenciadas por una consulta, según el parser de DuckDB.
    Lista vacía si la consulta no es parseable."""
    try:
        serializado = con.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()[0]
        ast = json.loads(serializado)
    except Exception:
        return []
    if ast.get("error"):
        return []
    encontradas = set()
    _recorrer(ast.get("statements", []), encontradas)
    return sorted(encontradas)


def _objetos_del_almacen(con) -> set:
    filas = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_catalog != 'system'"
    ).fetchall()
    return {f[0] for f in filas if not f[0].startswith("_")}


def analizar_uso(con, minimo_repeticiones: int = 3) -> dict:
    """Uso real del almacén a partir de `_consultas`."""
    registros = con.execute(
        "SELECT sql, origen, objeto, filas, duracion, estado FROM _consultas WHERE estado = 'OK'"
    ).fetchall()

    uso = {}
    por_firma = {}
    for sql, origen, objeto, filas, duracion, _estado in registros:
        tablas = [t for t in tablas_de(con, sql) if t not in TABLAS_SISTEMA]
        # Un export no lleva SQL de usuario: la vista exportada es su objeto.
        if origen == "export" and objeto:
            tablas = [objeto]
        for tabla in tablas:
            uso[tabla] = uso.get(tabla, 0) + 1
        if origen == "consulta" and tablas:
            # Firma = conjunto de tablas tocadas. Agrupa consultas de la misma
            # forma aunque cambien los literales, sin tener que normalizar texto.
            firma = ", ".join(tablas)
            entrada = por_firma.setdefault(firma, {"veces": 0, "ejemplo": sql})
            entrada["veces"] += 1

    existentes = _objetos_del_almacen(con)
    sin_uso = sorted(existentes - set(uso))

    lentas = con.execute(
        """SELECT sql, origen, objeto, filas, duracion FROM _consultas
           WHERE estado = 'OK' AND duracion IS NOT NULL
           ORDER BY duracion DESC LIMIT 5"""
    ).fetchall()

    errores = con.execute(
        "SELECT count(*) FROM _consultas WHERE estado = 'ERROR'"
    ).fetchone()[0]

    return {
        "total_registradas": len(registros),
        "uso_por_objeto": sorted(uso.items(), key=lambda x: -x[1]),
        "sin_uso": sin_uso,
        "recurrentes": sorted(
            (
                {"tablas": firma, "veces": datos["veces"], "ejemplo": datos["ejemplo"]}
                for firma, datos in por_firma.items()
                if datos["veces"] >= minimo_repeticiones
            ),
            key=lambda x: -x["veces"],
        ),
        "lentas": lentas,
        "errores": errores,
    }
