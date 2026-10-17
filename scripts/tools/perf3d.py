"""rAF frame gaps while wheel-scrolling (no screen capture overhead). usage: python tools/perf3d.py <url> [<url> ...]"""
import sys
from playwright.sync_api import sync_playwright
FL = ["--window-position=-2400,0", "--disable-features=CalculateNativeWinOcclusion", "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding"]
PROBE = "window.__g=[];let pv=performance.now();(function l(t){window.__g.push(t-pv);pv=t;requestAnimationFrame(l)})(pv);"
with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel="chrome", args=FL)
    for url in sys.argv[1:]:
        pg = b.new_page(viewport={"width": 1920, "height": 960})
        pg.add_init_script(PROBE)
        pg.goto(url)
        pg.wait_for_function("document.getElementById('load').classList.contains('done')", timeout=180000)
        pg.wait_for_timeout(8000)
        pg.mouse.move(960, 480)
        pg.evaluate("window.__g.length=0")
        for d in (100, -100, 100, -100):
            for _ in range(40):
                pg.mouse.wheel(0, d); pg.wait_for_timeout(60)
        g = sorted(pg.evaluate("window.__g.slice(1)"))
        q = lambda x: g[int(x * (len(g) - 1))]
        print(f"{url.split('?')[-1][:40]:40s} median {q(.5):.1f} p95 {q(.95):.1f} max {g[-1]:.0f} over25 {sum(x > 25 for x in g)}/{len(g)}")
        pg.close()
    b.close()
