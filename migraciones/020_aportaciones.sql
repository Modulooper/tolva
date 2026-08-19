-- 020_aportaciones.sql
-- Sin DDL: la detección vive en motor/aportaciones.py y en el hook que el
-- repositorio distribuye, no en el almacén. Se registra aquí porque cambia lo
-- que el sistema hace cuando alguien toca el framework.

INSERT INTO _decisiones (tipo, descripcion, evidencia, migracion_asociada) VALUES (
    'diseño_motor',
    'Escribir fuera de propio/ dispara un aviso: un hook PostToolUse se lo ' ||
    'devuelve al asistente en el momento, y "db nucleo" lo resume a demanda y ' ||
    'en el respaldo de fin de sesión. El aviso no decide, plantea las dos ' ||
    'salidas posibles —si es un proceso suyo va a propio/, y si es una ' ||
    'capacidad del framework hay que mandarla— porque desde la ruta no se ' ||
    'distinguen. AVISA Y NO IMPIDE: se descarta un PreToolUse que deniegue la ' ||
    'escritura, porque una heurística que falle dejaría a un tercero sin poder ' ||
    'editar motor/ sin entender por qué, y eso es peor que una divergencia; ' ||
    'con git de por medio, avisar después no pierde nada. Y NO ENVÍA NADA: ' ||
    'detecta, avisa y como mucho prepara un .patch, pero subirlo lo decide una ' ||
    'persona, porque un diff del núcleo puede arrastrar nombres de columna, ' ||
    'SQL o fixtures con datos de negocio dentro. El aviso se apaga con ' ||
    '"mantenedor": true en config.local.json, que es de cada máquina y ya está ' ||
    'fuera del control de versiones; a mano y no con db init, que es el ' ||
    'comando de las cuatro rutas y no debe convertirse en el comando de todo. ' ||
    'La comprobación va ANTES del corte por "no hay respaldo configurado" en ' ||
    'db respaldar: son cosas independientes, y quien no respalda es quien más ' ||
    'falta le hace enterarse de que su núcleo ha divergido.',
    'La primera instalación ajena (agosto 2026) extendió el framework en su ' ||
    'primera sesión: le pidieron poder configurar el formato de una salida y ' ||
    'el asistente añadió un bloque al JSON de la carga y adaptó el generador. ' ||
    'La forma era la correcta —declarativo en la definición, motor ' ||
    'determinista— pero la capacidad se quedó en ese clon, donde muere, y su ' ||
    'copia del núcleo divergió de la publicada sin que nadie lo supiera. De ' ||
    'ahí las dos observaciones que fijan el diseño: cuando la interfaz del ' ||
    'framework es un asistente capaz de modificar el propio framework, cada ' ||
    'instalación genera cambios de núcleo, y el argumento que hace que se ' ||
    'manden no es el altruismo sino que sin rama aparte el próximo git pull ' ||
    'da un conflicto. El caso mayoritario además no será la aportación sino el ' ||
    'error: un proceso de negocio escrito en el núcleo, que hasta ahora solo ' ||
    'se cazaba en las migraciones (prueba del hito 26) y en el resto del árbol ' ||
    'no lo miraba nadie.',
    '020_aportaciones.sql'
);
