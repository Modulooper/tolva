-- 019_respaldo.sql
-- Sin DDL: el respaldo no añade ni una tabla. Se registra aquí porque las
-- decisiones de formato y de retención no son obvias y son caras de revertir
-- el día que alguien tenga que restaurar de verdad.

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_motor',
    'El respaldo se escribe en parquet vía EXPORT DATABASE, no copiando el ' ||
    'fichero .duckdb. Cada snapshot es una carpeta fechada AAAAMMDD-HHMMSS con ' ||
    'el export (que incluye schema.sql y load.sql, o sea autocontenido), una ' ||
    'copia de la capa propia y un manifiesto.json con versión de DuckDB, ' ||
    'migraciones aplicadas y filas por tabla para poder verificar la ' ||
    'restauración. La restauración NO se automatiza: IMPORT DATABASE sobre un ' ||
    'almacén con datos lo pisa, así que el manifiesto lleva los pasos escritos ' ||
    'y el gatillo lo aprieta una persona, igual que db init no mueve nada y la ' ||
    'purga de documentos no se ejecuta sola.',
    'Medido sobre el almacén real: 190,8 MB de .duckdb contra 8,9 MB de ' ||
    'parquet+zstd, en 0,3 s. Pero lo que decide no es el tamaño sino la ' ||
    'longevidad: el formato de fichero de DuckDB puede cambiar entre versiones ' ||
    'mayores, que es la razón por la que requirements.txt fija duckdb<2.0, y un ' ||
    'binario de 200 MB que dentro de tres años no abre no es un respaldo. ' ||
    'Parquet lo lee cualquier cosa, incluido Excel o Power BI si hace falta ' ||
    'rescatar una tabla suelta sin montar nada.',
    '019_respaldo.sql'
);

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_motor',
    'Los documentos archivados NO entran en cada snapshot: van una sola vez a ' ||
    'un espejo incremental en <respaldo>/documentos, y la retención ' ||
    'abuelo-padre-hijo (7 diarios + 8 semanales + 12 mensuales) no los toca ' ||
    'nunca. Solo caducan los snapshots. El ajuste respaldo es además el único ' ||
    'de los cuatro sin valor por defecto, y su aviso es el inverso al de los ' ||
    'datos: vale si sale de la máquina (carpeta sincronizada) o al menos del ' ||
    'disco, así que estar dentro de OneDrive aquí es lo correcto y no el ' ||
    'problema.',
    'Los documentos están direccionados por su SHA-256, o sea que son ' ||
    'inmutables: meterlos dentro de cada copia guardaría N veces los mismos ' ||
    'bytes (47 MB por snapshot en la instalación donde se diseñó esto, contra ' ||
    '9 MB del export entero). Y son lo único genuinamente irrecuperable, ' ||
    'porque el resto de tablas se puede volver a cargar desde ellos: purgarlos ' ||
    'por retención sería el error que el sistema entero existe para evitar. ' ||
    'Lo de no darle valor por defecto sale de que el repo distribuye un hook ' ||
    'de fin de sesión en .claude/settings.json: con un defecto tipo ROOT/' ||
    'respaldo, cualquiera que clonase el framework se encontraría una carpeta ' ||
    'que no pidió, y encima con el respaldo pegado al original, que no protege ' ||
    'de nada.',
    '019_respaldo.sql'
);
