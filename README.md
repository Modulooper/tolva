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
/entrada/           carpetas vigiladas donde se depositan los ficheros a cargar
/export/            vistas de consumo volcadas a parquet/csv
/datos/almacen.duckdb   estado (no versionado)
```

## Uso

```bash
pip install -r requirements.txt

python -m motor.cli db migrar
python -m motor.cli db consultar "select * from cliente"
```

## Estado actual

Hito 1: estructura del repo, migración núcleo (`persona`, `cliente`, `proyecto`
+ tablas de sistema `_ejecuciones`, `_rechazos`, `_decisiones`) y CLI mínima
(`db migrar`, `db consultar`).
