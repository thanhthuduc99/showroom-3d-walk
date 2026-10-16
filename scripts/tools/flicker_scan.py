"""Find frames whose light jumps against their neighbours (denoiser boil, fireflies, a bad render).
For each frame t: 16 px block means of t vs the average of t-1 and t+1, scored by the 90th percentile of the
block differences (moving edges stay in the top 10 %). Frames above median + 3 MAD are listed.
usage: python tools/flicker_scan.py [frames_dir=frames]"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "frames")


def blocks(p):
    a = np.asarray(Image.open(p).convert("L").resize((800, 450), Image.BILINEAR), np.float32)
    return a.reshape(450 // 9, 9, 800 // 16, 16).mean(axis=(1, 3))


files = [p for p in sorted(SRC.glob("f[0-9][0-9][0-9].png")) if p.stat().st_size]
B = [blocks(p) for p in files]
score = []
for t in range(1, len(B) - 1):
    d = np.abs(B[t] - (B[t - 1] + B[t + 1]) / 2)
    score.append((files[t].stem, float(np.percentile(d, 90)), float(d.mean())))
s = np.array([x[1] for x in score])
med, mad = np.median(s), np.median(np.abs(s - np.median(s)))
lim = med + 3 * 1.4826 * mad
print(f"{len(files)} frames, p90 block jump: median {med:.2f}, max {s.max():.2f} grey levels, outlier limit {lim:.2f}")
bad = [x for x in score if x[1] > lim]
print("outliers:", ", ".join(f"{n} ({v:.2f})" for n, v, _ in bad) or "none")
