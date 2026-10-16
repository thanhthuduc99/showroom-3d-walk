"""Grid of images with their names: python tools/contact_sheet.py <out.png> <cols> <cell_width> img1 img2 ...  (globs ok)"""
import glob
import sys

from PIL import Image, ImageDraw

out, cols, cw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
files = [f for a in sys.argv[4:] for f in sorted(glob.glob(a))]
ims = [Image.open(f).convert("RGB") for f in files]
ch = round(cw * ims[0].height / ims[0].width)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * cw, rows * ch), (20, 20, 20))
d = ImageDraw.Draw(sheet)
for i, (f, im) in enumerate(zip(files, ims)):
    x, y = (i % cols) * cw, (i // cols) * ch
    sheet.paste(im.resize((cw, ch), Image.LANCZOS), (x, y))
    d.text((x + 6, y + 4), f.replace("\\", "/").split("/")[-1], fill=(255, 255, 0))
sheet.save(out)
print(out, len(ims))
