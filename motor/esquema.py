"""Borrador de esquema a partir del perfil de un fichero.

Traduce el perfil (`motor/perfil.py`) a un `CREATE TABLE` y a una entrada de
catálogo, **como borrador para revisar**, no como decisión tomada.

La inferencia acierta el tipo de almacenamiento y falla la semántica: en un
fichero real, `MES` con valores "03" se infiere `integer` y se comería el
cero; `DESCARGA_COMIENZO` con 20260320003000 se infiere `integer` y en
realidad es una fecha; y un código de cliente numérico es un identificador
aunque parezca un número. Por eso cada columna dudosa sale marcada con un
aviso: el objetivo es que la persona vea dónde tiene que decidir, no
esconderlo detrás de un tipo plausible.
"""

import re
import unicodedata

TIPOS = {
    "integer": "INTEGER",
    "double": "DOUBLE",
    "double (formato_numerico: es)": "DOUBLE",
    "fecha (candidato date_format)": "DATE",
    "varchar": "VARCHAR",
}

CAMPOS_SISTEMA = """    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"""

COLA_SISTEMA = """    origen_carga VARCHAR NOT NULL,
    ejecucion_id BIGINT,
    extra_fields VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp"""

_RE_IDENTIFICADOR = re.compile(r"(^|_)(id|codigo|cod|num|numero|ref|nif|cif)($|_)", re.I)


def normalizar_nombre(nombre: str, posicion: int) -> str:
    """Nombre de columna válido en SQL a partir de la cabecera del fichero.

    Tolera cabeceras con acentos o con caracteres corruptos por una
    codificación perdida en origen (p. ej. 'AÑO' llegando como 'A�O').
    """
    texto = unicodedata.normalize("NFKD", str(nombre or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("�", "")
    texto = re.sub(r"[^0-9a-zA-Z]+", "_", texto).strip("_").lower()
    texto = re.sub(r"_+", "_", texto)
    if not texto:
        return f"columna_{posicion}"
    if texto[0].isdigit():
        texto = f"c_{texto}"
    return texto


def _digitos(valores: list) -> list:
    return [str(v).strip() for v in valores if str(v).strip().isdigit()]


def _parece_fecha_compacta(valor: str) -> bool:
    """AAAAMMDD o AAAAMMDDHHMMSS con componentes plausibles.

    Comprobar solo la longitud daría falsos positivos constantes: un id de
    transportista como 86169897 tiene 8 dígitos y no es ninguna fecha (mes 16,
    día 98).
    """
    if len(valor) not in (8, 14):
        return False
    anio, mes, dia = int(valor[:4]), int(valor[4:6]), int(valor[6:8])
    if not (1900 <= anio <= 2100 and 1 <= mes <= 12 and 1 <= dia <= 31):
        return False
    if len(valor) == 8:
        return True
    hora, minuto, segundo = int(valor[8:10]), int(valor[10:12]), int(valor[12:14])
    return hora <= 23 and minuto <= 59 and segundo <= 59


def _avisos_columna(columna: dict) -> tuple:
    """Devuelve (avisos, notas): lo que exige decisión y lo que solo informa."""
    avisos, notas = [], []
    nombre = columna["columna"]
    tipo = columna["tipo_aparente"]
    muestra = [str(v).strip() for v in columna["muestra_valores"]]

    if tipo == "desconocido (todo vacío)":
        return ["sin un solo valor: no hay evidencia para tipar, decide tú (o descártala)"], []

    if tipo == "integer":
        numeros = _digitos(muestra)
        ceros = [v for v in numeros if len(v) > 1 and v.startswith("0")]
        if ceros:
            avisos.append(
                f"parece integer pero hay ceros a la izquierda ({', '.join(ceros[:3])}): "
                "VARCHAR o se pierden"
            )
        if numeros and all(_parece_fecha_compacta(v) for v in numeros):
            largo = len(numeros[0])
            avisos.append(
                "número de 8 dígitos: ¿es una fecha AAAAMMDD?"
                if largo == 8
                else "número de 14 dígitos: ¿es fecha y hora AAAAMMDDHHMMSS?"
            )
        if _RE_IDENTIFICADOR.search(nombre):
            avisos.append("el nombre sugiere identificador: valorar VARCHAR (no se opera con él)")

    if tipo == "double (formato_numerico: es)":
        avisos.append('decimales con coma: el mapping necesita "formato_numerico": "es"')

    if tipo == "fecha (candidato date_format)":
        avisos.append('necesita date_format con el formato exacto (p. ej. "%d/%m/%Y")')

    if columna["nulos"] == 0 and columna["filas_totales"] > 0:
        notas.append("sin nulos en lo analizado: candidata a NOT NULL")

    return avisos, notas


def proponer(perfil: dict, tabla: str) -> dict:
    """Devuelve el borrador de esquema: columnas, DDL y entrada de catálogo."""
    columnas = []
    usados = set()
    for i, columna in enumerate(perfil["columnas"], start=1):
        nombre = normalizar_nombre(columna["columna"], i)
        while nombre in usados:
            nombre = f"{nombre}_{i}"
        usados.add(nombre)
        avisos, notas = _avisos_columna(columna)
        columnas.append(
            {
                "origen": columna["columna"],
                "nombre": nombre,
                "tipo": TIPOS.get(columna["tipo_aparente"], "VARCHAR"),
                "tipo_aparente": columna["tipo_aparente"],
                "nulos": columna["nulos"],
                "cardinalidad": columna["cardinalidad"],
                "muestra": columna["muestra_valores"],
                "avisos": avisos,
                "notas": notas,
            }
        )

    lineas = [CAMPOS_SISTEMA]
    for c in columnas:
        comentario = f"  -- OJO: {c['avisos'][0]}" if c["avisos"] else ""
        lineas.append(f"    {c['nombre']} {c['tipo']},{comentario}")
    lineas.append(COLA_SISTEMA)
    ddl = f"CREATE TABLE {tabla} (\n" + "\n".join(lineas) + "\n);"

    entrada_catalogo = {
        "entidad": tabla,
        "tabla": tabla,
        "descripcion": f"TODO: describir {tabla}.",
        "campos": {
            "id": {"tipo": "uuid", "obligatorio": True, "sistema": True,
                   "descripcion": "Identificador interno.", "sinonimos": []},
            **{
                c["nombre"]: {
                    "tipo": c["tipo"].lower(),
                    "obligatorio": False,
                    "descripcion": "TODO: describir.",
                    "sinonimos": [c["origen"]] if c["origen"] else [],
                }
                for c in columnas
            },
            "origen_carga": {"tipo": "varchar", "obligatorio": True, "sistema": True,
                             "descripcion": "Nombre de la carga que insertó el registro.", "sinonimos": []},
            "ejecucion_id": {"tipo": "integer", "obligatorio": False, "sistema": True,
                             "descripcion": "Id de la ejecución de carga que insertó la fila.", "sinonimos": []},
            "extra_fields": {"tipo": "varchar", "obligatorio": False, "sistema": True,
                             "descripcion": "JSON con columnas no declaradas en el mapping.", "sinonimos": []},
            "created_at": {"tipo": "timestamp", "obligatorio": True, "sistema": True,
                           "descripcion": "Fecha de alta del registro.", "sinonimos": []},
            "updated_at": {"tipo": "timestamp", "obligatorio": True, "sistema": True,
                           "descripcion": "Fecha de última modificación.", "sinonimos": []},
        },
        "relaciones": [],
    }

    return {
        "tabla": tabla,
        "columnas": columnas,
        "ddl": ddl,
        "catalogo": entrada_catalogo,
        "muestreado": perfil.get("muestreado", False),
        "filas_analizadas": perfil["filas_leidas"],
    }
