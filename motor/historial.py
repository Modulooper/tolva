"""Política de historial: cuánto conserva cada proceso de sus documentos.

Un proceso —una carga de fichero o una entidad del CLI— declara en su
definición cuánto guarda:

    "historial": "siempre"                                  (por defecto)
    "historial": {"tipo": "ficheros", "cantidad": 10}
    "historial": {"tipo": "anios",    "cantidad": 3}
    "historial": {"tipo": "ficheros", "cantidad": 10,
                  "tags_exentos": ["justificante pago"]}

Va en `/cargas/<nombre>.json` para las cargas y en `/catalogo/<tabla>.json`
para las entidades del CLI.

Dos reglas que hacen que esto sea seguro:

1. **Purgar vacía los bytes, nunca la fila.** El documento queda en
   `_documentos` con `estado = 'purgado'`: se sigue sabiendo de qué fichero
   salió cada línea aunque ya no se pueda abrir. Si la purga borrase el
   metadato, rompería justo la trazabilidad que la justifica.
2. **Un documento se conserva si lo conserva _algún_ proceso.** El mismo
   fichero puede estar vinculado a una carga con historial corto y a un
   ticket con historial "siempre"; en ese caso no se purga. La decisión se
   toma sobre la unión, nunca proceso a proceso.

El valor por defecto es "siempre": nadie pierde nada por no declarar
historial, y en particular los justificantes de gasto —que Hacienda exige
conservar años— no desaparecen por descuido.
"""

from datetime import datetime

SIEMPRE = "siempre"
POR_DEFECTO = SIEMPRE

SCHEMA_HISTORIAL = {
    "oneOf": [
        {"const": SIEMPRE},
        {
            "type": "object",
            "properties": {
                "tipo": {"enum": ["ficheros", "anios"]},
                "cantidad": {"type": "integer", "minimum": 1},
                "tags_exentos": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tipo", "cantidad"],
            "additionalProperties": False,
        },
    ]
}


def proceso_de(carga: str, tipo: str) -> str:
    """Nombre del proceso al que pertenece una ejecución. En una carga es el
    nombre de la carga; en el CLI, la operación es 'ticket.crear' y el
    proceso es la tabla."""
    return carga if tipo == "carga" else carga.split(".", 1)[0]


def politicas() -> dict:
    """Política declarada por cada proceso, leyendo las definiciones de carga
    y las fichas de catálogo. Los procesos sin declaración no aparecen: al
    consultarlos se aplica POR_DEFECTO."""
    from . import cargas, catalogo

    declaradas = {}
    for ruta in cargas.listar_definiciones():
        definicion = cargas.cargar(str(ruta))
        if "historial" in definicion:
            declaradas[definicion["nombre"]] = definicion["historial"]
    for nombre in catalogo.listar_entidades():
        entidad = catalogo.cargar_entidad(nombre)
        if "historial" in entidad:
            declaradas[entidad["tabla"]] = entidad["historial"]
    return declaradas


def _hace_anios(momento: datetime, anios: int) -> datetime:
    try:
        return momento.replace(year=momento.year - anios)
    except ValueError:  # 29 de febrero de un año bisiesto
        return momento.replace(month=2, day=28, year=momento.year - anios)


def _usos(con) -> dict:
    """Uso de cada documento por proceso: {proceso: {hash: (ultima_fecha, tags)}}."""
    filas = con.execute(
        """SELECT ed.hash, ed.tag, ed.fecha, e.tipo, e.carga
           FROM _ejecucion_documento ed
           JOIN _ejecuciones e ON e.id = ed.ejecucion_id"""
    ).fetchall()

    por_proceso = {}
    for hash_doc, tag, fecha, tipo, carga in filas:
        proceso = proceso_de(carga, tipo)
        documentos_proceso = por_proceso.setdefault(proceso, {})
        ultima, tags = documentos_proceso.get(hash_doc, (fecha, set()))
        documentos_proceso[hash_doc] = (max(ultima, fecha), tags | {tag})
    return por_proceso


def a_conservar(con, ahora: datetime = None) -> set:
    """Hashes que algún proceso quiere conservar."""
    ahora = ahora or datetime.now()
    declaradas = politicas()
    conservar = set()

    for proceso, documentos_proceso in _usos(con).items():
        politica = declaradas.get(proceso, POR_DEFECTO)
        if politica == SIEMPRE:
            conservar.update(documentos_proceso)
            continue

        exentos = set(politica.get("tags_exentos", []))
        conservar.update(
            hash_doc
            for hash_doc, (_, tags) in documentos_proceso.items()
            if tags & exentos
        )

        if politica["tipo"] == "ficheros":
            recientes = sorted(
                documentos_proceso.items(), key=lambda par: par[1][0], reverse=True
            )[: politica["cantidad"]]
            conservar.update(hash_doc for hash_doc, _ in recientes)
        else:  # anios
            limite = _hace_anios(ahora, politica["cantidad"])
            conservar.update(
                hash_doc
                for hash_doc, (ultima, _) in documentos_proceso.items()
                if ultima >= limite
            )

    return conservar


def purgables(con, ahora: datetime = None) -> list:
    """Documentos disponibles que ningún proceso quiere conservar."""
    conservar = a_conservar(con, ahora)
    filas = con.execute(
        """SELECT hash, nombre_original, bytes, ruta
           FROM _documentos WHERE estado = 'disponible'
           ORDER BY bytes DESC"""
    ).fetchall()
    return [fila for fila in filas if fila[0] not in conservar]
