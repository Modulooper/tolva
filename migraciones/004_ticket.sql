-- 004_ticket.sql
-- Tickets de gasto (viajes, hoteles, gasolina) atados a cliente y persona.

CREATE TABLE ticket (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id UUID NOT NULL REFERENCES cliente(id),
    persona_id UUID NOT NULL REFERENCES persona(id),
    concepto VARCHAR NOT NULL CHECK (concepto IN ('viajes', 'hoteles', 'gasolina')),
    descripcion VARCHAR,
    importe DOUBLE NOT NULL,
    fecha DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'ticket referencia tanto a cliente (para quién fue el gasto) como a persona ' ||
    '(quién lo generó), en vez de guardar esos datos como texto suelto. ' ||
    '"concepto" queda restringido por CHECK a viajes/hoteles/gasolina; ampliar ' ||
    'la lista en el futuro requiere una migración pequeña (ALTER ... DROP ' ||
    'CONSTRAINT / ADD CONSTRAINT), a cambio de evitar valores inconsistentes ' ||
    'desde ya.',
    'Petición explícita del usuario: tickets de viajes/hoteles/gasolina, con ' ||
    'importe, fecha y cliente; persona añadida a petición suya para saber ' ||
    'quién generó el gasto.',
    '004_ticket.sql'
);
