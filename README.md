# ClaudETL

Plataforma local, monousuario y autónoma sobre DuckDB para gestionar información
de trabajo propia: procesos de negocio (CRUD) y ETL conversacional de ficheros
recurrentes. Sin servidor, sin autenticación, sin multiusuario.

## Instalación

Requisitos: Python 3.11+ y Git.

```bash
git clone <url-del-repo>
cd ClaudETL

python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash / PowerShell: .venv\Scripts\Activate.ps1
                                 # macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt

python -m motor.cli db migrar
```

El último comando crea `datos/almacen.duckdb` desde cero y aplica todas las
migraciones en orden. `datos/`, `entrada/` y `export/` están en `.gitignore`
(son estado local, no código), así que cada instalación arranca con el
almacén vacío.

Comprobación rápida:

```bash
python -m motor.cli ticket listar
python -m motor.cli idea listar
```
Ambos deberían devolver "(0 filas)" en una instalación nueva sin errores.

### Instalación asistida por IA

Este repo incluye skills de Claude Code en `.claude/skills/` (`definir-carga`,
`crear-proceso`) que son el diferencial del proyecto: perfilan ficheros,
comprueban solapamiento contra el catálogo semántico y proponen esquema antes
de tocar nada. Para que la instalación completa (clonar, crear venv, instalar
dependencias, migrar, y luego usar esos skills) la haga la IA sola, hace falta
**Claude Code** (la CLI), no Claude Desktop/claude.ai: Code tiene acceso
directo a terminal y sistema de ficheros locales, que es lo que requieren los
pasos de arriba y lo que activa `.claude/skills/` automáticamente al abrir el
repo. Claude Desktop, sin un MCP de terminal/filesystem conectado, no puede
ejecutar `git clone`, `pip install` ni `python -m motor.cli` — como mucho
podría leer este README y devolver los pasos en texto para que los ejecutes
tú. Con un MCP de ese tipo configurado sí podría, en teoría, pero no es la
vía pensada ni probada para este proyecto.

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
python -m motor.cli db uso [--minimo 3]

python -m motor.cli etl definir <fichero-muestra> [--formato --delimitador --encoding --hoja --fila-cabecera] [--json]
python -m motor.cli etl validar <carga>
python -m motor.cli etl dry-run <carga>
python -m motor.cli etl ejecutar <carga> [--forzar]
python -m motor.cli etl estado

python -m motor.cli ticket crear --cliente <nombre> --persona <nombre> --concepto <viajes|hoteles|gasolina|otros> --importe <n> --fecha <YYYY-MM-DD> [--descripcion <texto>]
python -m motor.cli ticket listar [--cliente] [--persona] [--concepto] [--desde YYYY-MM-DD] [--hasta YYYY-MM-DD]
python -m motor.cli ticket editar <id> [--concepto] [--descripcion] [--importe] [--fecha]
python -m motor.cli ticket borrar <id>

python -m motor.cli idea crear --persona <nombre> --texto <texto> [--cliente <nombre>] [--estado <pendiente|en_curso|descartada|hecha>] [--fecha YYYY-MM-DD]
python -m motor.cli idea listar [--persona] [--cliente] [--estado] [--desde YYYY-MM-DD] [--hasta YYYY-MM-DD]
python -m motor.cli idea editar <id> [--texto] [--cliente] [--estado] [--fecha]
python -m motor.cli idea borrar <id>
```

`cliente`/`persona` se gestionan por ahora con `db consultar` (no tienen
CRUD propio todavía). En `idea`, `--fecha` es opcional al crear (por defecto
hoy) y `--cliente` también (una idea no tiene por qué estar ligada a un
cliente concreto).

```bash
python -m motor.cli proceso analizar --campo <nombre-propuesto> [--valores v1,v2,...] [--umbral 0.5] [--json]

python -m motor.cli etl exportar <vista>
```

`<carga>` es el nombre de un fichero en `/cargas/<nombre>.json` (o una ruta
directa a un `.json`).

## Cómo escriben las cargas de fichero: singularidad

Las cargas de fichero **no hacen upsert fila a fila** (eso queda para las
acciones puntuales del CLI conversacional: `ticket editar`, `idea editar`).
Una carga declara `campos_singularidad` y el motor, en cada ejecución:

1. borra en bloque de la tabla destino las combinaciones de esos campos que
   aparecen en los datos entrantes,
2. inserta el bloque completo.

Así, recargar el fichero sustituye su porción y deja el resto intacto:

- **`"campos_singularidad": []`** (o ausente) → carga acumulativa pura, nunca
  borra nada.
- **`["centro", "mes"]`** → recargar un fichero con datos de un centro y mes
  sustituye solo esa combinación; el resto del histórico no se toca.
- **`["origen_carga"]`** → foto completa: cada carga sustituye entera a la
  anterior de esa misma carga (es el caso de `previ_transporte`).

### Tabla hall (la T de ETL)

Una carga puede declarar además `tabla_hall` + `transformacion_sql` (van
siempre juntos). La hall es la tabla de trabajo: **siempre foto completa**
(se vacía y se recarga con lo que trae el fichero, sin singularidad propia).
`transformacion_sql` es un `SELECT` sobre esa hall — con las columnas
calculadas, joins de enriquecimiento y filtros que hagan falta — y sus filas
resultantes son las que se promueven a `tabla_destino` aplicando
`campos_singularidad`. En ese caso el `mapping` valida contra el catálogo de
la hall, y las columnas de salida del `SELECT` contra el del destino.

```json
"tabla_hall": "hall_previsiones",
"transformacion_sql": "SELECT h.*, date_part('month', h.fecha_entrega) AS mes, c.nombre AS cliente FROM hall_previsiones h LEFT JOIN cliente c ON c.id = h.cliente_id WHERE h.importe IS NOT NULL",
"campos_singularidad": ["centro", "mes"]
```

La promoción desde la hall no saca los datos del motor: el `DELETE` y el
`INSERT ... SELECT` se resuelven dentro de DuckDB.

**Volumen**: toda escritura masiva pasa por DataFrame
(`motor_etl._insertar_bloque`), no por sentencias `INSERT` individuales.
DuckDB es columnar y degrada de forma no lineal con SQL fila a fila: medido,
1.000 filas por SQL tardan ~13s, mientras que 500.000 vía DataFrame tardan
~0,35s.

## Registro de consultas y uso real

Toda consulta conversacional (`db consultar`) y toda extracción
(`etl exportar`) queda registrada en la tabla de sistema `_consultas` con su
duración, filas devueltas, usuario y si falló. `db uso` lo resume:

- **Uso por objeto**: qué tablas y vistas se consultan de verdad.
- **Sin uso registrado**: lo que no toca nadie (candidato a revisar o
  eliminar).
- **Consultas recurrentes**: si preguntas repetidamente por las mismas
  tablas, esa consulta es candidata a convertirse en vista `*_consumo` con su
  export, en vez de reescribirla cada vez.
- **Más lentas**: para detectar degradación real con datos, no por intuición.

Las tablas que referencia cada consulta se extraen del AST que devuelve el
propio DuckDB (`json_serialize_sql`), no con expresiones regulares — igual
que el parseo de fechas, por evidencia y no por adivinación. `db uso` no se
registra a sí mismo.

**No propone índices, y es deliberado.** Medido sobre `previ_transporte`
(497.383 filas): un índice deja igual la consulta de punto (0,3 ms) y el
agregado (5,1 ms), y **empeora** el filtro por texto (1,8 ms → 4,4 ms).
DuckDB es columnar y mantiene *zonemaps* automáticos en todas las columnas,
así que el escaneo ya es rápido; los índices ART sirven para lookups muy
selectivos y para restricciones `UNIQUE`, y penalizan la escritura — mal
negocio en tablas que se recargan enteras en cada carga.

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

## Vistas de consumo y export

Las vistas de consumo (`movimiento_bancario_consumo`, `ticket_consumo`,
`idea_consumo`, ...) son `VIEW`s de DuckDB creadas por migración
(`005_vistas_consumo.sql`, `008_idea_consumo.sql`):
columnas curadas, con nombres amigables (`cliente`/`persona` en vez de los
`_id`), sin columnas de sistema. `etl exportar <vista>` vuelca la vista a
`/export/<vista>.parquet` y `/export/<vista>.csv`.

**Limitación de DuckDB**: mientras haya una conexión Python abierta al
`.duckdb`, el fichero queda bloqueado en escritura para cualquier otro
proceso. `etl exportar` cierra la conexión explícitamente al terminar
(`motor/export.py`), así que una vez el comando termina, tanto el almacén
como los `.parquet`/`.csv` exportados quedan libres para que Excel o Power
Query los abra sin conflicto. Si vas a dejar una consulta interactiva abierta
contra `almacen.duckdb` (p. ej. desde un notebook), ciérrala antes de abrir
los ficheros exportados desde otra herramienta.

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
- Hito 8: vistas de consumo (`migraciones/005_vistas_consumo.sql`) y export
  (`motor/export.py`, comando `etl exportar <vista>`) a `/export` en parquet
  y CSV, cerrando la conexión explícitamente al terminar. Probado extremo a
  extremo: exporté `movimiento_bancario_consumo`, releí el parquet con una
  conexión DuckDB nueva y los datos coincidían exactamente, y confirmé que
  el almacén no queda bloqueado después (una consulta inmediata posterior
  funciona sin conflicto).
- Hito 9: `ticket.concepto` amplía su `CHECK` a `otros`
  (`migraciones/006_ticket_concepto_otros.sql` — recrea la tabla porque
  DuckDB no soporta `ALTER TABLE ... DROP/ADD CONSTRAINT`). Segunda tabla de
  proceso de negocio con CRUD por CLI: `idea`
  (`migraciones/007_idea.sql`, `catalogo/idea.json`, `motor/ideas.py`,
  comandos `idea crear/listar/editar/borrar`), con `persona_id` obligatorio
  y `cliente_id` opcional, y su vista de consumo
  (`migraciones/008_idea_consumo.sql`, con `LEFT JOIN` a `cliente` porque el
  vínculo es opcional).
- Hito 10: nuevo modelo de escritura para cargas de fichero
  (`campos_singularidad` + promoción en bloque, tabla hall opcional con
  `transformacion_sql`), sustituyendo al upsert fila a fila y a la
  `estrategia: reemplazar` intermedia (ver `_decisiones`,
  `migraciones/010_modelo_carga_singularidad.sql`). Toda escritura masiva
  pasa por DataFrame: la carga real de `previ_transporte`
  (`migraciones/009_previ_transporte.sql`, 497.383 filas de previsión de
  costes de transporte) pasó de no terminar en 10 minutos a completarse en
  22s, y reejecutarla deja 497.383 filas (sustituye, no duplica).
  `movimientos_banco` se migró al mismo modelo (`campos_singularidad` = la
  antigua clave de upsert) y sigue sin duplicar.
- Hito 11: registro de consultas (`migraciones/011_consultas.sql`,
  `motor/consultas.py`, comando `db uso`). `db consultar` y `etl exportar`
  dejan traza en `_consultas`; el análisis extrae las tablas referenciadas
  del AST de DuckDB (`json_serialize_sql`) e informa de uso real, objetos sin
  uso, consultas recurrentes (candidatas a vista de consumo) y las más
  lentas. No propone índices: se midió que en DuckDB no aportan a este
  volumen y llegan a empeorar el filtro por texto (ver `_decisiones`).
