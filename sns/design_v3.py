"""Design v3: dark financial-terminal look (see RESEARCH.md section 9).

Flat near-black background, an opaque surface panel with a gold edge, left-aligned text at most 75% of the width,
numbers in gold (green / red when the sentence is about a gain / a cost), no gradients, glass, emoji or heavy shadows.
Motion is limited to opacity + a small upward slide (0.4 s ease-out) and a count-up on the big number.
"""
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .common import ROOT

W, H = 1080, 1920
BG, SURFACE, TEXT = (5, 7, 10), (16, 20, 25), (248, 250, 252)
SECOND, GOLD = (138, 148, 166), (200, 169, 106)
GREEN, RED = (74, 222, 128), (239, 68, 68)
RULE, EDGE = (30, 37, 47), (38, 46, 58)

MARGIN = 64                      # safe area
X0, X1 = 72, 72 + 810            # text column: 75% of the width, left aligned (clear of the right-side buttons)
PANEL_X = (MARGIN, W - MARGIN)
CENTER_Y = 900
REGION = (0, 300, W, 1700)       # the part of the frame that animates

FONTS = ROOT / "assets" / "fonts"
SERIF_CJK = ["/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", "/usr/share/fonts/noto-cjk/NotoSerifCJK-Bold.ttc"]

NUM_RE = re.compile(r"[0-9０-９][0-9０-９,，.]*(?:[万千百億][0-9０-９,，]*)*(?:円|パーセント|%|年|か月|ヶ月|日|歳|本|リットル|倍|つ|週|自治体|時間|分)?")
HERO_RE = re.compile(r"([0-9０-９][0-9０-９,，.]*(?:[万千億百][0-9０-９,，]*)*)(円|倍|パーセント|%|リットル|年|か月|ヶ月)")
NO_LINE_START = set("、。，．」』）】！？ーっゃゅょァィゥェォッャュョ%")
GAIN = re.compile(r"増|得|貯|戻|還元|節約|安く|下が|お得")
COST_DOWN = re.compile(r"(?:代|費|料|税|支出|出費)[がはも]?[^、。]{0,8}(?:減|下が|安く)")  # a bill going down is good news
COST = re.compile(r"損|減|(?<![年間分日])かかる|失う|払う|負担|ムダ|無駄|膨ら")
DOUBLE = re.compile(r"倍になる|倍に増")  # "お金が2倍になる" is good news even though the sentence also says かかる
LATIN = re.compile(r"([A-Za-z0-9 .,%&/\-]+)")


@lru_cache(maxsize=64)
def _plex(weight, size):
    return ImageFont.truetype(str(FONTS / f"IBMPlexSansJP-{weight}.ttf"), size)


@lru_cache(maxsize=32)
def _baskerville(size):
    f = ImageFont.truetype(str(FONTS / "LibreBaskerville-Variable.ttf"), size)
    try:
        f.set_variation_by_axes([700])
    except Exception:  # a build without variation support still draws the regular weight
        pass
    return f


@lru_cache(maxsize=32)
def _noto_serif(size):
    for p in SERIF_CJK:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return _plex("Bold", size)


class Serif:
    """Editorial face: Libre Baskerville for Latin letters, Noto Serif CJK for Japanese (Baskerville has no kana/kanji)."""

    def __init__(self, size):
        self.size = size

    def _parts(self, s):
        return [(p, _baskerville(self.size) if LATIN.fullmatch(p) else _noto_serif(self.size)) for p in LATIN.split(s) if p]

    def getlength(self, s):
        return sum(f.getlength(p) for p, f in self._parts(s))

    def draw(self, d, x, y, s, fill):
        for p, f in self._parts(s):
            d.text((x, y), p, font=f, fill=fill, anchor="ls")
            x += f.getlength(p)


class Sans:
    def __init__(self, weight, size):
        self.f = _plex(weight, size)

    def getlength(self, s):
        return self.f.getlength(s)

    def draw(self, d, x, y, s, fill):
        d.text((x, y), s, font=self.f, fill=fill, anchor="ls")


def _atoms(text):
    out, i = [], 0
    for m in NUM_RE.finditer(text):
        out += list(text[i:m.start()]) + [m.group(0)]
        i = m.end()
    return out + list(text[i:])


PARTICLES = set("はがをにでともへの")
MULTI_PARTICLES = ("から", "まで", "より", "など", "ので", "のに", "けど", "だけ", "しか", "でも")
HIRA = re.compile(r"[ぁ-ん]")
PUNCT = "、。！？"


def _phrases(text):
    """Split into phrases (bunsetsu-like) that may sit on one row: a break is allowed only after punctuation, after a
    particle, or between okurigana and the next kanji, never inside a word like 電気代 or after お/ご in お金."""
    atoms = _atoms(text)
    out, cur = [], ""
    for i, a in enumerate(atoms):
        cur += a
        nxt = atoms[i + 1] if i + 1 < len(atoms) else None
        if nxt is None:
            break
        ok = a[-1] in PUNCT
        if not ok and not HIRA.match(nxt[0]) and nxt[0] not in NO_LINE_START and HIRA.match(a[-1]):
            tail = "".join(atoms[max(0, i - 1):i + 1])
            if a in PARTICLES or tail.endswith(MULTI_PARTICLES):
                ok = True
            elif not (a in "おご" and (i == 0 or not HIRA.match(atoms[i - 1][-1]))):
                ok = len(cur) >= 2 or not HIRA.match(cur[0])  # okurigana -> next word
        if ok:
            out.append(cur)
            cur = ""
    return out + ([cur] if cur else [])


KATA = re.compile(r"[ァ-ヶー]")


def _subphrases(ph):
    """Weaker break points for an over-long phrase: after a particle, or where katakana turns into another script."""
    out, cur = [], ""
    atoms = _atoms(ph)
    for i, a in enumerate(atoms):
        cur += a
        nxt = atoms[i + 1] if i + 1 < len(atoms) else None
        prev = atoms[i - 1][-1] if i else ""
        particle = a in PARTICLES and prev and not HIRA.match(prev) and (nxt or "")[:1] not in ("は", "も")  # に after リンク, not the と inside まとめ
        if nxt and nxt[0] not in NO_LINE_START and (particle or (KATA.match(a[-1]) and re.match(r"[一-龥]", nxt[0]))):
            out.append(cur)
            cur = ""
    out.append(cur)
    return [x for x in out if x]


def _wrap(text, font, max_w):
    rows, cur = [], ""
    for ph in _phrases(text):
        if cur and font.getlength(cur + ph) <= max_w:
            cur += ph
            continue
        if cur:
            rows.append(cur)
            cur = ""
        if font.getlength(ph) <= max_w:
            cur = ph
            continue
        for a in _subphrases(ph):  # a phrase wider than the column: break at weaker points, then per character
            if cur and font.getlength(cur + a) > max_w and a[0] not in NO_LINE_START:
                rows.append(cur)
                cur = a
            else:
                cur += a
    return rows + [cur] if cur else rows


def _fit(text, make_font, base, max_rows):
    size = base
    while True:
        font = make_font(size)
        rows = _wrap(text, font, X1 - X0)
        if len(rows) >= 2:  # even out the rows
            alt = _wrap(text, font, min(X1 - X0, font.getlength(text) / len(rows) * 1.08))
            rows = alt if len(alt) == len(rows) else rows
        if len(rows) >= 2 and len(rows[-1]) <= 2:  # no one-word orphan on the last row
            for w in range(X1 - X0 - 20, X1 - X0 - 260, -20):
                alt = _wrap(text, font, w)
                if len(alt) <= max_rows and len(alt[-1]) > 2:
                    rows = alt
                    break
        if len(rows) <= max_rows or size <= 56:
            return font, size, rows
        size -= 6


def _runs(text):
    out, i = [], 0
    for m in NUM_RE.finditer(text):
        if m.start() > i:
            out.append((text[i:m.start()], False))
        out.append((m.group(0), True))
        i = m.end()
    if i < len(text):
        out.append((text[i:], False))
    return out


def _tone(text):
    """Colour of the big number: red when the sentence is about a cost, green about a gain, gold otherwise."""
    if COST_DOWN.search(text):
        return GREEN
    if DOUBLE.search(text):
        return GREEN
    if COST.search(text):
        return RED
    if GAIN.search(text):
        return GREEN
    return GOLD


def _draw_rows(d, x, top, rows, text, font, size, num_font, accent):
    lh = int(size * 1.34)
    pos = 0
    for i, row in enumerate(rows):
        base = top + i * lh + int(size * 0.98)
        cx = x
        for seg, hot in _runs(text[pos:pos + len(row)]):
            f = num_font(size) if hot else font
            f.draw(d, cx, base, seg, accent if hot else TEXT)
            cx += f.getlength(seg)
        pos += len(row)
    return lh * len(rows)


def _split_hero(hero):
    m = HERO_RE.fullmatch(hero)
    return (m.group(1), m.group(2)) if m else (hero, "")


def _count_text(big, p):
    """'120' -> '47' at p=0.4. Plain integers only; anything else is shown as is."""
    digits = big.replace(",", "").replace("，", "")
    if not digits.isdigit():
        return big
    v = int(int(digits) * min(1.0, p))
    return f"{v:,}" if "," in big else str(v)


UNIT_RE = re.compile(r"(円|パーセント|%|か月|ヶ月|年|倍)$")
_MULT = {"億": 10 ** 8, "万": 10 ** 4, "千": 1000, "百": 100, "": 1}


def _parse_amount(tok):
    """'13万7800円' -> 137800, '1万2千円' -> 12000. Returns None when it isn't a plain amount."""
    body = UNIT_RE.sub("", tok).replace(",", "").replace("，", "")
    parts = re.findall(r"([0-9.]+)(億|万|千|百)?", body)
    if not parts or "".join(a + b for a, b in parts) != body:
        return None
    try:
        return sum(float(a) * _MULT[b] for a, b in parts)
    except ValueError:
        return None


def visual_spec(text):
    """Pick a diagram for the numbers in a caption: comparison bars (2+ amounts, or 1 vs N倍), a % gauge, or a year timeline."""
    found = []
    for m in NUM_RE.finditer(text):
        tok = m.group(0)
        u = UNIT_RE.search(tok)
        v = _parse_amount(tok) if u else None
        if u and v:
            unit = {"%": "パーセント", "ヶ月": "か月"}.get(u.group(1), u.group(1))
            found.append((tok, unit, v))
    by = {}
    for tok, unit, v in found:
        by.setdefault(unit, []).append((tok, v))
    for unit, items in by.items():
        uniq = {v: tok for tok, v in items}
        if len(uniq) >= 2 and unit in ("円", "年", "か月"):
            return dict(type="bars", rows=[(t, v) for v, t in sorted(uniq.items())][-3:])
    if "倍" in by:
        tok, v = by["倍"][0]
        if 1 < v <= 100:
            return dict(type="bars", rows=[("1倍", 1.0), (tok, v)])
    if "パーセント" in by:
        tok, v = by["パーセント"][0]
        if 0 < v <= 100:
            return dict(type="gauge", tok=tok, value=v)
    for unit in ("年", "か月"):
        if unit in by:
            tok, v = by[unit][0]
            if 2 <= v <= (40 if unit == "年" else 36):
                return dict(type="timeline", tok=tok, value=v, unit=unit)
    return None


def _vis_height(spec):
    if not spec:
        return 0
    if spec["type"] == "bars":
        return len(spec["rows"]) * 64 + (len(spec["rows"]) - 1) * 18
    return 100 if spec["type"] == "gauge" else 110


def draw_visual(d, spec, x0, x1, top, accent, p):
    """Flat, animated diagram (opacity-free: it grows with p, ease-out, no overshoot)."""
    p = max(0.0, min(1.0, p))
    lab = Sans("SemiBold", 38)
    small = Sans("SemiBold", 32)
    if spec["type"] == "bars":
        rows = spec["rows"]
        lw = int(min(300, max(lab.getlength(t) for t, _ in rows) + 28))
        mx, bw = max(v for _, v in rows), x1 - x0 - lw
        for i, (tok, v) in enumerate(rows):
            y = top + i * (64 + 18)
            top_row = v == mx
            lab.draw(d, x0, y + 46, tok, (TEXT if top_row else SECOND) + (255,))
            d.rectangle([x0 + lw, y + 10, x0 + lw + bw, y + 14 + 36], fill=RULE + (255,))
            w = max(6, int(bw * v / mx * p))
            d.rectangle([x0 + lw, y + 10, x0 + lw + w, y + 50], fill=(accent if top_row else SECOND + (255,)))
    elif spec["type"] == "gauge":
        w = x1 - x0
        d.rectangle([x0, top + 6, x1, top + 38], fill=RULE + (255,))
        fw = max(6, int(w * spec["value"] / 100 * p))
        d.rectangle([x0, top + 6, x0 + fw, top + 38], fill=accent)
        d.rectangle([x0 + fw - 2, top, x0 + fw + 2, top + 44], fill=TEXT + (255,))
        for frac, t in ((0, "0"), (0.5, "50"), (1, "100%")):
            tx = x0 + int(w * frac)
            tw = small.getlength(t)
            small.draw(d, tx if frac == 0 else tx - tw if frac == 1 else tx - tw / 2, top + 88, t, SECOND + (255,))
    else:  # timeline
        w = x1 - x0 - 40
        n = spec["value"]
        step = 1 if n <= 12 else 5 if n <= 30 else 10
        y = top + 28
        d.rectangle([x0, y - 2, x0 + w, y + 2], fill=RULE + (255,))
        d.rectangle([x0, y - 3, x0 + int(w * p), y + 3], fill=accent)
        n = int(n)
        ticks = list(range(0, n + 1, step))
        if ticks[-1] != n:
            ticks.append(n)
        for t in ticks:
            tx = x0 + int(w * t / n)
            on = t / n <= p + 1e-6
            d.ellipse([tx - 9, y - 9, tx + 9, y + 9], fill=(accent if on else RULE + (255,)))
            lbl = spec["tok"] if t == n else str(t)
            tw = small.getlength(lbl)
            small.draw(d, min(max(tx - tw / 2, x0), x0 + w + 40 - tw), top + 88, lbl, (TEXT if t == n else SECOND) + (255,))


def plan(kind, text):
    """Layout facts for one caption chunk; the same plan is reused for every animation frame."""
    hero = None
    if kind == "line":
        m = HERO_RE.search(text)
        hero = m.group(0) if m and len(m.group(0)) <= 8 else None
    if kind == "hook":
        font, size, rows = _fit(text, Serif, 92, 5)
    elif hero:
        font, size, rows = _fit(text, lambda s: Sans("Bold", s), 64, 3)
    else:
        font, size, rows = _fit(text, lambda s: Sans("Bold", s), 82, 4)
    text_h = int(size * 1.34) * len(rows)
    spec = visual_spec(text) if kind == "line" else None
    vis_h = _vis_height(spec)
    pad = 64
    extra = (4 + 44) if kind == "hook" else (310 if hero else 0)
    panel_h = max(460 if kind == "hook" else 360, pad * 2 + extra + text_h + (vis_h + 44 if spec else 0))
    return dict(kind=kind, text=text, hero=hero, spec=spec, vis_h=vis_h, font=font, size=size, rows=rows, text_h=text_h, extra=extra,
                panel_h=panel_h, count=bool(hero and _split_hero(hero)[0].replace(",", "").isdigit()), anim=bool(spec) or bool(hero and _split_hero(hero)[0].replace(",", "").isdigit()), tone=_tone(text))


def draw_chrome(img, cfg, script, kind, idx, total, progress):
    """Header (category, PR, progress rule, title). Static during a chunk."""
    d = ImageDraw.Draw(img)
    cat = cfg["categories"].get(script["category"], {"label": ""})
    f = Sans("SemiBold", 40)
    d.rectangle([MARGIN + 8, 150, MARGIN + 24, 166], fill=GOLD)
    f.draw(d, MARGIN + 42, 170, cat["label"], SECOND)
    x = MARGIN + 42 + f.getlength(cat["label"]) + 28
    if script.get("affiliate"):
        fp = Sans("SemiBold", 32)
        wpr = fp.getlength("PR") + 28
        d.rectangle([x, 136, x + wpr, 180], outline=SECOND, width=2)
        fp.draw(d, x + 14, 170, "PR", SECOND)
    d.rectangle([MARGIN, 204, W - MARGIN, 205], fill=RULE)
    d.rectangle([MARGIN, 203, MARGIN + max(6, int((W - 2 * MARGIN) * progress)), 206], fill=GOLD)
    # A/B: the title often gives away the hook's answer, so one arm leaves it off the hook screen
    if not (kind == "hook" and script.get("variant") == "hook_title:hide"):
        Serif(52).draw(d, MARGIN + 8, 286, script["title"], SECOND)


def draw_content(layer, pl, count_p=1.0):
    """Panel + text on a transparent layer in full-frame coordinates."""
    d = ImageDraw.Draw(layer)
    top = CENTER_Y - pl["panel_h"] // 2
    bot = top + pl["panel_h"]
    d.rounded_rectangle([PANEL_X[0], top, PANEL_X[1], bot], radius=14, fill=SURFACE + (255,), outline=EDGE + (255,), width=2)
    d.rectangle([PANEL_X[0], top + 14, PANEL_X[0] + 5, bot - 14], fill=GOLD + (255,))
    kind, text, size, rows = pl["kind"], pl["text"], pl["size"], pl["rows"]
    y = top + 64
    if kind == "hook":
        d.rectangle([X0 + 32, y, X0 + 32 + 72, y + 4], fill=GOLD + (255,))
        y += 4 + 44
        _draw_rows(d, X0 + 32, y, rows, text, pl["font"], size, lambda s: Sans("SemiBold", s), GOLD + (255,))
        return
    accent = pl["tone"] + (255,)
    if pl["hero"]:
        big, unit = _split_hero(pl["hero"])
        hs = 230
        while Sans("SemiBold", hs).getlength(big) + 20 + (Sans("SemiBold", 76).getlength(unit) if unit else 0) > X1 - X0 - 40 and hs > 110:
            hs -= 10
        shown = _count_text(big, count_p) if pl["count"] else big
        fb = Sans("SemiBold", hs)
        base = y + int(hs * 0.92)
        fb.draw(d, X0 + 32, base, shown, accent)
        if unit:  # keep the final number's width so the unit doesn't jitter during the count-up
            Sans("SemiBold", 76).draw(d, X0 + 32 + fb.getlength(big) + 20, base, unit, SECOND + (255,))
        ry = base + 52
        d.rectangle([X0 + 32, ry, X1 - 8, ry + 2], fill=RULE + (255,))
        y = ry + 34
    used = _draw_rows(d, X0 + 32, y, rows, text, pl["font"], size, lambda s: Sans("SemiBold", s), accent)
    if pl["spec"]:
        draw_visual(d, pl["spec"], X0 + 32, X1 - 8, y + used + 44, accent, count_p)
    if kind == "cta":
        by = bot + 56
        d.rectangle([PANEL_X[0], by, PANEL_X[1], by + 92], outline=GOLD + (255,), width=3)
        Sans("Bold", 46).draw(d, X0 + 32, by + 64, "保存して、あとで見返す", GOLD + (255,))
        Sans("SemiBold", 40).draw(d, X0 + 32, by + 170, "フォローで毎日1分、お金に強くなる", SECOND + (255,))


def _ease(p):
    return 1 - (1 - p) ** 3  # ease-out cubic: settles without overshoot


def _base(cfg, script, kind, idx, total, progress):
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw_chrome(img, cfg, script, kind, idx, total, progress)
    return img


def still(cfg, script, text, kind, idx, total, out_png, progress=0.0):
    """Final (settled) frame, used for thumbnails and previews."""
    img = _base(cfg, script, kind, idx, total, progress)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_content(layer, plan(kind, text))
    Image.alpha_composite(img, layer).convert("RGB").save(out_png)


def chunk_frames(cfg, script, text, kind, idx, total, progress, dur, fps, workdir, n0):
    """Frames for one caption chunk: ~0.4 s fade + slide-up (with a count-up on the big number), then a held frame.

    Returns (concat-list lines, next frame number)."""
    pl = plan(kind, text)
    base = _base(cfg, script, kind, idx, total, progress)
    box = REGION
    region = base.crop(box)
    tr = min(0.4, dur * 0.5)
    n_tr = max(0, int(round(tr * fps)))
    lines, n = [], n0
    static = None
    if not pl["anim"]:
        static = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_content(static, pl)
        static = static.crop(box)
    for f in range(1, n_tr + 1):
        p = f / n_tr
        e = _ease(p)
        layer = static
        if layer is None:
            full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw_content(full, pl, count_p=e)
            layer = full.crop(box)
        a = layer.getchannel("A").point(lambda v, k=e: int(v * k))
        lay = layer.copy()
        lay.putalpha(a)
        frame = base.copy()
        reg = region.copy()
        reg.alpha_composite(lay, dest=(0, int(round((1 - e) * 36))))
        frame.paste(reg, (box[0], box[1]))
        png = Path(workdir) / f"slide{n:04d}.png"
        n += 1
        frame.convert("RGB").save(png, compress_level=1)
        lines.append(f"file '{png.name}'\nduration {1 / fps:.4f}")
    final = base.copy()
    full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_content(full, pl, 1.0)
    final = Image.alpha_composite(final, full).convert("RGB")
    png = Path(workdir) / f"slide{n:04d}.png"
    n += 1
    final.save(png, compress_level=1)
    lines.append(f"file '{png.name}'\nduration {max(0.05, dur - n_tr / fps):.4f}")
    return lines, n
