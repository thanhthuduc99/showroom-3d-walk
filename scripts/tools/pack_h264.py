"""Encode the frames as all-intra H.264 for the desktop WebCodecs player: every frame is a keyframe carrying its own
SPS/PPS, so the browser can hardware-decode any frame on its own, straight into GPU memory.
Applies the same bloom as pack_frames.py (lossless PNGs in renders/bloom/), then needs ffmpeg on PATH.
-> web/frames-h264/<v>/fNNN.h264 (Annex B) and web/frames-h264/<v>/codec.txt (WebCodecs codec string)
usage: python tools/pack_h264.py [crf=18]"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pack_frames import bloom

ROOT = Path(__file__).resolve().parents[1]
META = json.loads((ROOT / "web" / "frames.json").read_text(encoding="utf-8"))
OUT = ROOT / "web" / "frames-h264" / META["v"]
CRF = sys.argv[1] if len(sys.argv) > 1 else "18"
STREAM = ROOT / "renders" / "vc" / f"walk_crf{CRF}.h264"
BLOOM = ROOT / "renders" / "bloom"

BLOOM.mkdir(parents=True, exist_ok=True)
for src in sorted((ROOT / "frames").glob("f[0-9][0-9][0-9].png")):
    dst = BLOOM / src.name
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        with Image.open(src) as im:
            bloom(im.convert("RGB")).save(dst, compress_level=1)
STREAM.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "30", "-i", str(BLOOM / "f%03d.png"),
                "-vf", "scale=out_color_matrix=bt709:out_range=tv",           # tagged BT.709 so browsers decode the colours back exactly
                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                "-c:v", "libx264", "-preset", "slow", "-crf", CRF, "-pix_fmt", "yuv420p",
                "-x264-params", "keyint=1:min-keyint=1:scenecut=0:repeat-headers=1:aud=1", "-f", "h264", str(STREAM)], check=True)
data = STREAM.read_bytes()

# split on access unit delimiters (NAL type 9), one per frame
starts, i = [], 0
while True:
    i = data.find(b"\x00\x00\x01\x09", i)
    if i < 0:
        break
    starts.append(i - 1 if i > 0 and data[i - 1] == 0 else i)
    i += 4
starts.append(len(data))
frames = [data[a:b] for a, b in zip(starts, starts[1:])]
assert len(frames) == META["count"], (len(frames), META["count"])

sps = data.find(b"\x00\x00\x01\x67") + 4                     # profile_idc, constraint flags, level_idc
codec = "avc1." + data[sps:sps + 3].hex()
OUT.mkdir(parents=True, exist_ok=True)
for n, f in enumerate(frames):
    (OUT / f"f{n:03d}.h264").write_bytes(f)
(OUT / "codec.txt").write_text(codec, encoding="utf-8")
print(f"{len(frames)} frames, codec {codec}, {len(data) / 1e6:.1f} MB, avg {len(data) / len(frames) / 1e3:.0f} KB")
