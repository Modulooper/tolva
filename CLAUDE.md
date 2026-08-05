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
- **Todo lo decidido queda escrito** en `_decisiones` con su porqué, para que
  dentro de seis meses se sepa por qué `mes` es texto.

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
- Toda migración nueva sigue el patrón de `/migraciones/`: `CREATE TABLE`/
  `CREATE VIEW` + un `INSERT INTO _decisiones` en el mismo fichero explicando
  el porqué de las decisiones no obvias (ver cualquier migración existente
  como plantilla).
- Toda tabla nueva necesita su entrada en `/catalogo/<tabla>.json` antes de
  poder cargarse o referenciarse desde otra carga.
- DuckDB no soporta `ALTER TABLE ... DROP/ADD CONSTRAINT`: para cambiar un
  `CHECK` hay que recrear la tabla dentro de la migración (ver
  `006_ticket_concepto_otros.sql` como ejemplo).
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
