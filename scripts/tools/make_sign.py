"""A-board chalk texture for build_hem.py (Blender's Python has no PIL). Run with system python."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
FONT = 'C:/Windows/Fonts/segoeuib.ttf'
im = Image.new('RGB', (512, 768), (22, 24, 26)); dr = ImageDraw.Draw(im)
rng = np.random.default_rng(4)
for _ in range(4000):
    px, py = rng.integers(0, 512), rng.integers(0, 768); g = int(22 + rng.uniform(0, 12)); dr.point((int(px), int(py)), (g, g, g))
for txt, sz, yy, col in (('HẺM', 190, 210, (200, 255, 46)), ('streetwear', 52, 360, (236, 235, 228)),
                         ('mở cửa 9h - 22h', 40, 480, (236, 235, 228)), ('hàng mới mỗi thứ 6', 40, 540, (236, 235, 228))):
    fnt = ImageFont.truetype(FONT, sz); w_ = dr.textlength(txt, font=fnt); dr.text(((512 - w_) / 2, yy - sz * 0.75), txt, font=fnt, fill=col)
os.makedirs(os.path.join(ROOT, 'renders'), exist_ok=True)
im.save(os.path.join(ROOT, 'renders', 'aboard.png'))
