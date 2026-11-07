"""App-Icon zeichnen: dunkle Fläche, vier Balken (mittel, hoch, mittel, kurz) in Petrol.

Erzeugt packaging/icon.png (1024 px; PyInstaller macht daraus .icns, der Workflow das .ico für Windows).
Für die Webseite: `python packaging/make_icon.py ../vorleser-download/icon.png 1024` bzw.
`… ../vorleser-download/favicon.png 64 --tight` (ohne den macOS-Rand: im Browser-Tab füllt das Zeichen die Fläche).
Farben = Logo in der App (static/app.css `.brand .logo`) und auf der Webseite.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

BG = "#25292D"       # Anthrazit wie die dunkle Oberfläche der App
BAR = "#5FB7CB"      # Petrol, helle Variante (wie Akzent im Dunkelmodus)
S = 1024             # Raster; gezeichnet wird 4× größer und dann verkleinert (glatte Kanten)

# Raster wie macOS-Icons: Fläche 824 px mit 100 px Rand
TILE = (100, 100, 924, 924, 185)
BARS = [(332, 392, 632), (446, 292, 732), (560, 392, 632), (674, 452, 572)]   # x, oben, unten (Breite 64)
BAR_W, BAR_R = 64, 16


def draw(size: int, tight: bool = False) -> Image.Image:
    x0, y0, x1, y1, r = TILE
    big = 4 * size
    k = big / (x1 - x0) if tight else big / S          # tight: Kachel füllt das ganze Bild
    off = x0 if tight else 0
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = lambda v: (v - off) * k
    d.rounded_rectangle([f(x0), f(y0), f(x1), f(y1)], radius=r * k, fill=BG)
    for x, top, bottom in BARS:
        d.rounded_rectangle([f(x), f(top), f(x + BAR_W), f(bottom)], radius=BAR_R * k, fill=BAR)
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("icon.png")
    size = int(sys.argv[2]) if len(sys.argv) > 2 else S
    draw(size, tight="--tight" in sys.argv).save(out)
    print(f"{out} ({size} px)")
