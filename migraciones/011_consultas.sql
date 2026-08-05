-- 011_consultas.sql
-- Registro de consultas al almacén: las conversacionales (db consultar) y
-- las extracciones (etl exportar). Tabla de sistema, como _ejecuciones.

CREATE SEQUENCE seq_consultas START 1;

CREATE TABLE _consultas (
    id BIGINT PRIMARY KEY DEFAULT nextval('seq_consultas'),
    sql VARCHAR NOT NULL,
    origen VARCHAR NOT NULL CHECK (origen IN ('consulta', 'export')),
    objeto VARCHAR,
    filas BIGINT,
    duracion DOUBLE,
    estado VARCHAR NOT NULL CHECK (estado IN ('OK', 'ERROR')),
    error VARCHAR,
    usuario VARCHAR NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT current_timestamp
);

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    '_consultas registra qué se consulta y se extrae del almacén, para saber ' ||
    'qué tablas/vistas se usan de verdad, qué consultas se repiten (candidatas ' ||
    'a vista de consumo) y cuáles tardan. NO se usa para proponer índices: ' ||
    'medido sobre previ_transporte (497.383 filas), un índice no mejora nada ' ||
    '(consulta de punto 0,3ms igual con y sin índice; agregado 5,1ms igual) e ' ||
    'incluso empeora el filtro por texto (1,8ms -> 4,4ms). DuckDB es columnar ' ||
    'y mantiene zonemaps automáticos en todas las columnas, así que el ' ||
    'escaneo ya es rápido; los índices ART sirven para lookups muy selectivos ' ||
    'y restricciones UNIQUE, y penalizan la escritura (mal negocio en tablas ' ||
    'que se recargan enteras). El análisis de las consultas usa el parser de ' ||
    'DuckDB (json_serialize_sql) para extraer las tablas referenciadas, no ' ||
    'expresiones regulares, igual que el parseo de fechas se resuelve por ' ||
    'evidencia y no por adivinación.',
    'Petición del usuario: registrar consultas para proponer índices. La ' ||
    'medición desmontó la premisa de los índices, así que el registro se ' ||
    'reorientó a detectar uso real, consultas recurrentes y lentitud.',
    '011_consultas.sql'
);
