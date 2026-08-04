-- 005_vistas_consumo.sql
-- Vistas de consumo: columnas curadas y con nombres amigables para
-- Excel/Power BI, sin IDs internos ni columnas de sistema.

CREATE VIEW movimiento_bancario_consumo AS
SELECT fecha_ejecucion, fecha_valor, concepto, importe, saldo
FROM movimiento_bancario
ORDER BY fecha_ejecucion DESC, fecha_valor DESC;

CREATE VIEW ticket_consumo AS
SELECT t.fecha, c.nombre AS cliente, p.nombre AS persona, t.concepto, t.descripcion, t.importe
FROM ticket t
JOIN cliente c ON c.id = t.cliente_id
JOIN persona p ON p.id = t.persona_id
ORDER BY t.fecha DESC;

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'Las vistas de consumo exponen columnas curadas con nombres amigables ' ||
    '(cliente, persona en vez de cliente_id/persona_id) y sin columnas de ' ||
    'sistema (id, created_at, updated_at, extra_fields, origen_carga), pensadas ' ||
    'para exportarse con "etl exportar" y consumirse desde Excel/Power BI.',
    'Componente 6 de la especificación del proyecto.',
    '005_vistas_consumo.sql'
);
