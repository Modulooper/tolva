"""Dónde se buscan migraciones, catálogo y cargas: núcleo, ejemplos y propia.

El framework y lo que cada uno carga con él no son la misma cosa y no viven
en el mismo sitio. El núcleo son los directorios del repo (`migraciones/`,
`catalogo/`, `cargas/`); la capa propia es `propio/`, con la misma estructura
dentro, y está fuera del control de versiones del núcleo.

En medio hay una tercera capa, `ejemplos/`: un dominio inventado (una
librería) con datos dummy, que existe para dos cosas — que la batería de
pruebas tenga sujeto sin depender de ningún proceso real, y que quien clone
el repo pueda tocar el framework en cinco minutos sin definir nada. Sus
**migraciones son opt-in** (`db migrar --con-ejemplos`): nadie se encuentra
tablas dummy que no pidió. Sus fichas de catálogo y sus cargas sí se ven
siempre, marcadas con `"ejemplo": true`, y quien las consume las ignora por
defecto (ver `motor/solapamiento.py`, que si no propondría `demo_cliente`
como candidato a clave foránea de una tabla real).

La separación es **por directorio, no por disciplina**: los ficheros de una
carga real no pueden colarse en un commit del framework porque no están en su
árbol. Sin esta frontera, framework y negocio acaban en el mismo commit — pasó
literalmente: 17 ficheros de motor y 4 de negocio en el mismo cambio, y no por
descuido, sino porque la mejora del framework salió de trabajar con los datos
reales.

Reglas:

- **El núcleo va primero.** Las migraciones del framework se aplican antes que
  las de ejemplo y que las propias, que es el único orden que puede funcionar:
  las de fuera pueden depender de tablas del núcleo, nunca al revés.
- **En caso de mismo nombre, gana la capa propia.** Permite adaptar una ficha
  de catálogo o una carga del núcleo sin bifurcar el repo. En migraciones no
  aplica: son ficheros distintos y se ejecutan los dos.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EJEMPLOS_DIR = ROOT / "ejemplos"
PROPIO_DIR = ROOT / "propio"


def carpetas(nombre: str, carpeta_nucleo: Path = None, con_ejemplos: bool = True) -> list:
    """Las carpetas donde vive `nombre`, núcleo primero, solo las existentes.

    `con_ejemplos=False` deja fuera la capa de ejemplos. Lo usa `db migrar`,
    que solo las aplica si se piden: el catálogo y las cargas sí las ven
    siempre, porque ahí estorban menos que la incoherencia de una ficha que
    aparece y desaparece según cómo migraste.
    """
    nucleo = carpeta_nucleo if carpeta_nucleo is not None else ROOT / nombre
    candidatas = [nucleo]
    if con_ejemplos:
        candidatas.append(EJEMPLOS_DIR / nombre)
    candidatas.append(PROPIO_DIR / nombre)
    return [carpeta for carpeta in candidatas if carpeta.is_dir()]


def ficheros(nombre: str, patron: str, carpeta_nucleo: Path = None,
             con_ejemplos: bool = True) -> list:
    """Todos los ficheros que casan, núcleo primero y cada bloque ordenado.

    No deduplica: en migraciones dos ficheros con el mismo nombre en carpetas
    distintas son dos migraciones distintas, y `_migraciones` las distingue.
    """
    encontrados = []
    for carpeta in carpetas(nombre, carpeta_nucleo, con_ejemplos):
        encontrados.extend(sorted(carpeta.glob(patron)))
    return encontrados


def resolver(nombre: str, fichero: str, carpeta_nucleo: Path = None):
    """Ruta de un fichero concreto, con la capa propia teniendo prioridad
    sobre ejemplos, y ejemplos sobre el núcleo. None si no está en ninguna."""
    for carpeta in reversed(carpetas(nombre, carpeta_nucleo)):
        candidato = carpeta / fichero
        if candidato.exists():
            return candidato
    return None


def nombres(nombre: str, patron: str, carpeta_nucleo: Path = None) -> list:
    """Los `stem` únicos de los ficheros que casan, en orden alfabético."""
    return sorted({ruta.stem for ruta in ficheros(nombre, patron, carpeta_nucleo)})
