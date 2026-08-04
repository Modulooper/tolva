-- 003_ejecuciones_usuario.sql
-- Atribución de quién ejecutó cada carga. Sin autenticación: se rellena con
-- el login del sistema operativo en el momento de la ejecución. Semilla para
-- un eventual modo multiusuario futuro, no autenticación real hoy.

-- DuckDB no soporta añadir NOT NULL junto con ADD COLUMN sobre una tabla
-- existente; el DEFAULT ya garantiza que nunca quede a NULL en la práctica
-- (todo insert nuevo lo rellena explícitamente desde motor_etl.py).
ALTER TABLE _ejecuciones ADD COLUMN usuario VARCHAR DEFAULT 'desconocido';

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'Se añade "usuario" a _ejecuciones (login del SO, sin autenticación) como ' ||
    'atribución de quién ejecutó cada carga. Las filas previas a esta migración ' ||
    'quedan como ''desconocido'': no se reescribe el histórico con un valor ' ||
    'inventado. Es semilla para un eventual modo multiusuario futuro, no ' ||
    'implica autenticación real hoy.',
    'Petición explícita: "debería estar en el ADN del esquema" pensando en una ' ||
    'fase posterior multiusuario.',
    '003_ejecuciones_usuario.sql'
);
