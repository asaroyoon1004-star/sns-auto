"""Build the public site (docs/index.html, served by GitHub Pages) from config.affiliates.

The page doubles as the TikTok for Developers "Website URL": it must be a complete public site
that uses the same icon as the app (docs/icon.png) and links to the Terms and Privacy Policy.
"""
import html

from .common import ROOT, log

STYLE = """
:root{--bg:#f6f7f9;--fg:#14181f;--card:#fff;--mute:#5b6472;--accent:#1b6b5f;--line:#e3e6ea}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--fg:#eef1f5;--card:#1a1f26;--mute:#9aa4b2;--accent:#5cc8b0;--line:#2a313a}}
body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.7}
header,main,footer{max-width:680px;margin:0 auto;padding:0 16px}
header{display:flex;align-items:center;gap:12px;padding-top:20px;padding-bottom:12px;border-bottom:1px solid var(--line)}
header a{display:flex;align-items:center;gap:12px;color:var(--fg);text-decoration:none;font-weight:700}
header img{width:40px;height:40px;border-radius:10px}
main{padding-top:24px;padding-bottom:32px}
h1{font-size:24px;margin:0 0 8px} h2{font-size:18px;margin:32px 0 8px}
.hero{display:flex;gap:16px;align-items:center} .hero img{width:96px;height:96px;border-radius:20px;flex:none}
.sub,.en{color:var(--mute)} .en{font-size:14px}
ul{padding-left:20px}
.card{display:flex;align-items:center;gap:10px;background:var(--card);color:var(--fg);text-decoration:none;
padding:16px;border-radius:14px;margin:10px 0;font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.pr{font-size:11px;border:1px solid var(--mute);color:var(--mute);border-radius:4px;padding:1px 5px}
.arrow{margin-left:auto;color:var(--accent);font-size:22px}
.note{color:var(--mute);font-size:12px} .empty{color:var(--mute)}
footer{border-top:1px solid var(--line);padding-top:16px;padding-bottom:40px;font-size:14px;color:var(--mute)}
footer nav{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:8px} footer a{color:var(--accent)}
"""


def head(title):
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="icon" type="image/png" href="icon.png"><link rel="apple-touch-icon" href="icon.png">
<style>{STYLE}</style></head><body>"""


def header(name):
    return f'<header><a href="./"><img src="icon.png" alt="">{html.escape(name)}</a></header>'


def footer(name):
    return f"""<footer><nav><a href="./">ホーム / Home</a><a href="terms.html">利用規約 / Terms of Service</a>\
<a href="privacy.html">プライバシーポリシー / Privacy Policy</a></nav>© 2026 {html.escape(name)}</footer></body></html>
"""


def build(cfg):
    lc = cfg["landing"]
    name = cfg["channel_name"]
    cards = []
    for key, a in cfg["affiliates"].items():
        if not a.get("url"):
            continue
        cards.append(f'<a class="card" href="{html.escape(a["url"])}" rel="sponsored noopener" target="_blank">'
                     f'<span class="pr">PR</span>{html.escape(a["label"])}<span class="arrow">›</span></a>')
    if not cards:
        cards.append('<p class="empty">リンクは準備中です。 / Links coming soon.</p>')
    page = head(lc["title"]) + header(name) + f"""<main>
<div class="hero"><img src="icon.png" alt="{html.escape(name)}"><div>
<h1>{html.escape(name)}</h1>
<p class="sub">節約・貯金・税金など、暮らしのお金の知識を1分のショート動画で解説するチャンネルです。</p>
</div></div>
<p class="en">A Japanese short-video channel that explains everyday personal finance (saving, budgeting, taxes, energy bills) in one minute, published on TikTok and YouTube Shorts.</p>

<h2>このサイトについて / About</h2>
<p>当サイトは「{html.escape(name)}」の公式サイトです。動画の内容紹介と、動画で紹介したサービスのリンクを掲載しています。</p>
<p class="en">This is the official website of "{html.escape(name)}". It describes the channel and lists the services mentioned in our videos.</p>

<h2>アプリ「sns-auto」について / About the sns-auto app</h2>
<p>sns-auto は、運営者が自分で制作した動画を、運営者本人のTikTok・YouTubeアカウントに投稿し、再生数などの統計を確認するための個人用ツールです。第三者のアカウントやデータは扱いません。</p>
<ul class="en">
<li>Uploads videos created by the operator to the operator's own TikTok and YouTube accounts (TikTok Content Posting API).</li>
<li>Reads basic statistics (views, likes, follower count) of the operator's own videos to improve future content.</li>
<li>Does not access, collect or share data of any other users.</li>
</ul>

<h2>紹介サービス / Featured services</h2>
{''.join(cards)}
<p class="note">{html.escape(lc['disclosure'])}</p>
</main>""" + footer(name)
    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    log("wrote", out, f"({len([c for c in cards if 'card' in c])} links)")
    return out
