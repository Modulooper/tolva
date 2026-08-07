-- 001_nucleo.sql
-- Tablas de sistema: _ejecuciones, _rechazos, _decisiones. Nada más.
--
-- Aquí estuvieron persona, cliente y proyecto, y se fueron a la capa propia
-- en el hito 26. Eran un modelo de consultoría —quién hace el trabajo, para
-- quién, en el marco de qué— y venían de serie en la instalación de
-- cualquiera: quien quisiera usar esto para su bodega o su gimnasio heredaba
-- un vocabulario que no es el suyo. El framework no opina sobre qué entidades
-- tiene tu negocio; solo sobre cómo se declaran, se cargan y se rastrean.
--
-- Lo que queda es lo que sí es del framework: el diario de ejecuciones, los
-- rechazos y el registro de decisiones.

CREATE SEQUENCE seq_ejecuciones START 1;
CREATE SEQUENCE seq_rechazos START 1;
CREATE SEQUENCE seq_decisiones START 1;

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
