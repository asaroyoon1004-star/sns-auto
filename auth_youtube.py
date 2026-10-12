"""One-time: get a YouTube refresh token.

1. Google Cloud Console: enable "YouTube Data API v3", create an OAuth client of type "Desktop app".
2. YT_CLIENT_ID=... YT_CLIENT_SECRET=... python -m sns.auth_youtube
3. Open the printed URL, allow access, paste the `code` from the redirected localhost URL.
"""
import os
import urllib.parse

import requests

SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
REDIRECT = "http://localhost:8080/"


def main():
    cid, secret = os.environ["YT_CLIENT_ID"], os.environ["YT_CLIENT_SECRET"]
    q = urllib.parse.urlencode({"client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
                                "scope": SCOPES, "access_type": "offline", "prompt": "consent"})
    print("Open this URL and allow access:\n", "https://accounts.google.com/o/oauth2/v2/auth?" + q)
    raw = input("Paste the full redirected URL (or just the code): ").strip()
    code = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query).get("code", [raw])[0]
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": cid, "client_secret": secret, "redirect_uri": REDIRECT,
        "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    print("\nYT_REFRESH_TOKEN =", r.json()["refresh_token"])


if __name__ == "__main__":
    main()
