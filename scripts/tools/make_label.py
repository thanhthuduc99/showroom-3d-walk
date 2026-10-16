"""Example asset for build_scene.py: fictional whiskey labels (no real brand), assets/tex/label_<variant>.png,
700 x 900 px = 70 x 90 mm. Fonts: Georgia from FONT_DIR (default C:/Windows/Fonts). Make your own labels the same way:
never copy a real brand's label.
usage: python tools/make_label.py"""
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[1] / "assets" / "tex"
FONT_DIR = Path(os.environ.get("FONT_DIR", "C:/Windows/Fonts"))
FONT, FONT_B, FONT_I = (str(FONT_DIR / f) for f in ("georgia.ttf", "georgiab.ttf", "georgiai.ttf"))
VARIANTS = {"cream": ((236, 226, 202), (46, 34, 24), (150, 92, 40)),
            "kraft": ((196, 160, 112), (38, 26, 16), (90, 48, 20))}


def label(name, paper, ink, accent):
    w, h = 700, 900
    rng = np.random.default_rng(3)
    base = np.array(paper, np.float32) + rng.normal(0, 5, (h, w, 1))          # paper fibre
    im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    d = ImageDraw.Draw(im)
    d.rectangle((26, 26, w - 27, h - 27), outline=ink, width=3)
    d.rectangle((40, 40, w - 41, h - 41), outline=accent, width=1)

    def centre(y, text, size, font=FONT, fill=ink, spacing=0):
        f = ImageFont.truetype(font, size)
        tw = d.textlength(text, font=f) + spacing * (len(text) - 1)
        x = (w - tw) / 2
        for ch in text:
            d.text((x, y), ch, font=f, fill=fill)
            x += d.textlength(ch, font=f) + spacing

    centre(96, "EST. 2026", 30, spacing=8, fill=accent)
    centre(170, "HOLLOW", 104, FONT_B, spacing=6)
    centre(290, "OAK", 104, FONT_B, spacing=18)
    d.line((150, 430, w - 150, 430), fill=accent, width=2)
    centre(458, "Single Barrel", 46, FONT_I)
    centre(520, "SMALL BATCH WHISKEY", 28, spacing=4)
    centre(640, "aged in charred oak", 30, FONT_I, fill=accent)
    centre(760, "No. 12   ·   45% ALC/VOL   ·   700 ml", 24, spacing=1)
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / f"label_{name}.png")


for k, v in VARIANTS.items():
    label(k, *v)
print("labels ok")
