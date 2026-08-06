"""Registro de ejecuciones: toda escritura del sistema deja traza.

`_ejecuciones` no es solo el diario de las cargas de fichero. Cada operación
del CLI que escribe (crear, editar, borrar) registra también la suya, con
`tipo = 'cli'`. Eso permite colgar documentos de cualquier registro sin
duplicar el hash en las tablas de negocio: se llega por `ejecucion_id`.

La regla del encadenado (migración 013): **toda ejecución tiene principal**.
En una creación o una carga se apunta a sí misma; en una modificación
posterior apunta a la ejecución que creó la fila. De ahí salen las dos
consultas que interesan:

    id = ejecucion_id_principal               -> ejecuciones principales
    ejecucion_id_principal = N AND id <> N    -> historial de cambios de N

La fila de negocio guarda solo la ejecución de creación, así que editar no la
toca nunca.
"""

import getpass

from . import validaciones

TIPO_CARGA = "carga"
TIPO_CLI = "cli"


def registrar(con, operacion: str, tipo: str = TIPO_CLI, principal: int = None) -> int:
    """Abre una ejecución en estado EN_CURSO y devuelve su id.

    `principal` es la ejecución de creación cuando esta es una modificación
    posterior. Si no se pasa, la ejecución es su propia principal.
    """
    ejecucion_id = con.execute(
        """INSERT INTO _ejecuciones (carga, tipo, estado, usuario)
           VALUES (?, ?, 'EN_CURSO', ?) RETURNING id""",
        [operacion, tipo, getpass.getuser()],
    ).fetchone()[0]
    con.execute(
        "UPDATE _ejecuciones SET ejecucion_id_principal = ? WHERE id = ?",
        [principal if principal is not None else ejecucion_id, ejecucion_id],
    )
    return ejecucion_id


def marcar(con, ejecucion_id: int, estado: str) -> None:
    con.execute("UPDATE _ejecuciones SET estado = ? WHERE id = ?", [estado, ejecucion_id])


def principal_de(con, tabla: str, fila_id: str) -> int:
    """Ejecución que creó una fila, o None si es anterior al registro de
    ejecuciones. En ese caso la modificación será su propia principal: no se
    le inventa una creación que nunca se registró."""
    fila = con.execute(f"SELECT ejecucion_id FROM {tabla} WHERE id = ?", [fila_id]).fetchone()
    return fila[0] if fila else None


def envolver(con, operacion: str, tabla: str, escribir, principal: int = None):
    """Registra la ejecución, escribe protegido por los invariantes del
    catálogo y sella el estado final. Devuelve `(valor, resultados)`.

    `escribir` recibe el id de la ejecución, para que una creación pueda
    sellarlo en la propia fila.

    La ejecución se abre **fuera** de la transacción de `proteger_escritura`,
    así que un stop revierte la escritura pero deja la ejecución en ERROR:
    el intento fallido queda registrado. Es el mismo criterio que ya siguen
    las cargas de fichero (migración 012).
    """
    ejecucion_id = registrar(con, operacion, principal=principal)
    try:
        valor, resultados = validaciones.proteger_escritura(
            con, tabla, lambda: escribir(ejecucion_id)
        )
    except Exception:
        marcar(con, ejecucion_id, "ERROR")
        raise
    marcar(con, ejecucion_id, "OK")
    return valor, resultados


def historial(con, ejecucion_principal: int):
    """Ejecuciones encadenadas a una principal, creación incluida, en orden."""
    cursor = con.execute(
        """SELECT id, tipo, carga AS operacion, fecha, estado, usuario
           FROM _ejecuciones
           WHERE ejecucion_id_principal = ?
           ORDER BY id""",
        [ejecucion_principal],
    )
    return [d[0] for d in cursor.description], cursor.fetchall()
