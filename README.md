# Tolva

*English: [README.en.md](README.en.md) — short version. This page is the full
documentation, in Spanish.*

> *Tolva*: la boca por la que entra el material en una máquina.

**Por donde entran tus datos, y con la que se habla.** Le cuentas qué te llega;
te pregunta lo que no puede adivinar —esa columna de mes que pone `03`, ¿es
texto o número?—, y solo escribe cuando dices que sí.

Casi todas las herramientas de datos con IA se han puesto en el análisis, que
es el tramo que ya tenía herramientas. Esto va del principio: **la ingesta**.

Y con una regla que no se negocia: **la IA está en el diseño, no en la
ejecución**. De la conversación sale un fichero de configuración; a partir de
ahí es SQL corriendo solo, igual cada mes. **Ninguna carga la toca un modelo.**

Local, monousuario y autónomo, sobre DuckDB. Sin servidor, sin autenticación,
sin nube. Todo vive en un fichero en tu disco.

> **La excepción es la primera conversación.** Para proponerte un esquema hay
> que mirar tu fichero: al asistente le llegan los nombres de las columnas y
> **una muestra de valores reales** de cada una. Eso sale de tu equipo, a donde
> corra el modelo. De ahí en adelante, nunca más. Si tu fichero lleva datos que
> no pueden salir, mira [Qué ve el asistente](#qué-ve-el-asistente) **antes** de
> la primera carga.

## Qué problema resuelve

Casi todo el mundo tiene información de trabajo que no cabe en una herramienta
y no merece una: el Excel de gastos, el extracto que descargas cada mes, la
lista de cosas pendientes, el export del ERP que abres y cruzas a mano. Montar
una base de datos para eso cuesta más de lo que ahorra, así que no se monta, y
al final hay tres nombres para la misma cosa repartidos en cinco ficheros.

Tolva asume que el trabajo de modelar es conversación, y que lo caro no es
escribir el `CREATE TABLE` sino decidir qué va dentro. Los comandos existen
—están documentados más abajo— pero son el suelo, no la interfaz.

## Cómo se ve

```
> quiero llevar las tareas que tengo pendientes

Ya existe `idea`, y sus tres filas son tareas: "Publicar el proyecto en
GitHub", "Pensar un nombre". El análisis dice que `estado` coincide con
`idea.estado`, y que `cliente` solapa 1.0 con la tabla `cliente`, así que
irá como clave ajena y no como texto.

¿Son lo mismo, o una idea es lo que te gustaría hacer y una tarea lo que
tienes que hacer?

> lo segundo. y quiero apuntar las horas que me llevó al cerrarla

Propuesta: tabla `tarea` con fecha límite, fecha de cierre y horas reales.
Dos decisiones que necesito que confirmes...
```

De ahí sale una migración, una ficha de catálogo y una entrada en
`_decisiones` explicando por qué, para que dentro de seis meses se sepa.

## Qué hace por dentro

- **Nada se crea a ciegas.** Antes de una tabla nueva se comprueba
  solapamiento contra el catálogo y contra los datos reales, con evidencia
  medida y no con criterio.
- **Al cargar, lo importante es qué sustituye cada fichero.** Se declara una
  vez (`campos_singularidad`) y volver a subir el informe corregido reemplaza
  lo que toca en vez de duplicarlo.
- **Reglas de negocio que cortan.** Un `SELECT` que, si devuelve filas, aborta
  la carga o solo avisa. Los mismos invariantes rigen para el CRUD.
- **Todo deja rastro y el fichero de origen se guarda.** Desde una fila se
  llega al fichero que la trajo, y a los justificantes que se colgaron después.
- **Tres capas separadas por directorio**: el framework, un dominio de ejemplo
  para probar, y lo tuyo — que no sale del repositorio.

## Pruébalo en dos minutos

**No hace falta saber Python.** Abre una carpeta vacía con
[Claude Code](https://claude.com/claude-code) y pídeselo con tus palabras:

```
> instálame esto y enséñame el ejemplo: https://github.com/Modulooper/tolva.git
```

Se ocupa de lo mecánico —entorno, dependencias, migraciones— y te pregunta lo
único que no puede decidir por ti: dónde deben vivir tus datos y si quieres
respaldo. Acaba ejecutando una carga real de principio a fin —fichero,
transformación, una regla que salta a propósito y una salida en xlsx— sobre un
dominio de ejemplo: una librería inventada, con datos dummy.

Tu instalación arranca vacía: el framework **no crea ninguna tabla de
negocio**.

A partir de ahí ya no hay instalación, hay conversación: cuéntale qué quieres
llevar. Las skills que guían esa parte (`definir-carga`, `crear-proceso`)
vienen en el repositorio y son el diferencial del proyecto: perfilan el
fichero, comprueban solapamiento contra el catálogo semántico y proponen
esquema antes de tocar nada.

### O instálalo desde la consola

Requisitos: Python 3.11+ y Git.

```bash
git clone https://github.com/Modulooper/tolva.git
cd tolva
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt

python -m motor.cli db migrar --con-ejemplos
python -m motor.cli registro listar demo_venta
python -m motor.cli etl ejecutar demo_ventas
```

Mismo resultado, y la instalación completa —con las cuatro rutas y por qué
importan— está en [Instalación](#instalación).

## Dudas, fallos y contribuciones

Abre un **issue**. Se responde ahí y no por correo a propósito: así la
respuesta queda pública y la encuentra el siguiente con la misma duda.

Antes de un pull request, que pase la batería:

```bash
python -m unittest discover -s pruebas -t .
```

**Seguridad**: si encuentras una vulnerabilidad, no abras un issue público.
Escribe a modulooper@gmail.com y se coordina el arreglo antes de publicarlo.

## Licencia

[MIT](LICENSE).

## Instalación

Requisitos: Python 3.11+ y Git.

```bash
git clone https://github.com/Modulooper/tolva.git
cd tolva

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

Una instalación nueva no crea ninguna tabla de negocio: el núcleo es framework
y solo monta sus tablas de sistema. Para ver el sistema funcionando con datos,
instala el dominio de ejemplo:

```bash
python -m motor.cli db migrar --con-ejemplos
python -m motor.cli registro listar demo_venta
```

Debería devolver las ventas dummy de la librería de ejemplo, sin errores.

### Batería de pruebas

```bash
python -m unittest discover -s pruebas -t .
```

119 pruebas que cubren instalación, motor ETL, singularidad, hall, stops y
alarmas, salidas, CRUD genérico, trazabilidad, documentos, historial/purga,
parámetros, diagrama del modelo, descripciones de carga y separación
núcleo/ejemplos/capa propia. Corren contra el dominio de ejemplo, no contra
ningún proceso real. No hacen falta dependencias
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

### Qué asistente hace falta

Para que la instalación conversacional de arriba (clonar, crear venv, instalar
dependencias, migrar, y luego usar los skills de `.claude/skills/`) la haga la
IA sola, hace falta **Claude Code** (la CLI), no Claude Desktop/claude.ai:
Code tiene acceso directo a terminal y sistema de ficheros locales, que es lo
que requieren los pasos de arriba y lo que activa `.claude/skills/`
automáticamente al abrir el repo. Claude Desktop, sin un MCP de terminal/filesystem conectado, no puede
ejecutar `git clone`, `pip install` ni `python -m motor.cli` — como mucho
podría leer este README y devolver los pasos en texto para que los ejecutes
tú. Con un MCP de ese tipo configurado sí podría, en teoría, pero no es la
vía pensada ni probada para este proyecto.

Con otro asistente de código con terminal (Codex CLI, Copilot en modo agente,
Cursor) el framework funciona igual —es Python y DuckDB, sin dependencias de
LLM—, pero esos tres automatismos no los hay: cargar las instrucciones,
invocar los skills en el momento justo y respaldar al cerrar. [AGENTS.md](AGENTS.md)
es el adaptador que los suple, y no duplica nada: apunta a este README, a
[CLAUDE.md](CLAUDE.md) y a los dos skills.

## Estructura

```
/motor/            código Python del ETL y la CLI
/migraciones/       001_nucleo.sql (solo tablas de sistema), 003_..., en orden
/cargas/            una definición JSON por tipo de carga
/catalogo/          catálogo semántico del modelo de datos
/ejemplos/          dominio de ejemplo (una librería) con datos dummy: mismas
                    carpetas dentro, solo se instala con `--con-ejemplos`
/entrada/           carpetas vigiladas donde se depositan los ficheros a cargar (no versionado)
/export/            vistas de consumo volcadas a parquet/csv
/datos/almacen.duckdb   estado (no versionado)
/datos/documentos/  ficheros archivados por su hash: orígenes de carga y
                    justificantes (no versionado — lleva datos de clientes)
/propio/            tus cargas, catálogo y migraciones (no versionado aquí:
                    es tu repositorio git aparte — ver "Núcleo y capa propia")
```

## Dónde viven los datos

Cuatro ubicaciones, y **no son la misma cosa** por mucho que por defecto
cuelguen del repositorio:

| Ajuste | Qué guarda | Por defecto | Naturaleza |
|---|---|---|---|
| `datos` | `almacen.duckdb` | `datos/` | estado, irremplazable |
| `documentos` | ficheros de origen y justificantes | `<datos>/documentos` | estado, irremplazable |
| `export` | vistas y salidas (parquet, csv, xlsx) | `export/` | resultado, regenerable |
| `respaldo` | copias fechadas del estado | **ninguno** (opt-in) | seguro, ver [Respaldos](#respaldos) |

```bash
python -m motor.cli db rutas                        # dónde está cada cosa y por qué
python -m motor.cli db init --datos C:/datos/tolva
```

`respaldo` es el único sin valor por defecto, y a propósito: los otros tres
resuelven a una carpeta del repositorio, que es un sitio razonable para
empezar; para un respaldo no lo es, porque dejarlo junto al original no
protege de nada y una ruta que el framework se invente va a estar mal. Sin
configurar, `db respaldar` no hace nada y dice cómo configurarlo.

`db init` **no mueve nada**: solo declara dónde debe mirar el sistema. Si ya
tenías datos, muévelos tú — y mueve, no copies: dos almacenes divergiendo no
avisan de nada.

Precedencia:

```
variable de entorno  >  config.local.json  >  valor por defecto
```

El fichero (que escribe `db init`, y está en `.gitignore` porque es de tu
máquina) fija la instalación. Las variables `TOLVA_DATOS`,
`TOLVA_DOCUMENTOS`, `TOLVA_EXPORT` y `TOLVA_RESPALDO` quedan para lo puntual:
lanzar una carga contra otro almacén, o enrutar por usuario.

`db init` solo toca los ajustes que le indiques: fijar uno no desconfigura los
demás. Para devolver uno a su valor por defecto, indícalo vacío
(`--export ""`).

El orden no es arbitrario. Si solo hubiera variable de entorno, se pone en una
terminal, la siguiente sesión no la ve, se crea un almacén vacío **sin
quejarse** y parece que se han perdido los datos. El fichero no se olvida.

### Por qué son cuatro ajustes y no uno

Porque sus requisitos son opuestos.

**El almacén no debe vivir en una carpeta sincronizada.** Un fichero de base de
datos no es un documento, y OneDrive, SharePoint, Dropbox o Drive asumen que
pueden copiarlo cuando les parezca:

- Resuben el fichero entero en cada cambio. Un almacén de 200 MB se vuelve a
  subir porque has editado una fila.
- Pueden copiarlo **mientras se escribe**, y lo que sube es una foto
  incoherente que solo se descubre el día que la restauras.
- Si dos máquinas lo tocan no fusionan: dejan una *copia en conflicto* y a
  partir de ahí hay dos verdades divergentes sin que nadie avise.
- Mantienen handles abiertos, que es lo que convierte un borrado normal en un
  «acceso denegado».

**Las exportaciones, en cambio, a menudo quieres que sí estén ahí**: para eso
se generan, para abrirlas desde Excel o enlazarlas en Power BI, puede que desde
otra máquina. Son ficheros cerrados y regenerables.

Por eso `db migrar` y `db rutas` avisan si el almacén o los documentos caen en
una ruta con pinta de sincronizada, y **no dicen nada de las exportaciones**.
Es heurística sobre nombres de carpeta: avisa, nunca impide.

**El respaldo es el tercer requisito, y su aviso es el inverso**: quiere estar
sincronizado *y* lejos del almacén. La regla es que vale si **sale de la
máquina** (carpeta sincronizada) **o al menos sale del disco** (otra unidad);
con una de las dos basta. Así que una ruta dentro de OneDrive, que en `datos`
dispara un OJO, aquí es justo la respuesta buena. Lo que avisa es el caso
contrario: un respaldo en el mismo disco y sin sincronizar muere con el
original.

No se exige salir de la máquina porque no todo el mundo tiene sincronización,
y un disco aparte ya cubre el fallo más probable, que es que muera el disco.

## Qué ve el asistente

El reparto no es obvio, así que conviene tenerlo claro antes de la primera
carga: **el diseño ve una muestra, la ejecución no ve nada.**

**Sale de tu equipo**, una vez, al definir la carga o el proceso:

- el nombre del fichero y el de sus columnas,
- por columna: tipo aparente, nulos, cardinalidad y **una muestra de valores
  reales** (`etl definir`),
- si haces `dry-run`, unas cuantas filas válidas y las rechazadas con su
  motivo,
- lo que ya haya en tu catálogo, para comprobar solapamiento.

**No sale nunca:** la carga. `etl ejecutar` es Python y SQL contra
`datos/almacen.duckdb`, corre con el asistente cerrado, y es lo que vas a
repetir todos los meses durante años.

### Si el fichero tiene datos que no pueden salir

**Anonimiza, no inventes.** Coge el fichero real y sustituye los valores
sensibles **conservando su forma**: mismo largo, mismo formato, mismos ceros a
la izquierda, misma proporción de vacíos. Un NIF falso con forma de NIF perfila
igual que el bueno.

Lo que no funciona es fabricar un fichero de muestra desde cero. El perfilado es
precisamente lo que decide si `03` es texto o número y si las fechas van
día/mes; sobre un fichero inventado acertará, pero sobre el inventado. El
esquema que salga describirá al falso. Es el mismo motivo por el que perfilar y
cargar usan [el mismo lector](#xlsx).

Y si ni una muestra puede salir: el framework **no tiene ninguna dependencia de
LLM**. `/cargas/<nombre>.json` es texto documentado más abajo, se escribe a mano
o se le dicta a un modelo local. El motor no necesita la conversación; tú sí, así
que cuenta con escribir la definición a pulso.

## Respaldos

```bash
python -m motor.cli db init --respaldo "C:/Users/tu/OneDrive/Respaldo Tolva"
python -m motor.cli db respaldar     # snapshot fechado + retención
python -m motor.cli db respaldos     # qué copias hay
```

Cada snapshot es una carpeta `AAAAMMDD-HHMMSS` con el estado en **parquet**
(vía `EXPORT DATABASE`, que incluye `schema.sql` y `load.sql`, o sea que es
autocontenido), una copia de la capa propia y un `manifiesto.json` con la
versión de DuckDB, las migraciones aplicadas y las filas por tabla.

**Parquet y no una copia del `.duckdb`.** Medido sobre un almacén real: 190,8
MB de `.duckdb` contra 8,9 MB de parquet+zstd, en 0,3 s. Pero lo que decide no
es el tamaño, es que el formato de fichero de DuckDB puede cambiar entre
versiones mayores —por eso `requirements.txt` fija `<2.0`— y un binario de 200
MB que dentro de tres años no abre no es un respaldo.

**Los documentos van fuera del snapshot**, en un espejo incremental en
`<respaldo>/documentos`. Están direccionados por su SHA-256, o sea que son
inmutables: meterlos en cada copia guardaría N veces los mismos bytes. Cada
snapshot los referencia por hash desde su `_documentos.parquet`.

**Retención abuelo-padre-hijo**: 7 diarios, 8 semanales y 12 mensuales. De
cada cubo temporal sobrevive el más reciente, y un mismo snapshot puede ocupar
las tres plazas, que es lo que hace que el esquema se estabilice en vez de
crecer. **La retención no toca nunca los documentos**: son lo único
genuinamente irrecuperable —el resto de tablas se puede volver a cargar desde
ellos—, así que purgarlos para ahorrar disco sería el error que todo esto
existe para evitar.

### Automatizarlo

El repo trae un hook `SessionEnd` en `.claude/settings.json` que lanza
`db respaldar --silencioso` al cerrar una sesión de Claude Code. Lo ejecuta el
propio harness, sin arrancar ninguna sesión de IA: no cuesta tokens. Es inocuo
mientras no configures `respaldo`, que es la razón de que ese ajuste sea
opt-in.

`--silencioso` calla **solo** el caso de «no hay respaldo configurado». Un
error de verdad se sigue viendo y sigue saliendo con código distinto de cero:
un respaldo que falla en silencio es peor que no tener respaldo, porque encima
da tranquilidad.

Si trabajas mucho fuera de Claude Code, añade encima una tarea programada del
sistema con el mismo comando. Son compatibles.

### Recuperar

Un respaldo que nadie ha restaurado nunca es una suposición. El procedimiento
de abajo está **ensayado de principio a fin** contra un respaldo real, no
deducido.

`db restaurar` hace la mitad segura —importar a un fichero nuevo y verificar
contra el manifiesto—, y **se niega a escribir sobre un almacén que ya
exista**: `IMPORT DATABASE` pisa lo que haya, y el momento de recuperar es
justo cuando menos margen hay para un error irreversible. El paso destructivo
(sustituir el almacén vivo) se queda a mano, igual que `db init` no mueve nada
y la purga de documentos no se ejecuta sola.

**Lo que necesitas para recuperar desde cero**: este repositorio (es código,
va por git), Python con `requirements.txt`, y la carpeta de respaldos.

```bash
# 1. El framework y su entorno
git clone https://github.com/Modulooper/tolva.git && cd tolva
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt

# 2. El estado, a un fichero NUEVO. Sin argumento coge el snapshot más reciente.
python -m motor.cli db respaldos                       # ver qué hay
python -m motor.cli db restaurar --a C:/Tolva/almacen.duckdb
```

`db restaurar` importa, cuenta las filas de cada tabla y las compara con el
manifiesto. Si cuadran lo dice; si no, enumera cada descuadre y sale con
código distinto de cero. También recupera las **vistas de consumo**, que van
en el `schema.sql` del export.

```bash
# 3. Lo que no está en el almacén, y va a mano
#    - <respaldo>/documentos     -> la carpeta que diga `db rutas`
#    - <snapshot>/propio         -> propio/ del repositorio
#    - <snapshot>/config.local.json es INFORMATIVO: dice dónde vivía cada cosa
#      en la máquina original. En otra máquina esas rutas no existen.

# 4. Comprobar que el sistema funciona contra lo recuperado, no solo que los
#    ficheros están:
python -m motor.cli db migrar          # debe decir "No hay migraciones pendientes"
python -m motor.cli registro listar <una entidad>
python -m motor.cli documento listar   # deben salir 'disponible'
```

El paso 4 es el que convierte «he copiado unos ficheros» en «he recuperado el
sistema». Que `db migrar` no encuentre nada pendiente demuestra que
`_migraciones` viajó entera y que el framework reconoce el almacén como suyo.

Y como los documentos se guardan bajo el nombre de su SHA-256, la integridad
se puede comprobar sin fiarse de nadie: recalcula el hash de cada fichero y
compáralo con su propio nombre.

## Núcleo y capa propia

El framework y lo que tú cargas con él no viven en el mismo sitio:

| | Dónde | Se versiona en | Se instala |
|---|---|---|---|
| **Núcleo** | `migraciones/`, `catalogo/`, `cargas/` | este repositorio | siempre |
| **Ejemplos** | `ejemplos/…` | este repositorio | con `--con-ejemplos` |
| **Capa propia** | `propio/…` | el tuyo, privado | siempre |

`motor/rutas.py` resuelve las tres capas de forma transparente: `db migrar`
aplica las migraciones del núcleo **y después** las tuyas, y el catálogo y las
cargas se suman. Trabajas siempre sobre este repositorio, con lo tuyo colgando
de `propio/`; no mantienes dos copias del framework.

**El núcleo no crea ninguna tabla de negocio.** Una instalación limpia tiene
las de sistema (`_ejecuciones`, `_rechazos`, `_decisiones`, `_documentos`…) y
nada más: ni tickets, ni ideas, ni siquiera `persona`, `cliente` y `proyecto`,
que estuvieron aquí hasta el hito 26. Eran un modelo de consultoría —quién
hace el trabajo, para quién, en el marco de qué— y venía de serie con el
framework: quien quisiera usar esto para su bodega o su gimnasio heredaba un
vocabulario que no es el suyo. Tolva opina sobre **cómo** se declaran, se
cargan y se rastrean las entidades, no sobre **cuáles** son. Hay una prueba que
falla si alguna vez vuelve a colarse una tabla de negocio en el núcleo.

Las dimensiones compartidas siguen existiendo, pero son tuyas y viven en
`propio/`: en esta instalación son `persona`, `cliente` y `proyecto`, y la
skill `crear-proceso` mira `propio/catalogo/` para saber a qué debería
engancharse una tabla nueva.

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

## El dominio de ejemplo

`ejemplos/` es una librería inventada —`demo_cliente`, `demo_libro`,
`demo_venta`— con datos dummy sembrados en su propia migración. Existe para dos
cosas: que la batería de pruebas tenga sujeto sin depender de ningún proceso
real de nadie, y que quien clone el repositorio pueda probar el framework
entero sin definir nada.

```bash
python -m motor.cli db migrar --con-ejemplos
python -m motor.cli registro listar demo_venta
python -m motor.cli etl ejecutar demo_ventas
```

La carga `demo_ventas` ejercita de una vez lo que cuesta más de explicar:
tabla hall con `transformacion_sql` que resuelve los nombres del fichero
contra las dimensiones, `campos_singularidad` para que recargar el mes lo
sustituya en vez de duplicarlo, un `stop`, una `alarma` que salta a propósito
con un comprador que no está de alta, y una salida xlsx.

Tres decisiones que conviene entender antes de tocarlo:

- **Se instalan solo si se piden.** Datos dummy que nadie pidió son datos
  dummy que alguien acabará confundiendo con reales.
- **Dimensiones propias, nunca las del núcleo.** Los ejemplos no insertan en
  `cliente` ni en `persona`: una vez mezclados los dummies con clientes de
  verdad, no hay quien los separe. Y el dominio es deliberadamente lejano —una
  librería, no una consultoría— para que un dato inventado no se parezca a uno
  real.
- **Son invisibles por defecto.** Las fichas llevan `"ejemplo": true`, y quien
  recorre el catálogo las ignora salvo que las pida: `proceso analizar` no las
  propone como clave foránea, `etl definir` no sugiere sus campos y
  `db diagrama` no las dibuja (`--con-ejemplos` sí). Sin esto, un dominio dummy
  metido en el catálogo produce respuestas falsas sobre datos reales.

## CRUD genérico: `registro`

Un proceso de negocio (algo que tecleas: gastos, ideas, tareas) necesita altas,
bajas y modificaciones. Eso fueron durante un tiempo `motor/tickets.py` y
`motor/ideas.py`: el mismo código dos veces con los nombres cambiados. El
problema no era la repetición, era que **obligaba a que todo proceso fuese
público**, porque para dar de alta uno nuevo había que tocar `motor/` y
`motor/cli.py`, que son núcleo, y entonces venía de serie en la instalación de
cualquier tercero. Los dos módulos ya no existen.

`motor/registros.py` lo resuelve: la entidad no está en el código, se lee de su
ficha de catálogo — que puede vivir igual de bien en `catalogo/` que en
`propio/catalogo/`. Un proceso privado es una migración y una ficha, las dos en
`propio/`, y ya funciona.

```bash
python -m motor.cli registro campos demo_venta
python -m motor.cli registro crear demo_venta --set demo_cliente="Ateneo Mercantil" --set demo_libro="El jardín de arena" --set unidades=2 --set importe=39.00
python -m motor.cli registro listar demo_venta --filtro canal=web --filtro "fecha>=2026-05-01"
python -m motor.cli registro editar demo_venta <id> --set canal=feria --set unidades=3
python -m motor.cli registro borrar demo_venta <id>
```

Qué saca de la ficha:

- **`campos`** — qué se puede escribir. Los `sistema` (`id`, `created_at`,
  `updated_at`, `ejecucion_id`) se rechazan si los pasas a mano, y no salen en
  el listado.
- **`tipo`** — a qué convertir lo que llega del CLI, que siempre es texto.
  `importe=39,00` y `importe=39.00` valen los dos; un valor vacío deja el
  campo a nulo.
- **`relaciones`** — qué campos son referencias. `--set demo_cliente="Ateneo
  Mercantil"` resuelve contra la tabla destino por su `nombre` (sin distinguir
  mayúsculas) y el id en crudo también vale. En el listado se muestra el nombre, no el id, y se
  puede filtrar por él. Si la entidad destino no se identifica por `nombre`,
  su ficha lo declara con **`etiqueta`** (`demo_libro` usa `titulo`): asumir
  `nombre` siempre obligaría a escribir uuids justo en lo que peor se recuerda.
- **`validacion.lista_valores`** — falla con un mensaje legible antes de que
  salte el `CHECK`.

Lo que **no** comprueba, a propósito, es la obligatoriedad: una columna puede
ser `NOT NULL` y tener `DEFAULT` (`demo_venta.fecha`, `demo_venta.canal`), y desde la
ficha eso no se distingue de una que hay que rellenar sí o sí. La autoridad es
la base. Duplicar la regla solo crearía dos verdades que se separan con el
tiempo.

La trazabilidad es la misma que la del CRUD escrito a mano: el alta sella su
`ejecucion_id` en la fila, las ediciones se encadenan a esa principal sin
tocarlo, los invariantes del catálogo se comprueban en cada escritura y
`--documento` archiva el fichero del que salen los datos.

`ticket` e `idea` tuvieron subcomandos propios (`ticket crear`, `idea listar`)
y se retiraron al sacarlas del núcleo: ahora son entidades de la capa propia y
se operan con `registro`, como cualquier otra.

## Uso

```bash
pip install -r requirements.txt

python -m motor.cli db migrar [--con-ejemplos]
python -m motor.cli db consultar "select * from cliente"
python -m motor.cli db uso [--minimo 3]

python -m motor.cli etl definir <fichero-muestra> [--formato --delimitador --encoding --hoja --fila-cabecera] [--limite N] [--json]
python -m motor.cli etl esquema <fichero-muestra> --tabla <nombre> [--limite N] [--json]
python -m motor.cli etl validar <carga>
python -m motor.cli etl dry-run <carga>
python -m motor.cli etl ejecutar <carga> [--forzar] [--parametro nombre=valor ...]
python -m motor.cli etl estado

python -m motor.cli registro campos <entidad>
python -m motor.cli registro crear <entidad> --set campo=valor [--set ...] [--documento <ruta>]
python -m motor.cli registro listar <entidad> [--filtro campo=valor ...]
python -m motor.cli registro editar <entidad> <id> --set campo=valor [--set ...]
python -m motor.cli registro borrar <entidad> <id>
```

`registro` es el **CRUD genérico** y la única forma de dar altas por CLI:
sirve para cualquier entidad declarada en el catálogo, incluidas `cliente` y
`persona`, sin escribir una línea en el framework. Ver
[CRUD genérico](#crud-genérico-registro). `registro crear` acepta
`--documento <ruta>` para archivar en el mismo alta el justificante del que
salen los datos.

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
    "nombre": "ventas_por_genero",
    "fichero": "%Y%m%d_demo_ventas_por_genero.xlsx",
    "sql": "SELECT l.genero, sum(v.unidades) AS unidades, round(sum(v.importe), 2) AS importe FROM demo_venta v JOIN demo_libro l ON l.id = v.demo_libro_id GROUP BY l.genero ORDER BY importe DESC",
    "carpeta": "export"
  }
]
```

Ese ejemplo no es inventado: es la salida que declara
[`ejemplos/cargas/demo_ventas.json`](ejemplos/cargas/demo_ventas.json), así que
se puede ejecutar tras `db migrar --con-ejemplos`.

- **Formato** por extensión: `.xlsx`, `.csv` o `.parquet`. Siempre con fila de
  cabecera.
- **Nombre**: admite marcas de fecha de strftime (`%Y%m%d` → `20260805`,
  `%Y%m` → `202608`) y campos entre llaves de la ejecución: `{carga}` y
  `{ejecucion_id}`. Ej.: `"%Y%m%d_demo_detalle_{ejecucion_id}.csv"` →
  `20260805_demo_detalle_11.csv`.
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
  {"momento": "antes",         "sql": "..."},
  {"momento": "tras_validar",  "sql": "..."},
  {"momento": "tras_promover", "sql": "..."},
  {"momento": "al_fallar",     "sql": "DELETE FROM hall_previsiones"}
]
```

- **`antes`**: antes de materializar los datos entrantes.
- **`tras_validar`**: superados todos los stops, **antes** de promover.
- **`tras_promover`**: con el destino ya escrito. Es el único momento desde el
  que se ve el resultado de la carga, y el único donde existen `$promovidas`
  y `$borradas`.
- **`al_fallar`**: cuando un stop ha abortado la carga.

Todo corre dentro de la **misma transacción** que la promoción: si una acción
revienta, se revierte también lo que se acababa de escribir. O cuadra todo o
no cuadra nada.

Por defecto, un stop **no** limpia nada: la hall conserva los datos del fichero
rechazado y la ejecución queda registrada, para poder investigar con
`db consultar`. Si se quiere limpiar, se declara explícitamente con
`al_fallar`.

**La diferencia entre `tras_validar` y `tras_promover` importa más de lo que
parece.** En `tras_validar` tienes la hall (solo lo que trae este fichero) y
el destino **como estaba antes**. Si quieres alimentar una segunda tabla con
una singularidad distinta de la del destino —un histórico que acumula, un
agregado por sucursal— desde `tras_validar` tendrías que reproducir a mano la
regla de promoción para saber cómo va a quedar, y entonces
`campos_singularidad` estaría declarada en dos sitios: en el JSON y en tu SQL,
donde nadie la valida. Desde `tras_promover` lees el resultado y ya está.

Esa segunda tabla la mantienes tú, con tu propio `DELETE` + `INSERT`. Es más
dominio a cambio de más responsabilidad, y conviene saber qué se deja fuera:
el motor no le pondrá `ejecucion_id` a esas filas salvo que lo escribas
(`$ejecucion_id` está disponible, ver "Variables en el SQL"), y sin esa
columna no se le pueden adjuntar documentos ni encadenar ediciones.

#### Filtra por la ejecución, no por el dato

La forma natural de escribir esa acción es la equivocada:

```json
{"momento": "tras_promover",
 "sql": "INSERT INTO pedido_historico SELECT * FROM pedido WHERE mes = $p_mes"}
```

**El destino acumula todas las sucursales.** Al cargar Madrid de marzo, ese
`WHERE` se lleva también las filas de Bilbao de marzo que ya estaban, y el
histórico las duplica en cada carga. Un mes después nadie sabe por qué los
totales no cuadran.

Lo correcto es filtrar por la ejecución, que selecciona exacta y únicamente
lo que **esta** carga acaba de escribir:

```json
{"momento": "tras_promover",
 "sql": "INSERT INTO pedido_historico SELECT * FROM pedido WHERE ejecucion_id = $ejecucion_id"}
```

Dos avisos sobre eso:

- No añadas `$ejecucion_id` al `SELECT *` si la tabla destino ya tiene esa
  columna: el `*` la incluye y la duplicarías.
- **En una carga con hall, `ejecucion_id` no llega solo.** La hall tiene que
  declarar la columna y `transformacion_sql` tiene que arrastrarla; si no,
  queda a nulo en el destino y el filtro no casa con nada — la acción no
  falla, escribe cero filas.

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

## Lectura de ficheros: CSV y xlsx

Una carga declara su `formato`, que solo puede ser `"csv"` o `"excel"`. **CSV
es el caso normal**; xlsx es el que necesita cuidados, y por eso ocupa más
sitio aquí abajo. Que se explique más no quiere decir que sea el camino
principal: la carga de ejemplo del repo es CSV, y también lo es buena parte de
la batería de pruebas.

### CSV

```json
"formato": "csv",
"delimitador": ";",
"encoding": "utf-8",
"fila_cabecera": 1
```

- **`delimitador` es obligatorio** con `formato: "csv"`, y `etl validar` lo
  rechaza si falta. No se adivina a propósito: media Europa exporta con `;` y
  la otra media con `,`, y acertar por defecto el 50% de las veces significa
  partir mal las filas el otro 50% **sin error**, que es peor que no cargar.
- **`encoding`** por defecto es `utf-8-sig`, que se traga el BOM que ponen
  Excel y muchos exportadores de banca. Para ficheros que no vengan en UTF-8,
  declara el suyo (`latin-1`, `cp1252`).
- **`fila_cabecera`** por si el fichero trae líneas de título antes de los
  nombres de columna.

Los valores se leen **como texto**, y es el mapping declarado —no el lector—
quien decide los tipos. Así un mes `"03"` sigue siendo `"03"` hasta que alguien
diga qué es, en vez de convertirse en el número 3 y perder el cero.

[`ejemplos/cargas/demo_ventas.json`](ejemplos/cargas/demo_ventas.json) es una
carga CSV completa y ejecutable: delimitador `;`, tabla hall con join contra
dimensiones, singularidad por cuatro campos, un stop, una alarma y una salida.

Para perfilar un fichero de muestra antes de declarar nada:

```bash
python -m motor.cli etl definir extracto.csv --formato csv --delimitador ";"
```

### xlsx

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
`const` · `parametro` · `celda` · `date_format`. Un tipo no registrado aquí se
rechaza en `etl validar`, no en `etl ejecutar`.

Tres producen un valor sin leer ninguna columna: `const` lo lleva escrito en
la definición, `parametro` lo pide al ejecutar la carga (ver "Parámetros") y
`celda` lo lee de una posición fija del propio fichero.

### `celda`: los datos que están en la cabecera del Excel

El caso habitual: un informe con la sucursal en `B5`, el mes en `B6` y el año
en `B7`, y la tabla de detalle empezando en la fila 10. Esos tres datos son de
todas las filas, pero no están en ninguna columna.

```json
"fila_cabecera": 10,
"mapping": [
  {"origen": "Ref", "destino": "referencia", "operaciones": [{"tipo": "trim"}]},
  {"destino": "sucursal", "operaciones": [{"tipo": "celda", "referencia": "B5"}]},
  {"destino": "mes",      "operaciones": [{"tipo": "celda", "referencia": "B6"}]},
  {"destino": "anio",     "operaciones": [
      {"tipo": "celda", "referencia": "B7"}, {"tipo": "cast", "tipo_destino": "integer"}]}
]
```

La celda se lee **una vez** al abrir el fichero y se reparte por todas las
filas, y admite operaciones encadenadas detrás como cualquier otra columna.
Solo funciona con `formato: "excel"` —un CSV no tiene celdas con posición— y
`etl validar` lo rechaza si se declara sobre un CSV.

Esto es lo que hace que la carga siga siendo automática. La alternativa era
declarar la sucursal como parámetro y teclearla al ejecutar, lo que obliga a
abrir el Excel para saber qué escribir y deja la puerta abierta a cargar los
datos de una sucursal con el nombre de otra.

Y ojo con la decisión que va debajo: si un fichero corregido debe sustituir
solo su sucursal y su mes, esos tres campos tienen que estar en
`campos_singularidad` (ver "Cómo escriben las cargas de fichero").

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

## Variables en el SQL

Todo el SQL de una carga —`transformacion_sql`, acciones, validaciones y
salidas— admite variables con `$nombre`. Hay tres familias, y el prefijo no
separa espacios de nombres (el `$` ya evita chocar con una columna): separa
**quién garantiza el valor**.

| | Ejemplo | Quién responde |
|---|---|---|
| Sistema | `$ejecucion_id`, `$carga`, `$fichero`, `$hash_fichero`, `$promovidas`, `$borradas` | el motor |
| Parámetros | `$p_tienda` | quien lanza la carga |
| Variables | `$v_total` | quien escribió la carga |

**Se enlazan, no se interpolan.** `$v_nombre` se convierte en un marcador y el
valor viaja aparte, tipado. No es un detalle de estilo: pegando cadenas, una
sucursal llamada `O'Donnell` rompe la consulta y una fecha se serializa según
el locale. La contrapartida es que una variable solo puede ir **donde cabe un
valor**, nunca como nombre de tabla o de columna. Es deliberado.

`etl validar` comprueba que toda variable usada existe, sin ejecutar nada, así
que una errata en `$v_totl` se ve al definir la carga y no a mitad de una
acción que ya ha escrito media tabla.

### Variables de usuario

```json
"variables": [
  {"momento": "tras_promover",
   "sql": "SELECT count(*) AS lineas, sum(importe) AS total FROM pedido"}
]
```

**Cada columna del resultado es una variable**: eso define `$v_lineas` y
`$v_total` de una vez. El SQL tiene que devolver **exactamente una fila**;
cero o varias es un error duro y no un nulo silencioso, porque una variable
vacía porque un `WHERE` no casó acaba dentro de un `UPDATE` y el fallo se
descubre en los datos.

El valor queda **fijado en el momento en que se captura**. Una variable
capturada en `tras_validar` conserva lo que valía entonces aunque la tabla
cambie después.

### Por qué `$ejecucion_id` es de sistema y no se calcula

Tentación evidente: `SELECT max(id) FROM _ejecuciones`. Hoy acierta, pero
acierta **por casualidad** —porque una carga registra exactamente una
ejecución—, y no por definición. El día que eso cambie no fallará: escribirá
un número plausible y equivocado, que es el peor error de trazabilidad que
existe porque solo se nota al preguntar de dónde vino un dato, meses después.

El motor conoce el id antes de escribir nada. Por eso lo da hecho.

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

### Que Excel lea parquet: el driver ODBC de DuckDB

El parquet exportado conserva los tipos, que es justo lo que se pierde por el
camino con un CSV: una columna `mes` con valor `"03"` llega como texto y no
como el número 3. El problema es quién lo lee. **Power BI abre parquet de
forma nativa; Excel no.** Comprobado sobre esta instalación (Microsoft 365
x64, build 16.0.20403.20000):

- *Datos → Obtener datos → De un archivo* ofrece Excel, texto/CSV, XML, JSON,
  PDF y carpeta. No hay Parquet.
- Escrito a mano en el editor avanzado,
  `Parquet.Document(File.Contents("...parquet"))` responde
  `Expression.Error: The name 'Parquet.Document' wasn't recognized`, aunque el
  nombre de la función aparezca dentro de los binarios del motor.

Esto coincide con lo que documenta Microsoft: el conector Parquet lista como
productos soportados Power BI, Fabric, Power Apps y Customer Insights, y Excel
no está. Así que para Excel quedaba el CSV, con la pérdida de tipos que eso
supone.

La salida es el **driver ODBC de DuckDB**, que le da a Excel los tipos
reconocidos por un camino que sí sabe recorrer. Se instala una vez:

1. Descargar `duckdb_odbc-windows-amd64.zip` de las releases de
   [duckdb/duckdb-odbc](https://github.com/duckdb/duckdb-odbc/releases) y
   ejecutar el `odbc_install.exe` que trae.
2. Comprobar que **la versión del driver empareja con la de `duckdb` del
   venv**. El formato de fichero `.duckdb` va atado a la versión del motor y el
   driver lleva el suyo embebido: si actualizas uno sin el otro, deja de abrir.
   Aquí van la `v1.5.5.0` del driver contra `duckdb 1.5.5`.

A partir de ahí hay dos sitios a los que apuntarlo, y **solo uno es bueno**.

#### La vía buena: en memoria, contra los parquet exportados

DuckDB puede abrirse **sin fichero** (`database=:memory:`) y leer el parquet
desde SQL. Así Excel recibe los parquet con sus tipos y el almacén no se toca:

```
let Origen = Odbc.Query("driver={DuckDB Driver};database=:memory:", "SELECT * FROM read_parquet('<repo>\export\movimiento_bancario_consumo.parquet')") in Origen
```

Comprobado en Excel: 40 filas, 5 columnas, con `fecha_ejecucion` y
`fecha_valor` como Fecha e `importe`/`saldo` como decimal — los tipos que el
CSV perdía. Y comprobado además **con un escritor Python bloqueando el
almacén**: la consulta carga igual, porque no abre ningún `.duckdb`.

De paso se puede consultar más de una vista de golpe, que con el conector de
parquet de Power BI habría que hacer fichero a fichero:

```sql
SELECT * FROM read_parquet('<repo>\export\*_consumo.parquet', union_by_name := true)
```

La primera vez Excel pide credenciales para el origen ODBC: es *Default or
Custom* → *Conectar*, sin usuario ni contraseña. DuckDB en local no usa
ninguna.

#### La vía mala: apuntar Power Query al almacén vivo

Parece lo natural y es justo lo que no hay que hacer: **Power Query abre el
`.duckdb` en escritura, y no hay forma de impedírselo.**

El driver sí respeta `access_mode=read_only` cuando lo usa un cliente ODBC
normal — probado con `System.Data.Odbc`, deniega el `CREATE TABLE` y convive
con otros lectores. Pero Power Query no lo hereda. Con un lector en solo
lectura abierto contra el almacén, las tres formas de pedirlo fallan con
"fichero en uso":

| cadena desde Power Query | resultado |
|---|---|
| `dsn=Tolva` (con `read_only` en el DSN) | choca |
| `dsn=Tolva;access_mode=read_only` | choca |
| `driver={DuckDB Driver};database=...;access_mode=read_only` | choca |

Si pidiera solo lectura convivirían, porque DuckDB admite varios lectores a la
vez. Que choque contra un lector significa que está pidiendo escritura. Las
consecuencias son dos, y ninguna es teórica:

- Mientras Power Query refresca, **cualquier carga de Tolva falla**.
- El proceso `Microsoft.Mashup.Container` que evalúa la consulta **sobrevive al
  cierre del editor** y se queda con el fichero cogido. Pasó durante estas
  pruebas: el almacén siguió bloqueado un rato después de cerrar Power Query.

Si aun así quieres consultar el almacén vivo desde Excel de forma puntual, un
DSN con `access_mode=read_only` sirve para clientes ODBC normales (en esta
instalación existe uno llamado `Tolva`). Detalle al crearlo: el instalador del
driver solo reconoce `database`, así que `access_mode` hay que añadirlo a mano
a la clave del DSN (`HKCU\SOFTWARE\ODBC\ODBC.INI\<nombre>`).

#### Notas sueltas

- Mejor `Odbc.Query` que `Odbc.DataSource`: el *query folding* del driver es
  flojo y, si no mandas tú el `SELECT`, Power Query se trae la tabla entera y
  filtra en memoria.
- **Refrescar en el servicio de Power BI exige un gateway** en una máquina con
  el driver instalado y un DSN **de sistema** (el de usuario no vale). No es un
  conector certificado: va por la vía de ODBC genérico.
- **Excel de 32 bits no habla con un driver de 64.**
- Las consultas de Power Query se pueden crear **sin tocar la interfaz**, desde
  el modelo de objetos de Excel: `$wb.Queries.Add(nombre, m)` y un `QueryTable`
  con `CommandType = 2` para volcarla a hoja. Útil para generar libros
  enlazados a las vistas de consumo sin montarlos a mano.

## Historial de versiones

En [CHANGELOG.md](CHANGELOG.md).
