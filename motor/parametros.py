"""Parámetros de carga: lo que no viene dentro del fichero.

Un mismo formato de fichero puede llegar de sitios distintos sin que el dato
que los distingue esté en ninguna columna: veinte tiendas mandan el mismo
export de pedidos (fecha, importe, producto) y la tienda no aparece por
ningún lado. Eso se declara como parámetro y se pide al ejecutar la carga.

    "parametros": [
      {"nombre": "tienda", "obligatorio": true,
       "valores_de": {"tabla": "tienda", "etiqueta": "nombre"}},
      {"nombre": "comentario", "obligatorio": false}
    ]

Con `valores_de` la lista es cerrada: el valor se resuelve contra esa tabla
por nombre, igual que `ticket crear --cliente`, y lo que llega a la fila es
su id. Sin `valores_de`, es texto libre.

El valor llega a las filas por el mapping, con la operación `parametro`:

    {"destino": "tienda_id", "operaciones": [{"tipo": "parametro", "nombre": "tienda"}]}

Se hace así, y no por un canal aparte, para que un parámetro se comporte
exactamente igual que cualquier otra columna: mismas operaciones encadenables
detrás, mismo tratamiento en la hall y en las transformaciones.
"""

SCHEMA_PARAMETRO = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string", "minLength": 1},
        "descripcion": {"type": "string"},
        "obligatorio": {"type": "boolean"},
        "valores_de": {
            "type": "object",
            "properties": {
                "tabla": {"type": "string", "minLength": 1},
                "etiqueta": {"type": "string", "minLength": 1},
                "campo_valor": {"type": "string", "minLength": 1},
            },
            "required": ["tabla"],
            "additionalProperties": False,
        },
    },
    "required": ["nombre"],
    "additionalProperties": False,
}


class ParametroInvalidoError(ValueError):
    """Falta un parámetro obligatorio o su valor no existe en la lista cerrada."""


def declarados(definicion: dict) -> list:
    return definicion.get("parametros", []) or []


def nombres(definicion: dict) -> set:
    return {p["nombre"] for p in declarados(definicion)}


def _resolver_cerrado(con, parametro: dict, valor: str):
    """Resuelve el valor contra la tabla declarada. Si no existe, el error
    lista lo que sí hay: teclear el nombre de una tienda a mano falla más por
    una tilde que por otra cosa."""
    fuente = parametro["valores_de"]
    tabla = fuente["tabla"]
    etiqueta = fuente.get("etiqueta", "nombre")
    campo_valor = fuente.get("campo_valor", "id")

    filas = con.execute(
        f"SELECT {campo_valor} FROM {tabla} WHERE lower({etiqueta}) = lower(?)", [valor]
    ).fetchall()
    if len(filas) > 1:
        raise ParametroInvalidoError(
            f"el parámetro '{parametro['nombre']}' es ambiguo: hay más de un/a "
            f"{tabla} con {etiqueta} '{valor}'"
        )
    if not filas:
        disponibles = [f[0] for f in con.execute(
            f"SELECT {etiqueta} FROM {tabla} ORDER BY {etiqueta} LIMIT 20"
        ).fetchall()]
        raise ParametroInvalidoError(
            f"el parámetro '{parametro['nombre']}' no admite '{valor}': no hay "
            f"{tabla} con {etiqueta} '{valor}'. Disponibles: {', '.join(disponibles) or '(ninguno)'}"
        )
    return filas[0][0]


def resolver(con, definicion: dict, valores: dict) -> dict:
    """Comprueba y resuelve los parámetros aportados. Devuelve {nombre: valor}
    listo para inyectar en el mapping."""
    valores = valores or {}
    declarados_ = declarados(definicion)
    esperados = {p["nombre"] for p in declarados_}

    sobrantes = set(valores) - esperados
    if sobrantes:
        raise ParametroInvalidoError(
            f"la carga no declara el/los parámetro(s) {sorted(sobrantes)}; "
            f"declarados: {sorted(esperados) or '(ninguno)'}"
        )

    resueltos = {}
    for parametro in declarados_:
        nombre = parametro["nombre"]
        valor = valores.get(nombre)
        if valor is None or valor == "":
            if parametro.get("obligatorio"):
                descripcion = parametro.get("descripcion", "")
                raise ParametroInvalidoError(
                    f"falta el parámetro obligatorio '{nombre}'"
                    + (f" ({descripcion})" if descripcion else "")
                )
            resueltos[nombre] = None
            continue
        resueltos[nombre] = (
            _resolver_cerrado(con, parametro, valor) if "valores_de" in parametro else valor
        )
    return resueltos


def registro(definicion: dict, valores: dict, resueltos: dict) -> dict:
    """Lo que se guarda en `_ejecuciones.parametros`.

    De un parámetro de lista cerrada se guardan las dos caras: lo que se
    tecleó y el id al que resolvió. Solo con el id, renombrar o borrar la
    tienda dejaría la ejecución ilegible; solo con la etiqueta, no se podría
    volver a la fila exacta.
    """
    registrado = {}
    for parametro in declarados(definicion):
        nombre = parametro["nombre"]
        resuelto = resueltos.get(nombre)
        if resuelto is None:
            continue
        entrada = (valores or {}).get(nombre)
        registrado[nombre] = (
            {"entrada": entrada, "valor": resuelto}
            if "valores_de" in parametro
            else resuelto
        )
    return registrado
