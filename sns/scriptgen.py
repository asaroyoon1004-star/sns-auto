"""Pick the next script: Claude generates one when an API key is set, else the seed bank is used."""
import os
import random
import re
from datetime import datetime, timezone

from .common import SEED, USED, WEIGHTS, QUEUE, read_json, write_json, log

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "lines": {"type": "array", "items": {"type": "string"}},
        "cta": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "affiliate": {"type": ["string", "null"]},
        "fact_check_notes": {"type": "string"},
    },
    "required": ["title", "hook", "lines", "cta", "hashtags", "affiliate", "fact_check_notes"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """あなたは日本向けの「お金・節約の豆知識」縦型ショート動画（TikTok / YouTubeショート）の台本作家です。
顔出しなし、AI音声ナレーション＋大きな字幕だけで成立する台本を書きます。

守ること:
- 事実は日本の公的情報（国税庁、厚生労働省、金融庁、消費者庁など）で確認できる、変わりにくい内容だけを書く。自信のない数字は書かない。
- 「必ず儲かる」「絶対」など断定的な表現、特定の銘柄・商品の推奨はしない。投資の話には元本割れの可能性に触れる。
- hook は最初の1秒で指が止まる一文（30字以内）。疑問形か意外な事実で、できれば具体的な数字を入れる。
- hook で出した問いの答えは、lines の最初では言わず、最後の方まで引っ張る。
- 注意書き（投資の元本割れなど）が必要なときは、短い1文（25字以内）にする。
- lines は各40字以内の話し言葉。全体（hook+lines+cta）で {cmin}〜{cmax} 字にする。
- 記号や絵文字は使わない。数字は読み上げやすく書く（例: 1万2千円）。
- cta は保存・コメント・シェアを促す一文。affiliate が null でない場合のみ「プロフィールのリンク」に誘導する。
- hashtags は4つ。affiliate がある場合は必ず "PR" を含める。
- affiliate は次から最も自然なもの1つ、なければ null: {affiliates}
- fact_check_notes に、根拠にした公的情報の名前を短く書く（動画には出さない）。"""


def _client():
    import anthropic

    return anthropic.Anthropic()


def has_llm():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def pick_category(cfg):
    weights = read_json(WEIGHTS, {})
    cats = list(cfg["categories"].keys())
    w = [max(0.2, float(weights.get(c, 1.0))) for c in cats]
    return random.choices(cats, weights=w, k=1)[0]


def recent_titles(limit=60):
    titles = []
    for meta in sorted(QUEUE.glob("*/script.json"))[-limit:]:
        titles.append(read_json(meta, {}).get("title", ""))
    return [t for t in titles if t]


def generate_with_claude(cfg, category, top_hooks=None):
    import json

    client = _client()
    cat_label = cfg["categories"][category]["label"]
    affiliates = ", ".join(cfg["affiliates"].keys())
    avoid = "、".join(recent_titles()) or "なし"
    cmin, cmax = cfg["phases"][cfg.get("phase", "growth")]["chars"]
    hooks = "\n".join(f"- {h}" for h in (top_hooks or [])) or "- （まだデータなし）"
    user = (
        f"カテゴリ: {cat_label}\n"
        f"過去に作ったタイトル（重複禁止）: {avoid}\n"
        f"これまで再生数が良かったフック（型を参考に、内容は真似しない）:\n{hooks}\n\n"
        "このカテゴリで、新しい台本を1本作ってください。"
    )
    resp = client.beta.messages.create(
        model=cfg["llm"]["model"],
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": cfg["llm"].get("effort", "medium"),
                       "format": {"type": "json_schema", "schema": SCRIPT_SCHEMA}},
        system=SYSTEM_PROMPT.format(affiliates=affiliates, cmin=cmin, cmax=cmax),
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    data["category"] = category
    data["id"] = "g" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    data["source"] = "claude"
    if data.get("affiliate") not in cfg["affiliates"]:
        data["affiliate"] = None
    return data


def next_seed(cfg, category=None):
    seeds = read_json(SEED, [])
    used = set(read_json(USED, []))
    pool = [s for s in seeds if s["id"] not in used]
    if not pool:
        log("seed bank exhausted; recycling from the start")
        used = set()
        pool = seeds
    preferred = [s for s in pool if s["category"] == category]
    script = dict((preferred or pool)[0])
    used.add(script["id"])
    write_json(USED, sorted(used))
    script["source"] = "seed"
    return script


def validate(script, cfg):
    problems = []
    cmin, cmax = cfg["phases"][cfg.get("phase", "growth")]["chars"]
    total = len(script["hook"]) + sum(len(l) for l in script["lines"]) + len(script["cta"])
    if not 4 <= len(script["lines"]) <= 14:
        problems.append(f"lines={len(script['lines'])}")
    if not cmin * 0.85 <= total <= cmax * 1.2:
        problems.append(f"length {total} chars outside {cmin}-{cmax}")
    banned = re.compile(r"必ず儲か|絶対に儲か|元本保証で高利回り")
    for l in [script["hook"], *script["lines"]]:
        # allowed only when the line is warning against the phrase
        if banned.search(l) and not re.search(r"禁止|危険|詐欺|サイン|ブロック", l):
            problems.append(f"banned phrase: {l}")
    return problems


def next_script(cfg, top_hooks=None, seed_only=False):
    category = pick_category(cfg)
    if has_llm() and not seed_only:
        try:
            s = generate_with_claude(cfg, category, top_hooks)
            if not validate(s, cfg):
                return s
            log("generated script failed validation, using seed:", validate(s, cfg))
        except Exception as e:  # network, auth, refusal: never stop the daily run
            log("Claude generation failed, using seed:", repr(e))
    return next_seed(cfg, category)
