"""Screenshots of the real-time page at scroll fractions + console errors.
usage: python tools/shoot3d.py <url> <out_dir> [p p p ...]"""
import os, sys
from playwright.sync_api import sync_playwright
FL = ["--window-position=-2400,0", "--disable-features=CalculateNativeWinOcclusion", "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding"]
url, out = sys.argv[1], sys.argv[2]
ps = [float(x) for x in sys.argv[3:]] or [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]
os.makedirs(out, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel="chrome", args=FL)
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    logs = []
    pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
    pg.goto(url)
    pg.wait_for_function("document.getElementById('load').classList.contains('done')", timeout=240000)
    pg.wait_for_timeout(2500)
    for k, f in enumerate(ps):
        pg.evaluate(f"window.scrollTo(0, (document.documentElement.scrollHeight - innerHeight) * {f})")
        pg.wait_for_timeout(2600)
        pg.screenshot(path=os.path.join(out, f"s{k:02d}_{int(f * 1000):04d}.jpg"), quality=88)
    info = pg.evaluate("(() => { const r = window.__walk.renderer.info; return {calls: r.render.calls, tris: r.render.triangles, tex: r.memory.textures, geo: r.memory.geometries}; })()")
    print('INFO', info)
    for l in logs[:30]:
        print('LOG', l)
    b.close()
