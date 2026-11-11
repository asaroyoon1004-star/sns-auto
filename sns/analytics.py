"""Collect per-video stats, learn which categories/hooks work, and write a weekly report.

The learned weights feed scriptgen.pick_category; the top hooks are shown to Claude as examples.
"""
import csv
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone

from . import upload_tiktok, upload_youtube
from .common import DATA, ROOT, METRICS, QUEUE, WEIGHTS, read_json, write_json, log
from .scriptgen import hook_style

FIELDS = ["collected_at", "item", "platform", "video_id", "category", "hook_type", "hook", "views", "likes", "comments", "shares",
          # added for the research loop: what was tested, and how far / how well people watched
          "variant", "design", "slot_jst", "duration", "avg_view_pct", "avg_view_sec", "subs_gained", "engaged_views",
          # hours between posting and this snapshot: a video posted 2 h ago can't be compared with one that is 2 days old
          "age_hours",
          # which YouTube channel the video is on (videos posted through another account are left out of the report)
          "channel_id"]


def _age_hours(meta, now):
    try:
        made = datetime.strptime(meta["created_at"], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return ""
    return round((now - made).total_seconds() / 3600, 1)


def _context(d, meta, s):
    """Fields that describe the video itself, so results can be compared by time slot, length and A/B arm."""
    slot = ""
    if meta.get("created_at"):
        hour = (int(meta["created_at"][9:11]) + 9) % 24  # created_at is a UTC stamp YYYYMMDD-HHMMSS
        slot = f"{hour:02d}"
    return dict(item=d.name, category=s.get("category"), hook_type=s.get("hook_type") or hook_style(s.get("hook") or ""), hook=s.get("hook"),
                variant=s.get("variant", ""), design=meta.get("design", "v1"), slot_jst=slot, duration=meta.get("duration", ""),
                age_hours=_age_hours(meta, datetime.now(timezone.utc)))


def _ensure_header():
    """Rewrite metrics.csv with the current FIELDS when an older header is on disk (extra columns stay blank)."""
    if not METRICS.exists():
        return
    with open(METRICS, encoding="utf-8") as f:
        r = csv.DictReader(f)
        if r.fieldnames == FIELDS:
            return
        old = list(r)
    with open(METRICS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(old)


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
        ids = {u["id"]: (d, m, s) for d, m, s in items for u in m.get("uploads", []) if u["platform"] == "youtube"}
        deep = upload_youtube.analytics(list(ids))
        status = {"checked_at": now, "channel_id": upload_youtube.my_channel_id(),
                  "videos_with_data": len(deep), **upload_youtube.LAST_STATUS,
                  "channel_7d": upload_youtube.channel_summary(7),
                  "traffic_28d": upload_youtube.traffic_sources(28),
                  "diagnose": upload_youtube.diagnose(list(ids))}
        write_json(DATA / "analytics_status.json", status)
        log_channel_day(status, items)
        for vid, st in upload_youtube.stats(list(ids)).items():
            d, m, s = ids[vid]
            rows.append(dict(collected_at=now, platform="youtube", video_id=vid, **_context(d, m, s),
                             **{"shares": 0, **st, **deep.get(vid, {})}))
    if upload_tiktok.configured():
        by_hook = {s.get("hook"): (d, m, s) for d, m, s in items}
        for vid, st in upload_tiktok.stats().items():
            match = next((v for h, v in by_hook.items() if h and h in (st.get("title") or "")), None)
            if not match:
                continue
            d, m, s = match
            rows.append(dict(collected_at=now, platform="tiktok", video_id=vid, **_context(d, m, s),
                             views=st["views"], likes=st["likes"], comments=st["comments"], shares=st.get("shares", 0)))
    if rows:
        _ensure_header()
        new = not METRICS.exists()
        with open(METRICS, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerows(rows)
    log(f"collected {len(rows)} stat rows")
    return rows


CHANNEL_DAILY = DATA / "channel_daily.csv"
DAILY_FIELDS = ["date", "views_7d", "subs_gained_7d", "subs_lost_7d", "subs_per_1000_7d", "avg_view_pct_7d",
                "playlist_views_28d", "channel_page_views_28d", "videos_in_playlists", "playlist_error"]


def channel_day_row(status, items, date):
    """One row per day for the subscriber trend: channel-wide 7-day numbers, how many views come from playlists and the
    channel page (the paths a series opens), and whether the playlist step is working."""
    ch = status.get("channel_7d") or {}
    tr = status.get("traffic_28d") or {}
    ups = [u for _, m, _ in items for u in m.get("uploads", []) if u.get("platform") == "youtube"]
    errs = [u["playlist_error"] for u in ups if u.get("playlist_error")]
    views, subs = _num(ch.get("views")), _num(ch.get("subs_gained"))
    return {"date": date, "views_7d": ch.get("views", ""), "subs_gained_7d": ch.get("subs_gained", ""),
            "subs_lost_7d": ch.get("subs_lost", ""),
            "subs_per_1000_7d": f"{subs / views * 1000:.2f}" if views and subs is not None else "",
            "avg_view_pct_7d": ch.get("avg_view_pct", ""), "playlist_views_28d": tr.get("PLAYLIST", 0),
            "channel_page_views_28d": tr.get("YT_CHANNEL", 0), "videos_in_playlists": sum(1 for u in ups if u.get("playlist")),
            "playlist_error": ("権限なし" if "insufficient" in errs[-1].lower() or "403" in errs[-1] else errs[-1][:80]) if errs else ""}


def log_channel_day(status, items):
    """Append today's row to data/channel_daily.csv (a second run on the same day replaces it)."""
    row = channel_day_row(status, items, status["checked_at"][:10])
    old = []
    if CHANNEL_DAILY.exists():
        with open(CHANNEL_DAILY, encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if r.get("date") != row["date"]]
    with open(CHANNEL_DAILY, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DAILY_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(old + [row])


def subscriber_sections(rows, cfg, days=None):
    """The subscriber section of the report: the daily trend and the running experiment judged on subs per 1,000 views."""
    out = ["", "## チャンネル登録の推移（毎日記録）", "",
           "目標: 1,000再生あたりの登録を 0.6人（11/11までの全動画）から 1.5人以上へ。", ""]
    if days is None:
        days = []
        if CHANNEL_DAILY.exists():
            with open(CHANNEL_DAILY, encoding="utf-8") as f:
                days = list(csv.DictReader(f))
    if days:
        out += ["| 日付 | 7日の再生 | 7日の登録 | 解除 | 登録/1000再生 | 再生リスト経由(28日) | チャンネルページ経由(28日) | 再生リスト入り | 再生リストの状態 |",
                "|---|---|---|---|---|---|---|---|---|"]
        for d in days[-10:]:
            out.append(f"| {d['date']} | {d['views_7d']} | +{d['subs_gained_7d']} | {d['subs_lost_7d'] or '-'} | {d['subs_per_1000_7d'] or '-'} | "
                       f"{d['playlist_views_28d']} | {d['channel_page_views_28d']} | {d['videos_in_playlists']}本 | {d['playlist_error'] or 'OK'} |")
    else:
        out.append("- まだ記録がありません（次の分析から毎日1行ずつ増えます）")
    exp = cfg.get("experiment") or {}
    arms = exp.get("arms") or []
    if len(arms) > 1:
        out += ["", f"### 実験 {exp['name']}（判定は登録/1000再生。投稿から{MIN_AGE_H}時間以上の動画）", "",
                "| 群 | 本数 | 合計再生 | 登録 | 登録/1000再生 |", "|---|---|---|---|---|"]
        res = {}
        for a in arms:
            g = [r for r in mature(rows) if r.get("variant") == f"{exp['name']}:{a}"]
            tv = sum(int(r["views"]) for r in g)
            subs = sum(_num(r.get("subs_gained")) or 0 for r in g)
            res[a] = (len(g), tv, subs)
            out.append(f"| {a} | {len(g)} | {tv:,} | {subs:.0f} | {(f'{subs / tv * 1000:.2f}') if tv else '-'} |")
        ready = all(n >= 20 and tv >= 5000 for n, tv, _ in res.values())
        out += ["", "- 判定: " + ("各群が20本・5,000再生に届いた。1.5倍以上の差がある群を採用する" if ready else
                                "まだ判定しない（各群20本以上・5,000再生以上になってから）")]
    return out


def current_channel():
    return (read_json(DATA / "analytics_status.json", None) or {}).get("channel_id")


def channel_rows(rows, mine):
    """Drop YouTube videos that are on another channel (e.g. posted through the wrong account). Without a known channel, keep all."""
    if not mine:
        return rows
    return [r for r in rows if r.get("platform") != "youtube" or r.get("channel_id") == mine]


def latest():
    """Latest snapshot per (platform, video_id), for the channel the uploads go to."""
    if not METRICS.exists():
        return []
    snap = {}
    with open(METRICS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            snap[(r["platform"], r["video_id"])] = r
    return channel_rows(list(snap.values()), current_channel())


def learn(cfg):
    rows = mature(latest()) or latest()
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
    if current_channel():
        lines += ["- 対象: 今のYouTubeチャンネルの動画のみ（別アカウントに投稿された動画は除外）", ""]
    st = read_json(DATA / "analytics_status.json", None)
    if st is not None and not st.get("videos_with_data"):
        why = st.get("token_error") or "; ".join(f"{q['metric']}: HTTP {q['http']} {q.get('error', '') or str(q.get('rows')) + '行'}"[:160] for q in st.get("queries", [])) or "不明"
        lines += [f"- ⚠ YouTube Analytics の動画別データが取れていません（{why}）", ""]
    ch = (st or {}).get("channel_7d") or {}
    if ch.get("avg_view_pct") is not None:
        lines += [f"- チャンネル全体（直近{ch['days']}日）: 再生 {ch['views']:,.0f} / 平均視聴率 {ch['avg_view_pct']:.0f}% / 平均視聴 {ch['avg_view_sec']:.0f}秒 / 登録 +{ch['subs_gained']:.0f}", ""]
    lines += ["## 再生数トップ5", "", "| 媒体 | 再生 | いいね | フック |", "|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: int(r["views"]), reverse=True)[:5]:
        lines.append(f"| {r['platform']} | {int(r['views']):,} | {r['likes']} | {r['hook']} |")
    w = read_json(WEIGHTS, {})
    if w:
        lines += ["", "## 次の投稿配分（カテゴリ重み）", ""]
        lines += [f"- {cfg['categories'][c]['label']}: {v}" for c, v in sorted(w.items(), key=lambda x: -x[1])]
    lines += subscriber_sections(rows, cfg)
    lines += research_sections(rows, cfg)
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


MIN_N = 10  # per group, before a difference is treated as a finding rather than noise
MIN_AGE_H = 24  # younger videos are left out of comparisons: their views are still piling up


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _length_bucket(r):
    d = _num(r.get("duration"))
    if d is None:
        return ""
    return "〜29秒" if d < 30 else "30〜44秒" if d < 45 else "45〜60秒" if d <= 60 else "61秒〜"


def _table(rows, key, title):
    groups = defaultdict(list)
    for r in rows:
        k = key(r)
        if k:
            groups[k].append(r)
    if not groups:
        return []
    out = ["", f"## {title}", "",
           "| グループ | 本数 | 再生(中央値) | 平均視聴率 | いいね率 | コメント/1000再生 | シェア率 | 登録/1000再生 |", "|---|---|---|---|---|---|---|---|"]
    for k, g in sorted(groups.items(), key=lambda x: -statistics.median(int(r["views"]) for r in x[1])):
        views = [int(r["views"]) for r in g]
        tv = max(1, sum(views))
        pct = [p for p in (_num(r.get("avg_view_pct")) for r in g) if p is not None]
        subs = [x for x in (_num(r.get("subs_gained")) for r in g) if x is not None]
        out.append(f"| {k}{'' if len(g) >= MIN_N else ' ※少'} | {len(g)} | {statistics.median(views):,.0f} | "
                   f"{(f'{sum(pct) / len(pct):.0f}%') if pct else '-'} | "
                   f"{sum(int(r['likes']) for r in g) / tv:.1%} | {sum(int(r.get('comments') or 0) for r in g) / tv * 1000:.1f} | {sum(int(r.get('shares') or 0) for r in g) / tv:.2%} | "
                   f"{(f'{sum(subs) / tv * 1000:.1f}') if subs else '-'} |")
    return out


def mature(rows):
    """Rows old enough to compare. Rows without an age (collected before age_hours existed) count as old."""
    return [r for r in rows if (_num(r.get("age_hours")) is None or _num(r["age_hours"]) >= MIN_AGE_H)]


def research_sections(rows, cfg):
    """Breakdowns used to check the hypotheses in RESEARCH.md. '※少' marks groups below MIN_N videos."""
    young = len(rows) - len(mature(rows))
    rows = mature(rows)
    out = []
    if young:
        out += ["", f"※投稿から{MIN_AGE_H}時間たっていない動画 {young} 本は、以下の比較から除外しています。"]
    out += _table([r for r in rows if r.get("variant")], lambda r: r["variant"], "A/Bテスト（variant別）")
    out += _table(rows, lambda r: r.get("design"), "デザイン別（v1=旧、v2=カード+蛍光チップ、v3=ターミナル風、v3b=v3+冒頭を最初から表示）")
    out += _table(rows, lambda r: r.get("hook_type") or hook_style(r.get("hook") or ""), "フックの型別（警告・疑問・数字・言い切り。型を書いていない台本は冒頭の文から判定）")
    out += _table(rows, lambda r: r.get("hook") and ("冒頭に数字あり" if re.search(r"\d|[０-９]", r["hook"]) else "冒頭に数字なし"), "冒頭の数字の有無別")
    out += _table(rows, lambda r: r.get("slot_jst") and f"{r['slot_jst']}時台", "投稿時間（日本時間）別")
    out += _table(rows, _length_bucket, "尺別")
    labels = {k: v["label"] for k, v in cfg["categories"].items()}
    out += _table(rows, lambda r: labels.get(r.get("category"), r.get("category")), "カテゴリ別")
    if out:
        out += ["", f"※少 = {MIN_N}本未満。差があっても偶然の可能性が高いので、判断に使わない。",
                "平均視聴率・登録/1000再生は YouTube Analytics の権限があるときだけ入る（RESEARCH.md 参照）。"]
    return out
