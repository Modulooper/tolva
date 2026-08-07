"""Variables en el SQL de una carga: `$nombre` -> marcador enlazado.

Una carga necesita meter valores en su SQL que no conoce hasta que corre: el
id de la ejecución en curso, el parámetro que le pasaron al lanzarla, un total
calculado sobre la hall. Este módulo es el único sitio donde eso ocurre.

**No interpola texto, enlaza parámetros.** La diferencia no es de estilo: una
sucursal que se llame O'Donnell rompe una SQL construida pegando cadenas, y una
fecha o un nulo se serializan mal en cuanto alguien cambia el locale. Aquí
`$v_total` se convierte en un `?` y el valor viaja aparte, tipado, como en
cualquier consulta parametrizada.

Eso impone un límite: **una variable solo puede ir donde cabe un valor**, nunca
como nombre de tabla o de columna. Es deliberado. Nombres de objeto
construidos desde un fichero de configuración es una puerta que no interesa
abrir, y quien la necesite tiene `acciones` para escribir el SQL entero.

Tres sitios donde un `$` NO es una variable, y por eso esto es un escáner y no
una expresión regular:

- Dentro de comillas simples: `'cuesta $v_total euros'` es texto literal.
- En una cadena con comillas de dólar de DuckDB: `$$texto$$`, `$tag$texto$tag$`.
- En un comentario, `--` hasta fin de línea o `/* ... */`.

Sustituir en cualquiera de los tres desharía el SQL o descuadraría el número
de marcadores contra el de valores, que es un error que aparece lejos de su
causa. `$1` tampoco se toca: es un marcador posicional de DuckDB y un dígito
no puede empezar un nombre.
"""

import re

_INICIO_NOMBRE = re.compile(r"[A-Za-z_]")
_RESTO_NOMBRE = re.compile(r"[A-Za-z0-9_]")


class VariableDesconocida(ValueError):
    """El SQL usa una variable que nadie ha definido."""


def nombres_usados(sql: str) -> list:
    """Las variables que aparecen en el SQL, en orden de aparición y con
    repeticiones: es el orden en el que hay que enlazar los valores."""
    encontrados = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]

        if c == "'":  # literal de texto; '' es una comilla escapada
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue

        if c == '"':  # identificador entrecomillado
            i += 1
            while i < n and sql[i] != '"':
                i += 1
            i += 1
            continue

        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                i += 1
            continue

        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            fin = sql.find("*/", i + 2)
            i = n if fin == -1 else fin + 2
            continue

        if c == "$":
            # ¿Abre una cadena con comillas de dólar? $$...$$ o $tag$...$tag$
            j = i + 1
            while j < n and _RESTO_NOMBRE.match(sql[j]):
                j += 1
            if j < n and sql[j] == "$":
                etiqueta = sql[i : j + 1]
                fin = sql.find(etiqueta, j + 1)
                i = n if fin == -1 else fin + len(etiqueta)
                continue
            # Variable: $ seguido de un nombre que no empieza por dígito.
            if i + 1 < n and _INICIO_NOMBRE.match(sql[i + 1]):
                encontrados.append(sql[i + 1 : j])
                i = j
                continue

        i += 1
    return encontrados


def resolver(sql: str, contexto: dict):
    """`(sql_con_marcadores, valores)` listos para `con.execute(sql, valores)`.

    Un nombre que el contexto no define es un error, no un hueco que se deja
    tal cual: dejarlo pasar produce un SQL que falla más tarde con un mensaje
    que no menciona la variable.
    """
    usados = nombres_usados(sql)
    if not usados:
        return sql, []

    desconocidos = [u for u in dict.fromkeys(usados) if u not in contexto]
    if desconocidos:
        disponibles = ", ".join(f"${k}" for k in sorted(contexto)) or "(ninguna)"
        raise VariableDesconocida(
            f"variable(s) no definida(s) en el SQL: "
            f"{', '.join('$' + d for d in desconocidos)}. Disponibles: {disponibles}"
        )

    # Se rehace el recorrido para reemplazar solo las apariciones reales, con
    # los mismos criterios que las localizaron.
    salida, valores = [], []
    i, n, k = 0, len(sql), 0
    while i < n:
        c = sql[i]
        if c in "'\"":
            cierre = c
            j = i + 1
            while j < n:
                if sql[j] == cierre:
                    if cierre == "'" and j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            salida.append(sql[i:j])
            i = j
            continue
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i)
            j = n if j == -1 else j
            salida.append(sql[i:j])
            i = j
            continue
        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            fin = sql.find("*/", i + 2)
            j = n if fin == -1 else fin + 2
            salida.append(sql[i:j])
            i = j
            continue
        if c == "$":
            j = i + 1
            while j < n and _RESTO_NOMBRE.match(sql[j]):
                j += 1
            if j < n and sql[j] == "$":
                etiqueta = sql[i : j + 1]
                fin = sql.find(etiqueta, j + 1)
                j = n if fin == -1 else fin + len(etiqueta)
                salida.append(sql[i:j])
                i = j
                continue
            if i + 1 < n and _INICIO_NOMBRE.match(sql[i + 1]):
                salida.append("?")
                valores.append(contexto[usados[k]])
                k += 1
                i = j
                continue
        salida.append(c)
        i += 1
    return "".join(salida), valores


def ejecutar(con, sql: str, contexto: dict):
    """Atajo: resuelve y ejecuta. Devuelve el cursor."""
    consulta, valores = resolver(sql, contexto)
    return con.execute(consulta, valores)


def contexto_de(ejecucion_id=None, carga=None, fichero=None, hash_fichero=None,
                promovidas=None, borradas=None, parametros=None, variables=None) -> dict:
    """El contexto de una ejecución, con sus tres familias de nombres.

    - Sin prefijo, las de sistema: las pone el motor y siempre valen lo que
      dicen. `$ejecucion_id` es la ejecución en curso porque el motor la
      conoce, no porque nadie la deduzca.
    - `p_`, los parámetros que se pasaron al lanzar la carga.
    - `v_`, las variables que la propia carga calculó.

    El prefijo no separa espacios de nombres —el `$` ya evita chocar con una
    columna—, separa **quién garantiza el valor**: sin prefijo lo garantiza el
    framework; con prefijo, quien escribió la carga.
    """
    contexto = {}
    if ejecucion_id is not None:
        contexto["ejecucion_id"] = ejecucion_id
    if carga is not None:
        contexto["carga"] = carga
    if fichero is not None:
        contexto["fichero"] = fichero
    if hash_fichero is not None:
        contexto["hash_fichero"] = hash_fichero
    if promovidas is not None:
        contexto["promovidas"] = promovidas
    if borradas is not None:
        contexto["borradas"] = borradas
    for nombre, valor in (parametros or {}).items():
        contexto[f"p_{nombre}"] = valor
    for nombre, valor in (variables or {}).items():
        contexto[f"v_{nombre}"] = valor
    return contexto
