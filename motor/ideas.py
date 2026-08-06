"""CRUD de ideas sueltas, opcionalmente vinculadas a un cliente."""

from datetime import date

from . import documentos, ejecuciones, validaciones

ESTADOS_VALIDOS = ("pendiente", "en_curso", "descartada", "hecha")


def _resolver(con, tabla: str, nombre: str) -> str:
    filas = con.execute(f"SELECT id, nombre FROM {tabla} WHERE lower(nombre) = lower(?)", [nombre]).fetchall()
    if not filas:
        raise ValueError(f"no se encontró {tabla} con nombre '{nombre}'")
    if len(filas) > 1:
        raise ValueError(f"hay más de un/a {tabla} con nombre '{nombre}', usa un nombre único")
    return filas[0][0]


def resolver_persona(con, nombre: str) -> str:
    return _resolver(con, "persona", nombre)


def resolver_cliente(con, nombre: str) -> str:
    return _resolver(con, "cliente", nombre)


def crear(con, persona: str, texto: str, cliente: str = None, estado: str = None,
          fecha: date = None, documento=None) -> str:
    if estado is not None and estado not in ESTADOS_VALIDOS:
        raise ValueError(f"estado '{estado}' no válido, debe ser uno de {ESTADOS_VALIDOS}")
    persona_id = resolver_persona(con, persona)

    columnas = ["persona_id", "texto"]
    valores = [persona_id, texto]
    if cliente is not None:
        columnas.append("cliente_id")
        valores.append(resolver_cliente(con, cliente))
    if estado is not None:
        columnas.append("estado")
        valores.append(estado)
    if fecha is not None:
        columnas.append("fecha")
        valores.append(fecha)

    def escribir(ejecucion_id):
        cols = columnas + ["ejecucion_id"]
        vals = valores + [ejecucion_id]
        placeholders = ", ".join("?" for _ in vals)
        idea_id = con.execute(
            f"INSERT INTO idea ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
            vals,
        ).fetchone()[0]
        if documento:
            documentos.archivar(con, documento, ejecucion_id)
        return idea_id

    return ejecuciones.envolver(con, "idea.crear", "idea", escribir)


def listar(con, persona: str = None, cliente: str = None, estado: str = None, desde: date = None, hasta: date = None):
    condiciones = []
    parametros = []
    if persona:
        condiciones.append("lower(p.nombre) = lower(?)")
        parametros.append(persona)
    if cliente:
        condiciones.append("lower(c.nombre) = lower(?)")
        parametros.append(cliente)
    if estado:
        condiciones.append("i.estado = ?")
        parametros.append(estado)
    if desde:
        condiciones.append("i.fecha >= ?")
        parametros.append(desde)
    if hasta:
        condiciones.append("i.fecha <= ?")
        parametros.append(hasta)

    sql = """
        SELECT i.id, i.fecha, p.nombre AS persona, c.nombre AS cliente,
               i.texto, i.estado
        FROM idea i
        JOIN persona p ON p.id = i.persona_id
        LEFT JOIN cliente c ON c.id = i.cliente_id
    """
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY i.fecha DESC"

    cursor = con.execute(sql, parametros)
    columnas = [d[0] for d in cursor.description]
    return columnas, cursor.fetchall()


def editar(con, idea_id: str, **campos) -> None:
    if not campos:
        return
    if "estado" in campos and campos["estado"] is not None and campos["estado"] not in ESTADOS_VALIDOS:
        raise ValueError(f"estado '{campos['estado']}' no válido, debe ser uno de {ESTADOS_VALIDOS}")
    if "cliente" in campos:
        cliente = campos.pop("cliente")
        campos["cliente_id"] = resolver_cliente(con, cliente) if cliente is not None else None
    campos_presentes = {k: v for k, v in campos.items() if v is not None}
    if not campos_presentes:
        return
    existe = con.execute("SELECT count(*) FROM idea WHERE id = ?", [idea_id]).fetchone()[0]
    if not existe:
        raise ValueError(f"no existe idea con id '{idea_id}'")
    set_clause = ", ".join(f"{c} = ?" for c in campos_presentes) + ", updated_at = current_timestamp"
    parametros = list(campos_presentes.values()) + [idea_id]

    def escribir(_ejecucion_id):
        con.execute(f"UPDATE idea SET {set_clause} WHERE id = ?", parametros)

    # La edición no toca idea.ejecucion_id: se encadena a la ejecución que
    # creó la fila y queda como historial de esa principal.
    principal = ejecuciones.principal_de(con, "idea", idea_id)
    _, resultados = ejecuciones.envolver(
        con, "idea.editar", "idea", escribir, principal=principal
    )
    return resultados


def borrar(con, idea_id: str) -> None:
    existe = con.execute("SELECT count(*) FROM idea WHERE id = ?", [idea_id]).fetchone()[0]
    if not existe:
        raise ValueError(f"no existe idea con id '{idea_id}'")
    # Se lee la principal antes de borrar: después la fila ya no está y el
    # borrado quedaría suelto, sin la vida del registro a la que pertenece.
    principal = ejecuciones.principal_de(con, "idea", idea_id)
    ejecucion_id = ejecuciones.registrar(con, "idea.borrar", principal=principal)
    con.execute("DELETE FROM idea WHERE id = ?", [idea_id])
    ejecuciones.marcar(con, ejecucion_id, "OK")
