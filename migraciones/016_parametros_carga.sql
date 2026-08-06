-- 016_parametros_carga.sql
-- Los valores que se piden al subir un fichero quedan registrados en la
-- ejecución: saber que esa carga se hizo "para la tienda de Gran Vía" es
-- tanta trazabilidad como saber de qué fichero salió.

ALTER TABLE _ejecuciones ADD COLUMN parametros VARCHAR;

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_motor',
    'Una carga puede declarar "parametros": valores que no vienen dentro del ' ||
    'fichero y se piden al ejecutarla (la tienda de la que viene este fichero ' ||
    'de pedidos, un comentario). Cada parámetro declara si es obligatorio y, ' ||
    'con "valores_de", si su valor se resuelve contra una tabla existente ' ||
    '(lista cerrada, resolviendo por nombre como hace ticket crear --cliente) ' ||
    'o es texto libre. Llegan a las filas por el mapping, con una operación ' ||
    'nueva {"tipo":"parametro","nombre":...}, en vez de por un canal aparte: ' ||
    'así heredan el mismo tratamiento que el resto de columnas. Los valores ' ||
    'contestados se guardan en _ejecuciones.parametros como JSON. NO se ' ||
    'tocan las reglas de idempotencia: el motor sigue omitiendo un fichero ' ||
    'cuyo hash ya se procesó OK, aunque los parámetros sean distintos.',
    'Petición del usuario: un mismo formato de fichero de pedidos (fecha, ' ||
    'importe, producto) que llega de tiendas distintas, donde la tienda no ' ||
    'está dentro del fichero. El usuario descarta expresamente meterse por ' ||
    'ahora con la identidad por hash, asumiendo que dos ficheros idénticos de ' ||
    'tiendas distintas exigirían --forzar en el segundo. Confirma además que ' ||
    'la singularidad vendrá casi siempre de uno de estos valores más alguna ' ||
    'columna del fichero (fecha, producto), por lo que la validación avisa si ' ||
    'un parámetro no aparece en campos_singularidad.',
    '016_parametros_carga.sql'
);
