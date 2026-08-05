"""CRUD de tickets de gasto (viajes, hoteles, gasolina)."""

from datetime import date

from . import validaciones

CONCEPTOS_VALIDOS = ("viajes", "hoteles", "gasolina", "otros")


def _resolver(con, tabla: str, nombre: str) -> str:
    filas = con.execute(f"SELECT id, nombre FROM {tabla} WHERE lower(nombre) = lower(?)", [nombre]).fetchall()
    if not filas:
        raise ValueError(f"no se encontró {tabla} con nombre '{nombre}'")
    if len(filas) > 1:
        raise ValueError(f"hay más de un/a {tabla} con nombre '{nombre}', usa un nombre único")
    return filas[0][0]


def resolver_cliente(con, nombre: str) -> str:
    return _resolver(con, "cliente", nombre)


def resolver_persona(con, nombre: str) -> str:
    return _resolver(con, "persona", nombre)


def crear(con, cliente: str, persona: str, concepto: str, importe: float, fecha: date, descripcion: str = None):
    """Devuelve (id_ticket, resultados_validacion)."""
    if concepto not in CONCEPTOS_VALIDOS:
        raise ValueError(f"concepto '{concepto}' no válido, debe ser uno de {CONCEPTOS_VALIDOS}")
    cliente_id = resolver_cliente(con, cliente)
    persona_id = resolver_persona(con, persona)

    def escribir():
        return con.execute(
            """INSERT INTO ticket (cliente_id, persona_id, concepto, descripcion, importe, fecha)
               VALUES (?, ?, ?, ?, ?, ?) RETURNING id""",
            [cliente_id, persona_id, concepto, descripcion, importe, fecha],
        ).fetchone()[0]

    return validaciones.proteger_escritura(con, "ticket", escribir)


def listar(con, cliente: str = None, persona: str = None, concepto: str = None, desde: date = None, hasta: date = None):
    condiciones = []
    parametros = []
    if cliente:
        condiciones.append("lower(c.nombre) = lower(?)")
        parametros.append(cliente)
    if persona:
        condiciones.append("lower(p.nombre) = lower(?)")
        parametros.append(persona)
    if concepto:
        condiciones.append("t.concepto = ?")
        parametros.append(concepto)
    if desde:
        condiciones.append("t.fecha >= ?")
        parametros.append(desde)
    if hasta:
        condiciones.append("t.fecha <= ?")
        parametros.append(hasta)

    sql = """
        SELECT t.id, t.fecha, c.nombre AS cliente, p.nombre AS persona,
               t.concepto, t.descripcion, t.importe
        FROM ticket t
        JOIN cliente c ON c.id = t.cliente_id
        JOIN persona p ON p.id = t.persona_id
    """
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY t.fecha DESC"

    cursor = con.execute(sql, parametros)
    columnas = [d[0] for d in cursor.description]
    return columnas, cursor.fetchall()


def editar(con, ticket_id: str, **campos) -> None:
    if not campos:
        return
    if "concepto" in campos and campos["concepto"] is not None and campos["concepto"] not in CONCEPTOS_VALIDOS:
        raise ValueError(f"concepto '{campos['concepto']}' no válido, debe ser uno de {CONCEPTOS_VALIDOS}")
    campos_presentes = {k: v for k, v in campos.items() if v is not None}
    if not campos_presentes:
        return
    existe = con.execute("SELECT count(*) FROM ticket WHERE id = ?", [ticket_id]).fetchone()[0]
    if not existe:
        raise ValueError(f"no existe ticket con id '{ticket_id}'")
    set_clause = ", ".join(f"{c} = ?" for c in campos_presentes) + ", updated_at = current_timestamp"
    parametros = list(campos_presentes.values()) + [ticket_id]

    def escribir():
        con.execute(f"UPDATE ticket SET {set_clause} WHERE id = ?", parametros)

    _, resultados = validaciones.proteger_escritura(con, "ticket", escribir)
    return resultados


def borrar(con, ticket_id: str) -> None:
    existe = con.execute("SELECT count(*) FROM ticket WHERE id = ?", [ticket_id]).fetchone()[0]
    if not existe:
        raise ValueError(f"no existe ticket con id '{ticket_id}'")
    con.execute("DELETE FROM ticket WHERE id = ?", [ticket_id])
