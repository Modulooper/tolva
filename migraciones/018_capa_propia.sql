-- 018_capa_propia.sql
-- Sin DDL: la separación es de directorios y de resolución de rutas, no de
-- esquema. Se registra aquí porque cambia dónde vive lo que cada uno carga.

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_motor',
    'El framework y lo que cada uno carga con él se separan por directorio: el ' ||
    'núcleo son migraciones/, catalogo/ y cargas/ del repo, y la capa propia es ' ||
    'propio/ con la misma estructura dentro, fuera del control de versiones del ' ||
    'núcleo. motor/rutas.py resuelve las dos capas para db.migrar, catalogo, ' ||
    'cargas, historial y diagrama. Dos reglas: el núcleo se aplica primero, ' ||
    'porque una migración propia puede apoyarse en tablas del framework y nunca ' ||
    'al revés; y si coincide el nombre gana la capa propia, lo que permite ' ||
    'adaptar una ficha de catálogo sin bifurcar el repo. La separación es por ' ||
    'directorio y no por disciplina a propósito: los ficheros de una carga real ' ||
    'no pueden colarse en un commit del framework porque no están en su árbol.',
    'El objetivo es publicar el framework en abierto conservando privadas las ' ||
    'cargas reales. Un repositorio aparte no basta: el commit ae94a09 de este ' ||
    'mismo repo mezcla 17 ficheros de motor con 4 de negocio, y no por ' ||
    'descuido, sino porque la mejora del framework salió de trabajar con los ' ||
    'datos reales. Al mover previ_transporte a la capa propia salió además un ' ||
    'acoplamiento que no se veía: 012_validaciones.sql, migración del núcleo, ' ||
    'hacía ALTER TABLE previ_transporte, así que la instalación limpia de un ' ||
    'tercero se habría roto. Corregido: el núcleo solo toca sus propias tablas ' ||
    'y una tabla de la capa propia declara su ejecucion_id en su migración. La ' ||
    'suite lo fija con una prueba que falla si una migración del núcleo vuelve ' ||
    'a referenciar una tabla propia.',
    '018_capa_propia.sql'
);
