---
name: definir-carga
description: Define una carga ETL recurrente (Excel/CSV/texto) a partir de un fichero de muestra. Perfila las columnas con código, consulta el catálogo semántico, propone el mapping, valida con dry-run y guarda la definición en /cargas solo tras la aprobación del usuario. Úsala cuando el usuario quiera integrar un tipo de fichero que se repite (extractos, informes, exports) o pida explícitamente "definir una carga".
---

# definir-carga

Objetivo: convertir un fichero de muestra en una definición de carga
(`/cargas/<nombre>.json`) reutilizable. El modelo interviene **una sola vez**,
sobre el perfil de la muestra, para proponer la definición; a partir de ahí
ejecuta el motor (`motor/motor_etl.py`) y ninguna carga vuelve a pasar por un
modelo.

Ojo con lo que eso implica y hay que decirle al usuario si no lo ha planteado
él: el perfil incluye **valores reales** de sus columnas, así que esta primera
conversación sí saca una muestra de su equipo. Si el fichero lleva datos que no
pueden salir, remítele a "Qué ve el asistente" en el README **antes** de
perfilar nada: la salida buena es anonimizar conservando la forma de los
valores, no fabricar un fichero de muestra —un fichero inventado da un perfil
correcto sobre datos que no son los suyos.

No escribas nada en disco hasta el paso 8. Todo lo anterior es análisis y
propuesta en el chat.

## 1. Pide el fichero de muestra

Si el usuario no ha dado ya una ruta, pídesela. Puede ser el fichero real
que se repetirá (mejor) o un ejemplo representativo.

## 2. Perfila con código, no a ojo

Ejecuta:

```bash
python -m motor.cli etl definir "<ruta-fichero>" --json
```

Ajusta `--formato`, `--delimitador`, `--encoding`, `--hoja`, `--fila-cabecera`
según lo que veas del fichero (ábrelo con Read si hace falta para decidir
delimitador/encoding antes del primer intento). Si el CSV falla por encoding,
reintenta con `--encoding cp1252` o `--encoding latin-1` antes de asumir que
el fichero está corrupto — es el caso más común en exports de sistemas
españoles/bancarios.

El perfil te da, por columna: tipo aparente, nulos, cardinalidad, muestra de
valores y `sugerencias_catalogo` (coincidencias por sinónimo contra
`/catalogo/*.json`). No inventes tipos ni mappings sin mirar esto.

## 3. Consulta el catálogo

Lee `/catalogo/*.json` completo (no solo las sugerencias automáticas — los
sinónimos registrados pueden no cubrir todas las variantes). Para cada
columna del fichero decide:

- Si hay una entidad/campo existente que encaja → usarlo, y considera añadir
  el nombre de columna observado a `sinonimos` de ese campo en el catálogo
  (facilita el próximo `definir-carga`).
- Si la columna no encaja en ninguna tabla existente → NO crees una tabla
  nueva aquí. Eso es trabajo de la skill `crear-proceso`. Explícaselo al
  usuario y detente, o continúa solo con las columnas que sí encajan.

Si `tabla_destino` no tiene entrada en `/catalogo`, `etl validar` la va a
rechazar (ver Componente 2 del proyecto) — confírmalo con
`python -m motor.cli etl validar` antes de dar la carga por buena.

## 4. Fechas: nunca adivines el formato

Para toda columna con `tipo_aparente: "fecha (candidato date_format)"`:

- Mira la muestra de valores. Si ves algún componente >12 en primera o
  segunda posición, ya tienes evidencia del orden día/mes — dilo
  explícitamente en la propuesta.
- Si no hay evidencia en la muestra (todos los valores ≤12/≤12), NO pases
  dos formatos candidatos ambiguos esperando que el motor lo resuelva con
  más datos en la carga real — pregúntale al usuario el formato y usa un
  único `formatos: ["%d/%m/%Y"]` (o el que corresponda). El motor
  (`motor/fechas.py`) fallará explícitamente si la ambigüedad persiste sobre
  el fichero real; mejor detectarlo aquí que en `etl ejecutar`.
- Si los valores son numéricos en rango plausible (seriales de Excel), usa
  `date_format` igualmente — el motor detecta el serial automáticamente
  (época `epoch_excel: "1900"` por defecto, o `"1904"` si el usuario confirma
  que el fichero viene de Excel para Mac).

## 4b. Si la tabla destino no existe todavía

`python -m motor.cli etl esquema <fichero> --tabla <nombre> [--json]` da un
borrador de `CREATE TABLE` y de entrada de catálogo a partir del perfil, con
las columnas dudosas marcadas. **Es un punto de partida, no el esquema
final**: la inferencia acierta el tipo de almacenamiento y falla la
semántica (un mes "03" se infiere `integer` y pierde el cero; un
`20260320003000` se infiere `integer` y es una fecha; un código numérico es
un identificador aunque parezca número). Repasa cada aviso con el usuario
antes de convertirlo en migración, y sigue pasando por `crear-proceso` para
la comprobación de solapamiento.

Si usaste `--limite` para iterar rápido, vuelve a perfilar sin él antes de
fijar el esquema: con muestra, el tipo no está garantizado para el resto del
fichero.

## 5. Números en formato no estándar

Si `tipo_aparente` marca `double (formato_numerico: es)`, añade
`"formato_numerico": "es"` al `cast`. Si el fichero mezcla formatos o no
estás seguro, pregunta.

## 5b. Para qué se hace esta carga

Antes de decidir nada del mapping fino, escribe la `descripcion` de la carga
(campo obligatorio de la definición). **No es un rótulo.** El JSON ya dice a
qué columna va cada cosa; esto tiene que decir lo que el JSON no puede.

Cinco cosas que debe cubrir:

1. **Para qué se carga** — qué se decide, se factura o se informa con estos
   datos. Es lo primero y lo más importante: sin esto, dentro de un año nadie
   sabe si la carga sigue haciendo falta.
2. **De dónde sale el fichero** — quién lo genera o lo manda, cada cuánto, y
   si viene exportado a mano (lo que explica que cambien las columnas).
3. **Qué es una fila** en el mundo real, no en la tabla.
4. **Qué significa volver a subirlo corregido** — qué porción debe sustituir.
5. **Qué te haría desconfiar** al abrirlo.

**Redáctala tú primero y pásasela al usuario para que la corrija.** Un campo
que dice "documenta aquí tu carga" se queda vacío o se rellena con el nombre
del fichero; un borrador concreto sí se enmienda. Ya sabes bastante del paso
2 (perfil) y del 3 (catálogo): rellena lo que puedas y **pregunta solo lo que
no puedas deducir**, en una sola tanda, no de una en una:

> Antes de fijar el mapping, cuéntame cuatro cosas de este fichero:
> ¿para qué usáis estos datos?, ¿quién lo manda y cada cuánto?, ¿qué es una
> fila?, y si te llega uno corregido, ¿qué debería sustituir — solo su
> periodo, la foto entera, o nada porque solo añade?

La cuarta pregunta es la del paso 6 formulada en palabras, y ese es el punto:
**si la descripción y `campos_singularidad` no dicen lo mismo, uno de los dos
está mal**, y ahí se ve sin ejecutar nada. Escribir "sustituye el mes entero
de ese centro" y luego declarar `["fecha"]` es una contradicción visible.

Lo que responda el usuario en prosa alimenta además el paso 6c (stops) y el
6e (parámetros): "cada fichero es de una tienda" es un parámetro, y "si bajan
mucho las filas es que salió incompleto" es una alarma.

## 6. Campos de singularidad

Las cargas de fichero no hacen upsert fila a fila: declaran
`campos_singularidad`, y en cada ejecución el motor borra en bloque las
combinaciones de esos campos presentes en los datos entrantes antes de
insertar el bloque nuevo (ver README, "Cómo escriben las cargas de
fichero"). Propón esos campos preguntándote **qué porción del histórico
debe sustituir este fichero al recargarse**:

- Fichero que trae un periodo/ámbito concreto (p. ej. un centro y un mes) →
  esos campos (`["centro", "mes"]`): recargar sustituye solo esa porción.
- Fichero que es la foto completa del proceso y sustituye entera a la
  anterior → `["origen_carga"]` (caso de `previ_transporte`).
- Fichero que solo añade y nunca corrige → `[]` (acumulativo puro).
- Si no hay ID explícito pero cada fila es un hecho irrepetible, sirve la
  combinación que la identifica (`movimientos_banco` usa
  fecha+concepto+importe+saldo porque el extracto no trae ID de movimiento).

Explica el razonamiento al usuario, no lo des por hecho en silencio: elegir
mal aquí borra datos que no tocaba, o duplica los que sí.

## 6b. ¿Hace falta tabla hall?

Si los datos necesitan transformarse antes de llegar al destino (columnas
calculadas, enriquecer con datos de otra tabla, filtrar filas sin
correspondencia), propón `tabla_hall` + `transformacion_sql`: la hall recibe
el fichero tal cual (foto completa, se vacía y recarga), y el `SELECT` de
transformación produce las filas finales que se promueven al destino. Si el
fichero ya viene con la forma final, no la uses: añade complejidad sin
ganancia.

## 6c. ¿Hay condiciones que deban cortar la carga?

Pregunta al usuario qué haría el fichero **inaceptable** (un stop) y qué
sería solo raro pero admisible (una alarma). Una validación es un `SELECT`
sobre `_entrante` (los datos ya mapeados) o sobre la hall: si devuelve filas
se dispara, y las columnas que selecciones son el detalle que verá el
usuario, así que incluye lo que identifique el problema (valores implicados,
recuento). Ver README, "Stops y alarmas".

No inventes reglas de negocio: proponlas a partir de lo que el usuario diga
o de anomalías reales que hayas visto al perfilar (fechas fuera de rango,
importes negativos, códigos sin correspondencia), y confírmalas antes de
darlas por buenas. Si una regla vale para la tabla venga el dato de donde
venga, va en `/catalogo/<tabla>.json` en vez de en la carga.

## 6d. ¿Cuánto se conserva del fichero de origen?

Cada carga archiva su fichero en `datos/documentos/` por el hash del
contenido, así que desde cualquier fila se llega al fichero que la trajo. Lo
que hay que decidir es cuánto se guarda, con el bloque `historial` de la
definición:

```json
"historial": "siempre"
"historial": {"tipo": "ficheros", "cantidad": 10}
"historial": {"tipo": "anios",    "cantidad": 3}
```

Por defecto es `"siempre"`, así que **no declarar nada no pierde nada**: no
lo pongas por rellenar. Pregúntalo solo si el fichero es grande o llega muy
a menudo, que es cuando el espacio importa — un extracto de 4 KB mensual no
justifica la conversación. Ver README, "Historial de documentos".

## 6e. ¿Hay datos que no vienen en ninguna columna?

Dos casos distintos, y confundirlos sale caro.

**Está en el fichero, pero en la cabecera.** Un Excel con la sucursal en `B5`,
el mes en `B6` y la tabla empezando en la fila 10. Eso es la operación
`celda`, con `fila_cabecera` apuntando a la fila de nombres de columna. **No
lo declares como parámetro**: el dato está ahí, y pedirlo al ejecutar obliga a
abrir el Excel para saber qué teclear y permite cargar una sucursal con el
nombre de otra. Al perfilar se detecta solo: si las primeras filas tienen una
o dos celdas sueltas y la tabla empieza más abajo, pregunta qué es cada una.

**No está en el fichero en absoluto.** El caso típico es un mismo formato que
llega de varios sitios: veinte tiendas mandando el mismo export de pedidos, sin
que la tienda aparezca en ningún lado. Eso sí es `parametros`, y se pide al
ejecutar. Ver README, "Parámetros".

En los dos casos, la pregunta que va detrás es la misma y es la importante:
**si reenvían el fichero de esa sucursal y ese mes corregido, ¿qué debe
desaparecer?** Lo que conteste el usuario son los `campos_singularidad`, y esos
campos tienen que estar entre ellos o recargar una sucursal borrará las demás.

Detectarlo es fácil al perfilar: si dos ficheros de la misma carpeta tienen
las mismas columnas pero corresponden a ámbitos distintos, falta un
parámetro. Pregúntalo cuando el usuario mencione varias tiendas, delegaciones,
clientes o centros para el mismo formato.

Al proponerlo, decide con el usuario dos cosas:

1. **Cerrado o abierto.** Si el valor ya existe como tabla (`tienda`,
   `cliente`, `delegacion`), va con `valores_de` para que no se teclee mal.
   Si no existe tabla, texto libre — y plantéate si no debería existir
   (skill `crear-proceso`).
2. **Si entra en `campos_singularidad`.** Casi siempre sí, junto a alguna
   columna del fichero. Si no entra, recargar el fichero de una tienda borra
   las filas de las demás. `etl validar` lo avisa, pero es mejor decidirlo
   antes que descubrirlo por el aviso.

## 7. Construye el borrador y muéstralo

Arma el JSON completo de la definición (mismo esquema que
`motor/cargas.py:SCHEMA_DEFINICION`): `nombre`, `carpeta` (dentro de
`/entrada/`, no fuera del repo), `patron`, `formato`, `delimitador`/`hoja`,
`encoding` si aplica, `fila_cabecera`, `tabla_destino`,
`campos_singularidad`, `mapping` (y `tabla_hall` + `transformacion_sql` si
aplica). No incluyas en el mapping los campos de sistema
(`id`, `created_at`, `updated_at`, `extra_fields`) — el motor los gestiona
solo.

Muéstraselo al usuario en el chat con una explicación breve de cada
decisión no obvia (formato de fecha elegido y por qué, formato numérico,
campos de singularidad y qué porción sustituyen al recargar, columnas que se
ignoran y por qué). Pide confirmación o cambios antes de seguir.

## 8. Guarda, valida y dry-run

Solo tras la aprobación:

1. Escribe `/cargas/<nombre>.json`.
2. `python -m motor.cli etl validar <nombre>` — si falla, corrige el fichero
   y repite. No sigas con errores de validación.
3. Si el fichero de muestra debe quedar como primera carga real, cópialo a
   la carpeta `/entrada/...` declarada (recuerda: `/entrada/**` está en
   `.gitignore`, no se versiona).
4. `python -m motor.cli etl dry-run <nombre>` y enseña el resultado completo
   al usuario: filas ok, rechazadas (con motivo), columnas no declaradas.

## 9. Ejecutar solo con aprobación explícita

No ejecutes `etl ejecutar` automáticamente. Enseña el dry-run, y solo si el
usuario lo confirma después de verlo, ejecuta
`python -m motor.cli etl ejecutar <nombre>`.
