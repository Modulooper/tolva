"""Motor de validaciones: stops y alarmas.

Una validación es un `SELECT`. Si devuelve filas, se dispara:

- **stop**: el proceso no sigue adelante y queda como no OK.
- **alarma**: el proceso avanza, pero el aviso se muestra al terminar.

Las filas devueltas son el detalle que se enseña al usuario, así que la
consulta debe seleccionar lo que identifique el problema (número de fila,
valores implicados). El motor no interpreta esas columnas: muestra las que
vengan.

El mismo motor sirve a las cargas de fichero (validaciones declaradas en
`/cargas/<nombre>.json`) y a las entidades del CLI (invariantes declarados en
`/catalogo/<tabla>.json`), para que una regla de negocio no dependa de por
dónde entren los datos.
"""

TIPOS_VALIDOS = ("stop", "alarma")

SCHEMA_VALIDACION = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string", "minLength": 1},
        "tipo": {"enum": list(TIPOS_VALIDOS)},
        "sql": {"type": "string", "minLength": 1},
        "mensaje": {"type": "string", "minLength": 1},
        "limite_detalle": {"type": "integer", "minimum": 1},
    },
    "required": ["nombre", "tipo", "sql", "mensaje"],
    "additionalProperties": False,
}

LIMITE_DETALLE_POR_DEFECTO = 5


class ValidacionInvalidaError(ValueError):
    """La consulta de una validación no es ejecutable (SQL mal formado, tabla
    inexistente...). Es un fallo de la definición, no un dato inválido: se
    trata como error duro para no dar por buena una comprobación que en
    realidad nunca llegó a comprobar nada."""


def ejecutar(con, validaciones: list, contexto: dict = None) -> list:
    """Ejecuta las validaciones y devuelve un resultado por cada una.

    `contexto` son las variables disponibles (ver `motor/sustitucion.py`). Va
    vacío cuando la validación viene del catálogo y la dispara una escritura
    del CLI: ahí no hay carga, y un invariante de tabla que dependiera de una
    variable de carga no tendría sentido.
    """
    from . import sustitucion

    resultados = []
    for validacion in validaciones or []:
        limite = validacion.get("limite_detalle", LIMITE_DETALLE_POR_DEFECTO)
        try:
            cursor = sustitucion.ejecutar(con, validacion["sql"], contexto or {})
            columnas = [d[0] for d in cursor.description] if cursor.description else []
            filas = cursor.fetchall()
        except Exception as exc:
            raise ValidacionInvalidaError(
                f"la validación '{validacion['nombre']}' no se pudo ejecutar: {exc}"
            ) from exc
        resultados.append(
            {
                "nombre": validacion["nombre"],
                "tipo": validacion["tipo"],
                "mensaje": validacion["mensaje"],
                "disparada": bool(filas),
                "afectadas": len(filas),
                "columnas": columnas,
                "detalle": filas[:limite],
            }
        )
    return resultados


def hay_stop(resultados: list) -> bool:
    return any(r["disparada"] and r["tipo"] == "stop" for r in resultados)


def disparadas(resultados: list, tipo: str = None) -> list:
    return [r for r in resultados if r["disparada"] and (tipo is None or r["tipo"] == tipo)]


class StopError(ValueError):
    """Un stop impidió completar la operación. `resultados` lleva el detalle."""

    def __init__(self, mensaje: str, resultados: list):
        super().__init__(mensaje)
        self.resultados = resultados


def proteger_escritura(con, tabla: str, escribir):
    """Ejecuta `escribir()` y comprueba después los invariantes del catálogo.

    La comprobación va después de escribir (dentro de la misma transacción)
    para que la consulta pueda ver la fila nueva: así el mismo `SELECT` sirve
    igual venga el dato de una carga o del CLI. Si salta un stop se revierte
    todo y no queda escrito nada.
    """
    from . import catalogo  # local: catalogo importa este módulo

    reglas = catalogo.validaciones_de_tabla(tabla)
    if not reglas:
        return escribir(), []

    con.execute("BEGIN TRANSACTION")
    try:
        valor = escribir()
        resultados = ejecutar(con, reglas)
        if hay_stop(resultados):
            con.execute("ROLLBACK")
            raise StopError(
                "; ".join(formatear(r) for r in disparadas(resultados, "stop")), resultados
            )
        con.execute("COMMIT")
    except StopError:
        raise
    except Exception:
        con.execute("ROLLBACK")
        raise
    return valor, resultados


def formatear(resultado: dict) -> str:
    """Texto legible de una validación disparada, con el detalle de filas."""
    etiqueta = "STOP" if resultado["tipo"] == "stop" else "ALARMA"
    lineas = [
        f"{etiqueta} '{resultado['nombre']}': {resultado['mensaje']} "
        f"({resultado['afectadas']} filas afectadas)"
    ]
    for fila in resultado["detalle"]:
        valores = ", ".join(
            f"{col}={val}" for col, val in zip(resultado["columnas"], fila)
        )
        lineas.append(f"    {valores}")
    if resultado["afectadas"] > len(resultado["detalle"]):
        lineas.append(f"    ... y {resultado['afectadas'] - len(resultado['detalle'])} más")
    return "\n".join(lineas)
