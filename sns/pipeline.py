"""Entry point.

python -m sns.pipeline make [--count N] [--seed-only]   # script -> voice -> video into data/queue/
python -m sns.pipeline publish                          # upload every rendered-but-unposted video
python -m sns.pipeline daily [--count N]                # make + publish (what the scheduler runs)
python -m sns.pipeline analyze                          # collect stats -> learn weights -> report
python -m sns.pipeline landing                          # rebuild the link-in-bio page
"""
import argparse
import os
from datetime import datetime, timezone

from . import analytics, landing, upload_tiktok, upload_youtube
from .common import DATA, QUEUE, load_config, read_json, write_json, log
from .scriptgen import assign_variant, next_script


def make(cfg, count, seed_only=False):
    from .render import render  # heavy (Pillow/ffmpeg); not needed by analyze/landing
    made = []
    top_hooks = read_json(DATA / "top_hooks.json", [])
    for _ in range(count):
        s = next_script(cfg, top_hooks=top_hooks, seed_only=seed_only)
        s["variant"] = assign_variant(cfg)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        d = QUEUE / f"{stamp}-{s['id']}"
        d.mkdir(parents=True, exist_ok=True)
        write_json(d / "script.json", s)
        video, secs, engines = render(cfg, s, d)
        write_json(d / "meta.json", {"status": "rendered", "duration": round(secs, 2), "tts": engines,
                                     "created_at": stamp, "uploads": []})
        made.append(d)
    return made


def publish(cfg):
    targets = []
    if cfg["upload"]["youtube"]["enabled"] and upload_youtube.configured():
        targets.append(("youtube", upload_youtube.upload))
    if cfg["upload"]["tiktok"]["enabled"] and upload_tiktok.configured():
        targets.append(("tiktok", upload_tiktok.upload))
    if not targets:
        log("no platform credentials set; videos stay in data/queue (dry run)")
        return 0
    n = 0
    for d in sorted(QUEUE.iterdir()):
        meta = read_json(d / "meta.json", None)
        if not meta or meta["status"] in ("posted", "missing_video"):
            continue
        script = read_json(d / "script.json", {})
        if not (d / "video.mp4").exists():
            meta["status"] = "missing_video"
            write_json(d / "meta.json", meta)
            continue
        done = {u["platform"] for u in meta["uploads"]}
        for name, fn in targets:
            if name in done:
                continue
            try:
                meta["uploads"].append(fn(cfg, script, str(d / "video.mp4")))
                log(f"uploaded {d.name} to {name}")
            except Exception as e:
                meta.setdefault("errors", []).append(f"{name}: {e!r}"[:500])
                log(f"upload to {name} failed: {e!r}")
        if {t for t, _ in targets} <= {u["platform"] for u in meta["uploads"]}:
            meta["status"] = "posted"
            if os.environ.get("SNS_DELETE_AFTER_POST") == "1":
                (d / "video.mp4").unlink(missing_ok=True)
        write_json(d / "meta.json", meta)
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "publish", "daily", "analyze", "landing"])
    ap.add_argument("--count", type=int)
    ap.add_argument("--seed-only", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    count = a.count or cfg.get("posts_per_run", 1)
    if a.cmd in ("make", "daily"):
        make(cfg, count, a.seed_only)
    if a.cmd in ("publish", "daily"):
        publish(cfg)
    if a.cmd == "analyze":
        analytics.collect()
        analytics.learn(cfg)
        analytics.maybe_switch_phase(cfg)
        analytics.report(cfg)
    if a.cmd == "landing":
        landing.build(cfg)


if __name__ == "__main__":
    main()
