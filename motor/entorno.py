"""Dónde viven los datos, que no tiene por qué ser donde vive el código.

Hay cuatro ubicaciones y **no son la misma cosa**, por mucho que por defecto
cuelguen del repositorio:

- **El almacén** (`almacen.duckdb`): el estado. Irremplazable.
- **Los documentos archivados**: los ficheros de origen y los justificantes,
  direccionados por su hash. También irremplazables.
- **Las exportaciones**: vistas de consumo y salidas en parquet, CSV o xlsx.
  Son resultado, y se regeneran con `etl exportar` o `etl salida`.
- **Los respaldos**: copias fechadas del estado, en parquet. Ver
  `motor/respaldo.py`.

Se configuran por separado porque sus requisitos son **opuestos**. El almacén
no debe vivir en una carpeta sincronizada; las exportaciones a menudo sí, que
para eso se generan: alguien las abre desde Excel o las enlaza en Power BI,
puede que desde otra máquina. Una sola ruta para las dos cosas obligaría a
elegir mal en una.

Un fichero de base de datos **no es un documento**, y un cliente de
sincronización asume que puede copiarlo cuando le parezca: resube el fichero
entero en cada cambio, puede copiarlo a medio escribir, deja copias en
conflicto en vez de fusionar y mantiene handles que convierten un borrado
normal en un «acceso denegado». Por eso `db migrar` avisa si el almacén o los
documentos caen en una ruta con pinta de sincronizada — y no dice nada de las
exportaciones.

El respaldo es el tercer requisito, distinto de los otros dos: **quiere estar
sincronizado, y además lejos del almacén**. Su aviso es por tanto el inverso,
y vale con cumplir una de las dos condiciones (`aviso_de_respaldo`).

## Por qué el respaldo no tiene valor por defecto

Es el único de los cuatro que es opt-in, y a propósito. Los otros tres
resuelven a una carpeta del repositorio, que es un sitio razonable para
empezar. Para un respaldo no lo es: dejarlo junto al original no protege de
nada, y una ruta que el framework se invente va a estar mal. Sin configurar,
`db respaldar` no hace nada y dice cómo configurarlo — que es honesto, y
además hace inocuo el hook que el repo distribuye.

## Precedencia

    variable de entorno  >  config.local.json  >  valor por defecto

El fichero es lo que fija una instalación, y se escribe con `db init`. La
variable queda para lo puntual: lanzar una carga contra otro almacén, o
enrutar por usuario sin tocar la configuración.

El orden importa y es el que es por una razón concreta: si solo hubiera
variable de entorno, se pone en una terminal, la siguiente sesión no la ve, se
crea un almacén vacío sin quejarse y parece que se han perdido los datos. El
fichero no se olvida entre sesiones.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Fuera del control de versiones: es de esta máquina, no del proyecto.
FICHERO_CONFIG = ROOT / "config.local.json"

# clave -> (variable de entorno, cómo se calcula el valor por defecto)
# El respaldo devuelve None a propósito: es opt-in, ver el docstring del módulo.
AJUSTES = {
    "datos": ("TOLVA_DATOS", lambda cfg: ROOT / "datos"),
    "documentos": ("TOLVA_DOCUMENTOS", lambda cfg: ruta("datos", cfg) / "documentos"),
    "export": ("TOLVA_EXPORT", lambda cfg: ROOT / "export"),
    "respaldo": ("TOLVA_RESPALDO", lambda cfg: None),
}

# Solo el estado. Las exportaciones se quedan fuera a propósito: que estén en
# una carpeta compartida suele ser justo lo que se busca.
AJUSTES_QUE_NO_DEBEN_SINCRONIZARSE = ("datos", "documentos")

# Carpetas cuyo nombre delata un cliente de sincronización. No es una lista
# exhaustiva ni puede serlo: sirve para avisar, nunca para impedir nada.
INDICIOS_DE_SINCRONIZACION = ("onedrive", "dropbox", "google drive", "googledrive",
                              "icloud", "sharepoint", "nextcloud", "sync")


def config(fichero: Path = None) -> dict:
    """Lo que diga `config.local.json`, o vacío. Un fichero ilegible se ignora
    en silencio: no vale romper todos los comandos por una coma de más en un
    fichero opcional, y `db rutas` ya enseña de dónde sale cada valor."""
    fichero = fichero if fichero is not None else FICHERO_CONFIG
    try:
        contenido = json.loads(fichero.read_text(encoding="utf-8"))
        return contenido if isinstance(contenido, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def ruta(clave: str, cfg: dict = None) -> Path:
    """La ruta efectiva de un ajuste, aplicando la precedencia."""
    variable, por_defecto = AJUSTES[clave]
    cfg = config() if cfg is None else cfg

    valor = os.environ.get(variable) or cfg.get(clave)
    return Path(valor).expanduser() if valor else por_defecto(cfg)


def origen(clave: str, cfg: dict = None) -> str:
    """De dónde sale el valor. Para que `db rutas` pueda explicarlo: la mitad
    de los sustos con esto son 'creía que estaba mirando al otro almacén'."""
    variable, por_defecto = AJUSTES[clave]
    cfg = config() if cfg is None else cfg
    if os.environ.get(variable):
        return f"variable {variable}"
    if cfg.get(clave):
        return f"{FICHERO_CONFIG.name}"
    # Un ajuste opt-in sin configurar no tiene «valor por defecto»: no hay
    # valor. Decir que lo hay haría creer que la cosa está funcionando.
    return "valor por defecto" if por_defecto(cfg) is not None else "sin configurar"


def rutas_efectivas() -> dict:
    """{clave: (ruta, origen)} de los cuatro ajustes, resueltos de una vez.

    La ruta puede ser None si el ajuste es opt-in y nadie lo ha configurado.
    """
    cfg = config()
    return {clave: (ruta(clave, cfg), origen(clave, cfg)) for clave in AJUSTES}


def datos_dir() -> Path:
    """La carpeta del almacén. Se conserva por comodidad: es la que más se usa."""
    return ruta("datos")


def escribir_config(valores: dict, fichero: Path = None) -> Path:
    """Guarda los ajustes indicados. Solo los que traigan valor: lo que no se
    diga se queda con su valor por defecto en vez de quedar congelado."""
    fichero = fichero if fichero is not None else FICHERO_CONFIG
    actual = config(fichero)
    for clave, valor in valores.items():
        if clave not in AJUSTES:
            raise ValueError(f"ajuste desconocido '{clave}'; hay {sorted(AJUSTES)}")
        if valor:
            actual[clave] = str(Path(valor).expanduser())
        else:
            actual.pop(clave, None)
    fichero.write_text(
        json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return fichero


def carpeta_sincronizada(ruta_a_mirar: Path) -> str:
    """El nombre del tramo de ruta que parece sincronizado, o None.

    Se mira la ruta entera y no solo el último tramo: lo habitual es que el
    sospechoso sea un ancestro (`C:/Users/x/OneDrive - empresa/repo/datos`).
    """
    if ruta_a_mirar is None:
        return None
    for parte in Path(ruta_a_mirar).resolve().parts:
        minuscula = parte.lower()
        if any(indicio in minuscula for indicio in INDICIOS_DE_SINCRONIZACION):
            return parte
    return None


def aviso_de_sincronizacion() -> str:
    """El texto del aviso, o None si no hay nada que avisar.

    Se devuelve en vez de imprimirse: el motor no escribe en consola, y así una
    carga programada no ensucia su log con esto.
    """
    afectados = []
    for clave in AJUSTES_QUE_NO_DEBEN_SINCRONIZARSE:
        sospechosa = carpeta_sincronizada(ruta(clave))
        if sospechosa:
            afectados.append((clave, sospechosa))
    if not afectados:
        return None

    detalle = "\n".join(f"    {clave}: dentro de '{carpeta}'" for clave, carpeta in afectados)
    return (
        "AVISO: hay datos en lo que parece una carpeta sincronizada.\n"
        f"{detalle}\n"
        "  Un cliente de sincronización puede copiar el almacén a medio escribir, dejar\n"
        "  copias en conflicto o bloquearlo. Las exportaciones sí pueden estar ahí.\n"
        "  Para moverlo:  python -m motor.cli db init --datos C:/ruta/local\n"
        "  Y mueve a esa carpeta lo que ya tengas: el comando no copia nada."
    )


def respaldo_a_salvo(cfg: dict = None) -> bool:
    """Si el respaldo está en un sitio que sirve de respaldo.

    La regla, que es la inversa de la de arriba: vale si **sale de la máquina**
    (carpeta sincronizada) **o al menos sale del disco** (otra unidad). Con una
    de las dos basta, y por eso una ruta que aquí sería un problema —dentro de
    OneDrive— es justo la buena.

    No se exige salir de la máquina porque no todo el mundo tiene sincronización
    y un disco aparte ya cubre el fallo más probable, que es que muera el disco.
    """
    destino = ruta("respaldo", cfg)
    if destino is None:
        return False
    if carpeta_sincronizada(destino):
        return True
    return Path(destino).drive.lower() != Path(ruta("datos", cfg)).drive.lower()


def aviso_de_respaldo(cfg: dict = None) -> str:
    """El texto del aviso sobre el respaldo, o None si no hay nada que decir.

    Hay dos cosas distintas que avisar y no son el mismo problema: que no haya
    respaldo configurado, y que lo haya pero en un sitio que no protege de nada.
    """
    cfg = config() if cfg is None else cfg
    destino = ruta("respaldo", cfg)
    if destino is None:
        return (
            "AVISO: no hay respaldo configurado, así que no se está respaldando nada.\n"
            "  Para configurarlo:  python -m motor.cli db init --respaldo "
            "'C:/Users/tu/OneDrive/Respaldo Tolva'\n"
            "  Conviene que esté sincronizado (sale de la máquina) o al menos en otro disco."
        )
    if not respaldo_a_salvo(cfg):
        return (
            f"AVISO: el respaldo está en '{destino}', que no sale ni de la máquina ni del\n"
            "  disco donde vive el almacén. Un respaldo que muere con el original no es un\n"
            "  respaldo: si se te va el disco, se van los dos a la vez.\n"
            "  Para moverlo:  python -m motor.cli db init --respaldo <carpeta sincronizada>"
        )
    return None
