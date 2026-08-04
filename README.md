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

python -m motor.cli etl validar <carga>
python -m motor.cli etl dry-run <carga>
python -m motor.cli etl ejecutar <carga> [--forzar]
python -m motor.cli etl estado
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
