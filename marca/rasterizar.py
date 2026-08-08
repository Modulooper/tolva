"""Rasteriza la marca Tolva a PNG. Dibuja las mismas primitivas que el SVG
(rectangulos, anillos y el galon de la v con union bevel) y superescala."""
import math
from PIL import Image, ImageDraw

INK = (23, 26, 31)
AMBER = (217, 119, 6)
WHITE = (255, 255, 255)
SS = 4  # supermuestreo


def chevron(p0, apex, p2, w):
    """Contorno del trazo de un galon con union bevel abajo y remates a hueso."""
    h = w / 2.0
    d1 = (apex[0] - p0[0], apex[1] - p0[1])
    l1 = math.hypot(*d1)
    u1 = (d1[0] / l1, d1[1] / l1)
    n1 = (h * u1[1], -h * u1[0])          # lado interior del brazo izquierdo

    d2 = (p2[0] - apex[0], p2[1] - apex[1])
    l2 = math.hypot(*d2)
    u2 = (d2[0] / l2, d2[1] / l2)
    n2 = (h * u2[1], -h * u2[0])          # lado interior del brazo derecho

    sin_half = abs(d1[0]) / l1            # semiangulo respecto a la vertical
    miter = h / sin_half

    return [
        (p0[0] - n1[0], p0[1] - n1[1]),           # remate izq, exterior
        (apex[0] - n1[0], apex[1] - n1[1]),       # bevel, esquina izq
        (apex[0] - n2[0], apex[1] - n2[1]),       # bevel, esquina der
        (p2[0] - n2[0], p2[1] - n2[1]),           # remate der, exterior
        (p2[0] + n2[0], p2[1] + n2[1]),           # remate der, interior
        (apex[0], apex[1] - miter),               # muesca interior del vertice
        (p0[0] + n1[0], p0[1] + n1[1]),           # remate izq, interior
    ]


def dibujar(d, s, ox, oy, con_letras=True):
    def T(pts):
        return [(ox + x * s, oy + y * s) for x, y in pts]

    def rect(x0, y0, x1, y1, c):
        d.rectangle(T([(x0, y0), (x1, y1)]), fill=c)

    def anillo(cx, cy, r_out, r_in):
        d.ellipse(T([(cx - r_out, cy - r_out), (cx + r_out, cy + r_out)]), fill=INK)
        d.ellipse(T([(cx - r_in, cy - r_in), (cx + r_in, cy + r_in)]), fill=WHITE)

    if con_letras:
        rect(19.25, 14, 28.75, 78, INK)      # asta de la T
        rect(2, 14, 46, 23.5, INK)           # brazo de la T
        rect(114, 14, 123.5, 78, INK)        # l
        rect(231.5, 34, 241, 78, INK)        # asta de la a
        anillo(72, 56, 22, 12.5)             # o
        anillo(219, 56, 22, 12.5)            # cuenco de la a
        d.polygon(T(chevron((139, 34), (161, 75.7), (183, 34), 9.5)), fill=AMBER)
    else:
        d.polygon(T(chevron((9, 10), (32, 54), (55, 10), 10)), fill=AMBER)


def render(path, w, h, s, ox, oy, con_letras=True):
    img = Image.new("RGB", (w * SS, h * SS), WHITE)
    dibujar(ImageDraw.Draw(img), s * SS, ox * SS, oy * SS, con_letras)
    img.resize((w, h), Image.LANCZOS).save(path)
    print(f"{path}  {w}x{h}")


base = r"C:\Users\nacho\OneDrive - modulooper.com\Tolva\marca\png"

# Social preview de GitHub: 1280x640, marca centrada y lejos de los bordes.
s = 760 / 239.0
render(rf"{base}\tolva-social-preview-1280x640.png", 1280, 640,
       s, 260 - 2 * s, (640 - 64 * s) / 2 - 14 * s)

# Logotipo con plancha blanca y area de respeto (proporcion 327x152).
for ancho in (1200, 600):
    s = ancho / 327.0
    render(rf"{base}\tolva-logotipo-{ancho}.png", ancho, round(152 * s),
           s, 42 * s, 30 * s)

# Isotipo cuadrado, para avatar.
for lado in (512, 256):
    s = lado / 64.0
    render(rf"{base}\tolva-isotipo-{lado}.png", lado, lado, s, 0, 0, con_letras=False)
