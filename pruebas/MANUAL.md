# Pruebas manuales

Lo que la batería automática **no** puede confirmar: que el comportamiento sea
el que tú quieres, que los mensajes se entiendan, y que el flujo conversacional
—el diferencial del proyecto— funcione de verdad.

No repite lo que ya cubren las 69 pruebas de `/pruebas`. Aquí solo va lo que
necesita ojo humano o datos reales.

## Antes de empezar

- [ ] **Copia de seguridad.** Estas pruebas escriben en tu almacén real, y el
      bloque 8 borra ficheros de disco sin papelera.

```bash
cp "datos/almacen.duckdb" "datos/almacen.duckdb.bak"
```

- [ ] La batería automática pasa en tu máquina:

```bash
python -m unittest discover -s pruebas -t .
```

---

## 1. Instalación desde cero

En una carpeta aparte, como si fueras otra persona.

- [ ] `git clone` + venv + `pip install -r requirements.txt` + `db migrar` sin
      errores.
- [ ] `ticket listar` e `idea listar` devuelven `(0 filas)`.
- [ ] **Mira si el README te bastó** o tuviste que deducir algo. Es la única
      vez que vas a leerlo con ojos nuevos.

---

## 2. El flujo conversacional (lo que de verdad diferencia al proyecto)

Sin escribir comandos: cuéntaselo a la IA y deja que conduzca.

- [ ] "Tengo este fichero que me llega todos los meses, quiero cargarlo" con un
      fichero real tuyo. ¿Arranca sola la skill `definir-carga`?
- [ ] ¿Te **perfila** el fichero antes de proponer nada, o se lo inventa?
- [ ] ¿Te propone el mapping y **espera aprobación**, o escribe directamente?
- [ ] ¿Te pregunta por la singularidad explicando el porqué, o la decide en
      silencio?
- [ ] Pídele algo que ya exista con otro nombre ("quiero guardar los gastos de
      desplazamiento"). ¿Detecta que `ticket` ya lo cubre?

> Si algún "no" te chirría, es un problema del skill, no del motor. Dímelo y lo
> ajustamos: ahí es donde se decide si esto asesora o solo obedece.

---

## 3. Carga de fichero, ciclo completo

- [ ] `etl validar <carga>` → `OK`.
- [ ] `etl dry-run <carga>` → ¿los números cuadran con lo que esperas del
      fichero? ¿Los rechazos que salen son rechazos de verdad?
- [ ] `etl ejecutar <carga>` → filas en la tabla.
- [ ] Repite `etl ejecutar` sin cambiar nada → debe decir **OMITIDO**.
- [ ] Cambia una celda del fichero y vuelve a ejecutar → ahora **sí** entra.

---

## 4. Singularidad: el punto que hay que decidir mirando

Esto es lo más importante de toda la lista. La semántica es: **se borran solo
las combinaciones que trae el fichero**.

- [ ] Carga un fichero con 2 registros (A y B).
- [ ] Vuelve a cargar un fichero corregido que solo trae A.
- [ ] Comprueba: A queda actualizado y **B sigue ahí**.

**¿Es eso lo que quieres?** Si esperabas que B desapareciera —porque el fichero
nuevo es "la verdad completa"— entonces esa carga necesita una clave más gruesa
(`["origen_carga"]`, foto completa) en vez de una fina. Decidirlo ahora es
barato; descubrirlo dentro de seis meses con datos de cliente, no.

---

## 5. Parámetros (valores que no vienen en el fichero)

Necesitas una carga con `parametros` declarados.

- [ ] Ejecutar sin el obligatorio → corta **antes** de leer el fichero.
- [ ] Con un valor que no existe en la tabla → ¿el error te lista los
      disponibles y te sirve para corregir?
- [ ] Con el nombre en minúsculas o con tilde distinta → ¿resuelve igual?
- [ ] Carga la tienda A, luego la B, y recarga la A → **las filas de B no se
      tocan**.
- [ ] `db consultar "SELECT parametros FROM _ejecuciones ORDER BY id DESC LIMIT 3"`
      → ¿se lee bien lo que contestaste?
- [ ] Quita el parámetro de `campos_singularidad` y valida → debe salir el
      `AVISO`.

---

## 6. Stops y alarmas

- [ ] Provoca un stop (mete a mano una fila que lo dispare). ¿La carga se
      detiene y **no** escribe en destino?
- [ ] ¿El mensaje te dice **qué filas** fallan, o solo que algo falló?
- [ ] Provoca una alarma. ¿La carga termina y el aviso se ve al final?
- [ ] Con un fichero limpio, ¿no salta nada? Una alarma que salta siempre es
      ruido y hay que replantearla.

---

## 7. CRUD y documentos

- [ ] Mira primero qué acepta la entidad, sin adivinar campos:

```bash
python -m motor.cli registro campos <entidad>
```

- [ ] Da de alta un registro real con su justificante:

```bash
python -m motor.cli registro crear <entidad> --set campo=valor --documento "ruta/a/la/foto.jpg"
```

- [ ] Adjunta después un segundo documento con otro tag:

```bash
python -m motor.cli documento adjuntar <tabla> <id> "ruta/al/pago.pdf" --tag "justificante pago"
```

- [ ] `documento listar --tabla <tabla> --id <id>` → salen los dos, con su tag
      y su operación.
- [ ] Edita el registro (`registro editar`) y vuelve a listar → los documentos
      siguen ahí.
- [ ] Comprueba que el fichero archivado se **abre bien** desde
      `datos/documentos/...`. El hash no garantiza que la copia sea legible por
      Windows si el original estaba bloqueado.

---

## 8. Historial y purga ⚠️ destructivo

Borra ficheros de disco **sin papelera**. Con la copia de seguridad hecha.

- [ ] `documento purgar` sin nada declarado → "Nada que purgar".
- [ ] Declara `"historial": {"tipo": "ficheros", "cantidad": 1}` en una carga.
- [ ] `documento purgar` (en seco) → ¿la lista es la que esperas? **Léela
      entera antes de seguir.**
- [ ] `documento purgar --aplicar` → los bytes desaparecen.
- [ ] Comprueba que la ficha sobrevive:

```bash
python -m motor.cli db consultar "SELECT nombre_original, estado, fecha_purga FROM _documentos"
```

- [ ] Vuelve a cargar el fichero purgado → debe volver a `disponible`.
- [ ] Quita el `historial` que declaraste si era solo para la prueba.

---

## 9. Trazabilidad: la pregunta de dentro de seis meses

Sin mirar el código, intenta responder con el sistema:

- [ ] "¿De qué fichero salió esta fila?" — desde una fila cualquiera, llegar al
      documento por `ejecucion_id`.
- [ ] "¿Quién y cuándo tocó este ticket?" — `_ejecuciones` con
      `ejecucion_id_principal`.
- [ ] "¿Por qué `mes` es texto?" — `db consultar "SELECT * FROM _decisiones"`.
- [ ] Si alguna cuesta más de dos minutos, falta una vista de consumo o un
      comando. Dilo.

---

## 10. Salidas y consumo (el mundo real)

- [ ] `etl exportar <vista>` y **abre el resultado desde Excel o Power BI**, no
      solo desde el terminal. Es donde aparecen los problemas de encoding,
      separadores decimales y fechas.
- [ ] Una carga con `salidas` declaradas → el fichero se genera al terminar,
      con la fecha en el nombre.
- [ ] Tras exportar, ¿`almacen.duckdb` queda libre? Vuelve a lanzar cualquier
      comando: si da error de bloqueo, hay una conexión sin cerrar.

---

## 11. Rendimiento con tu fichero gordo

- [ ] Carga el xlsx grande y cronométralo. Referencia medida: 497.383 filas en
      ~12 s, incluido el archivado de 45 MB.
- [ ] `du -sh datos/documentos` → decide si ese crecimiento te vale o hay que
      declarar `historial` en esa carga.

---

## Al terminar

- [ ] Borra la copia de seguridad si todo fue bien, o restaura desde ella si
      algo se torció:

```bash
cp "datos/almacen.duckdb.bak" "datos/almacen.duckdb"
```

- [ ] Anota lo que haya quedado cojo en la entidad que uses para eso:

```bash
python -m motor.cli registro crear <entidad> --set texto="..."
```
