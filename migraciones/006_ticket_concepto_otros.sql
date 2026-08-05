-- 006_ticket_concepto_otros.sql
-- Amplía el CHECK de ticket.concepto para admitir 'otros', tal y como se
-- anticipaba en 004_ticket.sql. DuckDB no soporta ALTER TABLE ... DROP/ADD
-- CONSTRAINT, así que la tabla se recrea con el nuevo CHECK y se migran los
-- datos existentes.

DROP VIEW ticket_consumo;

CREATE TABLE ticket_new (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id UUID NOT NULL REFERENCES cliente(id),
    persona_id UUID NOT NULL REFERENCES persona(id),
    concepto VARCHAR NOT NULL CHECK (concepto IN ('viajes', 'hoteles', 'gasolina', 'otros')),
    descripcion VARCHAR,
    importe DOUBLE NOT NULL,
    fecha DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

INSERT INTO ticket_new SELECT * FROM ticket;

DROP TABLE ticket;

ALTER TABLE ticket_new RENAME TO ticket;

CREATE VIEW ticket_consumo AS
SELECT t.fecha, c.nombre AS cliente, p.nombre AS persona, t.concepto, t.descripcion, t.importe
FROM ticket t
JOIN cliente c ON c.id = t.cliente_id
JOIN persona p ON p.id = t.persona_id
ORDER BY t.fecha DESC;

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'ticket.concepto amplía su CHECK para admitir "otros" además de ' ||
    'viajes/hoteles/gasolina. DuckDB no soporta ALTER TABLE DROP/ADD ' ||
    'CONSTRAINT, así que la migración recrea la tabla (y la vista ' ||
    'ticket_consumo, que depende de ella) preservando los datos existentes.',
    'Petición explícita del usuario: gasto de material de oficina que no ' ||
    'encajaba en ninguno de los 3 conceptos originales.',
    '006_ticket_concepto_otros.sql'
);
