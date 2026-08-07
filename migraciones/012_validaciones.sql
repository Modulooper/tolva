-- 012_validaciones.sql
-- Stops y alarmas: registro de lo que se dispara en cada ejecución, e
-- identificador de carga en las tablas de destino para poder deshacer o
-- inspeccionar por proceso de carga.

CREATE SEQUENCE seq_validaciones_disparadas START 1;

CREATE TABLE _validaciones_disparadas (
    id BIGINT PRIMARY KEY DEFAULT nextval('seq_validaciones_disparadas'),
    ejecucion_id BIGINT,
    origen VARCHAR NOT NULL,
    nombre VARCHAR NOT NULL,
    tipo VARCHAR NOT NULL CHECK (tipo IN ('stop', 'alarma')),
    mensaje VARCHAR NOT NULL,
    afectadas BIGINT NOT NULL,
    detalle VARCHAR,
    fecha TIMESTAMP NOT NULL DEFAULT current_timestamp
);

-- Aquí había un `ALTER TABLE movimiento_bancario ADD COLUMN ejecucion_id`.
-- Se retiró al mover esa tabla a la capa propia (hito 25): el núcleo no puede
-- alterar tablas que no sabe si existen, y en una instalación limpia de un
-- tercero esta migración reventaba. La columna la declara ahora la migración
-- que crea la tabla. Ver motor/rutas.py y la prueba
-- `test_el_nucleo_no_referencia_tablas_de_la_capa_propia`.

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'Las cargas y las entidades del CLI pueden declarar validaciones: un ' ||
    'SELECT que, si devuelve filas, se dispara. "stop" aborta el proceso y lo ' ||
    'deja como no OK; "alarma" deja el aviso y el proceso continúa. Las filas ' ||
    'devueltas son el detalle que se muestra, así que la consulta selecciona ' ||
    'lo que identifica el problema. Una validación que no se puede ejecutar ' ||
    '(SQL mal formado, tabla inexistente) es error duro, no se da por ' ||
    'superada: una comprobación que nunca comprobó nada no puede contar como ' ||
    'válida. Cuando un stop aborta una carga, el destino no se toca pero la ' ||
    'hall y el registro de la ejecución SÍ se conservan (commit), para poder ' ||
    'investigar el fichero rechazado con db consultar; si se quiere limpiar, ' ||
    'se declara explícitamente una acción con momento "al_fallar". ' ||
    'ejecucion_id se rellena solo en las tablas que tengan esa columna, y da ' ||
    'una palanca de borrado por proceso de carga independiente de los campos ' ||
    'de negocio.',
    'Petición explícita del usuario: stops y alarmas como SELECT que corta o ' ||
    'avisa, con detalle de las filas implicadas, acciones dependientes según ' ||
    'el resultado, y un id único por proceso de carga para poder borrar por ' ||
    'él con facilidad.',
    '012_validaciones.sql'
);
