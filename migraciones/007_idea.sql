-- 007_idea.sql
-- Ideas sueltas capturadas por una persona, opcionalmente vinculadas a un
-- cliente. Sin fichero intermedio: se insertan directamente por CLI.

CREATE TABLE idea (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id UUID NOT NULL REFERENCES persona(id),
    cliente_id UUID REFERENCES cliente(id),
    texto VARCHAR NOT NULL,
    estado VARCHAR NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'en_curso', 'descartada', 'hecha')),
    fecha DATE NOT NULL DEFAULT current_date,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'idea referencia persona (obligatorio, quién la apunta) y cliente ' ||
    '(opcional, por si la idea nace vinculada a un cliente concreto). No ' ||
    'referencia proyecto: a este nivel de captura rápida no se pide asociar ' ||
    'a un proyecto concreto. "estado" queda restringido por CHECK a ' ||
    'pendiente/en_curso/descartada/hecha, por defecto pendiente. "fecha" ' ||
    'por defecto es la fecha actual para no exigirla en una captura rápida.',
    'Petición explícita del usuario: quería ir cargando ideas sueltas desde ' ||
    'CLI sin fichero intermedio, con cliente opcional añadido a petición ' ||
    'suya tras la propuesta inicial.',
    '007_idea.sql'
);
