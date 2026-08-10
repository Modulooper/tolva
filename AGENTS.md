# AGENTS.md

Instrucciones para asistentes de código que no sean Claude Code (Codex CLI,
Copilot en modo agente, Cursor, Windsurf…).

**Este fichero no es la documentación del proyecto, y no debe crecer hasta
serlo.** Todo lo que hay que saber para trabajar aquí está en
[CLAUDE.md](CLAUDE.md) y en [README.md](README.md). Lo único que contiene esta
página son los tres automatismos que Claude Code aplica por mecanismo y que tu
herramienta no te va a dar: cargar las instrucciones, invocar los
procedimientos en el momento justo, y respaldar al cerrar. Si mañana los
implementa tu herramienta, esta página sobra.

## Qué es Tolva

Framework ETL conversacional local sobre DuckDB. La regla que lo define:
**la IA está en el diseño, no en la ejecución.** La conversación produce un
fichero de configuración; a partir de ahí es SQL corriendo solo, idéntico cada
mes. Ningún modelo toca una fila de datos.

Todo el producto es Python + DuckDB sin dependencias de LLM, así que se opera
igual desde cualquier agente con terminal y acceso a ficheros. Lo que sí
cambia entre herramientas es la disciplina de diseño, que es de lo que va esto.

## 1. Lee CLAUDE.md antes de tocar nada

Claude Code lo carga solo al abrir el repositorio. Tú tienes que abrirlo:

- [CLAUDE.md](CLAUDE.md) — cómo se trabaja aquí, qué va al núcleo y qué a la
  capa propia, y qué hacer si es una instalación nueva.
- [README.md](README.md) — comandos completos, vocabulario ETL, respaldos y
  recuperación. Es la fuente de verdad; no reproduzcas su contenido en el chat,
  remite a él.

## 2. Los dos procedimientos, con nombre y momento

En Claude Code estos dos ficheros se invocan solos cuando la conversación entra
en su terreno. Fuera son ficheros que nadie abre, así que aquí va cuándo:

- **Antes de crear una tabla o un CRUD nuevos** — lee
  [.claude/skills/crear-proceso/SKILL.md](.claude/skills/crear-proceso/SKILL.md)
  y síguelo entero. Comprueba solapamiento con el catálogo **ejecutando
  código**, no a ojo, y no escribe ninguna migración sin aprobación explícita
  del usuario.
- **Antes de definir la carga de un fichero recurrente** (extractos, informes,
  exports mensuales) — lee
  [.claude/skills/definir-carga/SKILL.md](.claude/skills/definir-carga/SKILL.md)
  y síguelo entero. Perfila la muestra con `etl definir`, propone el mapping,
  y solo escribe en disco tras la aprobación; después `dry-run` antes de
  `ejecutar`.

Saltárselos es la única forma de romper el proyecto sin que nada falle: acabas
con tres tablas para lo mismo y con columnas cuyo tipo nadie decidió. No es
opcional porque tu herramienta no te lo recuerde.

## 3. El respaldo no corre solo

El repo trae un hook `SessionEnd` en `.claude/settings.json` que respalda al
cerrar sesión. **Fuera de Claude Code ese hook no existe**, así que si no
programas nada, no se respalda nada y nadie se entera.

```bash
python -m motor.cli db respaldar --silencioso
```

Prográmalo en el sistema (Programador de tareas en Windows, `cron` o un timer
de systemd en Linux/macOS). Antes hay que configurar el destino con
`db init --respaldo <ruta>`: sin eso el comando no hace nada, a propósito.
El detalle está en [README.md](README.md), en «Respaldos» → «Automatizarlo».

## Y una cosa que no es un automatismo

La carpeta `ejemplos/` es un dominio inventado (`demo_cliente`, `demo_libro`,
`demo_venta`) que existe para las pruebas y para que puedas trastear sin
ensuciar nada. **No cuenta como evidencia de nada**: no la uses al comprobar
solapamiento, no la propongas al diseñar un proceso y no la incluyas en
resúmenes salvo que el usuario la pida por su nombre.
