-- 017_descripcion_cargas.sql
-- Sin DDL: la descripción vive en la definición de la carga
-- (/cargas/<nombre>.json), no en el almacén. Se registra aquí porque cambia
-- lo que el sistema exige al dar de alta un proceso.

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_motor',
    'Toda carga declara una "descripcion" obligatoria (mínimo 40 caracteres) ' ||
    'que no es un rótulo sino el para qué: para qué se cargan estos datos, de ' ||
    'dónde sale el fichero, qué es una fila en el mundo real, qué debe ' ||
    'sustituir una versión corregida, y qué haría desconfiar al abrirlo. Es ' ||
    'lo que el JSON no puede decir: el mapping ya declara a qué columna va ' ||
    'cada cosa. El skill definir-carga la redacta a partir del perfilado y de ' ||
    'una tanda de preguntas directas, y el usuario la corrige — un campo que ' ||
    'pide "documenta aquí" se queda vacío, un borrador concreto se enmienda. ' ||
    'Va antes de elegir campos_singularidad a propósito: la pregunta "qué ' ||
    'sustituye un fichero corregido" es la singularidad contada en palabras, ' ||
    'así que si la descripción y la clave no dicen lo mismo, la contradicción ' ||
    'se ve sin ejecutar nada. Se muestra en "etl validar" y en "db diagrama", ' ||
    'donde explica el modelo tanto como las relaciones. El mismo criterio ' ||
    'rige la descripcion de las fichas de catálogo en crear-proceso.',
    'Propuesta del usuario: enfocar la documentación de cada carga y proceso ' ||
    'desde el para qué y el contenido, no desde lo descriptivo, generándola a ' ||
    'partir de lo que cuenta más preguntas directas, para que el contexto ' ||
    'resultante dé consistencia al trabajo posterior. Detectado además que ' ||
    '/cargas/*.json no tenía ningún campo de prosa: el catálogo describía la ' ||
    'tabla destino y _decisiones el porqué del esquema, pero de la carga en ' ||
    'sí no había una sola línea en ningún sitio.',
    '017_descripcion_cargas.sql'
);
