"""TikTok upload via the Content Posting API.

mode "inbox"  : the video lands in the TikTok app's inbox as a draft; you tap Post (works before app audit).
mode "direct" : posts publicly; requires the app to pass TikTok's audit (unaudited apps can only post SELF_ONLY).

Env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN  (get them once with `python -m sns.auth_tiktok`).
"""
import math
import os

import requests

API = "https://open.tiktokapis.com/v2"
CHUNK = 10 * 1024 * 1024


def configured():
    return all(os.environ.get(k) for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"))


def access_token():
    r = requests.post(f"{API}/oauth/token/", data={
        "client_key": os.environ["TIKTOK_CLIENT_KEY"],
        "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": os.environ["TIKTOK_REFRESH_TOKEN"],
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"TikTok token refresh failed: {j}")
    # TikTok rotates refresh tokens; surface the new one so the workflow can store it.
    if j.get("refresh_token") and j["refresh_token"] != os.environ["TIKTOK_REFRESH_TOKEN"]:
        print("::notice::TikTok issued a new refresh token; update the TIKTOK_REFRESH_TOKEN secret")
    return j["access_token"]


def caption(script):
    tags = list(dict.fromkeys([*script["hashtags"], "お金の知識"]))
    pr = "【PR】" if script.get("affiliate") else ""
    return f"{pr}{script['hook']} " + " ".join("#" + t for t in tags)


def _source_info(size):
    chunk = min(CHUNK, size)
    count = max(1, size // chunk)
    return {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}, chunk, count


def upload(cfg, script, video_path):
    mode = cfg["upload"]["tiktok"].get("mode", "inbox")
    token = access_token()
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    size = os.path.getsize(video_path)
    src, chunk, count = _source_info(size)
    if mode == "direct":
        info = requests.post(f"{API}/post/publish/creator_info/query/", headers=h, timeout=30).json()
        levels = info.get("data", {}).get("privacy_level_options", ["SELF_ONLY"])
        privacy = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in levels else levels[0]
        body = {"post_info": {"title": caption(script), "privacy_level": privacy,
                              "disable_comment": False, "disable_duet": False, "disable_stitch": False,
                              "brand_content_toggle": False, "brand_organic_toggle": bool(script.get("affiliate")),
                              "is_aigc": True},
                "source_info": src}
        url = f"{API}/post/publish/video/init/"
    else:
        body = {"source_info": src}
        url = f"{API}/post/publish/inbox/video/init/"
    r = requests.post(url, headers=h, json=body, timeout=60)
    j = r.json()
    if r.status_code != 200 or j.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init failed: {j}")
    upload_url, publish_id = j["data"]["upload_url"], j["data"]["publish_id"]
    with open(video_path, "rb") as f:
        for i in range(count):
            start = i * chunk
            end = size - 1 if i == count - 1 else start + chunk - 1
            f.seek(start)
            data = f.read(end - start + 1)
            pr = requests.put(upload_url, data=data, timeout=600, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(data)),
                "Content-Range": f"bytes {start}-{end}/{size}"})
            if pr.status_code not in (200, 201, 206):
                raise RuntimeError(f"TikTok chunk {i} failed: {pr.status_code} {pr.text[:200]}")
    return {"platform": "tiktok", "id": publish_id, "mode": mode, "caption": caption(script)}


def stats(_video_ids=None):
    """Return {video_id: {views, likes, comments, shares, title}} for the account's recent videos."""
    token = access_token()
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    out, cursor = {}, None
    for _ in range(5):
        body = {"max_count": 20, **({"cursor": cursor} if cursor else {})}
        r = requests.post(f"{API}/video/list/", headers=h, json=body, timeout=30,
                          params={"fields": "id,title,view_count,like_count,comment_count,share_count,create_time"})
        d = r.json().get("data", {})
        for v in d.get("videos", []):
            out[v["id"]] = {"views": v.get("view_count", 0), "likes": v.get("like_count", 0),
                            "comments": v.get("comment_count", 0), "shares": v.get("share_count", 0),
                            "title": v.get("title", ""), "create_time": v.get("create_time")}
        if not d.get("has_more"):
            break
        cursor = d.get("cursor")
    return out


def follower_count():
    token = access_token()
    r = requests.get(f"{API}/user/info/", params={"fields": "follower_count"},
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    return int(r.json().get("data", {}).get("user", {}).get("follower_count", 0))
