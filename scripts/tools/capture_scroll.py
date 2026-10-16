"""Record what the screen actually shows while wheel-scrolling: every compositor frame via CDP screencast,
then measure per frame: motion step (phase correlation), repeats, sharpness. Works on any URL (also finely-crafted).
usage: python tools/capture_scroll.py <url> <tag> [--dpr=1] [--notches=24] [--gap=80] [--setup=finely]
   --setup=finely clicks through finely-crafted.com's cookie / Enter / Skip Video buttons (for the side-by-side)
-> screenshots/cap-<tag>/NNNN.jpg (project folder) + report on stdout and in report.json"""
import asyncio
import base64
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.async_api import async_playwright

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OPT = {a[2:].split("=")[0]: a.split("=")[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
URL, TAG = ARGS[0], ARGS[1]
DPR, NOTCHES, GAP = float(OPT.get("dpr", 1)), int(OPT.get("notches", 24)), int(OPT.get("gap", 80))
OUT = Path(__file__).resolve().parents[1] / "screenshots" / f"cap-{TAG}"
FLAGS = ["--window-position=-2400,0", "--disable-features=CalculateNativeWinOcclusion",
         "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding"]


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.jpg"):
        f.unlink()
    frames = []
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False, channel="chrome", args=FLAGS)
        ctx = await b.new_context(viewport={"width": int(OPT.get("vw", 1440)), "height": int(OPT.get("vh", 900))}, device_scale_factor=DPR)
        pg = await ctx.new_page()
        await pg.goto(URL)
        if OPT.get("setup") == "finely":                  # cookie, Enter, skip intro video
            for label in ("Accept All Cookies", "Enter", "Skip Video"):
                await pg.get_by_role("button", name=label).click(timeout=60000)
                await pg.wait_for_timeout(4000)
            await pg.wait_for_timeout(8000)
        else:
            await pg.wait_for_function("document.getElementById('load').classList.contains('done')", timeout=180000)
            await pg.wait_for_timeout(30000)
        if OPT.get("setup") != "finely":                  # grain is animated noise: hide it so only the picture is measured
            await pg.add_style_tag(content="#grain{display:none!important}.spot::after{animation:none!important}")
        await pg.mouse.move(720, 450)
        cdp = await ctx.new_cdp_session(pg)

        def on_frame(e):
            frames.append((e["metadata"]["timestamp"], e["data"]))
            asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": e["sessionId"]}))

        cdp.on("Page.screencastFrame", on_frame)
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "everyNthFrame": 1})
        await pg.wait_for_timeout(600)
        t_start = len(frames)
        for _ in range(NOTCHES):
            await pg.mouse.wheel(0, 100)
            await pg.wait_for_timeout(GAP)
        await pg.wait_for_timeout(2500)
        await cdp.send("Page.stopScreencast")
        await b.close()

    ts = np.array([t for t, _ in frames])
    imgs = []
    for n, (_, data) in enumerate(frames):
        p = OUT / f"{n:04d}.jpg"
        p.write_bytes(base64.b64decode(data))
        imgs.append(p)
    # analysis on the middle of the screen (captions and hotspots sit elsewhere)
    def grey(p):
        im = Image.open(p).convert("L")
        w, h = im.size
        return np.asarray(im.crop((int(w * .2), int(h * .12), int(w * .8), int(h * .62))), np.float32)

    def small(g):
        return np.asarray(Image.fromarray(g.astype(np.uint8)).resize((g.shape[1] // 4, g.shape[0] // 4), Image.BILINEAR), np.float32)

    G = [grey(p) for p in imgs]
    sharp = []
    for g in G:
        l = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
        sharp.append(float(l.var()))
    shift = [0.0]
    for a, c in zip(G, G[1:]):
        A, C = np.fft.fft2(a - a.mean()), np.fft.fft2(c - c.mean())
        r = np.fft.ifft2(A * np.conj(C) / (np.abs(A * np.conj(C)) + 1e-6)).real
        y, x = np.unravel_index(np.argmax(r), r.shape)
        y = y - r.shape[0] if y > r.shape[0] / 2 else y
        x = x - r.shape[1] if x > r.shape[1] / 2 else x
        diff = float(np.abs(a - c).mean())
        shift.append(float(np.hypot(x, y)) if diff > 0.5 else 0.0)
    dt = np.diff(ts) * 1000
    S = [small(g) for g in G]
    change = [0.0] + [float(np.abs(S[i] - S[i - 1]).mean()) for i in range(1, len(S))]
    moving = [i for i in range(1, len(G)) if change[i] > 0.8]
    first, lastm = (moving[0], moving[-1]) if moving else (0, 0)
    seg = range(first, lastm + 1)
    ch = np.array([change[i] for i in seg]) if moving else np.array([0.0])
    med = float(np.median(ch))
    holds = int(sum(c < 0.25 * med for c in ch))
    jumps = int(sum(c > 2.0 * med for c in ch))
    steps = [shift[i] for i in seg]
    gaps = [float(dt[i - 1]) for i in seg]
    rest = sharp[-1]
    mv = [sharp[i] for i in seg]
    report = {
        "tag": TAG, "dpr": DPR, "frames_captured": len(G), "motion_frames": len(seg),
        "frame_interval_ms_median": round(float(np.median(gaps)), 1) if gaps else None,
        "frame_interval_ms_p95": round(float(np.percentile(gaps, 95)), 1) if gaps else None,
        "frames_over_25ms": int(sum(g > 25 for g in gaps)),
        "repeated_frames_while_moving": holds,
        "change_per_frame_median": round(med, 2),
        "change_cv": round(float(ch.std() / (ch.mean() + 1e-6)), 2),
        "jump_frames_over_2x": jumps,
        "step_px_median": round(float(np.median(steps)), 1) if steps else None,
        "step_px_p95": round(float(np.percentile(steps, 95)), 1) if steps else None,
        "step_cv": round(float(np.std(steps) / (np.mean(steps) + 1e-6)), 2) if steps else None,
        "sharpness_moving_median": round(float(np.median(mv))) if mv else None,
        "sharpness_moving_min": round(float(min(mv))) if mv else None,
        "sharpness_at_rest": round(rest),
        "sharpness_moving_vs_rest": round(float(np.median(mv)) / rest, 2) if mv else None,
    }
    (OUT / "report.json").write_text(json.dumps({**report, "per_frame": [
        {"n": i, "t_ms": round((ts[i] - ts[0]) * 1000, 1), "change": round(change[i], 2), "sharp": round(sharp[i])} for i in range(len(G))]}, indent=1))
    print(json.dumps(report))


asyncio.run(main())
