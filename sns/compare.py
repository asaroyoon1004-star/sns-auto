"""Render one script in several video styles so they can be compared side by side.

    python -m sns.compare --seed s011 --styles v1,v4,sb,sc --out out/compare [--engine openjtalk]

Writes <style>.mp4, <style>_plan.json (scene plan + QA report) and sheet.png (the same moments of every style in rows).
Styles: v1 original, v3/v3b terminal look, v4 premium finance (A), sb high-retention explainer (B), sc data storytelling (C).
"""
import argparse
import copy
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw

from .common import ROOT, read_json
from .render import render


def contact_sheet(videos, out_png, fractions=(0.02, 0.12, 0.3, 0.5, 0.7, 0.92), thumb=(270, 480)):
    from .tts import duration

    w, h = thumb
    sheet = Image.new("RGB", (20 + len(fractions) * (w + 16), 20 + len(videos) * (h + 44)), (28, 28, 28))
    d = ImageDraw.Draw(sheet)
    with tempfile.TemporaryDirectory() as tmp:
        for r, (name, path) in enumerate(videos.items()):
            dur = duration(str(path))
            for c, f in enumerate(fractions):
                png = Path(tmp) / f"{name}_{c}.png"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{dur * f:.2f}", "-i", str(path), "-frames:v", "1", str(png)], check=True)
                x, y = 20 + c * (w + 16), 20 + r * (h + 44)
                sheet.paste(Image.open(png).resize(thumb), (x, y + 26))
                d.text((x, y + 6), f"{name}  {dur * f:.1f}s", fill=(230, 230, 230))
    sheet.save(out_png)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", default="s011", help="id of a script in data/seed/scripts.json")
    ap.add_argument("--styles", default="v4,sb,sc")
    ap.add_argument("--out", default="out/compare")
    ap.add_argument("--engine", default=None, help="tts engine override, e.g. openjtalk for offline runs")
    a = ap.parse_args(argv)
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if a.engine:
        cfg["tts"]["engine"] = a.engine
    script = next(s for s in read_json(ROOT / "data" / "seed" / "scripts.json", []) if s["id"] == a.seed)
    script = dict(script, variant="hook_title:hide")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    videos = {}
    for design in a.styles.split(","):
        c = copy.deepcopy(cfg)
        c["video"]["design"] = design
        t = time.time()
        with tempfile.TemporaryDirectory() as tmp:
            video, total, _ = render(c, dict(script), tmp)
            shutil.copy(video, out / f"{design}.mp4")
            if (Path(tmp) / "scene_plan.json").exists():
                shutil.copy(Path(tmp) / "scene_plan.json", out / f"{design}_plan.json")
        videos[design] = out / f"{design}.mp4"
        print(f"{design}: {total:.1f}s video, rendered in {time.time() - t:.0f}s -> {videos[design]}")
    contact_sheet(videos, out / "sheet.png")
    print("sheet:", out / "sheet.png")


if __name__ == "__main__":
    main()
