"""Scene-based video styles, driven by the scene plan (sns/scenes.py) and the script's own diagram data (`visual`).

  sb  HIGH-RETENTION EXPLAINER  pure black, white + yellow, no cards, very large caption, hook straight on screen, hard cuts,
                                chunky diagram under the caption
  sc  DATA STORYTELLING         navy, cyan + amber, the diagram is the stage: caption on top, a large chart or flow below,
                                the active row highlighted, big number counter

Style A (premium finance) is design v4 in design_v3.py. Every style shares the caption timing, pauses and audio of the
render, keeps important content inside the safe area (top 150 px, bottom 420 px, right 140 px) and never zooms or flashes.
All sizes, colours and timings are in PRESETS and can be overridden in config.json video.styles.<design>.
"""
import copy
from pathlib import Path

from PIL import Image, ImageDraw

from . import design_v3 as v3, scenes as scene_mod

W, H = 1080, 1920

PRESETS = {
    "sb": {
        "colors": {"bg": "#000000", "text": "#FFFFFF", "accent": "#FFD60A", "pos": "#30D158", "neg": "#FF453A", "dim": "#8E8E93",
                   "track": "#1C1C1E", "past": "#D1D5DB"},
        "fonts": {"hook": 112, "caption": 100, "caption_min": 72, "hero": 300, "hero_caption": 76, "label": 46, "value": 52},
        "layout": {"margin": 64, "right": 140, "top": 150, "bottom": 420, "text_top": 230, "text_bottom": 900,
                   "diagram_top": 920, "row_pitch": 124},
        "anim": {"fade_sec": 0.18, "slide_px": 28, "visual_sec": 0.7, "count_sec": 0.7, "stagger": 0.22},
        "caption": {"max_chars": 14, "min_chars": 5, "lead_sec": 0.1, "weight": "mora"},
        "pause": {"sec": 0.2, "after_hook": 0.35, "after_question": 0.35},
    },
    "sc": {
        "colors": {"bg": "#0A1020", "text": "#F1F5F9", "accent": "#38BDF8", "hi": "#FBBF24", "pos": "#34D399", "neg": "#F87171",
                   "dim": "#64748B", "track": "#16223A", "surface": "#111B30", "edge": "#24324D"},
        "fonts": {"hook": 96, "caption": 84, "caption_min": 60, "hero": 210, "hero_caption": 64, "label": 48, "value": 58},
        "layout": {"margin": 64, "right": 140, "top": 150, "bottom": 420, "text_top": 200, "text_bottom": 660,
                   "diagram_top": 700, "row_pitch": 190},
        "anim": {"fade_sec": 0.25, "slide_px": 24, "visual_sec": 1.0, "count_sec": 0.9, "stagger": 0.25},
        "caption": {"max_chars": 16, "min_chars": 6, "lead_sec": 0.12, "weight": "mora"},
        "pause": {"sec": 0.25, "after_hook": 0.45, "after_question": 0.4},
    },
}
DESIGNS = tuple(PRESETS)

LIMITS = {("anim", "slide_px"): (0, 48), ("anim", "fade_sec"): (0.0, 0.6), ("anim", "visual_sec"): (0.2, 1.4),
          ("anim", "count_sec"): (0.2, 1.2), ("anim", "stagger"): (0.0, 0.5), ("caption", "lead_sec"): (0.0, 0.25),
          ("pause", "sec"): (0.1, 0.6), ("pause", "after_hook"): (0.1, 0.8), ("pause", "after_question"): (0.1, 0.8)}


def style(cfg):
    design = cfg["video"]["design"]
    st = copy.deepcopy(PRESETS[design])
    v3._merge(st, copy.deepcopy((cfg["video"].get("styles") or {}).get(design, {})))
    for (grp, key), (lo, hi) in LIMITS.items():
        st[grp][key] = min(hi, max(lo, st[grp][key]))
    st["design"] = design
    st["rgb"] = {k: v3._rgb(v) for k, v in st["colors"].items()}
    return st


def _fit(text, base, smallest, width, max_rows, weight="Bold"):
    size = base
    while True:
        font = v3.Sans(weight, size)
        rows = v3._wrap(text, font, width)
        if len(rows) >= 2:  # even out the rows
            alt = v3._wrap(text, font, min(width, font.getlength(text) / len(rows) * 1.08))
            rows = alt if len(alt) == len(rows) else rows
        if len(rows) <= max_rows or size <= smallest:
            return font, size, rows
        size -= 6


def _tone(text, rgb):
    """Colour of the big number: red for a cost, green for a gain, the style's accent otherwise."""
    if v3.COST_DOWN.search(text) or v3.DOUBLE.search(text):
        return rgb["pos"]
    if v3.COST.search(text):
        return rgb["neg"]
    if v3.GAIN.search(text):
        return rgb["pos"]
    return rgb["accent"]


def _rich(d, x, top, rows, text, font, size, fill, accent, lh=1.25, center=None):
    """Rows of text with its numbers in the accent colour. Returns the height used."""
    pos, step = 0, int(size * lh)
    for i, row in enumerate(rows):
        base = top + i * step + int(size * 0.92)
        cx = x if center is None else center - font.getlength(row) / 2
        for seg, hot in v3._runs(text[pos:pos + len(row)]):
            font.draw(d, cx, base, seg, accent if hot else fill)
            cx += font.getlength(seg)
        pos += len(row)
    return step * len(rows)


def _a(c):
    return tuple(c) + (255,)


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------- diagrams

def _shrink(weight, size, texts, max_w, smallest=32):
    """Font of the given weight, reduced from `size` until the widest text fits in max_w."""
    while size > smallest:
        f = v3.Sans(weight, size)
        if max(f.getlength(t) for t in texts) <= max_w:
            return f
        size -= 2
    return v3.Sans(weight, smallest)


def _row_p(p, i, n, stagger):
    return v3._row_p(p, i, n, stagger) if stagger else v3._ease(p)


def _diagram_b(d, st, vis, step, grow, p):
    """Chunky rows under the caption: bars (a comparison) or numbered steps; the row for the line being said is yellow."""
    c, lo, an = st["rgb"], st["layout"], st["anim"]
    x0, x1 = lo["margin"], W - lo["right"] - 4
    top, rows = lo["diagram_top"], vis["rows"]
    n = len(rows)
    pitch = lo["row_pitch"] - 14
    tag = v3.Sans("SemiBold", 36)
    tag.draw(d, x0, top + 30, vis["title"], _a(c["dim"]))
    labels, texts = [r["label"] for r in rows], [r.get("text", "") for r in rows]
    bars = vis["type"] == "bars"
    lab = _shrink("SemiBold", st["fonts"]["label"], labels, (x1 - x0) * (0.3 if bars else 0.8))
    val = _shrink("Bold", st["fonts"]["value"], texts, (x1 - x0) * 0.34)
    y0 = top + 56
    bh = int(pitch * 0.56)
    if bars:
        lw = int(max(lab.getlength(t) for t in labels) + 24)
        tw = int(max(val.getlength(t) for t in texts) + 24)
        bx0, bx1 = x0 + lw, x1 - tw
        mx = max(r["value"] for r in rows)
        for i, r in enumerate(rows):
            y = y0 + i * pitch
            on, cur = r["line"] <= step, r["line"] == step
            rp = _row_p(p, i, n, an["stagger"]) if i in grow else 1.0
            lab.draw(d, x0, y + int(pitch * 0.62), r["label"], _a(c["accent"] if cur else c["text"] if on else c["dim"]))
            d.rectangle([bx0, y + 8, bx1, y + 8 + bh], fill=_a(c["track"]))
            if on:
                w = max(6, int((bx1 - bx0) * r["value"] / mx * rp))
                d.rectangle([bx0, y + 8, bx0 + w, y + 8 + bh], fill=_a(c["accent"] if cur else c["past"]))
                val.draw(d, bx1 + 16, y + int(pitch * 0.64), r["text"], _a(_mix(c["bg"], c["accent"] if cur else c["text"], rp)))
    else:
        cr = int(pitch * 0.62)
        for i, r in enumerate(rows):
            y = y0 + i * pitch
            on, cur = r["line"] <= step, r["line"] == step
            rp = _row_p(p, i, n, an["stagger"]) if i in grow else 1.0
            col = c["accent"] if cur else c["text"]
            d.ellipse([x0, y + 4, x0 + cr, y + 4 + cr], fill=_a(_mix(c["bg"], col, rp)) if on else None,
                      outline=_a(col if on else c["dim"]), width=4)
            nf = v3.Sans("Bold", int(cr * 0.6))
            nf.draw(d, x0 + cr / 2 - nf.getlength(str(i + 1)) / 2, y + 4 + int(cr * 0.7), str(i + 1), _a(c["bg"] if on else c["dim"]))
            if on:
                lab.draw(d, x0 + cr + 28, y + 4 + int(cr * 0.72), r["label"], _a(_mix(c["bg"], col, rp)))


def _diagram_c(d, st, vis, step, grow, p):
    """The stage: a large bar chart with gridlines, or a flow of boxes joined by arrows. The active row is amber."""
    c, lo, an = st["rgb"], st["layout"], st["anim"]
    x0, x1 = lo["margin"], W - lo["right"] - 4
    top, rows = lo["diagram_top"], vis["rows"]
    n = len(rows)
    pitch = min(lo["row_pitch"], (H - lo["bottom"] - top - 70) // max(1, n))
    tag = v3.Sans("SemiBold", 38)
    tag.draw(d, x0, top + 34, vis["title"], _a(c["dim"]))
    labels, texts = [r["label"] for r in rows], [r.get("text", "") for r in rows]
    bars = vis["type"] == "bars"
    lab = _shrink("SemiBold", st["fonts"]["label"], labels, (x1 - x0) * (0.9 if bars else 0.72))
    val = _shrink("Bold", st["fonts"]["value"], texts, (x1 - x0) * 0.34)
    y0 = top + 74
    if bars:
        tw = int(max(val.getlength(t) for t in texts) + 24)
        bx0, bx1 = x0, x1 - tw
        mx = max(r["value"] for r in rows)
        for g in range(5):  # gridlines at 0, 25, 50, 75, 100 % of the longest bar
            gx = bx0 + (bx1 - bx0) * g / 4
            d.rectangle([gx - 1, y0, gx + 1, y0 + n * pitch - 20], fill=_a(c["track"]))
        for i, r in enumerate(rows):
            y = y0 + i * pitch
            on, cur = r["line"] <= step, r["line"] == step
            rp = _row_p(p, i, n, an["stagger"]) if i in grow else 1.0
            lab.draw(d, x0, y + int(pitch * 0.26), r["label"], _a(c["hi"] if cur else c["text"] if on else c["dim"]))
            by0, by1 = y + int(pitch * 0.34), y + int(pitch * 0.34) + int(pitch * 0.4)
            d.rectangle([bx0, by0, bx1, by1], fill=_a(c["surface"]), outline=_a(c["edge"]), width=2)
            if on:
                w = max(8, int((bx1 - bx0) * r["value"] / mx * rp))
                d.rectangle([bx0, by0, bx0 + w, by1], fill=_a(c["hi"] if cur else c["accent"]))
                val.draw(d, bx1 + 16, by1 - 6, r["text"], _a(_mix(c["bg"], c["hi"] if cur else c["text"], rp)))
    else:
        bh = pitch - 40
        for i, r in enumerate(rows):
            y = y0 + i * pitch
            on, cur = r["line"] <= step, r["line"] == step
            rp = _row_p(p, i, n, an["stagger"]) if i in grow else 1.0
            edge = c["hi"] if cur else c["accent"] if on else c["edge"]
            d.rounded_rectangle([x0, y, x1, y + bh], radius=16, fill=_a(c["surface"] if on else c["bg"]), outline=_a(_mix(c["bg"], edge, rp) if on else edge), width=4 if cur else 3)
            nf = v3.Sans("Bold", 40)
            d.ellipse([x0 + 24, y + bh // 2 - 28, x0 + 80, y + bh // 2 + 28], fill=_a(_mix(c["bg"], edge, rp)) if on else None, outline=_a(edge), width=3)
            nf.draw(d, x0 + 52 - nf.getlength(str(i + 1)) / 2, y + bh // 2 + 14, str(i + 1), _a(c["bg"] if on else c["dim"]))
            if on:
                lab.draw(d, x0 + 106, y + bh // 2 + 16, r["label"], _a(_mix(c["bg"], c["hi"] if cur else c["text"], rp)))
            if i < n - 1:  # arrow to the next box
                ax, ay = x0 + 52, y + bh
                d.rectangle([ax - 2, ay, ax + 2, ay + 38], fill=_a(c["edge"] if not on else c["accent"]))
                d.polygon([(ax - 10, ay + 28), (ax + 10, ay + 28), (ax, ay + 40)], fill=_a(c["edge"] if not on else c["accent"]))


# ---------------------------------------------------------------- caption layer

def caption_layer(st, kind, text, scene, count_p=1.0):
    """Everything that fades/slides with a caption chunk: the text, the big number, the call to action."""
    c, lo, fo = st["rgb"], st["layout"], st["fonts"]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, x1 = lo["margin"], W - lo["right"] - 4
    width = x1 - x0
    sb = st["design"] == "sb"
    hero = None
    if kind == "line":
        m = v3.HERO_RE.search(text)
        hero = m.group(0) if m and len(m.group(0)) <= 8 else None
    top, bot = lo["text_top"], lo["text_bottom"]
    tone = _tone(text, c)
    if kind == "hook":
        font, size, rows = _fit(text, fo["hook"], fo["caption_min"], width, 4 if sb else 3)
        h = int(size * 1.25) * len(rows)
        y = top + (bot - top - h) // 2 if sb else top + (bot - top - h) // 2
        d.rectangle([x0, y - 36, x0 + 96, y - 28], fill=_a(c["accent"]))
        _rich(d, x0, y, rows, text, font, size, _a(c["text"]), _a(c["accent"]))
        return layer
    if kind == "cta":
        font, size, rows = _fit(text, fo["caption"] - 8 if sb else 76, fo["caption_min"], width, 3 if sb else 2)
        h = int(size * 1.25) * len(rows)
        y = top + (bot - top - h) // 2 - 120 if sb else top + 10
        _rich(d, x0, y, rows, text, font, size, _a(c["text"]), _a(c["accent"]))
        py = y + h + 40
        d.rounded_rectangle([x0, py, x1, py + 104], radius=18, outline=_a(c["accent"]), width=4)
        v3.Sans("Bold", 50).draw(d, x0 + 36, py + 70, "保存して、あとで見返す", _a(c["accent"]))
        v3.Sans("SemiBold", 38).draw(d, x0, py + 104 + 56, "フォローで毎日1分、お金に強くなる", _a(c["dim"]))
        return layer
    if hero:
        big, unit = v3._split_hero(hero)
        hs = fo["hero"]
        while v3.Sans("Bold", hs).getlength(big) + 24 + (v3.Sans("Bold", int(hs * 0.3)).getlength(unit) if unit else 0) > width and hs > 120:
            hs -= 10
        shown = v3._count_text(big, count_p) if big.replace(",", "").replace("，", "").isdigit() else big
        fb = v3.Sans("Bold", hs)
        base = top + int(hs * 0.88) + (0 if not sb else 20)
        fb.draw(d, x0, base, shown, _a(tone))
        if unit:
            v3.Sans("Bold", int(hs * 0.3)).draw(d, x0 + fb.getlength(big) + 24, base, unit, _a(c["dim"]))
        font, size, rows = _fit(text, fo["hero_caption"], fo["caption_min"] - 12, width, 3)
        _rich(d, x0, base + 50, rows, text, font, size, _a(c["text"]), _a(tone))
        return layer
    font, size, rows = _fit(text, fo["caption"], fo["caption_min"], width, 3 if sb else 3)
    h = int(size * 1.25) * len(rows)
    y = top + (bot - top - h) // 2
    _rich(d, x0, y, rows, text, font, size, _a(c["text"]), _a(tone if v3.HERO_RE.search(text) else c["accent"]))
    return layer


def draw_frame(st, script, kind, text, scene, ctx, progress, grow=(), p=1.0, count_p=1.0, fade=1.0, slide=0):
    c, lo = st["rgb"], st["layout"]
    img = Image.new("RGBA", (W, H), _a(c["bg"]))
    d = ImageDraw.Draw(img)
    x0, x1 = lo["margin"], W - lo["right"] - 4
    d.rectangle([x0, 168, x1, 173], fill=_a(c["track"]))
    d.rectangle([x0, 168, x0 + max(6, int((x1 - x0) * progress)), 173], fill=_a(c["accent"] if st["design"] == "sb" else c["hi"]))
    vis = ctx.get("visual")
    if vis:
        (_diagram_b if st["design"] == "sb" else _diagram_c)(d, st, vis, ctx["step"], grow, p)
    layer = caption_layer(st, kind, text, scene, count_p)
    if fade < 1.0 or slide:
        a = layer.getchannel("A").point(lambda v, k=fade: int(v * k))
        layer.putalpha(a)
        shifted = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shifted.alpha_composite(layer, dest=(0, int(round(slide))))
        layer = shifted
    img.alpha_composite(layer)
    return img


def _ctx(script):
    return {"visual": script.get("visual"), "shown": set(), "step": 0, "scenes": None}


def dock_ctx_for(script):
    return _ctx(script)


def _scene(ctx, script, idx, st):
    if ctx.get("scenes") is None:
        ctx["scenes"] = scene_mod.plan_scenes(script, "cut" if st["design"] == "sb" else "slide")
    return ctx["scenes"][min(idx - 1, len(ctx["scenes"]) - 1)]


def still(cfg, script, text, kind, idx, total, out_png, progress=0.0):
    st = style(cfg)
    ctx = _ctx(script)
    ctx["step"] = 0 if kind == "hook" else (len(script["lines"]) if kind == "cta" else idx - 1)
    if kind == "cta" and ctx["visual"]:
        ctx["shown"] = set(range(len(ctx["visual"]["rows"])))
    draw_frame(st, script, kind, text, None, ctx, progress).convert("RGB").save(out_png)


def configure(cfg):
    return style(cfg)


def chunk_frames(cfg, script, text, kind, idx, total, progress, dur, fps, workdir, n0, ctx=None):
    """Frames for one caption chunk. The caption fades/slides in (the hook is on screen from frame 0); a row of the diagram
    that the narration has just reached grows in, a big number counts up. Returns (concat-list lines, next frame number)."""
    st = style(cfg)
    an = st["anim"]
    ctx = ctx if ctx is not None else _ctx(script)
    ctx["step"] = 0 if kind == "hook" else (len(script["lines"]) if kind == "cta" else idx - 1)
    scene = _scene(ctx, script, idx, st)
    vis = ctx.get("visual")
    grow = set()
    if vis:
        grow = set(v3.visual_rows(vis, ctx["step"])) - ctx["shown"]
        ctx["shown"] |= grow
    hero = kind == "line" and v3.HERO_RE.search(text) and len(v3.HERO_RE.search(text).group(0)) <= 8
    big = v3._split_hero(v3.HERO_RE.search(text).group(0))[0] if hero else ""
    counting = bool(hero and big.replace(",", "").replace("，", "").isdigit())
    tr = 0.0 if kind == "hook" else min(an["fade_sec"], dur * 0.5)
    tr_vis = min(an["visual_sec"], dur * 0.8) if grow else 0.0
    tr_cnt = min(an["count_sec"], dur * 0.8) if counting else 0.0
    n_tr = int(round(max(tr, tr_vis, tr_cnt) * fps))
    lines, n = [], n0
    for f in range(1, n_tr + 1):
        t = f / fps
        e = v3._ease(min(1.0, t / tr)) if tr else 1.0
        img = draw_frame(st, script, kind, text, scene, ctx, progress, grow, min(1.0, t / tr_vis) if tr_vis else 1.0,
                         v3._ease(min(1.0, t / tr_cnt)) if tr_cnt else 1.0, e, (1 - e) * an["slide_px"])
        png = Path(workdir) / f"slide{n:04d}.png"
        n += 1
        img.convert("RGB").save(png, compress_level=1)
        lines.append(f"file '{png.name}'\nduration {1 / fps:.4f}")
    final = draw_frame(st, script, kind, text, scene, ctx, progress)
    png = Path(workdir) / f"slide{n:04d}.png"
    n += 1
    final.convert("RGB").save(png, compress_level=1)
    lines.append(f"file '{png.name}'\nduration {max(0.05, dur - n_tr / fps):.4f}")
    return lines, n
