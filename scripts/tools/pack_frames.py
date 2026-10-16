"""Pack the rendered walk frames (frames/fNNN.png) into WebP for the site, with a soft camera-like bloom:
web/frames-webp/<v>/<W>/fNNN.webp (full render width W, q80) and web/frames-webp/<v>/960/fNNN.webp (q78),
v and W from web/frames.json. Safe to run while Blender is still rendering.
Idempotent: skips outputs newer than their source, and sources still being written (Blender placeholders are 0 bytes).
usage: python tools/pack_frames.py"""
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frames"
META = json.loads((ROOT / "web" / "frames.json").read_text(encoding="utf-8"))
OUT = ROOT / "web" / "frames-webp" / META["v"]
SIZES = {META["width"]: 80, 960: 78}
SETTLE = 10  # seconds a source must be untouched before we trust it is fully written


def mb(n):
    return f"{n / 1e6:.1f} MB"


def bloom(im):
    """Same fixed glow on every frame (so it adds no flicker): bright pixels bleed softly, screen-blended."""
    a = np.asarray(im).astype(np.float32) / 255
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mask = np.clip((lum - 0.8) / 0.2, 0, 1)[..., None]
    src = Image.fromarray((a * mask * 255).astype(np.uint8))
    glow = np.asarray(src.filter(ImageFilter.GaussianBlur(im.width * 0.012))).astype(np.float32) / 255
    out = 1 - (1 - a) * (1 - glow * 0.25)
    return Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))


def main():
    for w in SIZES:
        (OUT / str(w)).mkdir(parents=True, exist_ok=True)
    now = time.time()
    made = skipped = pending = 0
    srcs = sorted(SRC.glob("f[0-9][0-9][0-9].png"))
    for src in srcs:
        st = src.stat()
        if st.st_size == 0 or now - st.st_mtime < SETTLE:
            pending += 1
            continue
        todo = {w: OUT / str(w) / f"{src.stem}.webp" for w in SIZES}
        todo = {w: p for w, p in todo.items() if not (p.exists() and p.stat().st_mtime >= st.st_mtime)}
        if not todo:
            skipped += 1
            continue
        try:
            with Image.open(src) as im:
                im.load()
                im = bloom(im.convert("RGB"))
        except OSError as e:  # truncated / half-written file
            print(f"{src.name}: not readable yet ({e})")
            pending += 1
            continue
        for w, dst in todo.items():
            img = im if im.width == w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            tmp = dst.with_suffix(".tmp")
            img.save(tmp, "WEBP", quality=SIZES[w], method=6)
            tmp.replace(dst)
        made += 1

    # a source deleted after packing (e.g. a bad frame queued for a redo) must not linger as WebP
    dropped = 0
    for w in SIZES:
        for p in (OUT / str(w)).glob("f*.webp"):
            if not (SRC / f"{p.stem}.png").exists():
                p.unlink()
                dropped += 1

    n = META["count"]
    print(f"packed {made}, up to date {skipped}, waiting {pending}, dropped {dropped} orphans")
    print(f"png   {len(srcs):3d} files {mb(sum(p.stat().st_size for p in srcs))}")
    for w in SIZES:
        files = sorted((OUT / str(w)).glob("f*.webp"))
        total = sum(p.stat().st_size for p in files)
        avg = total / len(files) if files else 0
        print(f"{w:<5} {len(files):3d} files {mb(total)}  avg {avg / 1e3:.0f} KB  (x{n} = {mb(avg * n)})")


if __name__ == "__main__":
    main()
