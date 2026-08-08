# Marca

La marca es la palabra, con la `v` en ámbar. Nada más.

La `v` va más ancha que una v normal y termina en corte plano en vez de en
punta: es la boquilla de la tolva. Quien lo vea, lo ve; quien no, lee una
palabra bien dibujada. El significado lo pone el nombre, que para eso se
eligió.

El **logotipo** es la palabra completa. El **isotipo** es esa misma `v`
ampliada — la misma forma, no un dibujo aparte — para donde no cabe la palabra:
favicon, avatar, cualquier caja cuadrada.

## Por qué no hay icono

Se probaron trece formas de meter una referencia a lo conversacional en la
marca: un globo de diálogo dentro de la boca de la `v`, una hoja cayendo con
él, puntos de escritura, raya de diálogo, cursor de prompt, la `o` sustituida
por un bocadillo, el contrapunzón de la `o` con forma de bocadillo, la `v`
fundida con el bocadillo. Ninguna se sostenía.

El patrón que salió en todas: o el icono se mete dentro de la `v` y compite
con la letra, o se muda a otra letra y entonces el isotipo se queda sin él. Y
en todos los casos añadía una segunda idea a una marca que ya tenía una.

**No añadas un icono.** Si dentro de un año parece que falta algo, es esto lo
que hay que releer antes de volver a intentarlo.

## Ficheros

| Fichero | Para qué |
|---|---|
| `tolva-logotipo.svg` | Marca principal, fondo claro |
| `tolva-logotipo-oscuro.svg` | Marca principal, fondo oscuro |
| `tolva-logotipo-mono.svg` | Una sola tinta, hereda `currentColor` |
| `tolva-logotipo-fondo-blanco.svg` | Con plancha blanca y área de respeto incluida. Para README de GitHub y sitios donde no controlas el fondo |
| `tolva-isotipo.svg` | Solo la v, fondo claro |
| `tolva-isotipo-oscuro.svg` | Solo la v, fondo oscuro |
| `tolva-isotipo-mono.svg` | Solo la v, `currentColor` |
| `favicon.svg` | Trazo engordado para 16–32 px. Cambia solo con `prefers-color-scheme` |

Los `-mono` heredan `currentColor`: hay que incrustarlos inline en el HTML,
con `<img>` no funcionan.

En `png/` hay rásters sobre blanco para donde no se admite SVG:

| Fichero | Para qué |
|---|---|
| `tolva-social-preview-1280x640.png` | La tarjeta de GitHub (Settings → Social preview). Marca al 59 % del ancho y a 260 px de los bordes, que los recortan |
| `tolva-logotipo-1200.png` · `-600.png` | Logotipo con plancha y área de respeto |
| `tolva-isotipo-512.png` · `-256.png` | Cuadrado, para avatar |

Se generan con el script de `marca/rasterizar.py`: dibuja las mismas primitivas
que el SVG y superescala ×4. Si cambia la marca, hay que volver a lanzarlo.

## Color

| | Claro | Oscuro |
|---|---|---|
| Tinta (letras) | `#171A1F` | `#F2EFE9` |
| Ámbar (la v) | `#D97706` | `#F0A83C` |

Dos tonos y ya. El ámbar solo toca la `v`: es lo único que se sale de la tinta,
y por eso se identifica sola cuál de las cinco letras es la marca.

## Letras

El logotipo son curvas, no texto: no depende de ninguna fuente instalada y no
hace falta convertir nada para llevarlo a imprenta. Es una geométrica dibujada
a medida (grotesca de trazo constante, 9,5 unidades sobre altura de ascendente
64, «a» de un solo piso).

Si hace falta texto acompañando a la marca (claim, subtítulo), la pila
razonable es Inter → Segoe UI → system-ui.

### Interletraje

El ritmo lo marca la T: el hueco que se ve entre su palo vertical y la o son
21,25 unidades, y ese es el blanco de referencia. El techo de la T casi toca la
o (4 unidades) y da igual — lo que el ojo lee ahí es el hueco de debajo del
brazo, no el borde de la barra.

Los pares en minúscula van medidos borde a borde:

| Par | Hueco | Por qué |
|---|---|---|
| o‑l | 20 | curva a recta, prácticamente el nominal |
| l‑v | 11 | la diagonal ya abre blanco hacia abajo |
| v‑a | 10 | ídem, y encima la a es curva |

Los 11 y 10 parecen poco escritos así, pero el hueco de la v crece 22 unidades
de la altura de x a la línea base: medido a media altura son los mismos ~21 que
en el resto. Con los tres pares a 21 exactos la v se queda flotando en mitad de
la palabra — está probado.

## Reglas

- **Área de respeto**: la altura de la x (44 unidades del `viewBox`) por todos
  los lados en el logotipo; el ancho de un brazo de la v en el isotipo.
- **Tamaño mínimo**: 150 px de ancho para el logotipo, 24 px para el isotipo.
  Por debajo de eso, `favicon.svg`.
- **No** pongas otra letra en ámbar ni la `v` en tinta.
- **No** apliques `letter-spacing` ni reescales la palabra en horizontal. El
  interletraje está resuelto par a par y no es uniforme.
- **No** rehagas la palabra con una fuente parecida. Las curvas son las que son.
