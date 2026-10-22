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

NUM_RE = re.compile(r"[0-9０-９][0-9０-９,，.]*(?:万|千|百|億)?[0-9０-９]*(?:円|パーセント|%|年|か月|ヶ月|日|歳|本|リットル|倍|つ|週|自治体|時間|分)?")
HERO_RE = re.compile(r"([0-9０-９][0-9０-９,，.]*(?:万|千|億)?)(円|倍|パーセント|%|リットル|年|か月|ヶ月)")
NO_LINE_START = set("、。，．」』）】！？ーっゃゅょァィゥェォッャュョ%")
GAIN = re.compile(r"増|得|貯|戻|還元|節約|安く|下が|お得")
COST_DOWN = re.compile(r"(?:代|費|料|税|支出|出費)[がはも]?[^、。]{0,8}(?:減|下が|安く)")  # a bill going down is good news
COST = re.compile(r"損|減|かかる|失う|払う|負担|ムダ|無駄")
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


def _wrap(text, font, max_w):
    rows, cur = [], ""
    for a in _atoms(text):
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
    pad = 64
    extra = (4 + 44) if kind == "hook" else (310 if hero else 0)
    panel_h = max(460 if kind == "hook" else 360, pad * 2 + extra + text_h)
    return dict(kind=kind, text=text, hero=hero, font=font, size=size, rows=rows, text_h=text_h, extra=extra,
                panel_h=panel_h, count=bool(hero and _split_hero(hero)[0].replace(",", "").isdigit()), tone=_tone(text))


def draw_chrome(img, cfg, script, kind, idx, total, progress):
    """Header (category, PR, counter, progress rule, title). Static during a chunk."""
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
    cnt = f"{idx:02d} / {total:02d}"
    f.draw(d, W - MARGIN - 8 - f.getlength(cnt), 170, cnt, SECOND)
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
    _draw_rows(d, X0 + 32, y, rows, text, pl["font"], size, lambda s: Sans("SemiBold", s), accent)
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
    if not pl["count"]:
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
