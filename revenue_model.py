"""Month-by-month revenue model. Every number is an editable assumption, not a promise.

python -m sns.revenue_model            # base case
python -m sns.revenue_model --all      # conservative / base / optimistic
"""
import argparse

SCENARIOS = {
    "conservative": dict(avg_views=[150, 400, 900, 1600, 2500, 3500, 4500, 5500, 6500, 7500, 8500, 9500],
                         link_ctr=0.002, lp_ctr=0.25, cvr=0.02, reward=3500, crp_per_1k=60),
    "base":         dict(avg_views=[300, 800, 2000, 4000, 6500, 9000, 11000, 12500, 14000, 15000, 16000, 17000],
                         link_ctr=0.003, lp_ctr=0.30, cvr=0.03, reward=4000, crp_per_1k=80),
    "optimistic":   dict(avg_views=[600, 2000, 5000, 9000, 14000, 18000, 22000, 25000, 28000, 30000, 32000, 34000],
                         link_ctr=0.004, lp_ctr=0.35, cvr=0.04, reward=4500, crp_per_1k=110),
}
COMMON = dict(
    posts_per_month=90,          # 3 per day, same video on each platform
    platforms=("tiktok", "youtube"),
    follow_rate=0.007,           # followers gained per view
    crp_min_followers=10_000,    # TikTok Creator Rewards: 10k followers, 100k views/30d, videos > 1 min
    crp_qualified_share=0.7,     # share of views that count as qualified
    ypp_subs=1_000, ypp_shorts_views_90d=10_000_000,
    yt_rpm=30,                   # JPY per 1k Shorts views once in YPP (finance niche, estimate)
)


def run(name, months=12):
    s = {**COMMON, **SCENARIOS[name]}
    followers = {p: 0 for p in s["platforms"]}
    yt_hist = []
    rows = []
    for m in range(months):
        avg = s["avg_views"][min(m, len(s["avg_views"]) - 1)]
        views = {p: avg * s["posts_per_month"] for p in s["platforms"]}
        for p in s["platforms"]:
            followers[p] += int(views[p] * s["follow_rate"])
        yt_hist.append(views["youtube"])
        total_views = sum(views.values())
        conversions = total_views * s["link_ctr"] * s["lp_ctr"] * s["cvr"]
        aff = conversions * s["reward"]
        crp = 0
        if followers["tiktok"] >= s["crp_min_followers"] and views["tiktok"] >= 100_000:
            crp = views["tiktok"] * s["crp_qualified_share"] / 1000 * s["crp_per_1k"]
        yt = 0
        if followers["youtube"] >= s["ypp_subs"] and sum(yt_hist[-3:]) >= s["ypp_shorts_views_90d"]:
            yt = views["youtube"] / 1000 * s["yt_rpm"]
        rows.append(dict(month=m + 1, avg_views=avg, views=total_views, tt_followers=followers["tiktok"],
                         yt_subs=followers["youtube"], conversions=round(conversions, 1),
                         affiliate=round(aff), crp=round(crp), yt_ads=round(yt), total=round(aff + crp + yt)))
    return rows


def table(name):
    rows = run(name)
    out = [f"### {name}", "", "| 月 | 1本平均再生 | 月間総再生 | TikTokフォロワー | YT登録者 | 成約件数 | アフィ | TikTok報酬 | YT広告 | 合計(円) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['month']} | {r['avg_views']:,} | {r['views']:,} | {r['tt_followers']:,} | {r['yt_subs']:,} | "
                   f"{r['conversions']} | {r['affiliate']:,} | {r['crp']:,} | {r['yt_ads']:,} | **{r['total']:,}** |")
    hit = next((r["month"] for r in rows if r["total"] >= 250_000), None)
    out += ["", f"月25万円の到達: {'%d か月目' % hit if hit else '12か月以内には未達'}", ""]
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    for n in (SCENARIOS if a.all else ["base"]):
        print(table(n))
