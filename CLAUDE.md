# Tolva — instrucciones para Claude Code

Framework ETL conversacional local sobre DuckDB para gestionar información de
trabajo propia (procesos de negocio y ETL de ficheros recurrentes):
la IA no es un asistente que ejecuta comandos sueltos, es la interfaz
principal para modelar datos, cargar ficheros y llevar el día a día.

## Primera vez en este repo

Si `datos/almacen.duckdb` no existe todavía (comprueba con un `ls`/`Test-Path`
antes de asumir nada), esto es una instalación nueva. Sigue "Instalación" en
[README.md](README.md) sin preguntar paso a paso (clonar ya hecho, venv, pip
install), y verifica al final con `db migrar --con-ejemplos` y
`registro listar demo_venta`: una instalación limpia del núcleo no crea
ninguna tabla de negocio —solo las de sistema—, así que lo único que se puede
listar de entrada es el dominio de ejemplo.

**Antes de migrar, pregunta dónde deben vivir los datos.** Es lo único de la
instalación que no se puede decidir por el usuario, y lo único que cuesta caro
cambiar después, porque hay que mover ficheros a mano. Lanza `db rutas` para
ver los valores por defecto y plantéale dos cosas:

- Si el repositorio está dentro de una carpeta sincronizada (OneDrive,
  SharePoint, Dropbox, Drive), **el almacén tiene que salir de ahí**: propón
  una ruta local con `db init --datos <ruta>` y explica por qué (ver README,
  "Dónde viven los datos"). `db rutas` te lo marca con un OJO.
- Las **exportaciones** son el caso contrario: pregúntale si quiere que vayan
  a una carpeta compartida, porque suele ser justo lo que busca para abrirlas
  desde Excel o Power BI.

Si acepta las rutas por defecto, no escribas `config.local.json`: un fichero de
configuración que solo repite los valores por defecto es ruido que además hay
que mantener.

Justo después de dejarlo instalado y verificado — o al arrancar en un repo
que ya estaba instalado pero es la primera vez que hablas con este usuario —
**explica brevemente en el chat cómo se trabaja con este sistema**, sin
esperar a que pregunte. Esto es lo esencial, contado como a alguien que
todavía no sabe qué puede pedir:

- **Aquí no se ejecutan comandos, se habla.** El usuario cuenta lo que
  necesita y tú decides si eso pide migración, CRUD o carga de fichero. Los
  comandos existen (README) pero son el suelo, no la interfaz.
- **Dos puertas de entrada**: un **fichero que se repite** (extracto, export
  mensual) es una *carga* — skill `definir-carga`; algo que el usuario
  teclea (gastos, ideas, clientes) es un *proceso de negocio* con su CRUD —
  skill `crear-proceso`, sin fichero de por medio.
- **Nada se crea a ciegas**: antes de una tabla nueva se comprueba
  solapamiento contra el catálogo (`/catalogo/*.json`) y contra los datos
  reales (`proceso analizar`), para no acabar con tres nombres para lo
  mismo. El esquema se propone como borrador (`etl esquema`) marcando lo que
  la inferencia no puede decidir — un mes `"03"` parece número y hay que
  guardarlo como texto o pierde el cero — y el usuario aprueba.
- **Al cargar, lo importante es qué sustituye cada fichero**: si al volver a
  subir el informe corregido debe reemplazar solo ese mes, la foto entera, o
  añadir sin borrar (`campos_singularidad`). Se declara una vez.
- **Se pueden encadenar transformaciones SQL dentro de la propia carga**, no
  solo comprobaciones: columnas calculadas, joins para traer datos de otra
  tabla, filtrar filas que no interesan, normalizar valores. Van sobre la
  tabla *hall* (la de trabajo, que se vacía y recarga en cada ejecución) vía
  `transformacion_sql`, y lo que salga de ahí es lo que se guarda. Y hay
  `acciones` SQL en momentos del ciclo: antes de cargar, tras superar las
  validaciones, o cuando algo falla.
- **Stops y alarmas**: un `SELECT` que, si devuelve filas, corta la carga
  (`stop`, diciendo qué filas fallan) o solo avisa (`alarma`). Los mismos
  invariantes en `/catalogo/<tabla>.json` rigen también para el CRUD del CLI.
- **Para sacar datos**, vistas de consumo (`*_consumo`) exportadas con
  `etl exportar` para enlazar desde Excel/Power BI, y `salidas`: ficheros
  xlsx/CSV/parquet desde un `SELECT` libre, con nombre por fecha
  (`20260805_previ_ok.xlsx`), generados solos al terminar la carga.
- **Todo lo que escribe deja rastro, y el fichero de origen se guarda**: cada
  carga y cada alta o edición del CLI registra su ejecución, y el fichero del
  que salieron los datos se archiva por su hash. Así se llega desde una fila
  hasta el fichero que la trajo. A un registro se le pueden colgar documentos
  después (`documento adjuntar`, con un `--tag` libre: el justificante de pago
  que llega semanas más tarde queda junto a la foto del alta). Cada proceso
  declara cuánto conserva (`historial`), y purgar vacía los bytes pero nunca
  la ficha: se sigue sabiendo de qué fichero venía cada dato.
- **Todo lo decidido queda escrito** en `_decisiones` con su porqué, para que
  dentro de seis meses se sepa por qué `mes` es texto.
- **Lo suyo va en `propio/`, que no sale del repositorio público**, y hay un
  dominio de ejemplo (una librería inventada, `db migrar --con-ejemplos`) para
  trastear sin ensuciar nada. Los ejemplos son invisibles: no salen en el
  diagrama ni cuentan como evidencia al diseñar nada.

Cierra invitándole a empezar por lo más tonto que tenga a mano: un fichero
que abre cada mes, o una lista que lleva en un Excel suelto. En una
conversación queda montado y de paso ve el flujo entero.

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
- **Un proceso nuevo va a la capa propia, nunca al núcleo.** Migración en
  `propio/migraciones/` y ficha en `propio/catalogo/`. El núcleo es el
  framework y **no crea ninguna tabla de negocio**: una instalación limpia
  solo tiene las de sistema. Ni siquiera `persona`, `cliente` y `proyecto`,
  que estuvieron ahí hasta el hito 26 y eran un modelo de consultoría que
  heredaba cualquiera. Hay una prueba
  (`test_el_nucleo_no_crea_ninguna_tabla_de_negocio`) que falla si se cuela
  algo. Si crees que algo debe ir al núcleo, pregúntalo antes: casi siempre es
  que no.
- **Las dimensiones compartidas de esta instalación** (`persona`, `cliente`,
  `proyecto`) están en `propio/`, no en el framework. Siguen siendo aquello a
  lo que se engancha una tabla nueva, pero no des por hecho que existen al
  hablar del framework en abstracto: en la instalación de otro pueden ser
  otras o no haber ninguna.
- **Las entidades de ejemplo (`ejemplos/`) son invisibles en el chat.** Son una
  librería inventada con datos dummy (`demo_cliente`, `demo_libro`,
  `demo_venta`) que existe para las pruebas y para que un tercero pueda
  probar el framework. No las cuentes en resúmenes ni informes, no las uses
  como evidencia de nada, no las propongas al diseñar un proceso y no las
  incluyas en visualizaciones salvo que el usuario las pida por su nombre.
  El código ya las oculta por defecto (`catalogo.listar_entidades`); esta
  regla es para lo que decides tú, que el código no puede filtrar.
- **No escribas un módulo CRUD nuevo en `motor/`.** El CRUD lo da
  `motor/registros.py` leyendo la ficha de catálogo: `registro
  crear/listar/editar/borrar <entidad>`. Hubo un `motor/tickets.py` y un
  `motor/ideas.py` y se borraron en el hito 25 justamente por esto: un módulo
  por entidad mete el proceso en el repo público. Lo que sí hay que cuidar es
  la ficha, porque es de donde sale todo: las `relaciones` permiten
  `--set cliente="<nombre>"`, `etiqueta` dice con qué columna se nombra la entidad
  cuando no es `nombre` (`demo_libro` usa `titulo`), y
  `validacion.lista_valores` da un error legible en vez de un `CHECK` violado.
- Toda migración nueva sigue el patrón de `/migraciones/`: `CREATE TABLE`/
  `CREATE VIEW` + un `INSERT INTO _decisiones` en el mismo fichero explicando
  el porqué de las decisiones no obvias (ver cualquier migración existente
  como plantilla).
- Toda tabla nueva necesita su ficha (`propio/catalogo/<tabla>.json`) antes de
  poder cargarse, referenciarse desde otra carga u operarse con `registro`.
- DuckDB no soporta `ALTER TABLE ... DROP/ADD CONSTRAINT`: para cambiar un
  `CHECK` hay que recrear la tabla dentro de la migración (ver
  `006_ticket_concepto_otros.sql` como ejemplo). Tampoco admite `ADD COLUMN`
  con constraint (ni `CHECK` ni FK), ni alterar una tabla que sea destino de
  una FK ajena: para eso hay que apartar y recrear la que referencia (ver
  `013_trazabilidad_ejecuciones.sql` con `_rechazos`). Por eso los
  `ejecucion_id` del modelo son referencias lógicas sin FK declarada.
- **La purga de documentos no se ejecuta sola**: hoy solo corre si alguien
  lanza `documento purgar --aplicar`. Va en seco por defecto y borra los
  ficheros directamente, sin papelera. No la lances por iniciativa propia;
  propónsela al usuario y que decida.
- **Nada de escribir volumen fila a fila.** DuckDB es columnar y degrada de
  forma no lineal con `INSERT` por fila: medido, 1.000 filas por SQL tardan
  ~13s frente a ~0,35s por 500.000 vía DataFrame. Usa
  `motor_etl._insertar_bloque` o resuélvelo en SQL dentro del motor.
- **No propongas índices para acelerar consultas** sin medir antes: se
  comprobó sobre 497.383 filas que no aportan y llegan a empeorar el filtro
  por texto (está en `_decisiones`, migración 011). DuckDB ya mantiene
  zonemaps automáticos.
- Las cargas de fichero no hacen upsert: declaran `campos_singularidad` y el
  motor borra en bloque esas combinaciones antes de insertar. El upsert fila
  a fila es solo para las acciones puntuales del CLI.
- Las reglas de negocio (stops y alarmas) **las decide el usuario, no tú**:
  propón candidatas a partir de lo que diga o de anomalías reales que veas al
  perfilar, y confírmalas antes de instalarlas. Una alarma que salta en miles
  de filas cada carga es ruido, no aviso.
- Tras exportar (`etl exportar`), la conexión se cierra explícitamente para
  no dejar `almacen.duckdb` bloqueado — no abras una conexión interactiva
  larga contra él si luego vas a exportar o si alguien va a abrir los
  ficheros exportados desde Excel/Power Query a continuación.

Para todo lo demás (estructura de carpetas, comandos completos, vocabulario
de operaciones ETL, changelog de hitos), la fuente de verdad es
[README.md](README.md).
