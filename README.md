# ClaudETL

Framework ETL conversacional sobre DuckDB, local, monousuario y autónomo, para
gestionar información de trabajo propia: procesos de negocio (CRUD) y carga de
ficheros recurrentes. Sin servidor, sin autenticación, sin multiusuario.

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

### Batería de pruebas

```bash
python -m unittest discover -s pruebas -t .
```

90 pruebas que cubren instalación, motor ETL, singularidad, hall, stops y
alarmas, salidas, CRUD, trazabilidad, documentos, historial/purga, parámetros,
diagrama del modelo, descripciones de carga y separación núcleo/capa propia. No hacen falta dependencias
extra: usan `unittest` de la librería estándar.

Cada prueba corre contra un **almacén temporal recién migrado**, con su propio
catálogo, cargas y almacén de documentos: ninguna toca `datos/almacen.duckdb`
ni `datos/documentos/`. El catálogo real se copia al temporal en vez de
inventarse uno, así que las pruebas comprueban de paso que las fichas del repo
siguen casando con el esquema que crean las migraciones.

[`pruebas/MANUAL.md`](pruebas/MANUAL.md) complementa la batería con 51
comprobaciones a mano: lo que ningún test automático puede validar — que el
flujo conversacional conduzca bien, que los mensajes de error sirvan para
corregir, que la semántica de la singularidad sea la que esperas, y que los
ficheros exportados abran bien desde Excel o Power BI.

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
/datos/documentos/  ficheros archivados por su hash: orígenes de carga y
                    justificantes (no versionado — lleva datos de clientes)
/propio/            tus cargas, catálogo y migraciones (no versionado aquí:
                    es tu repositorio git aparte — ver "Núcleo y capa propia")
```

## Núcleo y capa propia

El framework y lo que tú cargas con él no viven en el mismo sitio:

| | Dónde | Se versiona en |
|---|---|---|
| **Núcleo** | `migraciones/`, `catalogo/`, `cargas/` | este repositorio |
| **Capa propia** | `propio/migraciones/`, `propio/catalogo/`, `propio/cargas/` | el tuyo, privado |

`motor/rutas.py` resuelve las dos capas de forma transparente: `db migrar`
aplica las migraciones del núcleo **y después** las tuyas, y el catálogo y las
cargas se suman. Trabajas siempre sobre este repositorio, con lo tuyo colgando
de `propio/`; no mantienes dos copias del framework.

Dos reglas:

- **El núcleo se aplica primero.** Una migración tuya puede apoyarse en tablas
  del framework; al revés nunca. Por eso una tabla tuya declara su
  `ejecucion_id` en su propia migración en vez de esperar a que se lo añada
  una del núcleo.
- **Si coincide el nombre, gana la capa propia.** Permite adaptar una ficha de
  catálogo o una carga sin bifurcar el repositorio.

La separación es **por directorio, no por disciplina**: los ficheros de una
carga real no pueden colarse en un commit del framework porque no están en su
árbol. La numeración del núcleo tiene huecos donde una migración era de
negocio y se movió a la capa propia; es intencionado y no rompe nada, porque
`_migraciones` indexa por nombre de fichero.

## Uso

```bash
pip install -r requirements.txt

python -m motor.cli db migrar
python -m motor.cli db consultar "select * from cliente"
python -m motor.cli db uso [--minimo 3]

python -m motor.cli etl definir <fichero-muestra> [--formato --delimitador --encoding --hoja --fila-cabecera] [--limite N] [--json]
python -m motor.cli etl esquema <fichero-muestra> --tabla <nombre> [--limite N] [--json]
python -m motor.cli etl validar <carga>
python -m motor.cli etl dry-run <carga>
python -m motor.cli etl ejecutar <carga> [--forzar] [--parametro nombre=valor ...]
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
cliente concreto). `ticket crear` e `idea crear` aceptan `--documento <ruta>`
para archivar en el mismo alta el justificante del que salen los datos.

```bash
python -m motor.cli documento adjuntar <tabla> <id> <ruta> [--tag <etiqueta>]
python -m motor.cli documento listar [--tabla <tabla> --id <id>] [--ejecucion <n>]
python -m motor.cli documento purgar [--aplicar]
```

`documento adjuntar` sirve para lo que llega después del alta (un justificante
de pago, un comprobante): el `--tag` es texto libre y lo agrupa todo bajo el
mismo registro. `documento purgar` va **en seco** salvo que se pase
`--aplicar`, y nunca borra la ficha de un documento: libera los bytes y lo
deja como `purgado`, para que el rastro de qué fichero originó cada dato
sobreviva a la limpieza. Cuánto se conserva lo decide el bloque `historial`
de cada proceso (ver [Historial de documentos](#historial-de-documentos)).

```bash
python -m motor.cli proceso analizar --campo <nombre-propuesto> [--valores v1,v2,...] [--umbral 0.5] [--json]

python -m motor.cli etl exportar <vista>
python -m motor.cli etl salida <carga> [--nombre <salida>]
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

## Definir la tabla: `etl esquema`

`etl definir` perfila el fichero (tipo aparente, nulos, cardinalidad, muestra
de valores, sinónimos del catálogo) y ya distingue decimales con punto de
decimales con coma (`double (formato_numerico: es)`) y candidatos a fecha.
`etl esquema` traduce ese perfil a un **borrador** de `CREATE TABLE` y de
entrada de catálogo (`--json`), con los campos de sistema ya puestos.

Es un borrador, no una decisión: la inferencia acierta el tipo de
almacenamiento y **falla la semántica**, así que cada columna dudosa sale
marcada. Sobre un fichero real:

```
    descarga_comienzo INTEGER,  -- OJO: número de 14 dígitos: ¿es fecha y hora AAAAMMDDHHMMSS?
    mes INTEGER,                -- OJO: parece integer pero hay ceros a la izquierda (03): VARCHAR o se pierden
    codigo_ut INTEGER,          -- OJO: el nombre sugiere identificador: valorar VARCHAR (no se opera con él)
```

Las tres son correctas como tipo y equivocadas como decisión: `mes` guardado
como `INTEGER` pierde el cero de `"03"`, y `descarga_comienzo` es una fecha
disfrazada de número. Ningún volumen de filas analizadas arregla eso — por eso
se marcan en vez de esconderlas tras un tipo plausible.

La detección de fecha compacta valida los componentes, no solo la longitud: un
identificador como `86169897` tiene 8 dígitos pero no puede ser una fecha (mes
16, día 98), así que no se marca como tal.

### Muestreo

`--limite N` analiza solo las primeras N filas y **deja de leer ahí**: sobre un
xlsx de 44,8 MB, 200 filas tardan 2,7 s frente a 37 s leyéndolo entero. A
cambio, el tipo inferido deja de estar garantizado —basta un decimal con coma
más allá de la muestra para que el tipo real sea otro—, así que la salida lo
avisa de forma explícita. Úsalo para iterar rápido y confirma sin `--limite`
antes de dar el esquema por bueno.

## Salidas (ficheros de resultado)

Una carga puede declarar `salidas`: ficheros generados a partir de un `SELECT`
libre sobre cualquier tabla o vista, con el nombre compuesto. Se generan
automáticamente al terminar una carga correcta (nunca si un stop la abortó), o
a mano con `etl salida <carga> [--nombre <salida>]`.

```json
"salidas": [
  {
    "nombre": "resumen_delegacion",
    "fichero": "%Y%m%d_previ_ok.xlsx",
    "sql": "SELECT deleg_nombre, anio, mes, count(*) AS lineas, sum(coste_ventilado) AS coste FROM previ_transporte GROUP BY 1,2,3",
    "carpeta": "export"
  }
]
```

- **Formato** por extensión: `.xlsx`, `.csv` o `.parquet`. Siempre con fila de
  cabecera.
- **Nombre**: admite marcas de fecha de strftime (`%Y%m%d` → `20260805`,
  `%Y%m` → `202608`) y campos entre llaves de la ejecución: `{carga}` y
  `{ejecucion_id}`. Ej.: `"%Y%m%d_previ_detalle_{ejecucion_id}.csv"` →
  `20260805_previ_detalle_11.csv`.
- **`carpeta`** es opcional; por defecto `/export`.

Se generan con la carga ya confirmada: escribir un fichero no puede deshacer
datos correctos, y el `SELECT` ve ya lo promovido.

A diferencia de `etl exportar <vista>`, que vuelca una vista de consumo a un
nombre fijo en parquet y CSV a la vez, aquí el SQL y el nombre son libres.

El xlsx lo escribe la extensión `excel` de DuckDB dentro del motor (83.440
filas en 0,6 s). Si no estuviera disponible —requiere red la primera vez que se
instala— se recurre a openpyxl, que ya es dependencia pero pasa las filas por
Python.

## Stops y alarmas

Una validación es un `SELECT`. **Si devuelve filas, se dispara**; si no
devuelve ninguna, pasa. Las filas devueltas son el detalle que se muestra, así
que la consulta debe seleccionar lo que identifique el problema.

- **`stop`**: el proceso no sigue. La carga queda como no OK (`etl ejecutar`
  devuelve código 1) y **la tabla destino no se toca**.
- **`alarma`**: el proceso avanza y el aviso se muestra al terminar.

Puede haber varias de cada tipo; basta un stop disparado para abortar.

```json
"validaciones": [
  {
    "nombre": "anio_actual",
    "tipo": "stop",
    "mensaje": "El fichero incluye fechas de años distintos al actual.",
    "sql": "SELECT anio, mes, count(*) AS filas FROM _entrante WHERE anio <> year(current_date) GROUP BY 1,2",
    "limite_detalle": 5
  }
]
```

Los datos entrantes están disponibles como **`_entrante`** (tabla temporal con
las filas ya mapeadas, más `ejecucion_id`), y también en la hall si la carga
tiene. Una validación que no se puede ejecutar (SQL mal formado, tabla
inexistente) es error duro: una comprobación que nunca comprobó nada no cuenta
como superada.

Las mismas validaciones pueden declararse en `/catalogo/<tabla>.json` como
invariantes de la tabla. Entonces se comprueban en **cualquier** escritura,
también desde el CLI (`ticket crear`, `idea editar`...): la comprobación corre
después de escribir y dentro de la misma transacción, así que un stop revierte
y no queda nada grabado.

### Acciones del ciclo de vida

```json
"acciones": [
  {"momento": "antes",        "sql": "..."},
  {"momento": "tras_validar", "sql": "..."},
  {"momento": "al_fallar",    "sql": "DELETE FROM hall_previsiones"}
]
```

- **`antes`**: antes de materializar los datos entrantes.
- **`tras_validar`**: superados todos los stops, antes de promover.
- **`al_fallar`**: cuando un stop ha abortado la carga.

Por defecto, un stop **no** limpia nada: la hall conserva los datos del fichero
rechazado y la ejecución queda registrada, para poder investigar con
`db consultar`. Si se quiere limpiar, se declara explícitamente con
`al_fallar`.

### Trazabilidad por carga

Cada ejecución se registra en `_ejecuciones` **antes** de escribir, así que
tiene id desde el principio y una carga abortada también deja traza. Las tablas
que declaren la columna `ejecucion_id` la reciben rellena en cada fila, lo que
permite borrar o inspeccionar exactamente lo que metió un proceso de carga
concreto, sin depender de los campos de negocio:

```sql
DELETE FROM previ_transporte WHERE ejecucion_id = 9;
```

Lo que se dispara queda en `_validaciones_disparadas`, con el detalle de las
filas implicadas en JSON.

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

## Lectura de ficheros xlsx

Los xlsx los lee la extensión `excel` de DuckDB (`read_xlsx` con
`all_varchar=true`), tanto al cargar como al perfilar. Con openpyxl como
respaldo si la extensión no está disponible —requiere red la primera vez— o si
la carga declara `fila_cabecera` distinta de 1, caso que el lector nativo no
cubre.

Medido sobre un fichero de 44,8 MB y 497.383 filas: **4,9 s frente a 23,4 s**.
Comparados ambos lectores fila a fila sobre ese fichero: misma cabecera, mismo
número de filas y **cero celdas distintas tras el mapping**.

`all_varchar=true` deja los valores como texto, igual que el lector de CSV, de
modo que sea el mapping declarado —y no el lector— quien decida los tipos. Eso
además corrige un fallo latente: una celda con fecha real de Excel llega como
serial (`"46101"`), que `motor/fechas.py` sí resuelve, mientras que con
openpyxl llegaba como `datetime` y el parseo fallaba, rechazando la fila.

Perfilado y carga usan el mismo lector a propósito: perfilar con uno distinto
del que luego carga daría un esquema que describe datos que no son los que van
a entrar.

## Vocabulario de operaciones ETL

`rename` · `cast` (`varchar`/`integer`/`double`/`boolean`/`date`) · `trim` ·
`const` · `parametro` · `date_format`. Un tipo no registrado aquí se rechaza
en `etl validar`, no en `etl ejecutar`.

`parametro` es como `const`, pero el valor se resuelve al ejecutar la carga en
vez de estar escrito en la definición (ver "Parámetros").

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

## La descripción de una carga: el para qué, no un rótulo

Toda carga declara una `descripcion` **obligatoria**. No es un título: el
mapping ya dice a qué columna va cada cosa, así que esto tiene que decir lo
que el JSON no puede.

Cinco cosas que debe cubrir:

1. **Para qué se carga** — qué se decide, se factura o se informa con estos
   datos. Sin esto, dentro de un año nadie sabe si la carga sigue haciendo
   falta.
2. **De dónde sale el fichero** — quién lo manda, cada cuánto, y si viene
   exportado a mano (lo que explica que cambien las columnas).
3. **Qué es una fila** en el mundo real.
4. **Qué significa volver a subirlo corregido** — qué porción sustituye.
5. **Qué haría desconfiar** al abrirlo.

El punto 4 es deliberado: es `campos_singularidad` contado en palabras. Si la
descripción dice *"sustituye el mes entero de ese centro"* y la definición
declara `["fecha"]`, **la contradicción se ve sin ejecutar nada**. Por eso el
skill `definir-carga` la escribe antes de elegir la clave, no después.

La redacta la IA a partir del perfilado y de una tanda de preguntas directas,
y tú la corriges — un campo que pide "documenta aquí" se queda vacío; un
borrador concreto se enmienda. Se muestra en `etl validar` y en
`db diagrama`, donde explica el modelo tanto como las relaciones.

El mismo criterio rige la `descripcion` de las fichas de `/catalogo`: decir
qué representa un registro, no repetir el nombre de la tabla.

## Parámetros: lo que no viene dentro del fichero

Veinte tiendas mandan el mismo export de pedidos (fecha, producto, importe) y
la tienda no aparece en ninguna columna. Eso se declara como parámetro y se
pide al ejecutar:

```json
"parametros": [
  {"nombre": "tienda", "obligatorio": true,
   "descripcion": "Tienda de la que viene este fichero",
   "valores_de": {"tabla": "tienda", "etiqueta": "nombre"}},
  {"nombre": "comentario", "obligatorio": false}
]
```

Con `valores_de` la lista es **cerrada**: el valor se resuelve contra esa tabla
por nombre (sin distinguir mayúsculas) y lo que llega a la fila es su id; si no
existe, el error lista los valores disponibles. Sin `valores_de` es **texto
libre**. Sin `obligatorio`, opcional.

El valor llega a las filas por el mapping, con la operación `parametro`:

```json
{"destino": "tienda_id", "operaciones": [{"tipo": "parametro", "nombre": "tienda"}]}
```

Se hace por el mapping, y no por un canal aparte, para que un parámetro se
comporte igual que cualquier otra columna: mismas operaciones encadenables
detrás y mismo tratamiento en la hall y en las transformaciones.

```bash
python -m motor.cli etl ejecutar pedidos --parametro tienda="Gran Vía" --parametro comentario="fichero corregido"
```

Falta un obligatorio y la carga corta **antes de leer el fichero**. Los valores
contestados quedan en `_ejecuciones.parametros`, guardando de una lista cerrada
las dos caras —lo que se tecleó y el id al que resolvió— para que renombrar la
tienda mañana no deje la ejecución ilegible.

**El parámetro casi siempre debe entrar en `campos_singularidad`**, junto a
alguna columna del fichero (fecha, producto). Si no está, recargar el fichero
de una tienda borra las filas de las demás, porque las combinaciones que se
borran no distinguen la tienda. `etl validar` lo avisa:

```
AVISO: el parámetro obligatorio 'tienda' llega a 'tienda_id', que no está en
campos_singularidad ['fecha', 'producto']: al recargar, el fichero de un valor
borrará las filas de los demás
```

**Límite conocido**: la idempotencia sigue siendo por hash del fichero. Dos
tiendas que manden ficheros byte a byte idénticos harán que el segundo se omita
como "ya procesado"; hay que cargarlo con `--forzar`. Es una decisión explícita
(ver `_decisiones`, migración 016), no un descuido.

## Historial de documentos

Todo fichero que entra se archiva en `datos/documentos/`, direccionado por su
SHA-256: el mismo fichero subido dos veces ocupa una sola vez. Las cargas
archivan su origen solas; en el CLI se adjunta con `--documento` al crear o
con `documento adjuntar` después.

Cuánto se conserva lo declara cada proceso, en `/cargas/<nombre>.json` o en
`/catalogo/<tabla>.json`:

```json
"historial": "siempre"
"historial": {"tipo": "ficheros", "cantidad": 10}
"historial": {"tipo": "anios",    "cantidad": 3}
"historial": {"tipo": "ficheros", "cantidad": 10, "tags_exentos": ["justificante pago"]}
```

Por defecto es `"siempre"`: no declarar nada no pierde nada. Dos reglas hacen
que purgar sea seguro:

1. **Se vacían los bytes, nunca la ficha.** El documento queda como `purgado`
   con su `fecha_purga`. Se sigue sabiendo de qué fichero salió cada línea
   aunque ya no se pueda abrir; si la purga borrase el metadato, rompería la
   trazabilidad que la justifica.
2. **Se conserva si lo conserva algún proceso.** Un mismo fichero puede colgar
   de una carga con historial corto y de un ticket con `"siempre"`. La
   decisión se toma sobre la unión de todos los procesos, nunca uno a uno.

Reponer un fichero purgado (volver a cargarlo o adjuntarlo) lo devuelve a
`disponible`: el hash garantiza que el contenido es exactamente el mismo.

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
- Hito 12: stops y alarmas (`motor/validaciones.py`,
  `migraciones/012_validaciones.sql`). Una validación es un `SELECT` que, si
  devuelve filas, corta la carga (`stop`) o deja aviso (`alarma`), mostrando
  el detalle de las filas implicadas. Se declaran en la carga o, como
  invariantes de tabla, en `/catalogo/<tabla>.json`, y en ese caso rigen
  también para las escrituras del CLI (`ticket crear`, `idea editar`), donde
  un stop revierte la operación. Acciones declarativas por momento del ciclo
  de vida (`antes`, `tras_validar`, `al_fallar`) y `ejecucion_id` en las
  tablas de carga para poder deshacer o inspeccionar por proceso de carga.
- Hito 13: salidas (`motor/salidas.py`, comando `etl salida`). Una carga puede
  declarar ficheros de resultado a partir de un `SELECT` libre, en xlsx, CSV o
  parquet, con nombre compuesto por fecha (`%Y%m%d`) y datos de la ejecución
  (`{carga}`, `{ejecucion_id}`). Se generan al terminar una carga correcta, con
  los datos ya confirmados. El xlsx lo escribe la extensión `excel` de DuckDB
  (83.440 filas en 0,6 s), con respaldo en openpyxl si no está disponible.
- Hito 14: borrador de esquema (`motor/esquema.py`, comando `etl esquema`) a
  partir del perfil del fichero: `CREATE TABLE` y entrada de catálogo con las
  columnas dudosas marcadas (identificadores, ceros a la izquierda, fechas
  disfrazadas de número). `--limite N` en `definir` y `esquema` muestrea
  parando la lectura (2,7 s frente a 37 s en el xlsx de previsiones),
  avisando de que el tipo inferido ya no está garantizado.
- Hito 15: lectura de xlsx con la extensión `excel` de DuckDB en carga y
  perfilado (4,9 s frente a 23,4 s en el fichero de previsiones), con openpyxl
  de respaldo. Verificado comparando ambos lectores fila a fila: cero celdas
  distintas tras el mapping sobre 497.383 filas. De paso corrige que una celda
  con fecha real de Excel acabara rechazando la fila.
- Hito 16: trazabilidad de ejecuciones (`motor/ejecuciones.py`,
  `migraciones/013_trazabilidad_ejecuciones.sql`). `_ejecuciones` deja de ser
  el diario de las cargas de fichero para registrar **toda escritura del
  sistema**: gana `tipo` (`carga`/`cli`) y `ejecucion_id_principal`, que en una
  creación o una carga apunta a sí misma. `id = ejecucion_id_principal` da las
  ejecuciones principales y `ejecucion_id_principal = N AND id <> N` el
  historial de cambios de N. `ticket` e `idea` guardan en `ejecucion_id` solo
  la ejecución de creación, así que editar no toca la fila: crear, editar y
  borrar quedan encadenados bajo la misma principal. Se descarta llevar el
  hash del fichero a las tablas de ingesta por redundante: se recupera por
  join desde `ejecucion_id`. `fichero` y `hash_fichero` pasan a nullable
  porque una operación de CLI no tiene fichero; para alterarlos hay que
  recrear `_rechazos`, cuya FK impedía tocar la tabla referenciada.
- Hito 17: almacén de documentos (`motor/documentos.py`,
  `migraciones/014_documentos.sql`). Los ficheros se archivan en
  `datos/documentos/<hash[:2]>/<hash><ext>` direccionados por su SHA-256:
  `_documentos` guarda los atributos del contenido (nombre, tamaño, mime,
  `estado`) y `_ejecucion_documento` el vínculo con la ejecución, donde vive
  el `tag` — texto libre (`crear`, `justificante pago`, `doc AB545`) porque
  califica el uso y no el contenido. Como toda escritura deja ejecución y las
  modificaciones se encadenan a la de creación (hito 16), `documentos.de_fila`
  devuelve de una vez todos los documentos de la vida de un registro, tanto el
  que lo originó como los que se añadan después. Las cargas archivan su
  fichero de origen automáticamente con tag `crear`. Deduplicación verificada:
  dos ejecuciones del mismo CSV dejan un documento y dos vínculos. El hash se
  calcula por bloques de 1 MB y es el mismo que identifica la ejecución (una
  sola implementación), verificado sobre el xlsx de 45 MB. `datos/documentos/`
  entra en `.gitignore` desde el primer día: son extractos y justificantes de
  clientes.
- Hito 18: historial declarativo y purga (`motor/historial.py`,
  `migraciones/015_historial_documentos.sql`). Cada proceso declara cuánto
  conserva con un bloque `historial` en `/cargas/<nombre>.json` o
  `/catalogo/<tabla>.json`: `"siempre"` (por defecto),
  `{"tipo":"ficheros","cantidad":N}`, `{"tipo":"anios","cantidad":N}`, con
  `tags_exentos` opcional. `documento purgar` va en seco salvo `--aplicar`,
  libera los bytes y marca `estado = 'purgado'` **sin borrar nunca la ficha**,
  así que se sigue sabiendo de qué fichero salió cada dato. Un documento se
  conserva si lo conserva algún proceso: la decisión se toma sobre la unión,
  nunca proceso a proceso. Verificado que un documento fuera de la retención
  de su carga sobrevive mientras siga vinculado a un ticket, que al aplicar la
  purga la ficha queda con `fecha_purga` y los bytes desaparecen, y que volver
  a cargar el fichero lo repone a `disponible`.
- Hito 19: CLI de documentos (`documento adjuntar|listar|purgar`) y
  `--documento` en `ticket crear` / `idea crear`, para archivar el justificante
  del que salen los datos en el mismo alta. `documento adjuntar <tabla> <id>
  <ruta> --tag` abre una ejecución encadenada a la de creación, de modo que un
  justificante de pago que llega semanas después aparece junto a la foto del
  alta en `documento listar --tabla ticket --id <id>`. Adjuntar sobre un
  registro anterior a la migración 013 falla con un mensaje explícito en vez de
  inventarle una cadena.
- Hito 20: parámetros de carga (`motor/parametros.py`,
  `migraciones/016_parametros_carga.sql`). Una carga declara `parametros`:
  valores que no vienen dentro del fichero y se piden al ejecutarla — la tienda
  de la que llega este export de pedidos, un comentario libre. Con `valores_de`
  la lista es cerrada y se resuelve contra una tabla por nombre, listando los
  disponibles si falla; sin él, texto libre. Llegan a las filas por el mapping,
  con la operación nueva `parametro`, para que se comporten igual que cualquier
  otra columna. Falta un obligatorio y la carga corta antes de leer el fichero.
  Los valores contestados quedan en `_ejecuciones.parametros`, guardando de una
  lista cerrada tanto lo tecleado como el id resuelto, para que renombrar la
  tienda no deje la ejecución ilegible. `etl validar` avisa si un parámetro
  obligatorio no entra en `campos_singularidad`, que es el error caro: recargar
  el fichero de una tienda borraría las filas de las demás. Verificado con dos
  tiendas sobre el mismo fichero: recargar una sustituye solo sus filas
  (`sustituidas=3`) y deja intactas las de la otra. La idempotencia sigue
  siendo por hash, decisión explícita: dos ficheros idénticos de tiendas
  distintas exigen `--forzar` en el segundo.
- Hito 21: batería de pruebas (`/pruebas`, `python -m unittest discover -s
  pruebas -t .`). 69 pruebas sobre `unittest` de la librería estándar, sin
  dependencias nuevas, cubriendo instalación desde cero, motor ETL,
  singularidad, hall, stops y alarmas, salidas, CRUD, trazabilidad, documentos,
  historial/purga y parámetros. Cada una corre contra un almacén temporal
  recién migrado con su propio catálogo, cargas y almacén de documentos, así
  que la suite no puede tocar los datos reales. Comprueba además dos
  invariantes del repo: que el esquema de una instalación nueva coincide con el
  del almacén migrado incrementalmente, y que toda migración deja su entrada en
  `_decisiones` (salvo la de arranque, que es quien crea esa tabla).
- Hito 22: descripción obligatoria de cada carga (`descripcion` en
  `/cargas/*.json`, `migraciones/017_descripcion_cargas.sql`) enfocada al para
  qué y no a lo descriptivo: para qué se cargan los datos, de dónde sale el
  fichero, qué es una fila, qué sustituye una versión corregida y qué haría
  desconfiar. El skill `definir-carga` la redacta desde el perfilado más una
  tanda de preguntas directas y la sitúa **antes** de elegir
  `campos_singularidad`, porque la pregunta "qué sustituye un fichero
  corregido" es esa clave contada en palabras: si prosa y clave no coinciden,
  la contradicción se ve sin ejecutar nada. Se muestra en `etl validar` y en
  una sección nueva de `db diagrama`. Los errores de esquema ahora nombran el
  campo que falla (`estructura inválida en descripcion: ...`), que antes había
  que adivinar. De paso se corrigió que `db diagrama` abortaba con
  `UnicodeEncodeError` en consola cp1252 por una flecha U+2192, con una prueba
  que vigila los `print` del motor.
- Hito 23: separación núcleo / capa propia (`motor/rutas.py`,
  `migraciones/018_capa_propia.sql`). El framework vive en `migraciones/`,
  `catalogo/` y `cargas/`; lo que cada uno carga con él, en `propio/` con la
  misma estructura, fuera del control de versiones del núcleo. `db migrar`
  aplica el núcleo primero y las propias después —una migración propia puede
  apoyarse en tablas del framework, nunca al revés—, y si coincide el nombre
  gana la capa propia, lo que permite adaptar una ficha sin bifurcar el repo.
  La separación es por directorio y no por disciplina: los ficheros de una
  carga real no pueden colarse en un commit del framework porque no están en su
  árbol. Al mover la primera carga salió un acoplamiento que no se veía:
  `012_validaciones.sql`, del núcleo, hacía `ALTER TABLE` sobre una tabla de
  negocio, así que la instalación limpia de un tercero se habría roto; ahora
  una prueba falla si el núcleo vuelve a referenciar una tabla propia.
