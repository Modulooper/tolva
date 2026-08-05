-- 008_idea_consumo.sql
-- Vista de consumo para idea, mismo patrón que movimiento_bancario_consumo y
-- ticket_consumo (005_vistas_consumo.sql): columnas curadas, sin IDs
-- internos, pensada para exportarse con "etl exportar".

CREATE VIEW idea_consumo AS
SELECT i.fecha, p.nombre AS persona, c.nombre AS cliente, i.texto, i.estado
FROM idea i
JOIN persona p ON p.id = i.persona_id
LEFT JOIN cliente c ON c.id = i.cliente_id
ORDER BY i.fecha DESC;

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'idea_consumo hace LEFT JOIN con cliente (a diferencia de ticket_consumo, ' ||
    'que usa JOIN) porque cliente_id es opcional en idea: una idea sin ' ||
    'cliente vinculado debe seguir apareciendo en la vista, con esa columna ' ||
    'vacía.',
    'Petición explícita del usuario: exportar ideas a Power BI/Excel igual ' ||
    'que tickets y movimientos bancarios.',
    '008_idea_consumo.sql'
);
