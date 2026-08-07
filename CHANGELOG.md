# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Este proyecto usa [versionado semántico](https://semver.org/lang/es/).

El historial anterior a la primera versión pública era un diario de hitos de
desarrollo privado y no se conserva aquí; está en el histórico de git si hace
falta. El **porqué** de cada decisión de modelo sí se conserva, pero no en este
fichero: vive en la tabla `_decisiones` del propio almacén, junto a la
migración que la tomó.

## [0.1.0] — 2026-08-07

Primera versión pública.

### El framework

- **Motor ETL sobre DuckDB** para ficheros recurrentes: perfilado del fichero
  de muestra, mapping declarativo con un vocabulario cerrado de operaciones,
  rechazos con motivo y `extra_fields` para columnas no declaradas.
- **Singularidad en vez de upsert.** Cada carga declara qué combinación de
  campos identifica una fila; el motor borra ese bloque y reinserta, así que
  volver a subir el fichero corregido de un mes sustituye ese mes y no
  duplica nada.
- **Tabla hall y `transformacion_sql`** para la T del ETL: columnas
  calculadas, joins de enriquecimiento y filtros antes de promover al destino.
- **Stops y alarmas**: un `SELECT` que, si devuelve filas, corta la carga o
  solo avisa. Los mismos invariantes declarados en el catálogo rigen también
  para las escrituras del CLI.
- **Parámetros** para lo que no viene dentro del fichero, y **acciones** SQL
  en momentos del ciclo de vida.
- **CRUD genérico** (`registro`) dirigido por el catálogo: da de alta, lista,
  edita y borra cualquier entidad declarada, sin escribir código.
- **Catálogo semántico**: una ficha por entidad con tipos, sinónimos,
  relaciones, invariantes y política de conservación. Es la fuente de la que
  salen el CRUD, la validación de mappings y el diagrama del modelo.
- **Trazabilidad completa**: toda escritura registra su ejecución, las
  ediciones se encadenan a la creación, y el fichero del que salieron los
  datos se archiva por su hash. Se llega desde una fila hasta su origen.
- **Documentos** adjuntables a un registro con etiqueta libre, con política
  de conservación por proceso y purga que libera bytes sin perder la ficha.
- **Salidas y vistas de consumo** a xlsx/CSV/parquet para enlazar desde Excel
  o Power BI.
- **Registro de consultas** para saber qué se usa de verdad del modelo.

### Tres capas

- **Núcleo** (`migraciones/`, `catalogo/`, `cargas/`): el framework. Una
  instalación limpia **no crea ninguna tabla de negocio**, solo las de
  sistema.
- **Ejemplos** (`ejemplos/`): una librería inventada con datos dummy, opt-in
  con `db migrar --con-ejemplos` e invisible por defecto para el análisis y
  el diagrama.
- **Capa propia** (`propio/`): tus migraciones, fichas y cargas, fuera del
  control de versiones de este repositorio.

### Interfaz conversacional

- Skills de Claude Code (`crear-proceso`, `definir-carga`) que toman
  requisitos por preguntas, comprueban solapamiento con evidencia de los
  datos reales y no escriben nada sin aprobación explícita.

### Pruebas

- 120 pruebas automáticas y un manual de pruebas a mano (`pruebas/MANUAL.md`).
  Corren contra el dominio de ejemplo, no contra procesos reales de nadie.
