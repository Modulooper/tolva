-- 014_documentos.sql
-- Almacén de documentos direccionado por contenido y su vínculo con las
-- ejecuciones. Todo lo que escribe deja una ejecución (migración 013), así
-- que colgando los documentos de la ejecución se llega a ellos desde
-- cualquier registro por join, sin duplicar el hash en las tablas de negocio.

CREATE SEQUENCE seq_ejecucion_documento START 1;

-- La clave es el hash del contenido: el mismo fichero subido dos veces se
-- guarda una sola vez en disco y comparte fila. Los atributos que describen
-- el contenido viven aquí y no en el vínculo, porque la purga es por
-- contenido: se vacían los bytes una vez, no una vez por cada uso.
CREATE TABLE _documentos (
    hash VARCHAR PRIMARY KEY,
    nombre_original VARCHAR NOT NULL,
    extension VARCHAR,
    mime VARCHAR,
    bytes BIGINT NOT NULL,
    ruta VARCHAR NOT NULL,
    estado VARCHAR NOT NULL DEFAULT 'disponible' CHECK (estado IN ('disponible', 'purgado')),
    fecha_alta TIMESTAMP NOT NULL DEFAULT current_timestamp,
    fecha_purga TIMESTAMP
);

-- El vínculo N:M. El tag va aquí y no en _documentos porque califica el uso,
-- no el contenido: el mismo fichero puede ser 'crear' en una ejecución y
-- 'comprobante' en otra. Texto libre a propósito ('justificante pago',
-- 'doc AB545'); 'crear' queda como convención para el documento que originó
-- el registro.
CREATE TABLE _ejecucion_documento (
    id BIGINT PRIMARY KEY DEFAULT nextval('seq_ejecucion_documento'),
    ejecucion_id BIGINT NOT NULL,
    hash VARCHAR NOT NULL,
    tag VARCHAR NOT NULL DEFAULT 'crear',
    fecha TIMESTAMP NOT NULL DEFAULT current_timestamp,
    UNIQUE (ejecucion_id, hash, tag)
);

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'Los documentos se guardan direccionados por contenido: _documentos tiene ' ||
    'el hash SHA-256 como clave primaria y los bytes van a ' ||
    'datos/documentos/<hash[:2]>/<hash><ext>. Subir dos veces el mismo ' ||
    'fichero no duplica ni fila ni disco. Los atributos del contenido ' ||
    '(nombre, tamaño, mime, estado) viven en _documentos y el "tag" vive en ' ||
    '_ejecucion_documento, porque el tag califica el uso y no el contenido: ' ||
    'el mismo fichero puede entrar como "crear" en una ejecución y como ' ||
    '"comprobante" en otra. La purga (migración siguiente) borrará los bytes ' ||
    'y marcará estado = purgado, pero nunca la fila: si se borrase el ' ||
    'metadato, cada purga rompería la trazabilidad que justifica todo esto. ' ||
    'Ni ejecucion_id ni hash llevan FOREIGN KEY declarada: es el patrón ' ||
    'dominante del repo para ejecucion_id (previ_transporte, ' ||
    'movimiento_bancario, _validaciones_disparadas, ticket, idea) y evita ' ||
    'repetir el bloqueo que causó la única FK que sí existe, la de _rechazos.',
    'Diseño acordado con el usuario. La FK de _rechazos contra _ejecuciones ' ||
    'obligó en la migración 013 a destruir y recrear esa tabla solo para ' ||
    'poder alterar la referenciada ("Dependency Error: Cannot alter entry ' ||
    '_ejecuciones because there are entries that depend on it"), y ' ||
    '_ejecuciones va a seguir evolucionando con el historial declarativo. ' ||
    'Sobre la necesidad de purga: el fichero de previsiones de transporte ' ||
    'ocupa 45 MB, así que archivar cada versión distinta no es gratis.',
    '014_documentos.sql'
);
