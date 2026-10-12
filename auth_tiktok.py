"""One-time: get a TikTok refresh token.

1. developers.tiktok.com: create an app, add Login Kit + Content Posting API,
   scopes video.upload (+ video.publish for direct mode) and video.list, redirect URI e.g. https://<you>.github.io/sns-auto/
2. TIKTOK_CLIENT_KEY=... TIKTOK_CLIENT_SECRET=... TIKTOK_REDIRECT=... python -m sns.auth_tiktok
3. Open the URL, allow, paste the redirected URL.
"""
import os
import secrets
import urllib.parse

import requests


def main():
    key, secret, redirect = os.environ["TIKTOK_CLIENT_KEY"], os.environ["TIKTOK_CLIENT_SECRET"], os.environ["TIKTOK_REDIRECT"]
    q = urllib.parse.urlencode({"client_key": key, "scope": "user.info.basic,user.info.stats,video.upload,video.publish,video.list",
                                "response_type": "code", "redirect_uri": redirect, "state": secrets.token_hex(8)})
    print("Open this URL and allow access:\n", "https://www.tiktok.com/v2/auth/authorize/?" + q)
    raw = input("Paste the full redirected URL: ").strip()
    code = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query)["code"][0]
    r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={
        "client_key": key, "client_secret": secret, "code": code, "grant_type": "authorization_code",
        "redirect_uri": redirect}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    print("\nTIKTOK_REFRESH_TOKEN =", r.json()["refresh_token"])


if __name__ == "__main__":
    main()
