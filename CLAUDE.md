# ClaudETL — instrucciones para Claude Code

Plataforma local sobre DuckDB para gestionar información de trabajo propia
(procesos de negocio y ETL de ficheros recurrentes) de forma conversacional:
la IA no es un asistente que ejecuta comandos sueltos, es la interfaz
principal para modelar datos, cargar ficheros y llevar el día a día.

## Primera vez en este repo

Si `datos/almacen.duckdb` no existe todavía (comprueba con un `ls`/`Test-Path`
antes de asumir nada), esto es una instalación nueva. Sigue "Instalación" en
[README.md](README.md) sin preguntar paso a paso (clonar ya hecho, venv, pip
install, `db migrar`), y verifica al final con `ticket listar` / `idea
listar`.

Justo después de dejarlo instalado y verificado — o al arrancar en un repo
que ya estaba instalado pero es la primera vez que hablas con este usuario —
**explica brevemente en el chat cómo se trabaja con este sistema**, sin
esperar a que pregunte. No hace falta un tocho: 4-6 líneas con lo esencial:

- Esto no es "corre estos comandos": se le habla a la IA en lenguaje natural
  y ella decide si hace falta migración, CRUD o carga de fichero.
- Hay dos formas de meter datos: **cargas ETL recurrentes** desde un fichero
  de muestra (extractos bancarios, exports...) vía el skill `definir-carga`,
  y **procesos de negocio** (tablas tipo `ticket`, `idea`) con CRUD directo
  vía el skill `crear-proceso`, sin fichero de por medio.
- Antes de crear una tabla nueva, el flujo comprueba solapamiento contra el
  catálogo semántico (`/catalogo/*.json`) y contra los datos reales
  (`proceso analizar`), para no duplicar una entidad que ya existe con otro
  nombre.
- Todo lo que sale del almacén para Excel/Power BI pasa por vistas de
  consumo (`*_consumo`) exportadas con `etl exportar <vista>` a
  `/export/*.parquet` y `.csv`.
- Cada decisión de esquema no obvia queda registrada en la tabla
  `_decisiones` (consultable con `db consultar`), con el porqué.

No repitas el README entero — para el detalle de cada comando, remite a él
en vez de listarlos todos en el chat.

## Cómo trabajar en este repo

- **Nunca crees una tabla ni un CRUD nuevo sin pasar por el skill
  `crear-proceso`** (`.claude/skills/crear-proceso/SKILL.md`): comprobación
  de solapamiento con código, propuesta de esquema con evidencia, y
  aprobación explícita antes de escribir migración.
- **Nunca definas una carga de fichero recurrente sin pasar por
  `definir-carga`** (`.claude/skills/definir-carga/SKILL.md`): perfilado del
  fichero de muestra, mapping propuesto, aprobación, y solo entonces
  `dry-run` antes de `ejecutar`.
- Toda migración nueva sigue el patrón de `/migraciones/`: `CREATE TABLE`/
  `CREATE VIEW` + un `INSERT INTO _decisiones` en el mismo fichero explicando
  el porqué de las decisiones no obvias (ver cualquier migración existente
  como plantilla).
- Toda tabla nueva necesita su entrada en `/catalogo/<tabla>.json` antes de
  poder cargarse o referenciarse desde otra carga.
- DuckDB no soporta `ALTER TABLE ... DROP/ADD CONSTRAINT`: para cambiar un
  `CHECK` hay que recrear la tabla dentro de la migración (ver
  `006_ticket_concepto_otros.sql` como ejemplo).
- Tras exportar (`etl exportar`), la conexión se cierra explícitamente para
  no dejar `almacen.duckdb` bloqueado — no abras una conexión interactiva
  larga contra él si luego vas a exportar o si alguien va a abrir los
  ficheros exportados desde Excel/Power Query a continuación.

Para todo lo demás (estructura de carpetas, comandos completos, vocabulario
de operaciones ETL, changelog de hitos), la fuente de verdad es
[README.md](README.md).
