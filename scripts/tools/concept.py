"""Concept image with Codex image_gen (the ChatGPT plan logged in to Codex CLI, no API key, no paid image API).
usage: python tools/concept.py <name> "<prompt>" [-i ref.png ...]   (at most 5 reference images, e.g. screenshots of the
       reference site for mood only) -> refs/<name>.png + refs/<name>.log"""
import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("prompt")
ap.add_argument("-i", dest="refs", action="append", default=[])
a = ap.parse_args()
if len(a.refs) > 5:
    raise SystemExit("image_gen takes at most 5 reference images")
refs = [Path(r).resolve() for r in a.refs]
(ROOT / "refs").mkdir(exist_ok=True)

roles = "\n".join(f"Image {i}: mood and lighting reference only. Do not copy its logos, text or exact layout." for i in range(1, len(refs) + 1))
task = (
    "Use the built-in image_gen tool to generate exactly ONE landscape 16:9 image.\n"
    + (f"Attached images, in order:\n{roles}\nPass them to image_gen as references.\n" if refs else "")
    + f"After generating, copy the image to refs/{a.name}.png. Do not modify any other file. Print the saved path.\n\n"
    + f"Prompt:\n<<<\n{a.prompt}\n>>>\n"
)
cmd = [shutil.which("codex") or "codex", "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(ROOT)]
for r in refs:
    cmd += ["-i", str(r)]
cmd.append("-")
with open(ROOT / "refs" / f"{a.name}.log", "w", encoding="utf-8") as log:
    r = subprocess.run(cmd, input=task, text=True, encoding="utf-8", stdout=log, stderr=subprocess.STDOUT)
out = ROOT / "refs" / f"{a.name}.png"
print(f"exit={r.returncode} {'OK ' + str(out) if out.exists() else 'NO IMAGE, see ' + str(out.with_suffix('.log'))}")
