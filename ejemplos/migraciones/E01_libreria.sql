-- E01_libreria.sql
-- Dominio de ejemplo: una librería. Inventado a propósito, y a propósito
-- lejos de cualquier modelo de trabajo real: si se pareciese, un dato dummy y
-- uno de verdad serían indistinguibles de un vistazo. Por eso también el
-- prefijo demo_, que los delata en cualquier SQL suelto, y las dimensiones
-- propias: los ejemplos NUNCA escriben en las tablas de la capa propia,
-- porque una vez mezclados no hay quien los separe.
--
-- Solo se aplica con `db migrar --con-ejemplos`. Sirve para dos cosas: que la
-- batería de pruebas tenga sujeto sin depender de ningún proceso real, y que
-- quien clone el repo pueda probar el framework entero (CRUD, carga de
-- fichero, singularidad, stops, vista de consumo) sin definir nada.
--
-- El prefijo E de la numeración evita confundir estas migraciones con las del
-- núcleo al leer `_migraciones`, donde conviven todas.

CREATE TABLE demo_cliente (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR NOT NULL,
    ciudad VARCHAR,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE demo_libro (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo VARCHAR NOT NULL,
    autor VARCHAR NOT NULL,
    genero VARCHAR NOT NULL
        CHECK (genero IN ('novela', 'ensayo', 'poesia', 'infantil')),
    precio DOUBLE NOT NULL CHECK (precio >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

-- La tabla de hechos. Tiene las dos puertas de entrada del framework a la
-- vez, que es justo lo que se quiere poder demostrar: se le dan altas por
-- CLI (`registro crear demo_venta`) y también la llena una carga de fichero
-- (`etl ejecutar demo_ventas`), acotada por origen_carga.
CREATE TABLE demo_venta (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    demo_cliente_id UUID REFERENCES demo_cliente(id),
    demo_libro_id UUID REFERENCES demo_libro(id),
    fecha DATE NOT NULL DEFAULT current_date,
    unidades INTEGER NOT NULL DEFAULT 1 CHECK (unidades > 0),
    importe DOUBLE NOT NULL CHECK (importe >= 0),
    canal VARCHAR NOT NULL DEFAULT 'tienda'
        CHECK (canal IN ('tienda', 'web', 'feria')),
    origen_carga VARCHAR,
    extra_fields VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    -- Igual que en la capa propia: lo declara su propia migración, porque el
    -- núcleo no puede alterar tablas que se crean después que él.
    ejecucion_id BIGINT
);

-- Tabla hall de la carga de ejemplo: la de trabajo, foto completa, que se
-- vacía y recarga en cada ejecución. El fichero trae el comprador y el título
-- por su nombre, no por id, así que la `transformacion_sql` de la carga hace
-- el join contra las dimensiones y lo que sale de ahí es lo que se promueve.
CREATE TABLE demo_hall_ventas (
    fecha DATE,
    cliente VARCHAR,
    titulo VARCHAR,
    unidades INTEGER,
    importe DOUBLE,
    canal VARCHAR,
    origen_carga VARCHAR,
    extra_fields VARCHAR
);

CREATE VIEW demo_venta_consumo AS
SELECT v.fecha, c.nombre AS cliente, c.ciudad, l.titulo, l.autor, l.genero,
       v.canal, v.unidades, v.importe
FROM demo_venta v
LEFT JOIN demo_cliente c ON c.id = v.demo_cliente_id
LEFT JOIN demo_libro l ON l.id = v.demo_libro_id
ORDER BY v.fecha DESC;

-- Datos dummy sembrados aquí y no en un fichero semilla aparte: así son
-- deterministas, viajan con la migración y no pueden desincronizarse del
-- esquema que acaban de crear.
INSERT INTO demo_cliente (nombre, ciudad) VALUES
    ('Ateneo Mercantil', 'Valencia'),
    ('Colegio San Blas', 'Zaragoza'),
    ('Librería Rayuela', 'Gijón'),
    ('Biblioteca Municipal', 'Cuenca');

INSERT INTO demo_libro (titulo, autor, genero, precio) VALUES
    ('El jardín de arena', 'Marta Olivares', 'novela', 19.50),
    ('Cuadernos de invierno', 'Iván Serrano', 'ensayo', 24.00),
    ('Once maneras de callar', 'Lucía Benavent', 'poesia', 14.90),
    ('El topo que perdió el mapa', 'Rosa Iturbe', 'infantil', 11.25),
    ('La costumbre de mirar', 'Marta Olivares', 'ensayo', 21.00);

INSERT INTO demo_venta (demo_cliente_id, demo_libro_id, fecha, unidades, importe, canal)
SELECT c.id, l.id, v.fecha, v.unidades, v.importe, v.canal
FROM (VALUES
    ('Ateneo Mercantil',     'El jardín de arena',         DATE '2026-03-02',  3,  58.50, 'tienda'),
    ('Ateneo Mercantil',     'La costumbre de mirar',      DATE '2026-03-11',  1,  21.00, 'web'),
    ('Colegio San Blas',     'El topo que perdió el mapa', DATE '2026-03-04', 25, 281.25, 'tienda'),
    ('Colegio San Blas',     'Once maneras de callar',     DATE '2026-04-08',  2,  29.80, 'tienda'),
    ('Librería Rayuela',     'Cuadernos de invierno',      DATE '2026-04-15',  4,  96.00, 'feria'),
    ('Librería Rayuela',     'El jardín de arena',         DATE '2026-05-06',  2,  39.00, 'feria'),
    ('Biblioteca Municipal', 'La costumbre de mirar',      DATE '2026-05-20',  6, 126.00, 'web'),
    ('Biblioteca Municipal', 'Once maneras de callar',     DATE '2026-05-21',  1,  14.90, 'web')
) AS v(cliente, titulo, fecha, unidades, importe, canal)
JOIN demo_cliente c ON c.nombre = v.cliente
JOIN demo_libro l ON l.titulo = v.titulo;

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_esquema',
    'El dominio de ejemplo es una librería, deliberadamente lejos del modelo ' ||
    'de trabajo de quien monta la instalación. Si demo_cliente se pareciese ' ||
    'a su tabla de clientes, un ' ||
    'dato dummy y uno real serían indistinguibles al leer una consulta, y en ' ||
    'un almacén con las dos cosas eso es una trampa. Por lo mismo los ' ||
    'ejemplos tienen dimensiones propias (demo_cliente, demo_libro) y nunca ' ||
    'insertan en las dimensiones reales de la instalación: una vez mezclados ' ||
    'los dummies con clientes y personas de verdad, no hay quien los separe. ' ||
    'demo_venta lleva a la vez CRUD por CLI y carga de fichero acotada por ' ||
    'origen_carga, porque el ejemplo tiene que poder demostrar las dos ' ||
    'puertas de entrada del framework, no solo una.',
    'Petición explícita del usuario: datos dummy para pruebas y para que un ' ||
    'tercero pueda probar el framework, mantenidos ocultos a efectos del ' ||
    'chat y las visualizaciones. Antes de esto la batería de pruebas usaba ' ||
    'ticket e idea como sujeto, lo que impedía sacarlos del núcleo.',
    'E01_libreria.sql'
);
