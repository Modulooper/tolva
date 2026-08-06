---
name: crear-proceso
description: Toma de requisitos por preguntas para crear una entidad nueva de negocio (p.ej. contactos, horas por cliente, gastos). Antes de proponer nada consulta el catálogo semántico completo y comprueba solapamientos con código (no solo criterio del modelo). Salida: migración propuesta + catálogo actualizado + entrada en _decisiones, todo pendiente de tu aprobación. Úsala cuando el usuario quiera "crear un proceso", "una tabla nueva para...", o describa un tipo de registro que quiere empezar a llevar.
---

# crear-proceso

Objetivo: convertir una necesidad descrita en lenguaje natural en una tabla
nueva bien integrada con el modelo existente — nunca una tabla aislada que
duplique algo que ya existe. Ningún DDL se ejecuta sin que tú lo apruebes:
todo pasa por un fichero de migración que revisas primero.

## 1. Entiende el requisito

Pregunta lo que haga falta para tener claro: qué se quiere registrar, qué
campos tiene cada registro, ejemplos reales de valores (sobre todo para
campos que parezcan nombres de entidades: clientes, proyectos, personas,
categorías), y si hay un fichero de ejemplo (si lo hay, mejor: puedes pedir
también valores de muestra de ahí en vez de preguntarlos uno a uno).

## 2. Lee el catálogo completo, no solo el automatch

Lee **todos** los ficheros de `/catalogo/*.json`, no te fíes solo de las
coincidencias automáticas. Los sinónimos registrados no cubren todo.

## 3. Comprueba solapamiento con código, campo a campo

Para cada campo propuesto que pueda ser una entidad existente (no para
campos claramente propios como un importe o una fecha):

```bash
python -m motor.cli proceso analizar --campo "<nombre propuesto>" --valores "<v1,v2,v3,...>" --json
```

Esto te da, con evidencia real de la base (`motor/solapamiento.py`), no
opinión:

- `coincidencias_por_nombre`: si el nombre/sinónimo ya existe en el catálogo.
- `cardinalidad`: si los valores parecen una categoría cerrada (pocos
  distintos, ratio de unicidad bajo — como `ticket.concepto`) o una entidad
  con identidad propia (muchos distintos, ratio alto).
- `candidatos_fk`: tablas/columnas existentes cuyos valores reales solapan
  con los propuestos por encima de un umbral (0.5 por defecto). Un ratio
  alto es evidencia fuerte de que el campo debe ser una FK a esa tabla, no
  una columna de texto nueva.

Si no tienes valores de ejemplo todavía, pídeselos al usuario antes de
proponer el esquema — sin evidencia no hay comprobación real, solo
suposición, y eso es justo lo que hay que evitar aquí.

Interpreta los resultados así:
- `candidatos_fk` con ratio alto → usa FK a la tabla existente, no crees un
  campo de texto duplicado.
- `coincidencias_por_nombre` sin `candidatos_fk` → puede ser coincidencia de
  nombre pero dominio distinto (revisa los valores a mano); no asumas FK
  solo por el nombre.
- Cardinalidad baja y estable → candidato a `VARCHAR` con `CHECK` (como
  `ticket.concepto`), no a tabla propia.
- Cardinalidad alta, sin candidatos_fk → probablemente sí es una entidad
  nueva legítima.

## 4. Núcleo: referencia o justifica

Toda tabla nueva debe referenciar `persona`, `cliente` o `proyecto` cuando
corresponda (vía FK real, nunca un campo de texto libre con el nombre). Si
no referencia ninguna, explica por qué en la propuesta — el mismo patrón que
`movimiento_bancario` (ver su entrada en `_decisiones`).

## 4a. Para qué existe este proceso

La `descripcion` de la ficha de catálogo no es un rótulo: **repetir el nombre
de la tabla no aporta nada.** Tiene que decir para qué se lleva ese registro
y qué representa una fila en el mundo real — lo que no se deduce leyendo las
columnas. Compara:

- ❌ `"Tabla de tickets."`
- ✅ `"Ticket de gasto (viajes, hoteles, gasolina) atado a un cliente y a la
  persona que lo generó."`

Redáctala tú a partir de lo que el usuario haya contado y pásasela para que
la corrija; si algo no lo puedes deducir, pregúntalo en una sola tanda junto
al resto de la toma de requisitos: para qué se usan estos datos, qué es una
fila, y quién los mete y cuándo.

Lo mismo para la `descripcion` de cada campo cuando el nombre no baste: en
`ticket.concepto` lo útil no es "concepto del ticket", es qué categorías hay
y por qué esas.

## 4b. Trazabilidad: `ejecucion_id` y documentos

Toda tabla con CRUD por CLI lleva `ejecucion_id BIGINT` (nullable, marcado
`"sistema": true` en el catálogo): guarda la ejecución que **creó** la fila,
y las ediciones posteriores no lo tocan — se encadenan a ella en
`_ejecuciones`. Eso es lo que permite colgar documentos del registro
(`documento adjuntar`) sin duplicar nada, así que inclúyelo en el esquema
propuesto y hazlo escribir por `ejecuciones.envolver` en el `crear`, igual
que `motor/tickets.py`.

Si a la entidad se le van a adjuntar justificantes (gastos, facturas,
contratos), no declares `historial` con recorte: el valor por defecto
`"siempre"` es lo correcto ahí. Ver README, "Historial de documentos".

## 5. Propón el esquema y pide aprobación

Antes de escribir nada, muestra en el chat:

- Nombre de tabla y columnas (tipo, obligatoriedad, FKs, `CHECK` si aplica).
- Por cada decisión no obvia, la evidencia de código que la respalda (el
  resultado de `proceso analizar`, no "me parece que...").
- El siguiente número de migración libre (revisa `/migraciones/`, usa el
  siguiente entero con cero a la izquierda si aplica, `NNN_nombre.sql`).
- Borrador de la entrada de catálogo (`/catalogo/<tabla>.json`, mismo
  formato que las existentes: campos, tipos, sinónimos, relaciones).
- Borrador del texto para `_decisiones` (tipo, descripción, evidencia,
  migración asociada).

Pide confirmación o cambios. No sigas sin aprobación explícita.

## 6. Escribe, aplica y valida — solo tras la aprobación

1. Escribe el fichero de migración en `/migraciones/NNN_<nombre>.sql`: el
   `CREATE TABLE` y el `INSERT INTO _decisiones` en el mismo fichero (mismo
   patrón que las migraciones anteriores).
2. Escribe `/catalogo/<tabla>.json`.
3. `python -m motor.cli db migrar` y comprueba que se aplica sin error.
4. Si el usuario quiere también CRUD por CLI para la tabla nueva (como
   `ticket crear/listar/editar/borrar`), constrúyelo como paso siguiente,
   no lo des por incluido automáticamente — pregúntaselo.

## Lo que esta skill NO hace

No toca datos de negocio (esto es esquema, no carga). Para integrar
ficheros recurrentes sobre la tabla que acabas de crear, usa la skill
`definir-carga` después.
