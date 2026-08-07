-- 013_trazabilidad_ejecuciones.sql
-- _ejecuciones deja de ser el registro de las cargas de fichero para pasar a
-- ser el registro de toda escritura del sistema, también la del CLI. Base del
-- vínculo con documentos (migración siguiente): si todo lo que escribe deja
-- una ejecución, los documentos se cuelgan de la ejecución y no hace falta
-- duplicar el hash en cada tabla de negocio.

-- DuckDB no deja alterar una tabla que es destino de una FK ("Dependency
-- Error: Cannot alter entry _ejecuciones because there are entries that depend
-- on it"), y _rechazos.ejecucion_id la referencia. Como tampoco admite DROP
-- CONSTRAINT, hay que apartar _rechazos, alterar, y volver a crearla con su
-- FK intacta. Se preserva el contenido: aquí está vacía, pero en otra
-- instalación puede no estarlo. seq_rechazos no se toca, así que los ids
-- siguen su curso.
CREATE TABLE _rechazos_tmp AS SELECT * FROM _rechazos;
DROP TABLE _rechazos;

-- Una operación de CLI no tiene fichero de origen, así que los dos campos que
-- lo describen dejan de ser obligatorios. DuckDB sí admite DROP NOT NULL
-- (a diferencia de ADD/DROP CONSTRAINT), así que la propia _ejecuciones no
-- hay que recrearla ni tocar seq_ejecuciones.
ALTER TABLE _ejecuciones ALTER COLUMN fichero      DROP NOT NULL;
ALTER TABLE _ejecuciones ALTER COLUMN hash_fichero DROP NOT NULL;

-- 'carga' por DEFAULT deja correctas las filas existentes sin UPDATE: todas
-- las anteriores a esta migración son cargas de fichero. Sin CHECK porque
-- DuckDB no admite ADD COLUMN con constraints; el valor lo controla el motor
-- (mismo criterio que "usuario" en la migración 003).
ALTER TABLE _ejecuciones ADD COLUMN tipo VARCHAR DEFAULT 'carga';

-- Referencia lógica a _ejecuciones.id, sin FK declarada: ADD COLUMN con FK
-- tampoco está soportado. Mismo tratamiento que ejecucion_id en las tablas de
-- destino (migración 012).
ALTER TABLE _ejecuciones ADD COLUMN ejecucion_id_principal BIGINT;

-- Regla uniforme: toda ejecución tiene principal, y en una creación o una
-- carga se apunta a sí misma. Así:
--   id = ejecucion_id_principal                  -> ejecuciones principales
--   ejecucion_id_principal = N AND id <> N       -> historial de cambios de N
UPDATE _ejecuciones SET ejecucion_id_principal = id;

-- Las entidades del CLI guardan SOLO la ejecución de creación. Las ediciones
-- posteriores no tocan esta columna: cuelgan de la principal en _ejecuciones.
-- Nullable a propósito: las filas anteriores a esta migración no tienen
-- ejecución que las creara y no se les inventa una (mismo criterio que la
-- migración 003 con "usuario" = 'desconocido').
--
-- Aquí había un `ALTER TABLE` sobre ticket e idea. Se retiró al sacarlas del
-- núcleo (hito 25): cada una declara su ejecucion_id en la migración que la
-- crea, que es la única forma de que el framework no dependa de tablas de
-- negocio que en otra instalación no existen.

-- _rechazos vuelve tal y como estaba en 001_nucleo.sql, FK incluida.
CREATE TABLE _rechazos (
    id BIGINT PRIMARY KEY DEFAULT nextval('seq_rechazos'),
    ejecucion_id BIGINT NOT NULL REFERENCES _ejecuciones(id),
    num_fila BIGINT NOT NULL,
    motivo VARCHAR NOT NULL,
    campo_implicado VARCHAR,
    contenido_raw VARCHAR
);
INSERT INTO _rechazos SELECT * FROM _rechazos_tmp;
DROP TABLE _rechazos_tmp;

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    '_ejecuciones pasa a registrar toda escritura del sistema, no solo las ' ||
    'cargas de fichero: gana "tipo" (carga/cli) y "ejecucion_id_principal", ' ||
    'que en una creación o una carga apunta a sí misma. De ahí salen las dos ' ||
    'consultas que interesan: "id = ejecucion_id_principal" da las ' ||
    'ejecuciones principales, y "ejecucion_id_principal = N AND id <> N" da ' ||
    'el historial de modificaciones de N. Las tablas de negocio guardan solo ' ||
    'la ejecución de creación (ticket.ejecucion_id, idea.ejecucion_id) y no ' ||
    'se tocan al editar. Se descarta añadir el hash del fichero como columna ' ||
    'en las tablas de ingesta: es redundante, porque se recupera por join ' ||
    'desde ejecucion_id, y obligaría a mantener el mismo dato en dos sitios. ' ||
    'fichero y hash_fichero pasan a nullable porque una operación de CLI no ' ||
    'tiene fichero de origen. Ni "tipo" lleva CHECK ni ' ||
    '"ejecucion_id_principal" lleva FK porque DuckDB no admite ADD COLUMN ' ||
    'con constraints y recrear _ejecuciones arrastraría su secuencia; se ' ||
    'sigue el precedente de la migración 003. _rechazos se destruye y se ' ||
    'vuelve a crear idéntica (con sus filas) porque su FK contra ' ||
    '_ejecuciones impedía alterar la tabla referenciada y DuckDB tampoco ' ||
    'admite DROP CONSTRAINT.',
    'Diseño acordado con el usuario para dar trazabilidad a los documentos ' ||
    'de origen (una foto de un ticket, un extracto), incluidos los que se ' ||
    'añaden después sobre un registro ya creado. Verificado en esta sesión ' ||
    'contra DuckDB 1.5.5 que ALTER COLUMN ... DROP NOT NULL sí funciona, ' ||
    'mientras que ADD COLUMN con CHECK o con FK devuelve "Parser Error: ' ||
    'Adding columns with constraints not yet supported", y que alterar ' ||
    '_ejecuciones con la FK de _rechazos viva devuelve "Dependency Error: ' ||
    'Cannot alter entry _ejecuciones because there are entries that depend ' ||
    'on it". Las 13 filas existentes de ' ||
    '_ejecuciones son todas cargas de fichero, así que el DEFAULT las deja ' ||
    'correctas sin reescribir histórico.',
    '013_trazabilidad_ejecuciones.sql'
);
