"""Check the scroll site in real Chrome: screenshots on desktop and iPhone at 4 scroll points, one opened hotspot,
console errors, bytes transferred, and scroll smoothness (rAF gaps + canvas draw time while wheel-scrolling).
usage: python tools/shoot_site.py [url=http://127.0.0.1:8770/web/index.html] [tag=local] [--wait=12] [--only=desk|iphone]
shots -> screenshots/site/<tag>-<device>-NN.png (project folder)"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
URL = ARGS[0] if ARGS else "http://127.0.0.1:8770/web/index.html"
TAG = ARGS[1] if len(ARGS) > 1 else "local"
WAIT = int(next((a[7:] for a in sys.argv if a.startswith("--wait=")), 12)) * 1000
ONLY = next((a[7:] for a in sys.argv if a.startswith("--only=")), None)
OUT = Path(__file__).resolve().parents[1] / "screenshots" / "site"
OUT.mkdir(parents=True, exist_ok=True)
PROBE = """
window.__gaps = []; window.__paint = [];
let prev = performance.now();
(function loop(t) { window.__gaps.push(t - prev); prev = t; requestAnimationFrame(loop); })(prev);
const orig = CanvasRenderingContext2D.prototype.drawImage;
CanvasRenderingContext2D.prototype.drawImage = function (...a) {
  const t0 = performance.now(); const r = orig.apply(this, a); window.__paint.push(performance.now() - t0); return r;
};
"""
DEVICES = {"desk": dict(viewport={"width": 1440, "height": 900}),
           "iphone": dict(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True)}


def stats(xs):
    xs = sorted(xs)
    if not xs:
        return "n/a"
    q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
    return f"median {q(.5):.1f} ms, p95 {q(.95):.1f} ms, max {xs[-1]:.1f} ms, n={len(xs)}"


with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel="chrome", args=["--window-position=-2400,0", "--disable-features=CalculateNativeWinOcclusion", "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding"])
    for dev, opts in DEVICES.items():
        if ONLY and dev != ONLY:
            continue
        ctx = b.new_context(**opts)
        pg = ctx.new_page()
        pg.add_init_script(PROBE)
        errs, sizes = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.on("requestfinished", lambda r: sizes.append(r.sizes()["responseBodySize"]))
        pg.goto(URL)
        pg.wait_for_function("document.getElementById('load').classList.contains('done')", timeout=180000)
        pg.wait_for_timeout(WAIT)                        # let the 1600 set arrive
        for i, prog in enumerate([0, 0.33, 0.66, 1.0]):
            pg.evaluate(f"scrollTo(0, (document.documentElement.scrollHeight - innerHeight) * {prog})")
            pg.wait_for_timeout(1800)
            if prog == 1.0:
                spots = pg.evaluate("[...document.querySelectorAll('.spot.on')].map(s => s.getBoundingClientRect()).map(r => [Math.round(r.x + r.width / 2), Math.round(r.y + r.height / 2)])")
                print(dev, "visible hotspots at the end:", spots)
            pg.screenshot(path=str(OUT / f"{TAG}-{dev}-{i + 1:02d}.png"))
        pg.evaluate("document.querySelector('.spot.on') && document.querySelector('.spot.on').click()")
        pg.wait_for_timeout(900)
        pg.screenshot(path=str(OUT / f"{TAG}-{dev}-05-card.png"))
        if dev == "desk":
            pg.evaluate("scrollTo(0, 0)")
            pg.wait_for_timeout(1500)
            pg.mouse.move(720, 450)
            pg.evaluate("window.__gaps.length = 0; window.__paint.length = 0")
            for _ in range(2):
                for _ in range(90):
                    pg.mouse.wheel(0, 100)
                    pg.wait_for_timeout(30)
                for _ in range(90):
                    pg.mouse.wheel(0, -100)
                    pg.wait_for_timeout(30)
            gaps = pg.evaluate("window.__gaps.slice(1)")
            paint = pg.evaluate("window.__paint")
            print(dev, "frame gaps while scrolling:", stats(gaps))
            print(dev, "drawImage time:", stats(paint))
            print(dev, "gaps over 50 ms:", sum(g > 50 for g in gaps))
        print(dev, "bytes transferred:", f"{sum(s for s in sizes if s > 0) / 1e6:.1f} MB", "| errors:", errs or "none")
        ctx.close()
    b.close()
