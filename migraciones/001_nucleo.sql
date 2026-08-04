-- 001_nucleo.sql
-- Entidades núcleo (persona, cliente, proyecto) y tablas de sistema
-- (_ejecuciones, _rechazos, _decisiones).

CREATE SEQUENCE seq_ejecuciones START 1;
CREATE SEQUENCE seq_rechazos START 1;
CREATE SEQUENCE seq_decisiones START 1;

CREATE TABLE persona (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR NOT NULL,
    email VARCHAR,
    rol VARCHAR,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE cliente (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR NOT NULL,
    nif VARCHAR,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE proyecto (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id UUID NOT NULL REFERENCES cliente(id),
    nombre VARCHAR NOT NULL,
    codigo VARCHAR,
    fecha_inicio DATE,
    fecha_fin DATE,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE _ejecuciones (
    id BIGINT PRIMARY KEY DEFAULT nextval('seq_ejecuciones'),
    carga VARCHAR NOT NULL,
    fichero VARCHAR NOT NULL,
    hash_fichero VARCHAR NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT current_timestamp,
    filas_leidas BIGINT NOT NULL DEFAULT 0,
    filas_ok BIGINT NOT NULL DEFAULT 0,
    filas_rechazadas BIGINT NOT NULL DEFAULT 0,
    estado VARCHAR NOT NULL,
    duracion DOUBLE
);

CREATE TABLE _rechazos (
    id BIGINT PRIMARY KEY DEFAULT nextval('seq_rechazos'),
    ejecucion_id BIGINT NOT NULL REFERENCES _ejecuciones(id),
    num_fila BIGINT NOT NULL,
    motivo VARCHAR NOT NULL,
    campo_implicado VARCHAR,
    contenido_raw VARCHAR
);

CREATE TABLE _decisiones (
    id BIGINT PRIMARY KEY DEFAULT nextval('seq_decisiones'),
    fecha TIMESTAMP NOT NULL DEFAULT current_timestamp,
    tipo VARCHAR NOT NULL,
    descripcion VARCHAR NOT NULL,
    evidencia VARCHAR,
    migracion_asociada VARCHAR
);
