"""Almacén de documentos direccionado por contenido.

Los bytes van a `datos/documentos/<hash[:2]>/<hash><ext>` y la clave de todo
es el SHA-256 del contenido: subir dos veces el mismo fichero no duplica ni
fila ni disco. El vínculo con el registro no es directo, va por la ejecución
(migración 013): como toda escritura deja ejecución, y las modificaciones se
encadenan a la de creación, `de_fila` recupera de una vez todos los
documentos de la vida de un registro — el que lo originó y los que se
añadieron después.

El `tag` califica el uso, no el contenido, así que vive en el vínculo: el
mismo fichero puede ser 'crear' en una ejecución y 'justificante pago' en
otra.
"""

import hashlib
import mimetypes
import shutil
from pathlib import Path

from . import entorno
from .db import ROOT

DOCUMENTOS_DIR = entorno.ruta("documentos")
TAG_ORIGEN = "crear"
BLOQUE = 1024 * 1024


def hash_fichero(ruta: Path) -> str:
    """SHA-256 por bloques: los ficheros de carga pasan de 45 MB y no hay
    razón para tenerlos enteros en memoria solo para resumirlos."""
    resumen = hashlib.sha256()
    with open(ruta, "rb") as fichero:
        for bloque in iter(lambda: fichero.read(BLOQUE), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def _base(base) -> Path:
    """La carpeta del almacén se resuelve en cada llamada, no al importar el
    módulo: como valor por defecto de un argumento quedaría congelada, y
    apuntar el almacén a otro sitio (una prueba, otra instalación) no tendría
    ningún efecto."""
    return Path(base) if base is not None else DOCUMENTOS_DIR


def ruta_almacen(hash_doc: str, extension: str, base=None) -> Path:
    """Los dos primeros caracteres del hash como subcarpeta: evita meter
    decenas de miles de ficheros en un solo directorio."""
    return _base(base) / hash_doc[:2] / f"{hash_doc}{extension}"


def archivar(con, ruta, ejecucion_id: int, tag: str = TAG_ORIGEN, base=None) -> str:
    """Guarda el fichero si no estaba y lo vincula a la ejecución. Devuelve
    el hash. Reponer un documento purgado lo vuelve a dejar disponible: el
    hash garantiza que el contenido es exactamente el mismo."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ValueError(f"no existe el fichero '{ruta}'")

    hash_doc = hash_fichero(ruta)
    extension = ruta.suffix.lower()
    destino = ruta_almacen(hash_doc, extension, base)
    fila = con.execute("SELECT estado FROM _documentos WHERE hash = ?", [hash_doc]).fetchone()

    if fila is None:
        _copiar(ruta, destino)
        con.execute(
            """INSERT INTO _documentos (hash, nombre_original, extension, mime, bytes, ruta)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                hash_doc,
                ruta.name,
                extension,
                mimetypes.guess_type(ruta.name)[0],
                ruta.stat().st_size,
                _ruta_guardada(destino),
            ],
        )
    elif fila[0] == "purgado" or not destino.is_file():
        _copiar(ruta, destino)
        con.execute(
            "UPDATE _documentos SET estado = 'disponible', fecha_purga = NULL WHERE hash = ?",
            [hash_doc],
        )

    con.execute(
        """INSERT INTO _ejecucion_documento (ejecucion_id, hash, tag)
           VALUES (?, ?, ?) ON CONFLICT DO NOTHING""",
        [ejecucion_id, hash_doc, tag],
    )
    return hash_doc


def _copiar(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)


def _ruta_guardada(destino: Path) -> str:
    """Relativa al repo cuando el almacén está dentro (el caso normal, para
    que la base sea reubicable), absoluta cuando está fuera."""
    try:
        return destino.relative_to(ROOT).as_posix()
    except ValueError:
        return destino.as_posix()


def adjuntar(con, tabla: str, fila_id: str, ruta, tag: str = None, base=None) -> str:
    """Adjunta un documento a un registro ya existente.

    Abre una ejecución encadenada a la que creó la fila, así que el documento
    aparece en `de_fila` junto a los del alta sin tocar la fila de negocio.
    """
    from . import ejecuciones

    existe = con.execute(f"SELECT count(*) FROM {tabla} WHERE id = ?", [fila_id]).fetchone()[0]
    if not existe:
        raise ValueError(f"no existe {tabla} con id '{fila_id}'")

    principal = ejecuciones.principal_de(con, tabla, fila_id)
    if principal is None:
        raise ValueError(
            f"el registro {tabla} '{fila_id}' es anterior al registro de ejecuciones "
            "(migración 013) y no tiene cadena a la que colgar el documento: "
            "vuelve a crearlo para poder adjuntarle ficheros"
        )

    ejecucion_id = ejecuciones.registrar(con, f"{tabla}.adjuntar", principal=principal)
    hash_doc = archivar(con, ruta, ejecucion_id, tag or TAG_ORIGEN, base)
    ejecuciones.marcar(con, ejecucion_id, "OK")
    return hash_doc


def listar(con):
    """Todos los documentos del almacén, con su número de vínculos."""
    cursor = con.execute(
        """SELECT d.hash, d.nombre_original, d.bytes, d.estado, d.fecha_alta,
                  count(ed.id) AS vinculos,
                  string_agg(DISTINCT ed.tag, ', ') AS tags
           FROM _documentos d
           LEFT JOIN _ejecucion_documento ed ON ed.hash = d.hash
           GROUP BY d.hash, d.nombre_original, d.bytes, d.estado, d.fecha_alta
           ORDER BY d.fecha_alta DESC"""
    )
    return [d[0] for d in cursor.description], cursor.fetchall()


def purgar(con, aplicar: bool = False, base=None):
    """Libera los bytes de los documentos que ningún proceso quiere conservar.

    En seco por defecto: devuelve qué se purgaría sin tocar nada. Con
    `aplicar`, borra los ficheros y marca `estado = 'purgado'`, pero **nunca**
    borra la fila de `_documentos`: el rastro de qué fichero originó cada dato
    sobrevive a la purga.
    """
    from . import ejecuciones, historial

    candidatos = historial.purgables(con)
    if not aplicar or not candidatos:
        return candidatos

    ejecucion_id = ejecuciones.registrar(con, "documento.purgar")
    for hash_doc, _nombre, _bytes, ruta in candidatos:
        fichero = ROOT / ruta
        if fichero.is_file():
            fichero.unlink()
        con.execute(
            """UPDATE _documentos
               SET estado = 'purgado', fecha_purga = current_timestamp
               WHERE hash = ?""",
            [hash_doc],
        )
    ejecuciones.marcar(con, ejecucion_id, "OK")
    return candidatos


def de_ejecucion(con, ejecucion_id: int):
    """Documentos vinculados a una ejecución concreta."""
    cursor = con.execute(
        """SELECT d.hash, ed.tag, d.nombre_original, d.bytes, d.estado, ed.fecha
           FROM _ejecucion_documento ed
           JOIN _documentos d ON d.hash = ed.hash
           WHERE ed.ejecucion_id = ?
           ORDER BY ed.fecha""",
        [ejecucion_id],
    )
    return [d[0] for d in cursor.description], cursor.fetchall()


def de_fila(con, tabla: str, fila_id: str):
    """Documentos de toda la vida de un registro: los de la ejecución que lo
    creó y los de cualquier ejecución encadenada a ella."""
    cursor = con.execute(
        f"""SELECT d.hash, ed.tag, d.nombre_original, d.bytes, d.estado,
                   e.id AS ejecucion_id, e.carga AS operacion, ed.fecha
            FROM {tabla} f
            JOIN _ejecuciones e ON e.ejecucion_id_principal = f.ejecucion_id
            JOIN _ejecucion_documento ed ON ed.ejecucion_id = e.id
            JOIN _documentos d ON d.hash = ed.hash
            WHERE f.id = ?
            ORDER BY ed.fecha""",
        [fila_id],
    )
    return [d[0] for d in cursor.description], cursor.fetchall()
