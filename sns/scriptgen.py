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
        "hook_type": {"type": "string"},
        "lines": {"type": "array", "items": {"type": "string"}},
        "cta": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "affiliate": {"type": ["string", "null"]},
        "fact_check_notes": {"type": "string"},
        "visual": {
            "type": ["object", "null"],
            "properties": {
                "type": {"type": "string", "enum": ["bars", "steps"]},
                "title": {"type": "string"},
                "rows": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"label": {"type": "string"}, "text": {"type": "string"}, "value": {"type": "number"},
                                   "line": {"type": "integer"}},
                    "required": ["label", "text", "value", "line"], "additionalProperties": False}},
            },
            "required": ["type", "title", "rows"],
            "additionalProperties": False,
        },
    },
    "required": ["title", "hook", "hook_type", "lines", "cta", "hashtags", "affiliate", "fact_check_notes", "visual"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """あなたは日本向けの「お金・節約の豆知識」縦型ショート動画（TikTok / YouTubeショート）の台本作家です。
顔出しなし、AI音声ナレーション＋大きな字幕だけで成立する台本を書きます。

構成（テーマと尺に合うものを選ぶ。全部を機械的に入れなくてよい）:
HOOK → QUESTION → REVEAL → EXPLANATION → EXAMPLE → CAVEAT / PAYOFF
- hook（0〜2秒）: 視聴者に関係する疑問、意外な事実、具体的な数字、誤解の訂正のどれかで始める。30字以内。チャンネル名・カテゴリ名・自己紹介・前置きは入れない。最初の1秒で、何の話で、見ると何が分かるかが伝わること。「かもしれません」「知ってた？」などのぼかしは使わず、身近な物や場面を具体的に言い切る。
- QUESTION / REVEAL: hookの問いの答えを、引き延ばさず適切なタイミングで言う。必要以上に答えを隠さない。
- EXPLANATION: なぜそうなるのかを短く。抽象論で終わらず、金額・比較・具体例を使う。
- EXAMPLE: 数字には必ず条件を添える（例:「年利3パーセントで20年、毎月1万円積み立てた場合」）。
- CAVEAT / PAYOFF: 注意事項（元本割れ、手数料、税金など、文脈上必要なもの）と、覚えておくべき結論を1つだけ言う。hookの問いをここまでに回収する。
- 次の動画への誘導やループ（最後の一文を冒頭につなぐ）は、内容上自然で、再視聴する価値がある場合だけ。
1動画に伝えるメッセージは1つだけ。関連する別の話題は削る。

書き方:
- 事実は日本の公的情報（国税庁、厚生労働省、金融庁、消費者庁など）で確認できる、変わりにくい内容だけを書く。自信のない数字は書かない。
- 事実・仮定・予測を区別して話す。仮定や予測は「仮に」「たとえば」「〜の場合」「〜とすると」と言葉で示し、断定しない。計算条件を省かない。
- 「必ず」「絶対」「誰でも簡単に」「99パーセントが知らない」「9割の人が知らない」など、断定・誇張・根拠のない希少性の訴求はしない。損失を訴えるときは、事実として確認できる金額・条件だけを使う。特定の銘柄・商品の推奨もしない。投資の話には元本割れの可能性に触れる。
- 同じ説明を言い換えて繰り返さない。結論の前に要約を挟まない。
- 「こんにちは」「今日は〜について」「それでは」のような前置きは禁止。
- 注意書き（投資の元本割れなど）が必要なときは、短い1文（25字以内）にする。
- hook を制度名・商品名＋数字の説明文（例:「新NISAの年間枠は〜」「リボ払いの手数料は年15パーセント」）で始めない。視聴者の行動・持ち物・場面か、してはいけない行動の警告で始め、制度の名前や数字はその後で出す。
- lines は各40字以内、ナレーションで一息で読める話し言葉。難しい漢語より自然な言い回しにする。
- 長さの目安は hook+lines+cta で {cmin}〜{cmax} 字。内容が足りるなら短くてよい。字数合わせの水増し（重複、言い換え、不要な注意書き）は禁止。
- 記号や絵文字は使わない。数字は読み上げやすく書く（例: 1万2千円）。
- cta は保存・コメント・シェアを促す一文。affiliate が null でない場合のみ「プロフィールのリンク」に誘導する。
- hashtags は4つ。affiliate がある場合は必ず "PR" を含める。
- affiliate は次から最も自然なもの1つ、なければ null: {affiliates}
- visual は動画の下に出し続ける図。数字を比べる話なら type=bars（label=項目、value=棒の長さの比、text=表示する数字と単位、line=その数字を話す lines の番号）、そうでなければ type=steps（label=要点を20字以内、text は空文字、value は 0、line=その要点を話す lines の番号）。title は16字以内、rows は2〜4個。text と label に使う数字は台本に出てくるものだけにし、新しい数字を作らない。図にできる内容がなければ null。
- fact_check_notes（動画には出さない）に、(1)根拠にした公的情報の名前、(2)計算条件・前提、(3)どの文が事実で、どれが仮定・予測かを短く書く。"""


def live_affiliates(cfg):
    """Affiliates that have a link on the profile page. A video must not point to a link or carry a PR label before one exists."""
    return [k for k, a in cfg["affiliates"].items() if a.get("url")]


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


def topic_families(cfg, text):
    """Names of the topic families (config `topic_cooldown.families`) a text touches, e.g. {"ふるさと納税"}."""
    fams = (cfg.get("topic_cooldown") or {}).get("families", {})
    return {name for name, keys in fams.items() if any(k in text for k in keys)}


def script_text(s):
    return s.get("title", "") + s.get("hook", "") + "".join(s.get("lines", []))


def recent_families(cfg):
    """Topic families used in the last `topic_cooldown.videos` videos. The same topic two days running
    went from ~1,000 views to under 100 in late October 2026 (5 ふるさと納税 videos in 5 days)."""
    n = (cfg.get("topic_cooldown") or {}).get("videos", 0)
    if not n:
        return set()
    out = set()
    for p in sorted(QUEUE.glob("*/script.json"))[-n:]:
        out |= topic_families(cfg, script_text(read_json(p, {})))
    return out


def cooldown_problems(script, cfg, recent=None):
    recent = recent_families(cfg) if recent is None else recent
    return [f"topic used in the last {cfg['topic_cooldown']['videos']} videos: {f}"
            for f in sorted(topic_families(cfg, script_text(script)) & recent)]


def seasonal(cfg, month=None, category=None, blocked=()):
    """Seasonal topics for this month; with `category`, only the ones that fit it, minus families on cooldown."""
    month = month or datetime.now(timezone.utc).month
    out = [x for x in cfg.get("seasonal", []) if month in x["months"]]
    if category:
        out = [x for x in out if category in x.get("categories", [category])]
    return [x for x in out if not topic_families(cfg, x["topic"]) & set(blocked)]


def seasonal_hint(cfg, category=None, blocked=()):
    return " / ".join(x["topic"] for x in seasonal(cfg, category=category, blocked=blocked)) or "特になし"


# warnings and everyday scenes opened the ~1,000-view videos; plain statistics and rule explanations stalled under 250
HOOK_TYPES = {"警告": 3, "身近な場面": 2, "損失回避": 1, "逆説": 1, "疑問": 1, "比較": 1}


def generate_with_claude(cfg, category, top_hooks=None, feedback=None):
    import json

    client = _client()
    cat_label = cfg["categories"][category]["label"]
    affiliates = ", ".join(live_affiliates(cfg)) or "（まだ無い。必ず null）"
    avoid = "、".join(recent_titles()) or "なし"
    blocked = recent_families(cfg)
    cmin, cmax = cfg["phases"][cfg.get("phase", "growth")]["chars"]
    hooks = "\n".join(f"- {h}" for h in (top_hooks or [])) or "- （まだデータなし）"
    import random
    hook_type = random.choices(list(HOOK_TYPES), weights=list(HOOK_TYPES.values()), k=1)[0]
    user = (
        f"hookの型: {hook_type}（hook_type にこの語をそのまま入れる）\n"
        f"カテゴリ: {cat_label}\n"
        f"今の時期に関心が高い話題（カテゴリに合えば優先、合わなければ無視）: {seasonal_hint(cfg, category, blocked)}\n"
        f"直近の動画で扱ったので、今回は使わない話題: {'、'.join(sorted(blocked)) or 'なし'}\n"
        f"過去に作ったタイトル（重複禁止）: {avoid}\n"
        f"これまで再生数が良かったフック（型を参考に、内容は真似しない）:\n{hooks}\n\n"
        "このカテゴリで、新しい台本を1本作ってください。"
        + (f"\n\n前回の台本は次の点で不合格でした。直して作り直してください:\n- " + "\n- ".join(feedback) if feedback else "")
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
    if data.get("affiliate") not in live_affiliates(cfg):
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
    clean = [s for s in pool if not lint(s)]
    pool = clean or pool  # lint-clean seeds first; the rest only once those run out
    blocked = recent_families(cfg)
    fresh = [s for s in pool if not topic_families(cfg, script_text(s)) & blocked]
    pool = fresh or pool
    preferred = [s for s in pool if s["category"] == category]
    keys = [k for x in seasonal(cfg, blocked=blocked) for k in x["keywords"]]
    in_season = [s for s in pool if any(k in s["title"] + s["hook"] for k in keys)]
    # a seasonal seed gets ahead of the category pick half the time, so the timely topics go out while they matter
    if in_season and random.random() < 0.5:
        preferred = in_season
    script = dict((preferred or pool)[0])
    used.add(script["id"])
    write_json(USED, sorted(used))
    script["source"] = "seed"
    if script.get("affiliate") not in live_affiliates(cfg):
        script["affiliate"] = None  # no PR label or disclosure while there is no link to disclose
    return script


def seed_by_id(seed_id):
    """A specific seed again, e.g. to re-post a video that went to the wrong channel. Leaves used_ids alone."""
    for s in read_json(SEED, []):
        if s["id"] == seed_id:
            script = dict(s)
            script["source"] = "seed"
            return script
    raise SystemExit(f"seed id not found: {seed_id}")


PREAMBLE = re.compile(r"^(こんにちは|みなさん|皆さん|今日は|今回は|それでは|さて|ところで|この動画では|今から)")
HYPE = re.compile(r"絶対|間違いなく|驚愕|衝撃|激変|最強|大損|人生が変わ|誰でも簡単|99パーセント|9割の人|ほとんどの人が知らない|99%")
HOOK_WARN = re.compile(r"ください|ないで|危険|危な|詐欺|間違|やめ")
HOOK_HEDGE = re.compile(r"かもしれ|知ってた|知ってる|ご存知|ご存じ")
# a rule or product name explained with a number ("新NISAの年間枠は…", "リボ払いの手数料は…") stalled at 50-250 views
HOOK_LECTURE = re.compile(r"^(新?NISA|ニーサ|イデコ|iDeCo|信託報酬|リボ払い|ふるさと納税|ワンストップ|年末調整|確定申告|"
                          r"高額療養費|傷病手当金|控除|手数料|金利|年利)[^、。？?]{0,12}は")
HOOK_DEVICE = re.compile(r"[？?]|\d|[０-９]|実は|意外|なのに|ではなく|じゃない|のに|逆|知らない|損|違い|しないで|ください|危な|危険|間違|やめ")
PROJECTION = re.compile(r"(年利|利回り|複利).*(なります|になる|増え|貯ま|膨らみ)|(増え|貯ま|膨らみ).*(年利|利回り|複利)")
ASSUMPTION = re.compile(r"仮に|たとえば|例えば|として|場合|想定|もし|のとき|なら|前提|とすると")


def _bigrams(t):
    t = re.sub(r"[、。！？\s]", "", t)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def visual_problems(script):
    """Problems with the optional `visual` (the diagram shown under the captions): shape, sizes, line numbers, and numbers
    that the narration never says."""
    v = script.get("visual")
    if not v:
        return []
    out = []
    rows, n = v.get("rows") or [], len(script["lines"])
    if v.get("type") not in ("bars", "steps"):
        out.append("visual type")
    if not 2 <= len(rows) <= 4:
        out.append(f"visual rows={len(rows)}")
    if len(v.get("title", "")) > 16:
        out.append("visual title too long")
    body = script["hook"] + "".join(script["lines"])
    said = set(re.findall(r"\d+(?:\.\d+)?", body.replace(",", "").replace("，", "")))
    for r in rows:
        if not 1 <= r.get("line", 0) <= n:
            out.append(f"visual line {r.get('line')}")
        if len(r.get("label", "")) > 22 or len(r.get("text", "")) > 12 or not r.get("label"):
            out.append(f"visual row size: {r.get('label')}")
        if v.get("type") == "bars" and not r.get("value", 0) > 0:
            out.append(f"visual bar value: {r.get('label')}")
        for num in re.findall(r"\d+(?:\.\d+)?", r.get("label", "") + r.get("text", "")):
            if num not in said:
                out.append(f"visual number not in the script: {num}")
    return out


def hook_style(hook):
    """Label a hook by how it opens (警告 / 疑問 / 数字 / 言い切り), so seed scripts, which carry no hook_type, can be compared too."""
    if HOOK_WARN.search(hook):
        return "警告"
    if re.search(r"[？?]", hook):
        return "疑問"
    if re.search(r"\d|[０-９]", hook):
        return "数字"
    return "言い切り"


def lint(script):
    """Writing-quality problems of a script (hook device, preamble, hype, repetition, unqualified projections).
    Pure text checks, so they also apply to the seed bank; validate() adds the length and safety checks."""
    problems = []
    hook, lines = script["hook"], script["lines"]
    if len(hook) > 30:
        problems.append(f"hook {len(hook)} chars (>30)")
    if not HOOK_DEVICE.search(hook):
        problems.append("hook has no question, contrast or number")
    if HOOK_LECTURE.search(hook) and not HOOK_WARN.search(hook):
        problems.append(f"hook opens by explaining a rule: {hook}")
    if HOOK_HEDGE.search(hook):
        problems.append(f"hedged hook: {hook}")
    for l in [hook, *lines]:
        if PREAMBLE.search(l):
            problems.append(f"preamble: {l}")
        if HYPE.search(l) and not re.search(r"禁止|危険|詐欺|サイン|ブロック", l):
            problems.append(f"hype: {l}")
    for l in lines:
        if len(l) > 40:
            problems.append(f"line {len(l)} chars (>40): {l}")
        if PROJECTION.search(l) and not ASSUMPTION.search(l):
            problems.append(f"projection without a stated condition: {l}")
    seen = [(l, _bigrams(l)) for l in [hook, *lines] if len(l) >= 8]
    for i in range(len(seen)):
        for j in range(i + 1, len(seen)):
            a, b = seen[i][1], seen[j][1]
            if a and b and len(a & b) / len(a | b) >= 0.6:
                problems.append(f"repeats: {seen[i][0]} / {seen[j][0]}")
    if "fact_check_notes" in script and len(script["fact_check_notes"].strip()) < 6:
        problems.append("fact_check_notes empty")
    return problems + visual_problems(script)


def validate(script, cfg):
    problems = []
    cmin, cmax = cfg["phases"][cfg.get("phase", "growth")]["chars"]
    total = len(script["hook"]) + sum(len(l) for l in script["lines"]) + len(script["cta"])
    if not 4 <= len(script["lines"]) <= 14:
        problems.append(f"lines={len(script['lines'])}")
    if not cmin * 0.8 <= total <= cmax * 1.15:
        problems.append(f"length {total} chars outside {cmin}-{cmax}")
    banned = re.compile(r"必ず儲か|絶対に儲か|元本保証で高利回り|確実に(?:儲か|増え|稼げ)|今が買い時|おすすめ銘柄|爆上が|"
                        r"ノーリスク|リスクなしで(?:増|稼|儲)|誰でも簡単に(?:稼|儲)")
    for l in [script["hook"], *script["lines"]]:
        # allowed only when the line is warning against the phrase
        if banned.search(l) and not re.search(r"禁止|危険|詐欺|サイン|ブロック", l):
            problems.append(f"banned phrase: {l}")
    body = script["hook"] + "".join(script["lines"])
    if not script.get("affiliate") and "プロフィール" in body + script.get("cta", ""):
        problems.append("points to a profile link without an affiliate")
    if script.get("category") == "invest_basic" and not re.search(r"元本割れ|減る|下が|リスク|損", body):
        problems.append("invest script without a downside note")
    return problems + lint(script)


def assign_variant(cfg):
    """Alternate the active experiment's arms across rendered videos so each arm gets the same slots and days."""
    exp = cfg.get("experiment") or {}
    arms = exp.get("arms") or []
    if not arms:
        return ""
    counts = {a: 0 for a in arms}
    for p in QUEUE.glob("*/script.json"):
        v = read_json(p, {}).get("variant", "")
        name, _, arm = v.partition(":")
        if name == exp["name"] and arm in counts:
            counts[arm] += 1
    low = min(counts.values())
    return f"{exp['name']}:{random.choice([a for a, c in counts.items() if c == low])}"


def assign_design(cfg):
    """A/B the video design: alternate `video.design_arms` over videos made since `video.design_ab_start`
    (a UTC date YYYYMMDD), so each arm gets the same slots and days. Falls back to `video.design`."""
    v = cfg["video"]
    arms = v.get("design_arms") or []
    if not arms:
        return v.get("design", "v2")
    counts = {a: 0 for a in arms}
    for p in QUEUE.glob("*/meta.json"):
        if p.parent.name[:8] >= v.get("design_ab_start", "00000000"):
            d = read_json(p, {}).get("design")
            if d in counts:
                counts[d] += 1
    low = min(counts.values())
    return random.choice([a for a, c in counts.items() if c == low])


def next_script(cfg, top_hooks=None, seed_only=False):
    category = pick_category(cfg)
    if has_llm() and not seed_only:
        try:
            s = generate_with_claude(cfg, category, top_hooks)
            bad = validate(s, cfg) + cooldown_problems(s, cfg)
            if bad:
                log("generated script failed validation, retrying once:", bad)
                s = generate_with_claude(cfg, category, top_hooks, feedback=bad[:6])
                bad = validate(s, cfg) + cooldown_problems(s, cfg)
            if not bad:
                return s
            log("generated script failed validation, using seed:", bad)
        except Exception as e:  # network, auth, refusal: never stop the daily run
            log("Claude generation failed, using seed:", repr(e))
    return next_seed(cfg, category)
