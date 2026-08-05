-- 010_modelo_carga_singularidad.sql
-- Sin DDL: registra el cambio de modelo de las cargas de fichero, que
-- sustituye a la "estrategia reemplazar" descrita en 009_previ_transporte.sql.

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_motor',
    'Las cargas de fichero dejan de hacer upsert fila a fila. Ahora declaran ' ||
    '"campos_singularidad": antes de insertar, se borran en bloque las ' ||
    'combinaciones de esos campos presentes en los datos entrantes, y se ' ||
    'inserta el bloque completo. Sin campos_singularidad la carga es ' ||
    'acumulativa pura. Esto sustituye a "estrategia": "reemplazar" ' ||
    '(migración 009), que era el caso particular de singularidad = ' ||
    '{origen_carga}. El upsert fila a fila queda solo para las acciones ' ||
    'puntuales del CLI conversacional (ticket editar, idea editar). Además, ' ||
    'una carga puede declarar "tabla_hall" + "transformacion_sql": la hall ' ||
    'es siempre foto completa (se vacía y recarga) y el SELECT de ' ||
    'transformación produce las filas finales, que se promueven al destino ' ||
    'sin salir del motor.',
    'Petición explícita del usuario: en cargas de fichero el upsert es raro; ' ||
    'lo natural es borrar por campos de singularidad (p.ej. centro+mes) y ' ||
    'cargar en bloque. Medido además que la escritura fila a fila era ' ||
    'inviable: 1.000 filas por SQL tardaban ~13s (degradación no lineal), ' ||
    'mientras que 500.000 filas vía DataFrame tardan ~0,35s. La carga real ' ||
    'de previ_transporte (497.383 filas) pasó de no terminar en 10 minutos a ' ||
    'completarse en 22s, y se verificó que reejecutarla deja 497.383 filas ' ||
    '(sustituye, no duplica).',
    '010_modelo_carga_singularidad.sql'
);
