-- 002_movimiento_bancario.sql
-- Ledger de movimientos bancarios a partir de los extractos descargados del banco.

CREATE TABLE movimiento_bancario (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fecha_ejecucion DATE NOT NULL,
    fecha_valor DATE NOT NULL,
    concepto VARCHAR NOT NULL,
    importe DOUBLE NOT NULL,
    saldo DOUBLE NOT NULL,
    origen_carga VARCHAR NOT NULL,
    extra_fields VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    UNIQUE (fecha_ejecucion, fecha_valor, concepto, importe, saldo)
);

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'movimiento_bancario no referencia a cliente ni proyecto: es un asiento bruto ' ||
    'del libro bancario (ledger), no una operación de negocio atada a un cliente o ' ||
    'proyecto concreto. La clave de upsert (fecha_ejecucion, fecha_valor, concepto, ' ||
    'importe, saldo) sustituye a un id de movimiento porque el extracto del banco no ' ||
    'trae ninguno; "saldo" (acumulado) es lo que distingue movimientos idénticos en ' ||
    'fecha+concepto+importe el mismo día.',
    'Extracto real de banco: dos filas con la misma fecha, concepto e importe, ' ||
    'diferenciadas solo por el saldo.',
    '002_movimiento_bancario.sql'
);
