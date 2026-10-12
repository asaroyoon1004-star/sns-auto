"""Collect per-video stats, learn which categories/hooks work, and write a weekly report.

The learned weights feed scriptgen.pick_category; the top hooks are shown to Claude as examples.
"""
import csv
from collections import defaultdict
from datetime import datetime, timezone

from . import upload_tiktok, upload_youtube
from .common import DATA, ROOT, METRICS, QUEUE, WEIGHTS, read_json, write_json, log

FIELDS = ["collected_at", "item", "platform", "video_id", "category", "hook", "views", "likes", "comments", "shares"]


def _items():
    for d in sorted(QUEUE.iterdir()) if QUEUE.exists() else []:
        meta = read_json(d / "meta.json", None)
        if meta:
            yield d, meta, read_json(d / "script.json", {})


def collect():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    items = list(_items())
    if upload_youtube.configured():
        ids = {u["id"]: (d, s) for d, m, s in items for u in m.get("uploads", []) if u["platform"] == "youtube"}
        for vid, st in upload_youtube.stats(list(ids)).items():
            d, s = ids[vid]
            rows.append(dict(collected_at=now, item=d.name, platform="youtube", video_id=vid, category=s.get("category"),
                             hook=s.get("hook"), shares=0, **st))
    if upload_tiktok.configured():
        by_hook = {s.get("hook"): (d, s) for d, m, s in items}
        for vid, st in upload_tiktok.stats().items():
            match = next((v for h, v in by_hook.items() if h and h in (st.get("title") or "")), None)
            if not match:
                continue
            d, s = match
            rows.append(dict(collected_at=now, item=d.name, platform="tiktok", video_id=vid, category=s.get("category"),
                             hook=s.get("hook"), views=st["views"], likes=st["likes"], comments=st["comments"],
                             shares=st.get("shares", 0)))
    if rows:
        new = not METRICS.exists()
        with open(METRICS, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerows(rows)
    log(f"collected {len(rows)} stat rows")
    return rows


def latest():
    """Latest snapshot per (platform, video_id)."""
    if not METRICS.exists():
        return []
    snap = {}
    with open(METRICS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            snap[(r["platform"], r["video_id"])] = r
    return list(snap.values())


def learn(cfg):
    rows = latest()
    if not rows:
        log("no metrics yet; keeping equal category weights")
        return {}
    by_cat = defaultdict(list)
    for r in rows:
        v = int(r["views"])
        eng = (int(r["likes"]) + 3 * int(r["comments"]) + 5 * int(r.get("shares") or 0)) / max(v, 1)
        by_cat[r["category"]].append(v * (1 + 10 * eng))
    overall = sum(sum(v) for v in by_cat.values()) / max(1, sum(len(v) for v in by_cat.values()))
    weights = {}
    for c in cfg["categories"]:
        vals = by_cat.get(c)
        # shrink toward 1.0 when a category has few samples, so one viral video doesn't take over
        score = (sum(vals) / len(vals)) / max(overall, 1) if vals else 1.0
        n = len(vals or [])
        weights[c] = round((score * n + 1.0 * 3) / (n + 3), 3)
    write_json(WEIGHTS, weights)
    top = sorted(rows, key=lambda r: int(r["views"]), reverse=True)[:8]
    write_json(DATA / "top_hooks.json", [r["hook"] for r in top if r.get("hook")])
    log("category weights:", weights)
    return weights


def report(cfg):
    rows = latest()
    total = sum(int(r["views"]) for r in rows)
    lines = [f"# 週次レポート {datetime.now().strftime('%Y-%m-%d')}", "",
             f"- 計測した動画: {len(rows)} 本 / 合計再生: {total:,}", ""]
    lines += ["## 再生数トップ5", "", "| 媒体 | 再生 | いいね | フック |", "|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: int(r["views"]), reverse=True)[:5]:
        lines.append(f"| {r['platform']} | {int(r['views']):,} | {r['likes']} | {r['hook']} |")
    w = read_json(WEIGHTS, {})
    if w:
        lines += ["", "## 次の投稿配分（カテゴリ重み）", ""]
        lines += [f"- {cfg['categories'][c]['label']}: {v}" for c, v in sorted(w.items(), key=lambda x: -x[1])]
    out = DATA / "report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log("wrote", out)
    return out


def maybe_switch_phase(cfg):
    """Move to 61s+ videos once TikTok Creator Rewards is reachable (10k followers)."""
    if cfg.get("phase") != "growth" or not upload_tiktok.configured():
        return cfg.get("phase")
    n = upload_tiktok.follower_count()
    log(f"TikTok followers: {n:,}")
    if n >= 10_000:
        cfg["phase"] = "monetize"
        write_json(ROOT / "config.json", cfg)
        log("switched phase to monetize (61s+ videos)")
    return cfg["phase"]
