"""Cuándo lo que se acaba de tocar es el framework y no lo tuyo.

Este módulo existe por un problema que solo aparece cuando el framework lo usa
alguien que no lo escribió: **la interfaz de Tolva es un asistente capaz de
modificar el propio Tolva**. La primera instalación ajena lo hizo en la primera
sesión, y lo hizo bien: le pidieron poder configurar el formato de una salida y
el asistente extendió el JSON de la carga y adaptó el generador. La forma era la
correcta. El problema es que esa capacidad se quedó en el clon de esa persona,
donde acabará muriendo, y de paso su copia del núcleo divergió de la publicada
sin que nadie lo supiera.

Hay dos cosas distintas que detectar aquí, y conviene no mezclarlas:

- **Lo que debería haber ido a `propio/`.** Es el caso mayoritario y es un
  error: un proceso de negocio metido en el núcleo. El motor ya tiene una
  prueba que caza esto en las migraciones; en el resto del árbol no había nada.
- **Lo que sí es framework y merece volver.** Es el caso bueno y raro, y hoy no
  tiene ningún camino de vuelta.

Las dos se detectan igual —se ha escrito fuera de `propio/`— y se distinguen
preguntando, que es justo lo que hace el aviso.

## Por qué avisa y no impide

Podría hacerse con un `PreToolUse` que deniegue la escritura. No se hace: si la
heurística falla, un tercero se queda sin poder editar `motor/` y sin entender
por qué, y eso es peor que una divergencia. El aviso llega después de escribir,
que en un repositorio con git no pierde nada, y deja la decisión donde tiene que
estar. Mismo criterio que el resto del proyecto: `db init` no mueve ficheros, la
purga no se ejecuta sola y la restauración no pisa el almacén vivo.

## Por qué no envía nada

Un diff del núcleo puede arrastrar contexto de negocio —nombres de columna, el
SQL de una salida, un fixture con clientes dentro—. Tolva promete que lo tuyo no
sale del repositorio, así que esto detecta, avisa y como mucho prepara; subirlo
lo decide una persona. Sería incoherente que la primera cosa del proyecto que
manda algo a la red lo hiciera sin preguntar.

## El mantenedor no quiere el aviso

Quien desarrolla el framework toca `motor/` todo el rato y para él esto sería
ruido constante. Se apaga poniendo `"mantenedor": true` en `config.local.json`,
que ya está fuera del control de versiones y es de esa máquina. A mano y no con
`db init`, porque `db init` es el comando de las cuatro rutas y no conviene que
empiece a ser el comando de todo.
"""

import json
import subprocess
from pathlib import Path

from . import entorno

ROOT = entorno.ROOT

# Qué es «el núcleo» a estos efectos: lo que este repositorio versiona y
# distribuye. Se declara explícitamente en vez de preguntarle a git por lo
# ignorado, para que la detección siga funcionando en una copia sin git y para
# que la lista se pueda leer de un vistazo.
CARPETAS_NUCLEO = (
    "motor",
    "migraciones",
    "catalogo",
    "cargas",
    "ejemplos",
    "pruebas",
    ".claude",
    ".github",
)

FICHEROS_NUCLEO = (
    "README.md",
    "README.en.md",
    "CLAUDE.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "requirements.txt",
    ".gitignore",
)

# Lo que nunca es núcleo aunque cuelgue del repositorio. `propio/` es la razón
# de ser de todo esto; el resto son estado o resultado.
CARPETAS_PROPIAS = ("propio", "datos", "export", "entrada")


def es_del_nucleo(ruta) -> bool:
    """Si esa ruta es del framework y no de quien lo usa.

    Una ruta de fuera del repositorio no es núcleo: el asistente puede estar
    escribiendo en cualquier sitio de la máquina y eso no es asunto nuestro.
    """
    if not ruta:
        return False
    try:
        relativa = Path(ruta).resolve().relative_to(ROOT)
    except (ValueError, OSError):
        return False

    partes = relativa.parts
    if not partes:
        return False
    if partes[0] in CARPETAS_PROPIAS:
        return False
    if partes[0] in CARPETAS_NUCLEO:
        return True
    return len(partes) == 1 and partes[0] in FICHEROS_NUCLEO


def es_mantenedor(cfg: dict = None) -> bool:
    """Quien desarrolla el framework, que no quiere el aviso en cada edición."""
    cfg = entorno.config() if cfg is None else cfg
    return bool(cfg.get("mantenedor"))


def _git(*argumentos) -> str:
    """git, o cadena vacía si no hay git, no hay repositorio o el comando falla.

    Nunca levanta: esto corre dentro del hook de fin de sesión y del hook de
    edición, y ninguno de los dos puede permitirse tumbar nada.
    """
    try:
        completado = subprocess.run(
            ["git", *argumentos],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completado.stdout if completado.returncode == 0 else ""


def nucleo_modificado() -> dict:
    """Qué hay tocado del núcleo respecto a lo publicado.

    Dos cosas distintas, porque piden respuestas distintas:

    - `sin_confirmar`: escrito y todavía sin commit. Es el caso normal cuando un
      asistente acaba de extender algo, y el que se pierde sin dejar rastro.
    - `sin_enviar`: commiteado por delante del remoto. Ya no se pierde, pero
      sigue sin llegar a nadie.
    """
    sin_confirmar = []
    for linea in _git("status", "--porcelain").splitlines():
        # "XY ruta" y, en un rename, "XY origen -> destino".
        ruta = linea[3:].strip().strip('"').split(" -> ")[-1]
        if es_del_nucleo(ROOT / ruta):
            sin_confirmar.append(ruta)

    sin_enviar = []
    remoto = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}").strip()
    if remoto:
        for ruta in _git("diff", "--name-only", f"{remoto}..HEAD").splitlines():
            if ruta and es_del_nucleo(ROOT / ruta):
                sin_enviar.append(ruta)

    return {
        "sin_confirmar": sorted(set(sin_confirmar)),
        "sin_enviar": sorted(set(sin_enviar)),
        "rama": _git("rev-parse", "--abbrev-ref", "HEAD").strip(),
    }


def aviso_de_nucleo(estado: dict = None) -> str:
    """El texto para el resumen de fin de sesión, o None si no hay nada.

    Se devuelve en vez de imprimirse, igual que los avisos de `entorno`: el
    motor no escribe en consola.
    """
    if es_mantenedor():
        return None
    estado = nucleo_modificado() if estado is None else estado
    tocados = estado["sin_confirmar"] + estado["sin_enviar"]
    if not tocados:
        return None

    muestra = ", ".join(tocados[:4])
    resto = f" y {len(tocados) - 4} más" if len(tocados) > 4 else ""
    en_principal = estado["rama"] in ("main", "master")
    return (
        f"AVISO: hay {len(tocados)} fichero(s) del núcleo de Tolva modificados en esta\n"
        f"  instalación ({muestra}{resto}).\n"
        "  Si es un proceso tuyo, su sitio es propio/, y conviene moverlo antes de que\n"
        "  choque con el próximo 'git pull'. Si es una mejora del framework, mándala:\n"
        "  aquí se queda contigo y entra para todos si sale.\n"
        + ("  Estás en la rama principal: una rama aparte te evita el conflicto al\n"
           "  actualizar.\n" if en_principal else "")
        + "  El detalle:  python -m motor.cli db nucleo"
    )


def mensaje_para_hook(carga_util: str) -> str:
    """El aviso inmediato tras una escritura, o None.

    Recibe el JSON que el hook `PostToolUse` entrega por la entrada estándar y
    saca de ahí el fichero escrito. Todo lo que no se entienda devuelve None: un
    hook que se pone a hablar por un payload que no reconoce es ruido, y el
    resumen de fin de sesión ya cubre el caso por la otra vía.
    """
    if es_mantenedor():
        return None
    try:
        datos = json.loads(carga_util)
    except (TypeError, ValueError):
        return None
    if not isinstance(datos, dict):
        return None

    entrada = datos.get("tool_input") or {}
    ruta = entrada.get("file_path") or entrada.get("notebook_path")
    if not es_del_nucleo(ruta):
        return None

    relativa = Path(ruta).resolve().relative_to(ROOT)
    return (
        f"Acabas de escribir en el núcleo de Tolva: {relativa}\n"
        "Antes de seguir, decide con el usuario cuál de las dos cosas es:\n"
        "  - Un proceso o una carga suya. Entonces su sitio es propio/ y hay que\n"
        "    moverlo: en el núcleo se lo lleva por delante la próxima actualización, y\n"
        "    además no debería venir de serie en la instalación de nadie más.\n"
        "  - Una capacidad del framework, algo que cualquier instalación querría.\n"
        "    Entonces está bien donde está, pero que no muera en este clon: dilo,\n"
        "    propón dejarlo en una rama aparte y mandarlo al repositorio de Tolva.\n"
        "No lo decidas tú solo, y no lo des por bueno porque el código funcione."
    )
