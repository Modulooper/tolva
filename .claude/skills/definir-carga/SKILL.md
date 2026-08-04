---
name: definir-carga
description: Define una carga ETL recurrente (Excel/CSV/texto) a partir de un fichero de muestra. Perfila las columnas con código, consulta el catálogo semántico, propone el mapping, valida con dry-run y guarda la definición en /cargas solo tras la aprobación del usuario. Úsala cuando el usuario quiera integrar un tipo de fichero que se repite (extractos, informes, exports) o pida explícitamente "definir una carga".
---

# definir-carga

Objetivo: convertir un fichero de muestra en una definición de carga
(`/cargas/<nombre>.json`) reutilizable, sin que ningún dato pase por el
modelo — el modelo interviene una vez, sobre la muestra, para proponer la
definición; el motor (`motor/motor_etl.py`) es quien ejecuta después.

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

## 5. Números en formato no estándar

Si `tipo_aparente` marca `double (formato_numerico: es)`, añade
`"formato_numerico": "es"` al `cast`. Si el fichero mezcla formatos o no
estás seguro, pregunta.

## 6. Clave de upsert

Propón `clave_upsert` a partir de lo que identifica un registro de forma
única en la fuente real (no en la muestra): si no hay un ID explícito,
busca una combinación de campos que sea razonablemente única (ver el
ejemplo de `movimientos_banco`, que usa fecha+concepto+importe+saldo porque
el extracto no trae ID de movimiento). Explica el razonamiento al usuario,
no lo des por hecho en silencio.

## 7. Construye el borrador y muéstralo

Arma el JSON completo de la definición (mismo esquema que
`motor/cargas.py:SCHEMA_DEFINICION`): `nombre`, `carpeta` (dentro de
`/entrada/`, no fuera del repo), `patron`, `formato`, `delimitador`/`hoja`,
`encoding` si aplica, `fila_cabecera`, `tabla_destino`, `clave_upsert`,
`mapping`. No incluyas en el mapping los campos de sistema
(`id`, `created_at`, `updated_at`, `extra_fields`) — el motor los gestiona
solo.

Muéstraselo al usuario en el chat con una explicación breve de cada
decisión no obvia (formato de fecha elegido y por qué, formato numérico,
clave de upsert, columnas que se ignoran y por qué). Pide confirmación o
cambios antes de seguir.

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
