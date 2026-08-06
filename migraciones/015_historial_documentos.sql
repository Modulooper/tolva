-- 015_historial_documentos.sql
-- Sin DDL: _documentos ya nació en la migración 014 con "estado" y
-- "fecha_purga". Esta migración registra la política de retención, que vive
-- en las definiciones (/cargas/*.json y /catalogo/*.json), no en el esquema.

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_motor',
    'Cada proceso declara cuánto conserva de sus documentos con un bloque ' ||
    '"historial": "siempre" (por defecto), {"tipo":"ficheros","cantidad":N} o ' ||
    '{"tipo":"anios","cantidad":N}, más un "tags_exentos" opcional. Va en ' ||
    '/cargas/<nombre>.json para las cargas y en /catalogo/<tabla>.json para ' ||
    'las entidades del CLI. Dos reglas hacen que purgar sea seguro: (1) se ' ||
    'vacían los bytes y se marca estado = purgado, pero la fila de ' ||
    '_documentos no se borra nunca, así que se sigue sabiendo de qué fichero ' ||
    'salió cada dato aunque ya no se pueda abrir; (2) un documento se ' ||
    'conserva si lo conserva ALGÚN proceso, porque el mismo hash puede estar ' ||
    'vinculado a una carga con historial corto y a un ticket con historial ' ||
    '"siempre", y decidir proceso a proceso se llevaría por delante el ' ||
    'segundo. El valor por defecto es "siempre" a propósito: nadie pierde ' ||
    'nada por no declarar historial, y los justificantes de gasto no ' ||
    'desaparecen por descuido. La purga va en seco salvo que se pida ' ||
    '--aplicar, y cuando se aplica queda registrada como una ejecución más.',
    'Petición del usuario: poder medir el historial "en tiempo o número de ' ||
    'ficheros" (conservar los últimos 10 ficheros de un proceso, o los ' ||
    'últimos 3 años). El coste real que lo motiva: un solo fichero de ' ||
    'previsiones ocupa 45 MB en el almacén de documentos. El usuario aclara ' ||
    'después que ese tamaño era una prueba de límites y no lo habitual, por ' ||
    'lo que el defecto conservador ("siempre") no supone un problema de ' ||
    'espacio en el uso normal.',
    '015_historial_documentos.sql'
);
