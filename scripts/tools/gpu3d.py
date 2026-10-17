"""Which GPU Chrome renders with. usage: python tools/gpu3d.py <url>"""
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel="chrome", args=["--window-position=-2400,0"])
    pg = b.new_page()
    pg.goto(sys.argv[1])
    print(pg.evaluate("(() => { const g = document.createElement('canvas').getContext('webgl2'); const e = g.getExtension('WEBGL_debug_renderer_info'); return g.getParameter(e.UNMASKED_RENDERER_WEBGL) + ' | samples ' + g.getParameter(g.MAX_SAMPLES); })()"))
    b.close()
