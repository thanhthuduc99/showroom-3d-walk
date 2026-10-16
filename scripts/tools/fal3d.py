"""OPTIONAL, PAID. Make one prop with fal.ai: text -> product photo (nano-banana) -> 3D GLB (Hunyuan 3D Pro, PBR).
Key: env var FAL_AI_API_KEY, else the first .env (cwd and parents) that has it. Never printed.
usage: python tools/fal3d.py <name> "<prompt>" [--faces=N] [--pbr] [--image-only] [--from-url=<image url>]
       -> ./assets/ai/<name>.png (+ <name>.url), <name>.glb
price (2026-10): image ~$0.04, 3D $0.375 + $0.15 PBR (+ $0.15 only when --faces is given)"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

def find_key():
    if os.environ.get("FAL_AI_API_KEY"):
        return os.environ["FAL_AI_API_KEY"]
    for d in [Path.cwd(), *Path.cwd().parents]:
        env = d / ".env"
        if env.exists():
            for l in env.read_text(encoding="utf-8").splitlines():
                if l.startswith("FAL_AI_API_KEY="):
                    return l.split("=", 1)[1].strip().strip('"')
    sys.exit("FAL_AI_API_KEY not found in env or any .env up the tree")


KEY = find_key()
OUT = Path.cwd() / "assets" / "ai"
OUT.mkdir(parents=True, exist_ok=True)


def call(model, payload):
    hdr = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"https://queue.fal.run/{model}", json.dumps(payload).encode(), hdr)
    job = json.loads(urllib.request.urlopen(req, timeout=60).read())
    while True:
        st = json.loads(urllib.request.urlopen(urllib.request.Request(job["status_url"], headers=hdr), timeout=60).read())
        if st["status"] == "COMPLETED":
            return json.loads(urllib.request.urlopen(urllib.request.Request(job["response_url"], headers=hdr), timeout=60).read())
        time.sleep(5)


def get(url, dst):
    # curl (Schannel) rather than urllib: Python's store rejects the fal media CDN chain on this machine
    subprocess.run(["curl", "-sSfL", "--retry", "3", "-o", str(dst), url], check=True)


args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else True) for a in sys.argv[1:] if a.startswith("--")}
name, prompt = args[0], args[1] if len(args) > 1 else ""
t0 = time.time()
img = opt.get("from-url")
if not img:
    img = call("fal-ai/nano-banana", {"prompt": prompt, "num_images": 1})["images"][0]["url"]
    (OUT / f"{name}.url").write_text(img, encoding="utf-8")
    get(img, OUT / f"{name}.png")
    print(f"image {time.time() - t0:.0f}s", flush=True)
if opt.get("image-only"):
    sys.exit(0)
payload = {"input_image_url": img, "enable_pbr": bool(opt.get("pbr"))}
if "faces" in opt:
    payload["face_count"] = int(opt["faces"])
res = call("fal-ai/hunyuan-3d/v3.1/pro/image-to-3d", payload)
(OUT / f"{name}.glb.url").write_text(res["model_glb"]["url"], encoding="utf-8")
get(res["model_glb"]["url"], OUT / f"{name}.glb")
print(f"glb {time.time() - t0:.0f}s {(OUT / f'{name}.glb').stat().st_size // 1024} KB")
