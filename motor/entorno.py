"""Dónde viven los datos, que no tiene por qué ser donde vive el código.

Por defecto el almacén y los documentos cuelgan de `datos/`, dentro del
repositorio. Es cómodo para empezar y es lo que hace una instalación limpia,
pero deja de servir en cuanto el repositorio está en una carpeta que alguien
sincroniza —OneDrive, SharePoint, Dropbox, Drive—, y ese caso es más frecuente
de lo que parece porque la gente clona en Documentos.

**Un fichero de base de datos no es un documento.** Un cliente de
sincronización asume que puede copiar el fichero entero cuando le parezca, y
eso choca con cómo escribe DuckDB:

- Sube el fichero completo en cada cambio. Un almacén de 200 MB se resube
  entero cada vez que se toca una fila.
- Puede copiarlo mientras se está escribiendo, y lo que sube es una foto
  incoherente que solo se descubre al restaurarla.
- Si dos máquinas lo tocan no fusiona: deja una "copia en conflicto" y a
  partir de ahí hay dos verdades divergentes sin que nadie avise.
- Mantiene handles abiertos, que es lo que convierte un borrado normal en un
  "acceso denegado".

Por eso la ruta se puede mover fuera con una variable de entorno, sin tocar
el código ni sacar el repositorio de donde esté:

    CLAUDETL_DATOS=C:/datos/schemate

Lo que se mueve son los datos (almacén y documentos archivados). Las cargas,
el catálogo y las migraciones siguen donde están, versionadas: son código.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VARIABLE = "CLAUDETL_DATOS"

# Carpetas cuyo nombre delata un cliente de sincronización. No es una lista
# exhaustiva ni puede serlo: sirve para avisar, nunca para impedir nada.
INDICIOS_DE_SINCRONIZACION = ("onedrive", "dropbox", "google drive", "googledrive",
                              "icloud", "sharepoint", "nextcloud", "sync")


def datos_dir() -> Path:
    """La carpeta de datos: la de la variable de entorno, o `datos/`."""
    valor = os.environ.get(VARIABLE)
    if valor:
        return Path(valor).expanduser()
    return ROOT / "datos"


def carpeta_sincronizada(ruta: Path = None) -> str:
    """El nombre del tramo de ruta que parece sincronizado, o None.

    Se mira la ruta entera y no solo el último tramo: lo habitual es que el
    sospechoso sea un ancestro (`C:/Users/x/OneDrive - empresa/repo/datos`).
    """
    ruta = ruta if ruta is not None else datos_dir()
    for parte in ruta.resolve().parts:
        minuscula = parte.lower()
        if any(indicio in minuscula for indicio in INDICIOS_DE_SINCRONIZACION):
            return parte
    return None


def aviso_de_sincronizacion(ruta: Path = None) -> str:
    """El texto del aviso, o None si no hay nada que avisar. Se devuelve en
    vez de imprimirse: el motor no escribe en consola, eso es cosa del CLI."""
    sospechosa = carpeta_sincronizada(ruta)
    if not sospechosa:
        return None
    return (
        f"AVISO: el almacén vive dentro de '{sospechosa}', que parece una carpeta "
        f"sincronizada.\n"
        f"  Un cliente de sincronización puede copiar el fichero a medio escribir, "
        f"dejar copias\n"
        f"  en conflicto o bloquearlo. Para moverlo fuera, sin tocar el código:\n"
        f"      {VARIABLE}=C:/ruta/fuera/de/la/sincronizacion\n"
        f"  Y mueve a esa carpeta el almacén y los documentos que ya tengas."
    )
