# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Este proyecto usa [versionado semántico](https://semver.org/lang/es/).

El historial anterior a la primera versión pública era un diario de hitos de
desarrollo privado y no se conserva aquí; está en el histórico de git si hace
falta. El **porqué** de cada decisión de modelo sí se conserva, pero no en este
fichero: vive en la tabla `_decisiones` del propio almacén, junto a la
migración que la tomó.

## [0.4.0] — 2026-08-08

### Cambiado

- **El proyecto pasa a llamarse Tolva.** Antes ClaudETL, que ataba el nombre a
  una marca ajena y decía «ETL» justo a quien huye de esa palabra. Una tolva es
  la boca por la que entra el material en una máquina: apunta a la ingesta, que
  es de lo que va esto.
- **Las variables de entorno pasan de `CLAUDETL_*` a `TOLVA_*`.** Es un cambio
  incompatible, hecho ahora a propósito: todavía no hay ninguna instalación con
  ellas puestas. Después habría roto en silencio la de quien las tuviera,
  creándole un almacén vacío.

## [0.3.0] — 2026-08-08

### Añadido

- **Tres ubicaciones configurables por separado**: el almacén (`datos`), los
  documentos archivados (`documentos`) y las exportaciones (`export`). Se
  separan porque sus requisitos son opuestos: el almacén no debe vivir en una
  carpeta sincronizada y las exportaciones a menudo sí, que para eso se
  generan.
- **`db init`** escribe la configuración de esta máquina en
  `config.local.json` (fuera del control de versiones). No mueve nada: solo
  declara dónde mirar.
- **`db rutas`** enseña dónde está cada cosa y de dónde sale el valor —
  variable de entorno, fichero o valor por defecto—, que es la mitad de los
  sustos con esto.
- Precedencia `variable de entorno > config.local.json > valor por defecto`.
  El fichero fija la instalación; la variable queda para lo puntual. Si solo
  hubiera variable, olvidarla en una sesión crearía un almacén vacío sin
  quejarse y parecería que se han perdido los datos.
- **Aviso de carpeta sincronizada** en `db migrar` y `db rutas`, solo para el
  almacén y los documentos. Un cliente de sincronización resube el fichero
  entero en cada cambio, puede copiarlo a medio escribir, deja copias en
  conflicto en vez de fusionar y mantiene handles que bloquean borrados.

## [0.2.0] — 2026-08-07

### Añadido

- **Variables en el SQL de una carga** (`$nombre`), disponibles en
  `transformacion_sql`, acciones, validaciones y salidas. Tres familias: de
  sistema (`$ejecucion_id`, `$carga`, `$fichero`, `$hash_fichero`,
  `$promovidas`, `$borradas`), parámetros (`$p_tienda`) y calculadas por la
  propia carga (`$v_total`). Se enlazan como parámetros de consulta, nunca se
  interpolan como texto: un valor con comilla no puede romper el SQL. `etl
  validar` comprueba que toda variable usada existe, sin ejecutar nada.
- **Bloque `variables`**: valores calculados con un `SELECT` y fijados en el
  momento en que se capturan. Cada columna del resultado es una variable. Que
  devuelva cero filas o más de una es un error duro.
- **Momento `tras_promover`** para acciones y variables: el único desde el que
  se ve el resultado real de la escritura, dentro de la misma transacción.
  Permite alimentar una segunda tabla con una singularidad distinta sin
  reimplementar la regla de promoción.
- **Operación `celda`**: lee un dato de una posición fija del Excel (la
  sucursal en `B5`) y lo reparte por todas las filas del detalle. Es lo que
  hace automática una carga cuyos metadatos están en la cabecera, en vez de
  tener que teclearlos al ejecutar.

### Corregido

- Un parámetro declarado y usado solo en el SQL ya no se rechaza como
  huérfano: antes solo contaba si llegaba a una columna del mapping.
- El dry-run lee las celdas de cabecera igual que la carga real. Sin eso, la
  previsualización mostraba esos campos vacíos y la ejecución los rellenaba.

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
