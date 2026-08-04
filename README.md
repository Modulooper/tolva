# ClaudETL

Plataforma local, monousuario y autónoma sobre DuckDB para gestionar información
de trabajo propia: procesos de negocio (CRUD) y ETL conversacional de ficheros
recurrentes. Sin servidor, sin autenticación, sin multiusuario.

## Estructura

```
/motor/            código Python del ETL y la CLI
/migraciones/       001_nucleo.sql, 002_..., aplicadas en orden por `db migrar`
/cargas/            una definición JSON por tipo de carga
/catalogo/          catálogo semántico del modelo de datos
/entrada/           carpetas vigiladas donde se depositan los ficheros a cargar (no versionado)
/export/            vistas de consumo volcadas a parquet/csv
/datos/almacen.duckdb   estado (no versionado)
```

## Uso

```bash
pip install -r requirements.txt

python -m motor.cli db migrar
python -m motor.cli db consultar "select * from cliente"

python -m motor.cli etl definir <fichero-muestra> [--formato --delimitador --encoding --hoja --fila-cabecera] [--json]
python -m motor.cli etl validar <carga>
python -m motor.cli etl dry-run <carga>
python -m motor.cli etl ejecutar <carga> [--forzar]
python -m motor.cli etl estado

python -m motor.cli ticket crear --cliente <nombre> --persona <nombre> --concepto <viajes|hoteles|gasolina> --importe <n> --fecha <YYYY-MM-DD> [--descripcion <texto>]
python -m motor.cli ticket listar [--cliente] [--persona] [--concepto] [--desde YYYY-MM-DD] [--hasta YYYY-MM-DD]
python -m motor.cli ticket editar <id> [--concepto] [--descripcion] [--importe] [--fecha]
python -m motor.cli ticket borrar <id>
```

`cliente`/`persona` se gestionan por ahora con `db consultar` (no tienen
CRUD propio todavía).

```bash
python -m motor.cli proceso analizar --campo <nombre-propuesto> [--valores v1,v2,...] [--umbral 0.5] [--json]
```

`<carga>` es el nombre de un fichero en `/cargas/<nombre>.json` (o una ruta
directa a un `.json`).

## Vocabulario de operaciones ETL

`rename` · `cast` (`varchar`/`integer`/`double`/`boolean`/`date`) · `trim` ·
`const` · `date_format`. Un tipo no registrado aquí se rechaza en
`etl validar`, no en `etl ejecutar`.

`date_format` nunca delega el parseo al modelo: si dos formatos candidatos
son ambiguos en día/mes (`%d/%m/%Y` vs `%m/%d/%Y`), se resuelve por evidencia
sobre toda la columna; si no hay evidencia suficiente o es contradictoria,
la carga falla explícitamente pidiendo un formato único. Los seriales de
Excel se detectan por rango numérico plausible, con época configurable
(`epoch_excel: "1900"` compensa el bug del año bisiesto, o `"1904"`).

Las tablas destino con `clave_upsert` necesitan una restricción `UNIQUE`
sobre esas columnas (el motor hace `INSERT ... ON CONFLICT ... DO UPDATE`).

`cast` admite `formato_numerico: "es"` para números con miles en `.` y
decimales en `,` (p.ej. extractos bancarios españoles). La definición de
carga admite un campo opcional `encoding` (por defecto `utf-8-sig`) para
ficheros CSV que no vengan en UTF-8.

## Catálogo semántico

`/catalogo/<tabla>.json` es la fuente de verdad del modelo: por cada tabla,
sus campos (tipo, obligatoriedad, sinónimos observados, descripción) y sus
relaciones. `etl validar` exige que la tabla destino de una carga tenga
entrada en el catálogo y que cada campo del mapping esté declarado en ella;
un campo inexistente en el catálogo se rechaza ahí, no en `etl ejecutar`.
Toda tabla nueva necesita su entrada de catálogo antes de poder cargarse.

## Skill `definir-carga`

`.claude/skills/definir-carga/SKILL.md`. Toma un fichero de muestra,
lo perfila con `etl definir` (tipos aparentes, nulos, cardinalidad,
sugerencias de campo destino por sinónimo del catálogo), propone el mapping
completo explicando cada decisión no obvia (formato de fecha, formato
numérico, clave de upsert), y solo tras tu aprobación guarda
`/cargas/<nombre>.json`, valida y enseña el `dry-run`. Nunca ejecuta la
carga sin que confirmes el dry-run primero.

## Estado actual

- Hito 1: estructura del repo, migración núcleo (`persona`, `cliente`, `proyecto`
  + tablas de sistema `_ejecuciones`, `_rechazos`, `_decisiones`) y CLI mínima
  (`db migrar`, `db consultar`).
- Hito 2: motor ETL (`motor/cargas.py`, `motor/operaciones.py`, `motor/fechas.py`,
  `motor/motor_etl.py`) con las 5 primeras operaciones del vocabulario,
  idempotencia por hash de fichero, upsert por clave declarada, rechazos con
  motivo y `extra_fields` para columnas no declaradas. CLI `etl validar`,
  `etl dry-run`, `etl ejecutar [--forzar]`, `etl estado`.
- Hito 3: primera carga real (`cargas/movimientos_banco.json` +
  `migraciones/002_movimiento_bancario.sql`) sobre extractos bancarios reales
  (CSV `;`, cp1252, números en formato español). La clave de upsert
  (fecha_ejecucion, fecha_valor, concepto, importe, saldo) hace que subir el
  extracto acumulado del mes, mes a mes, solo añada los movimientos nuevos.
  Validado con dry-run y con reejecución sobre un extracto que solapaba
  movimientos ya cargados: no duplicó ninguno.
- Hito 4: catálogo semántico (`motor/catalogo.py` + `/catalogo/*.json` para
  `persona`, `cliente`, `proyecto`, `movimiento_bancario`). `cargas.validar`
  rechaza cualquier campo de mapping no declarado en el catálogo de la tabla
  destino, y cualquier tabla destino sin entrada de catálogo, sin necesitar
  conexión a la base.
- Hito 5: perfilado de ficheros de muestra (`motor/perfil.py`, comando
  `etl definir`) — tipos aparentes, nulos, cardinalidad, muestra de valores
  y sugerencias de campo destino cruzando cabeceras contra sinónimos del
  catálogo. Skill de Claude Code `definir-carga`
  (`.claude/skills/definir-carga/SKILL.md`) que usa ese perfil para proponer
  una definición de carga completa, mostrarla para aprobación, y solo
  entonces guardarla, validarla y enseñar el dry-run.
- Hito 6: primera tabla de proceso de negocio con CRUD por CLI.
  `migraciones/004_ticket.sql` (`ticket`, con `cliente_id`/`persona_id` como
  FK y `concepto` restringido por `CHECK` a viajes/hoteles/gasolina) +
  `catalogo/ticket.json` + comandos `ticket crear/listar/editar/borrar`.
  `migraciones/003_ejecuciones_usuario.sql` añade `usuario` (login del SO,
  sin autenticación) a `_ejecuciones` como semilla para un eventual modo
  multiusuario futuro; las filas anteriores a la migración quedan como
  `'desconocido'` en vez de reescribir el histórico.
- Hito 7: detección de solapamiento con código (`motor/solapamiento.py`,
  comando `proceso analizar --campo --valores`) — cruza nombre/sinónimo
  contra el catálogo, cardinalidad de los valores propuestos (categoría
  cerrada vs. entidad propia) y candidatos a clave foránea por solapamiento
  real de valores contra las tablas existentes. Skill de Claude Code
  `crear-proceso` (`.claude/skills/crear-proceso/SKILL.md`) que usa esa
  evidencia para tomar requisitos por preguntas, proponer el esquema de una
  entidad nueva integrada con lo existente (o justificar por qué no
  referencia núcleo, como `movimiento_bancario`), y solo tras tu aprobación
  escribir migración + `/catalogo/<tabla>.json` + entrada en `_decisiones`.
