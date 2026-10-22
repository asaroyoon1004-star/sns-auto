"""YouTube Shorts upload via the YouTube Data API v3 (OAuth refresh token, resumable upload).

Env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN  (get them once with `python -m sns.auth_youtube`).
"""
import os

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"


def configured():
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def access_token():
    r = requests.post(TOKEN_URL, data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def build_metadata(cfg, script):
    tags = " ".join("#" + h for h in script["hashtags"])
    desc = [script["hook"], "", *script["lines"], "", script["cta"], ""]
    if script.get("affiliate"):
        desc.append("※概要欄・プロフィールのリンクにはアフィリエイト広告（PR）を含みます。")
    desc += ["※この動画はAI音声・自動生成の字幕で制作しています。内容は一般的な情報で、個別の助言ではありません。", "", tags, "#Shorts"]
    title = f"{script['title']}｜{script['hook']}"
    if len(title) > 95:
        title = script["title"]
    return title, "\n".join(desc), script["hashtags"]


def upload(cfg, script, video_path):
    ycfg = cfg["upload"]["youtube"]
    title, desc, tags = build_metadata(cfg, script)
    token = access_token()
    body = {
        "snippet": {"title": title, "description": desc, "tags": tags, "categoryId": ycfg.get("category_id", "27"),
                    "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
        "status": {"privacyStatus": ycfg.get("privacy", "public"), "selfDeclaredMadeForKids": False,
                   # Synthetic voice + generated captions: disclose as altered/synthetic media.
                   "containsSyntheticMedia": True},
    }
    size = os.path.getsize(video_path)
    init = requests.post(
        UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        json=body, timeout=60,
    )
    init.raise_for_status()
    with open(video_path, "rb") as f:
        put = requests.put(init.headers["Location"], data=f,
                           headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"}, timeout=600)
    put.raise_for_status()
    vid = put.json()["id"]
    return {"platform": "youtube", "id": vid, "url": f"https://youtube.com/shorts/{vid}"}


def stats(video_ids):
    """Return {id: {views, likes, comments}} for uploaded videos."""
    if not video_ids:
        return {}
    token = access_token()
    out = {}
    for i in range(0, len(video_ids), 50):
        r = requests.get(f"{API}/videos", params={"part": "statistics", "id": ",".join(video_ids[i:i + 50])},
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
        r.raise_for_status()
        for it in r.json().get("items", []):
            s = it["statistics"]
            out[it["id"]] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                             "comments": int(s.get("commentCount", 0))}
    return out


def channel_summary(days=7):
    """Channel-wide totals for the last `days` days (no per-video filter): tells 'no data yet' apart from 'the video filter matched nothing',
    and gives an overall watch-percentage while the per-video numbers are still empty."""
    from datetime import date, timedelta

    try:
        token = access_token()
        end = date.today()
        r = requests.get(ANALYTICS, headers={"Authorization": f"Bearer {token}"}, timeout=30,
                         params={"ids": "channel==MINE", "startDate": (end - timedelta(days=days)).isoformat(), "endDate": end.isoformat(),
                                 "metrics": "views,averageViewDuration,averageViewPercentage,subscribersGained,estimatedMinutesWatched"})
        if r.status_code != 200:
            return {"http": r.status_code, "error": r.text[:300]}
        rows = r.json().get("rows") or []
        if not rows:
            return {"http": 200, "rows": 0}
        keys = ["views", "avg_view_sec", "avg_view_pct", "subs_gained", "minutes_watched"]
        return {"http": 200, "days": days, **dict(zip(keys, rows[0]))}
    except Exception as e:
        return {"error": type(e).__name__}


LAST_STATUS = {}  # what the last analytics() call saw; analytics.collect() saves it so a blank report can be diagnosed


def analytics(video_ids, start="2026-01-01"):
    """Return {id: {avg_view_sec, avg_view_pct, subs_gained, shares[, engaged_views]}} from the YouTube Analytics API.

    Needs the YouTube Analytics API enabled and a token with yt-analytics.readonly (re-run auth_youtube to add it).
    Returns {} instead of raising, so the weekly run still works with the older token.
    """
    if not video_ids:
        return {}
    from datetime import date

    LAST_STATUS.clear()
    LAST_STATUS.update(ids=len(video_ids), queries=[])
    try:
        token = access_token()
    except Exception as e:
        print("[sns] analytics token failed:", repr(e))
        LAST_STATUS["token_error"] = type(e).__name__
        return {}
    out = {}
    base = {"ids": "channel==MINE", "startDate": start, "endDate": date.today().isoformat(), "dimensions": "video"}
    queries = [("averageViewDuration,averageViewPercentage,subscribersGained,shares",
                ["avg_view_sec", "avg_view_pct", "subs_gained", "shares"]),
               ("engagedViews", ["engaged_views"])]  # newer metric; skipped quietly if the API rejects it
    for metrics, keys in queries:
        for i in range(0, len(video_ids), 200):
            chunk = video_ids[i:i + 200]
            r = requests.get(ANALYTICS, headers={"Authorization": f"Bearer {token}"}, timeout=30,
                             params={**base, "metrics": metrics, "filters": "video==" + ",".join(chunk),
                                     "sort": "-" + metrics.split(",")[0], "maxResults": len(chunk)})
            if r.status_code != 200:
                print(f"[sns] YouTube Analytics ({metrics.split(',')[0]}) unavailable: {r.status_code} {r.text[:200]}")
                LAST_STATUS["queries"].append({"metric": metrics.split(",")[0], "http": r.status_code, "error": r.text[:300]})
                break
            rows = r.json().get("rows", [])
            LAST_STATUS["queries"].append({"metric": metrics.split(",")[0], "http": 200, "rows": len(rows)})
            for row in rows:
                out.setdefault(row[0], {}).update({k: v for k, v in zip(keys, row[1:])})
    return out
