-- 009_previ_transporte.sql
-- Previsión de costes de transporte (TMS), cargada como foto completa: cada
-- ejecución de la carga borra la anterior (acotado por origen_carga) y
-- sustituye por la nueva. Ver migraciones/002_movimiento_bancario.sql para el
-- mismo razonamiento de no referenciar cliente/persona/proyecto.

CREATE TABLE previ_transporte (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_ut INTEGER NOT NULL,
    transportista VARCHAR NOT NULL,
    oracle_carrier_id INTEGER,
    oracle_carrier_site VARCHAR,
    coste_ventilado DOUBLE NOT NULL,
    codigo_dt INTEGER,
    albaran VARCHAR,
    management_unit INTEGER,
    descarga_comienzo DATE,
    nombre_cliente VARCHAR,
    contrato_oracle INTEGER,
    deleg_nombre VARCHAR,
    prime INTEGER,
    anio INTEGER,
    mes VARCHAR,
    origen_carga VARCHAR NOT NULL,
    extra_fields VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'previ_transporte no referencia cliente/persona/proyecto: nombre_cliente ' ||
    'y transportista son identificadores del sistema TMS de un dominio de ' ||
    'negocio distinto (transporte/logística), no clientes/personas de este ' ||
    'almacén. Comprobado con proceso analizar --campo nombre_cliente: 0 ' ||
    'coincidencias contra la tabla cliente existente, y confirmado ' ||
    'explícitamente por el usuario que no deben enlazarse. mes se guarda ' ||
    'como VARCHAR (no INTEGER) para no perder el cero a la izquierda ' ||
    '("03"), a diferencia de anio que sí es INTEGER. descarga_comienzo pierde ' ||
    'la hora al cargarse (el motor solo soporta cast a date, no a ' ||
    'timestamp) — decisión aceptada explícitamente por el usuario. La carga ' ||
    'usa estrategia "reemplazar" (ver motor/motor_etl.py _reemplazar): cada ' ||
    'ejecución borra las filas con origen_carga = nombre de la carga y ' ||
    'inserta la foto nueva completa, en vez de upsert por clave.',
    'Petición explícita del usuario: previsión de costes de transporte al ' ||
    'cierre, sustituyendo la foto completa en cada carga en vez de acumular ' ||
    'histórico por upsert.',
    '009_previ_transporte.sql'
);
