"""Download Poly Haven (CC0) models (.blend + their textures), texture sets and one HDRI into assets/.
usage: python tools/fetch_ph.py [--tex=a,b] [--model=id:res,id:res] [--hdri=id:res]
       defaults = the Hollow Oak example set below. Browse ids on https://polyhaven.com
-> assets/tex/<id>_{Diffuse,Rough,nor_gl}.jpg (2k), assets/ph/<id>/<id>_<res>.blend, assets/hdri/<id>_<res>.hdr
Max 3 parallel downloads: more and Windows runs out of socket buffers (ERR_NO_BUFFER_SPACE)."""
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

H = {"User-Agent": "Mozilla/5.0 showroom-3d-walk"}
ROOT = Path(__file__).resolve().parents[1] / "assets"

OPT = {a[2:].split("=")[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
TEXTURES = OPT.get("tex", "smooth_concrete_floor,white_plaster_02,black_walnut_veneer_01").split(",")
MODELS = [tuple(m.split(":")) for m in OPT.get("model", "wine_barrel_01:2k,metal_stool_01:1k,wine_bottles_01:1k,potted_plant_02:1k").split(",")]
HDRI = tuple(OPT.get("hdri", "lonely_road_afternoon_puresky:2k").split(":"))


def api(asset):
    return json.loads(urllib.request.urlopen(urllib.request.Request(f"https://api.polyhaven.com/files/{asset}", headers=H), timeout=60).read())


def get(url, dst: Path):
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    tmp.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=300).read())
    tmp.replace(dst)


def jobs():
    for t in TEXTURES:
        files = api(t)
        for kind in ("Diffuse", "Rough", "nor_gl"):
            yield files[kind]["2k"]["jpg"]["url"], ROOT / "tex" / f"{t}_{kind}.jpg"
    for m, res in MODELS:
        b = api(m)["blend"][res]["blend"]
        yield b["url"], ROOT / "ph" / m / Path(b["url"]).name
        for rel, info in b["include"].items():
            yield info["url"], ROOT / "ph" / m / rel
    name, res = HDRI
    yield api(name)["hdri"][res]["hdr"]["url"], ROOT / "hdri" / f"{name}_{res}.hdr"


todo = list(jobs())
with ThreadPoolExecutor(3) as ex:
    list(ex.map(lambda j: get(*j), todo))
print(len(todo), "files ok")
