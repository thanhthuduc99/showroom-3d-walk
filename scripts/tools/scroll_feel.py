"""How even the walk moves under a notched mouse wheel: one notch every 80 ms, progress sampled every display frame.
Reports per-frame movement (in % of the walk) and how much it pulses (coefficient of variation; lower = smoother).
usage: python tools/scroll_feel.py <url> [<url> ...]"""
import statistics
import sys

from playwright.sync_api import sync_playwright

PROBE = """
window.__p = [];
(function loop() {
  const m = /scaleX\\(([\\d.]+)\\)/.exec(document.getElementById('bar').style.transform || '');
  window.__p.push(m ? +m[1] : 0); requestAnimationFrame(loop);
})();
"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel="chrome", args=["--window-position=-2400,0", "--disable-features=CalculateNativeWinOcclusion", "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding"])
    for url in sys.argv[1:]:
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(url)
        pg.wait_for_function("document.getElementById('load').classList.contains('done')", timeout=180000)
        pg.wait_for_timeout(30000)
        pg.add_script_tag(content=PROBE)
        pg.mouse.move(720, 450)
        pg.wait_for_timeout(500)
        pg.evaluate("window.__p.length = 0")
        for _ in range(30):
            pg.mouse.wheel(0, 100)
            pg.wait_for_timeout(80)
        pg.wait_for_timeout(800)
        ps = pg.evaluate("window.__p")
        d = [b2 - a for a, b2 in zip(ps, ps[1:])]
        moving = [x for x in d if x > 1e-5]
        steady = moving[len(moving) // 5: -len(moving) // 5] or moving   # drop the start and the stop
        cv = statistics.pstdev(steady) / statistics.mean(steady)
        print(f"{url}\n  frames moving {len(moving)}, step per display frame median {100 * statistics.median(steady):.3f}% "
              f"max {100 * max(steady):.3f}%, pulsing (CV) {cv:.2f}")
        pg.close()
    b.close()
