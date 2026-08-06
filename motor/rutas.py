"""Dónde se buscan migraciones, catálogo y cargas: núcleo y capa propia.

El framework y lo que cada uno carga con él no son la misma cosa y no viven
en el mismo sitio. El núcleo son los directorios del repo (`migraciones/`,
`catalogo/`, `cargas/`); la capa propia es `propio/`, con la misma estructura
dentro, y está fuera del control de versiones del núcleo.

La separación es **por directorio, no por disciplina**: los ficheros de una
carga real no pueden colarse en un commit del framework porque no están en su
árbol. Sin esta frontera, framework y negocio acaban en el mismo commit — pasó
literalmente: 17 ficheros de motor y 4 de negocio en el mismo cambio, y no por
descuido, sino porque la mejora del framework salió de trabajar con los datos
reales.

Reglas:

- **El núcleo va primero.** Las migraciones del framework se aplican antes que
  las propias, que es el único orden que puede funcionar: las propias pueden
  depender de tablas del núcleo, nunca al revés.
- **En caso de mismo nombre, gana la capa propia.** Permite adaptar una ficha
  de catálogo o una carga del núcleo sin bifurcar el repo. En migraciones no
  aplica: son ficheros distintos y se ejecutan los dos.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROPIO_DIR = ROOT / "propio"


def carpetas(nombre: str, carpeta_nucleo: Path = None) -> list:
    """Las carpetas donde vive `nombre`, núcleo primero, solo las existentes."""
    nucleo = carpeta_nucleo if carpeta_nucleo is not None else ROOT / nombre
    return [carpeta for carpeta in (nucleo, PROPIO_DIR / nombre) if carpeta.is_dir()]


def ficheros(nombre: str, patron: str, carpeta_nucleo: Path = None) -> list:
    """Todos los ficheros que casan, núcleo primero y cada bloque ordenado.

    No deduplica: en migraciones dos ficheros con el mismo nombre en carpetas
    distintas son dos migraciones distintas, y `_migraciones` las distingue.
    """
    encontrados = []
    for carpeta in carpetas(nombre, carpeta_nucleo):
        encontrados.extend(sorted(carpeta.glob(patron)))
    return encontrados


def resolver(nombre: str, fichero: str, carpeta_nucleo: Path = None):
    """Ruta de un fichero concreto, con la capa propia teniendo prioridad.
    None si no está en ninguna de las dos."""
    for carpeta in reversed(carpetas(nombre, carpeta_nucleo)):
        candidato = carpeta / fichero
        if candidato.exists():
            return candidato
    return None


def nombres(nombre: str, patron: str, carpeta_nucleo: Path = None) -> list:
    """Los `stem` únicos de los ficheros que casan, en orden alfabético."""
    return sorted({ruta.stem for ruta in ficheros(nombre, patron, carpeta_nucleo)})
