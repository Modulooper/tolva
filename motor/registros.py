"""CRUD genérico dirigido por el catálogo: el núcleo no conoce las entidades.

`motor/tickets.py` y `motor/ideas.py` son el mismo código dos veces con los
nombres cambiados, y ese patrón tiene un coste que no se ve hasta que quieres
un proceso privado: para dar de alta una entidad nueva había que tocar el
framework, así que **todo proceso acababa siendo público**. Aquí la entidad no
está en el código: se lee de su ficha de catálogo, que puede vivir igual de
bien en `catalogo/` que en `propio/catalogo/`.

Lo que la ficha aporta y este módulo aprovecha:

- `campos`: qué se puede escribir. Los marcados `sistema` no se tocan desde
  fuera (`id`, `created_at`, `updated_at`, `ejecucion_id`).
- `tipo`: a qué convertir lo que llega del CLI, que siempre es texto.
- `relaciones`: qué campos son referencias. Un `persona_id` se puede dar por
  el nombre ("Nacho") y se resuelve contra la tabla destino, que es lo que
  evita el campo de texto libre duplicando una entidad que ya existe.
- `validacion.lista_valores`: los valores admitidos, para fallar con un
  mensaje legible en vez de con la violación del CHECK.

Lo que NO comprueba a propósito: la obligatoriedad. Una columna puede ser
`NOT NULL` y tener `DEFAULT` (`tarea.fecha`, `tarea.estado`), y desde la ficha
no se distingue de una que hay que rellenar sí o sí. La autoridad es la base:
si falta algo, salta el `NOT NULL`. Duplicar la regla aquí solo crearía dos
verdades que se separan con el tiempo.

La trazabilidad es la misma que la del CRUD escrito a mano: `ejecuciones.
envolver` sella el `ejecucion_id` de creación en la fila, las ediciones se
encadenan a esa principal sin tocarlo, y los invariantes del catálogo se
comprueban en cada escritura venga de donde venga.
"""

from datetime import date, datetime

from . import catalogo, documentos, ejecuciones

# Los que puede escribir el usuario son todos menos estos: `id` lo pone la
# base, los timestamps también, y `ejecucion_id` lo sella la propia ejecución.
CAMPOS_SISTEMA = ("id", "created_at", "updated_at", "ejecucion_id")

OPERADORES = ("<=", ">=", "<>", "!=", "<", ">", "=")


class CampoDesconocido(ValueError):
    """Un campo que la ficha de catálogo no declara."""


def entidad_de(nombre: str) -> dict:
    """La ficha de catálogo, mirando primero la capa propia."""
    return catalogo.cargar_entidad(nombre)


def _es_sistema(campo: str, meta: dict) -> bool:
    return campo in CAMPOS_SISTEMA or meta.get("sistema", False)


def campos_escribibles(entidad: dict) -> dict:
    return {c: m for c, m in entidad.get("campos", {}).items() if not _es_sistema(c, m)}


def _referencias(entidad: dict) -> dict:
    """{campo_fk: (alias, tabla_destino, columna_legible_o_None)}.

    El alias es el campo sin el `_id` final: se acepta `--set persona=Nacho`
    además de `--set persona_id=<uuid>`.

    La columna legible sale de `etiqueta` en la ficha destino, y si no se
    declara se prueba `nombre`. No basta con asumir `nombre` siempre: un libro
    se identifica por su `titulo`, y dar por hecho lo contrario obliga a
    escribir uuids a mano justo en las entidades que peor se recuerdan. Si la
    entidad destino no tiene ninguna de las dos, solo se admite el id.
    """
    mapa = {}
    for relacion in entidad.get("relaciones", []):
        campo = relacion["campo"]
        try:
            destino = entidad_de(relacion["entidad_destino"])
        except FileNotFoundError:
            continue
        campos_destino = destino.get("campos", {})
        legible = destino.get("etiqueta") or ("nombre" if "nombre" in campos_destino else None)
        if legible is not None and legible not in campos_destino:
            raise ValueError(
                f"la ficha de '{destino['entidad']}' declara etiqueta '{legible}', "
                f"que no es uno de sus campos"
            )
        alias = campo[:-3] if campo.endswith("_id") else campo
        mapa[campo] = (alias, destino["tabla"], legible)
    return mapa


def _canonico(entidad: dict, clave: str) -> str:
    """Nombre real de columna a partir de lo que escribió el usuario: acepta
    el campo tal cual, un alias de referencia (`persona`) o un sinónimo."""
    campos = entidad.get("campos", {})
    if clave in campos:
        return clave
    for campo, (alias, _, _) in _referencias(entidad).items():
        if clave == alias:
            return campo
    por_sinonimo = catalogo.buscar_por_sinonimo(entidad, clave)
    if por_sinonimo:
        return por_sinonimo
    escribibles = sorted(campos_escribibles(entidad))
    raise CampoDesconocido(
        f"'{clave}' no es un campo de '{entidad['entidad']}' "
        f"(campos: {', '.join(escribibles)})"
    )


def _convertir(valor, tipo: str, campo: str):
    """El CLI entrega texto; la ficha dice a qué convertirlo. Cadena vacía es
    NULL, que es como se vacía un campo opcional al editar."""
    if valor is None or isinstance(valor, (date, datetime, int, float, bool)):
        return valor
    texto = valor.strip()
    if texto == "":
        return None
    try:
        if tipo == "date":
            return date.fromisoformat(texto)
        if tipo == "timestamp":
            return datetime.fromisoformat(texto)
        if tipo == "integer":
            return int(texto)
        if tipo == "double":
            return float(texto.replace(",", "."))
        if tipo == "boolean":
            if texto.lower() in ("true", "si", "sí", "1"):
                return True
            if texto.lower() in ("false", "no", "0"):
                return False
            raise ValueError(texto)
    except ValueError:
        raise ValueError(f"'{texto}' no es un valor válido de tipo {tipo} para '{campo}'")
    return texto


def _validar_lista(entidad: dict, campo: str, valor) -> None:
    meta = entidad["campos"][campo]
    admitidos = meta.get("validacion", {}).get("lista_valores")
    if admitidos and valor is not None and valor not in admitidos:
        raise ValueError(
            f"'{valor}' no es un valor válido de '{campo}', debe ser uno de {tuple(admitidos)}"
        )


def _resolver_referencia(con, tabla: str, columna: str, valor: str, campo: str) -> str:
    """Un id se acepta tal cual; cualquier otra cosa se busca por nombre."""
    fila = con.execute(f'SELECT id FROM "{tabla}" WHERE CAST(id AS VARCHAR) = ?', [valor]).fetchone()
    if fila:
        return fila[0]
    if columna is None:
        raise ValueError(f"'{campo}' solo admite el id de {tabla}: '{valor}' no existe")
    filas = con.execute(
        f'SELECT id FROM "{tabla}" WHERE lower("{columna}") = lower(?)', [valor]
    ).fetchall()
    if not filas:
        raise ValueError(f"no se encontró {tabla} con {columna} '{valor}'")
    if len(filas) > 1:
        raise ValueError(f"hay más de un/a {tabla} con {columna} '{valor}', usa el id")
    return filas[0][0]


def normalizar(con, entidad: dict, valores: dict) -> dict:
    """{lo que escribió el usuario} -> {columna real: valor ya convertido}."""
    referencias = _referencias(entidad)
    normalizados = {}
    for clave, valor in valores.items():
        campo = _canonico(entidad, clave)
        meta = entidad["campos"][campo]
        if _es_sistema(campo, meta):
            raise CampoDesconocido(f"'{campo}' lo gestiona el sistema y no se escribe a mano")
        if campo in referencias:
            _, tabla_destino, columna = referencias[campo]
            texto = None if valor is None or str(valor).strip() == "" else str(valor).strip()
            normalizados[campo] = (
                None if texto is None
                else _resolver_referencia(con, tabla_destino, columna, texto, campo)
            )
            continue
        convertido = _convertir(valor, meta["tipo"], campo)
        _validar_lista(entidad, campo, convertido)
        normalizados[campo] = convertido
    return normalizados


def _tiene_ejecucion_id(con, tabla: str) -> bool:
    """Si la tabla puede sellar en la fila la ejecución que la creó.

    No todas pueden: `persona`, `cliente` y `proyecto` son de la migración de
    arranque y no la tienen, y añadírsela ahora no es opción —son destino de
    claves ajenas y DuckDB no deja alterar una tabla referenciada, así que la
    instalación limpia y la incremental acabarían con esquemas distintos—.
    Cuando falta, la ejecución se registra igual en `_ejecuciones`: lo que se
    pierde es poder ir de la fila a su ejecución, no el registro de que hubo
    una. Es la diferencia entre una dimensión y un proceso.
    """
    return bool(
        con.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = ? AND column_name = 'ejecucion_id'",
            [tabla],
        ).fetchone()[0]
    )


def crear(con, nombre_entidad: str, valores: dict, documento=None):
    """Alta de un registro. Devuelve `(id, resultados_de_validaciones)`."""
    entidad = entidad_de(nombre_entidad)
    tabla = entidad["tabla"]
    columnas_valores = normalizar(con, entidad, valores)
    sella = _tiene_ejecucion_id(con, tabla)

    def escribir(ejecucion_id):
        columnas = list(columnas_valores) + (["ejecucion_id"] if sella else [])
        parametros = list(columnas_valores.values()) + ([ejecucion_id] if sella else [])
        marcadores = ", ".join("?" for _ in parametros)
        entrecomilladas = ", ".join(f'"{c}"' for c in columnas)
        fila_id = con.execute(
            f'INSERT INTO "{tabla}" ({entrecomilladas}) VALUES ({marcadores}) RETURNING id',
            parametros,
        ).fetchone()[0]
        if documento:
            documentos.archivar(con, documento, ejecucion_id)
        return fila_id

    return ejecuciones.envolver(con, f"{nombre_entidad}.crear", tabla, escribir)


def _consulta_listado(entidad: dict):
    """SELECT con las referencias ya resueltas a su nombre legible.

    Devuelve `(sql_base, expresiones)`, donde `expresiones` dice con qué
    comparar cada campo al filtrar: la columna de la tabla, o el nombre de la
    entidad referenciada cuando se filtra por `cliente=Turri`.
    """
    tabla = entidad["tabla"]
    referencias = _referencias(entidad)
    seleccion = ['t."id"']
    joins = []
    expresiones = {"id": 't."id"'}

    for indice, (campo, meta) in enumerate(entidad.get("campos", {}).items()):
        if campo == "id":
            continue
        if campo in referencias:
            alias, tabla_destino, columna = referencias[campo]
            if columna is None:
                seleccion.append(f't."{campo}"')
                expresiones[campo] = f't."{campo}"'
                continue
            union = f"r{indice}"
            joins.append(f'LEFT JOIN "{tabla_destino}" {union} ON {union}."id" = t."{campo}"')
            seleccion.append(f'{union}."{columna}" AS "{alias}"')
            # Filtrar por nombre es lo natural ("las de Turri"), pero el id
            # sigue valiendo: se comparan los dos.
            expresiones[campo] = f'{union}."{columna}"'
            expresiones[alias] = f'{union}."{columna}"'
            continue
        if _es_sistema(campo, meta):
            continue
        seleccion.append(f't."{campo}"')
        expresiones[campo] = f't."{campo}"'

    sql = f'SELECT {", ".join(seleccion)} FROM "{tabla}" t'
    if joins:
        sql += " " + " ".join(joins)
    return sql, expresiones


def _orden(entidad: dict) -> str:
    campos = entidad.get("campos", {})
    for candidato in ("fecha", "created_at"):
        if candidato in campos:
            return f' ORDER BY t."{candidato}" DESC'
    return ""


def partir_filtro(texto: str):
    """`estado=pendiente` o `fecha_limite<=2026-08-31` -> (campo, op, valor)."""
    for operador in OPERADORES:
        if operador in texto:
            izquierda, _, derecha = texto.partition(operador)
            if izquierda.strip():
                return izquierda.strip(), operador, derecha.strip()
    raise ValueError(f"filtro '{texto}' mal formado, se espera campo=valor (o <=, >=, <, >, <>)")


def listar(con, nombre_entidad: str, filtros=None):
    entidad = entidad_de(nombre_entidad)
    sql, expresiones = _consulta_listado(entidad)
    referencias = _referencias(entidad)

    condiciones, parametros = [], []
    for campo_pedido, operador, valor in filtros or []:
        campo = _canonico(entidad, campo_pedido)
        expresion = expresiones.get(campo)
        if expresion is None:
            raise CampoDesconocido(f"no se puede filtrar por '{campo_pedido}'")
        meta = entidad["campos"][campo]
        if campo in referencias:
            # Se compara contra el nombre, así que el valor va tal cual y sin
            # distinguir mayúsculas, igual que al resolver la referencia.
            condiciones.append(f"lower({expresion}) {operador} lower(?)")
            parametros.append(valor)
        else:
            condiciones.append(f"{expresion} {operador} ?")
            parametros.append(_convertir(valor, meta["tipo"], campo))
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += _orden(entidad)

    cursor = con.execute(sql, parametros)
    return [d[0] for d in cursor.description], cursor.fetchall()


def _existe(con, tabla: str, fila_id: str) -> bool:
    return bool(
        con.execute(
            f'SELECT count(*) FROM "{tabla}" WHERE CAST(id AS VARCHAR) = ?', [str(fila_id)]
        ).fetchone()[0]
    )


def editar(con, nombre_entidad: str, fila_id: str, valores: dict):
    """Modifica un registro. No toca `ejecucion_id`: la ejecución de la
    edición se encadena a la que creó la fila (ver `motor/ejecuciones.py`)."""
    entidad = entidad_de(nombre_entidad)
    tabla = entidad["tabla"]
    if not valores:
        return None
    columnas_valores = normalizar(con, entidad, valores)
    if not _existe(con, tabla, fila_id):
        raise ValueError(f"no existe {nombre_entidad} con id '{fila_id}'")

    asignaciones = ", ".join(f'"{c}" = ?' for c in columnas_valores)
    parametros = list(columnas_valores.values()) + [str(fila_id)]

    def escribir(_ejecucion_id):
        con.execute(
            f'UPDATE "{tabla}" SET {asignaciones}, updated_at = current_timestamp '
            f"WHERE CAST(id AS VARCHAR) = ?",
            parametros,
        )

    principal = ejecuciones.principal_de(con, tabla, fila_id) if _tiene_ejecucion_id(con, tabla) else None
    _, resultados = ejecuciones.envolver(
        con, f"{nombre_entidad}.editar", tabla, escribir, principal=principal
    )
    return resultados


def borrar(con, nombre_entidad: str, fila_id: str) -> None:
    entidad = entidad_de(nombre_entidad)
    tabla = entidad["tabla"]
    if not _existe(con, tabla, fila_id):
        raise ValueError(f"no existe {nombre_entidad} con id '{fila_id}'")
    # Se lee la principal antes de borrar: después la fila ya no está y el
    # borrado quedaría suelto, sin la vida del registro a la que pertenece.
    principal = ejecuciones.principal_de(con, tabla, fila_id) if _tiene_ejecucion_id(con, tabla) else None
    ejecucion_id = ejecuciones.registrar(con, f"{nombre_entidad}.borrar", principal=principal)
    con.execute(f'DELETE FROM "{tabla}" WHERE CAST(id AS VARCHAR) = ?', [str(fila_id)])
    ejecuciones.marcar(con, ejecucion_id, "OK")


def describir(con, nombre_entidad: str):
    """Qué acepta `--set` para esta entidad: para no adivinar los campos."""
    entidad = entidad_de(nombre_entidad)
    referencias = _referencias(entidad)
    columnas = ["campo", "tipo", "obligatorio", "admite", "descripcion"]
    filas = []
    for campo, meta in campos_escribibles(entidad).items():
        if campo in referencias:
            alias, tabla_destino, columna = referencias[campo]
            admite = f"{tabla_destino}.{columna or 'id'} (alias: {alias})"
        else:
            admite = ", ".join(meta.get("validacion", {}).get("lista_valores", [])) or ""
        filas.append(
            [campo, meta["tipo"], "sí" if meta["obligatorio"] else "no", admite, meta["descripcion"]]
        )
    return columnas, filas
