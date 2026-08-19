-- 021_estilo_salidas.sql
-- Sin DDL: el estilo vive en la definición de la carga (/cargas/<nombre>.json)
-- y lo aplica motor/salidas.py, no el almacén. Se registra aquí porque cambia
-- para qué sirve una salida.

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_motor',
    'Una salida xlsx puede declarar "estilo": dónde arranca la cabecera, ' ||
    'colores, bordes, autofiltro, anchos y formatos de número. Los anchos y ' ||
    'formatos van POR NOMBRE DE COLUMNA del SELECT y no por letra de Excel, ' ||
    'porque la letra depende de "columna_inicio" y se rompe en cuanto se ' ||
    'reordena el SELECT. Una salida con estilo se escribe siempre por ' ||
    'openpyxl y no por el COPY de DuckDB, que vuelca la rejilla y no expone ' ||
    'estilos: es más lento y lo paga solo quien lo pide, porque sin "estilo" ' ||
    'el camino no cambia. Los dos errores posibles son duros y no silenciosos: ' ||
    'un nombre de columna que no existe falla al generar (no se puede saber ' ||
    'antes, las columnas salen del SELECT), y declarar "estilo" sobre csv o ' ||
    'parquet lo rechaza "etl validar" sin ejecutar nada, porque el formato se ' ||
    'sabe por la extensión del fichero desde que se define la carga — mismo ' ||
    'sitio y mismo criterio que la operación "celda" sobre un CSV. El alcance ' ||
    'es corto a propósito: cubre lo que hace presentable una tabla y nada ' ||
    'más. Para un logotipo, totales al pie o varias hojas, el sitio es una ' ||
    'plantilla xlsx y no más claves aquí.',
    'Aportación externa de Mañi, sobre la primera instalación de Tolva fuera ' ||
    'de la máquina de desarrollo. Su motivo, en sus palabras: conseguir estilo ' ||
    'para facilitar la lectura al usuario final, y que el output se vea como ' ||
    'algo para ser leído por una persona y no para ser cargado en otro ' ||
    'sistema. Eso es lo que faltaba y no se veía: las salidas del framework ' ||
    'nacieron todas para la máquina —parquet y CSV para enlazar desde Power ' ||
    'BI, xlsx como volcado— y el caso de un fichero que sale hacia otra ' ||
    'persona (un cliente, una gestoría) no estaba cubierto. Sin esto, ese ' ||
    'fichero se retoca a mano cada mes, que es exactamente el trabajo que el ' ||
    'resto del framework existe para quitar. El parche llegó con sus pruebas ' ||
    'y su documentación, y se le cambiaron tres cosas antes de entrar: el ' ||
    'ejemplo del README usaba una tabla de negocio real (pasa al dominio de ' ||
    'ejemplo, y así además es ejecutable), la comprobación de csv/parquet ' ||
    'corría al ejecutar en vez de al validar, y el contador de pruebas.',
    '021_estilo_salidas.sql'
);
