"""Render a 1080x1920 caption-style short from a script: one slide per sentence, synced to its narration."""
import json
import random
import re
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import ROOT, log
from .tts import synth

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
]
NO_LINE_START = set("、。，．」』）】！？ーっゃゅょァィゥェォッャュョ%")
NUM_RE = re.compile(r"[0-9０-９][0-9０-９,，.]*(?:万|千|百|億)?[0-9０-９]*(?:円|パーセント|%|年|か月|ヶ月|日|歳|本|リットル|倍|つ|週|自治体|時間|分)?")
SAFE_X = (90, 930)  # keep clear of the right-side action buttons
ACCENT = (255, 214, 10)
WHITE = (255, 255, 255)


def _font(size):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    raise RuntimeError("no Japanese font found; install fonts-noto-cjk")


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=8)
def _gradient_base(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    t, b = _hex(top), _hex(bottom)
    d = ImageDraw.Draw(img)
    for y in range(h):
        r = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(t[i] + (b[i] - t[i]) * r) for i in range(3)))
    return img


def _gradient(w, h, top, bottom):
    return _gradient_base(w, h, top, bottom).copy()


def wrap(text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if font.getlength(cur + ch) > max_w and cur and ch not in NO_LINE_START:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def wrap_balanced(text, font, max_w):
    rows = wrap(text, font, max_w)
    if len(rows) < 2:
        return rows
    target = font.getlength(text) / len(rows) * 1.08
    alt = wrap(text, font, min(max_w, target))
    return alt if len(alt) == len(rows) else rows


def _accent_mask(text):
    mask = [False] * len(text)
    for m in NUM_RE.finditer(text):
        for i in range(m.start(), m.end()):
            mask[i] = True
    return mask


def draw_rich(draw, xy_center_y, text, font, max_w, line_gap=1.35):
    """Draw centered, wrapped text; numbers in accent color; thick outline for legibility."""
    rows = wrap_balanced(text, font, max_w)
    size = font.size
    total_h = int(len(rows) * size * line_gap)
    y = xy_center_y - total_h // 2
    mask = _accent_mask(text)
    idx = 0
    cx = (SAFE_X[0] + SAFE_X[1]) // 2
    for row in rows:
        x = cx - font.getlength(row) / 2
        for ch in row:
            color = ACCENT if mask[idx] else WHITE
            draw.text((x, y), ch, font=font, fill=color, stroke_width=max(3, size // 14), stroke_fill=(0, 0, 0))
            x += font.getlength(ch)
            idx += 1
        y += int(size * line_gap)
    return total_h


def make_slide_v1(cfg, script, text, kind, idx, total, out_png, progress=0.0, scale=1.0, step=0):
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    cat = cfg["categories"].get(script["category"], {"label": "", "color": ["#222", "#444"]})
    img = _gradient(W, H, *cat["color"])
    d = ImageDraw.Draw(img)

    # header: category pill + title
    f_small, f_title = _font(40), _font(64)
    pill = f"  {cat['label']}  "
    pw = f_small.getlength(pill)
    d.rounded_rectangle([SAFE_X[0], 230, SAFE_X[0] + pw, 290], radius=30, fill=(255, 255, 255))
    d.text((SAFE_X[0], 236), pill, font=f_small, fill=_hex(cat["color"][0]))
    if script.get("affiliate"):
        d.rounded_rectangle([SAFE_X[0] + pw + 16, 230, SAFE_X[0] + pw + 116, 290], radius=12, outline=WHITE, width=3)
        d.text((SAFE_X[0] + pw + 36, 236), "PR", font=f_small, fill=WHITE)
    # A/B: the title often gives away the hook's answer (e.g. "72の法則"), so one arm leaves it off the hook screen
    if not (kind == "hook" and script.get("variant") == "hook_title:hide"):
        d.text((SAFE_X[0], 320), script["title"], font=f_title, fill=WHITE, stroke_width=4, stroke_fill=(0, 0, 0))

    # body
    size = int((92 if kind == "hook" else 80) * scale)
    font = _font(size)
    if kind == "hook":
        d.rounded_rectangle([60, 640, W - 60, 1260], radius=40, outline=ACCENT, width=8)
    draw_rich(d, 950, text, font, SAFE_X[1] - SAFE_X[0])

    if kind == "cta":
        draw_rich(d, 1250, "フォローで毎日1分、お金に強くなる", _font(48), SAFE_X[1] - SAFE_X[0])

    # step counter + progress bar
    f_c = _font(36)
    d.text((SAFE_X[0], 1430), f"{idx}/{total}", font=f_c, fill=(230, 230, 230))
    track = (SAFE_X[0], 1490, SAFE_X[1], 1504)
    d.rounded_rectangle(track, radius=7, fill=(70, 80, 90))
    d.rounded_rectangle((track[0], track[1], track[0] + max(14, int((track[2] - track[0]) * progress)), track[3]),
                        radius=7, fill=ACCENT)
    d.text((SAFE_X[0], 1640), cfg["channel_name"], font=f_c, fill=(255, 255, 255, 180))
    img.save(out_png)


# ---------------------------------------------------------------------------------------------------------------
# design v2: dark money-explainer look. Big outlined caption on a translucent card, numbers as highlighter chips,
# a hero number for amounts/ratios, a thin progress bar at the top, everything clear of the platform UI
# (top ~130px, right ~150px, bottom ~400px).
# ---------------------------------------------------------------------------------------------------------------
HERO_RE = re.compile(r"[0-9０-９][0-9０-９,，.]*(?:万|千|億)?(?:円|倍|パーセント|%|リットル|年|か月|ヶ月)")
INK = (20, 20, 24)


def _mix(c, d, f):
    return tuple(int(c[i] + (d[i] - c[i]) * f) for i in range(3))


_GLOWS = [((180, 420, 520), (900, 1250, 460)), ((860, 380, 500), (200, 1300, 520)),
          ((300, 700, 480), (860, 1100, 520)), ((820, 640, 520), (260, 1000, 480))]


@lru_cache(maxsize=32)
def _bg_v2(w, h, c0, c1, variant):
    top, bottom = _mix(_hex(c0), (0, 0, 0), 0.62), _mix(_hex(c1), (0, 0, 0), 0.5)
    base = _gradient_base(w, h, "#%02x%02x%02x" % top, "#%02x%02x%02x" % bottom).convert("RGBA")
    glow_c = _mix(_hex(c1), (255, 255, 255), 0.25)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    for x, y, r in _GLOWS[variant % 4]:
        g.ellipse([x - r, y - r, x + r, y + r], fill=(*glow_c, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    deco = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(deco)
    for k in range(-h, w, 110):  # faint diagonal stripes
        d.line([(k, h), (k + h * 0.75, 0)], fill=(255, 255, 255, 9), width=36)
    cx, cy = w - 120 + (variant % 2) * 40, 1480  # a faint coin
    for r, wd in ((520, 44), (380, 16)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, 20), width=wd)
    return Image.alpha_composite(Image.alpha_composite(base, glow), deco)


def _runs(text):
    mask = _accent_mask(text)
    out, i = [], 0
    while i < len(text):
        j = i
        while j < len(text) and mask[j] == mask[i]:
            j += 1
        out.append((text[i:j], mask[i]))
        i = j
    return out


def _atoms(text):
    """Characters, except a number with its unit stays in one piece so a line never breaks inside '120リットル'."""
    out, i = [], 0
    for m in NUM_RE.finditer(text):
        out += list(text[i:m.start()]) + [m.group(0)]
        i = m.end()
    return out + list(text[i:])


def _wrap_atoms(text, font, max_w):
    rows, cur = [], ""
    for a in _atoms(text):
        if cur and font.getlength(cur + a) > max_w and a[0] not in NO_LINE_START:
            rows.append(cur)
            cur = a
        else:
            cur += a
    return rows + [cur] if cur else rows


def _fit(text, base_size, max_w, max_rows):
    size = base_size
    while True:
        font = _font(size)
        rows = _wrap_atoms(text, font, max_w)
        if len(rows) >= 2:  # even out the rows
            alt = _wrap_atoms(text, font, min(max_w, font.getlength(text) / len(rows) * 1.08))
            rows = alt if len(alt) == len(rows) else rows
        if len(rows) <= max_rows or size <= 60:
            return font, size, rows
        size -= 8


def _caption_v2(draw, cy, text, font, size, rows, line_gap=1.3):
    """Draw pre-wrapped rows centered on cy; numeric runs sit on a yellow chip."""
    lh = int(size * line_gap)
    # CJK glyphs sit low in the font box (centre ~0.78 em below the draw origin); centre the glyphs, not the box
    y = int(cy - (len(rows) - 1) * lh / 2 - 0.78 * size)
    cx = (SAFE_X[0] + SAFE_X[1]) // 2
    pos = 0
    for row in rows:
        x = cx - font.getlength(row) / 2
        for seg, hot in _runs(text[pos:pos + len(row)]):
            sw = font.getlength(seg)
            if hot:
                pad = size * 0.1
                draw.rounded_rectangle([x - pad, y + size * 0.2, x + sw + pad, y + size * 1.36], radius=int(size * 0.22), fill=ACCENT)
                draw.text((x, y), seg, font=font, fill=INK)
            else:
                draw.text((x, y), seg, font=font, fill=WHITE, stroke_width=max(4, size // 13), stroke_fill=(0, 0, 0))
            x += sw
        pos += len(row)
        y += lh


def _pill(draw, x, y, text, font, fill, ink, outline=None):
    w = font.getlength(text) + 44
    draw.rounded_rectangle([x, y, x + w, y + 62], radius=31, fill=fill, outline=outline, width=3)
    draw.text((x + 22, y + 6), text, font=font, fill=ink)
    return w


def _bookmark(draw, x, y, s, fill):
    draw.polygon([(x, y), (x + s, y), (x + s, y + s * 1.5), (x + s / 2, y + s * 1.15), (x, y + s * 1.5)], fill=fill)


def make_slide(cfg, script, text, kind, idx, total, out_png, progress=0.0, scale=1.0, step=0):
    if cfg["video"].get("design", "v2") == "v1":
        return make_slide_v1(cfg, script, text, kind, idx, total, out_png, progress, scale, step)
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    cat = cfg["categories"].get(script["category"], {"label": "", "color": ["#222222", "#444444"]})
    img = _bg_v2(W, H, cat["color"][0], cat["color"][1], step).copy()
    d = ImageDraw.Draw(img)
    x0, x1 = SAFE_X
    accent = _mix(_hex(cat["color"][1]), (255, 255, 255), 0.35)

    # top: progress bar, then category / PR pills and the title
    d.rounded_rectangle([x0 - 30, 150, x1 + 30, 162], radius=6, fill=(255, 255, 255, 60))
    d.rounded_rectangle([x0 - 30, 150, x0 - 30 + max(12, int((x1 - x0 + 60) * progress)), 162], radius=6, fill=ACCENT)
    f_pill = _font(42)
    w = _pill(d, x0 - 30, 196, cat["label"], f_pill, WHITE, _mix(_hex(cat["color"][0]), (0, 0, 0), 0.3))
    if script.get("affiliate"):
        _pill(d, x0 - 30 + w + 14, 196, "PR", f_pill, (0, 0, 0, 0), WHITE, outline=WHITE)
    # A/B: the title often gives away the hook's answer, so one arm leaves it off the hook screen
    if not (kind == "hook" and script.get("variant") == "hook_title:hide"):
        d.text((x0 - 30, 296), script["title"], font=_font(58), fill=WHITE, stroke_width=4, stroke_fill=(0, 0, 0))

    # body: translucent card sized to the caption, with a hero number for amounts and ratios
    hero = None
    if kind == "line":
        m = HERO_RE.search(text)
        hero = m.group(0) if m and len(m.group(0)) <= 7 else None
    base = int((104 if kind == "hook" else 88 if not hero else 76) * scale)
    font, size, rows = _fit(text, base, x1 - x0 - 20, 4 if not hero else 3)
    text_h = int(size * 1.3) * len(rows)
    hero_h = 330 if hero else 0
    card_h = max(520 if kind == "hook" else 400, text_h + hero_h + 190)
    cy = 880
    card_top, card_bot = cy - card_h // 2, cy + card_h // 2
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([x0 - 40, card_top, x1 + 40, card_bot], radius=56, fill=(0, 0, 0, 120), outline=(*accent, 255), width=6)
    img = Image.alpha_composite(img, card)
    d = ImageDraw.Draw(img)
    if hero:
        hs = int(250 * scale)
        while _font(hs).getlength(hero) > x1 - x0 and hs > 120:
            hs -= 10
        d.text(((x0 + x1) / 2, card_top + 95 + hs * 0.55), hero, font=_font(hs), fill=ACCENT, anchor="mm", stroke_width=10, stroke_fill=(0, 0, 0))
        _caption_v2(d, card_bot - 95 - text_h / 2 + 0.2 * size, text, font, size, rows)
    else:
        _caption_v2(d, cy, text, font, size, rows)

    if kind == "cta":
        _bookmark(d, x0 + 20, 1405, 46, ACCENT)
        d.text((x0 + 92, 1400), "保存して、あとで見返す", font=_font(50), fill=WHITE, stroke_width=4, stroke_fill=(0, 0, 0))
        d.rounded_rectangle([x0 - 30, 1500, x1 + 30, 1596], radius=48, fill=ACCENT)
        d.text(((x0 + x1) / 2, 1548), "フォローで毎日1分、お金に強くなる", font=_font(44), fill=INK, anchor="mm")
    img.convert("RGB").save(out_png)


def split_chunks(text, min_len=6, max_chars=0):
    """Split a sentence into short caption phrases (~1.5-2.5 s each) so the picture changes every couple of seconds.

    With max_chars, a phrase longer than that is cut again at phrase boundaries (after a particle, never inside a word),
    packing as many phrases as fit and never leaving a tiny tail."""
    parts = [p for p in re.findall(r"[^、。！？]+[、。！？]?", text) if p.strip()]
    out = []
    for p in parts:
        if out and (len(out[-1].rstrip("、。！？")) < min_len or len(p.rstrip("、。！？")) < min_len):
            out[-1] += p
        else:
            out.append(p)
    out = out or [text]
    if not max_chars:
        return out
    from . import design_v3

    res = []
    for c in out:
        if len(c.rstrip("、。！？")) <= max_chars:
            res.append(c)
            continue
        cur = []
        n = -(-len(c.rstrip("、。！？")) // max_chars)  # pieces needed; aim for even pieces rather than a full one and a stub
        limit = min(max_chars, -(-len(c.rstrip("、。！？")) // n) + 2)
        for ph in design_v3._phrases(c):
            if cur and len(cur[-1].rstrip("、。！？")) + len(ph.rstrip("、。！？")) > limit:
                cur.append(ph)
            elif cur:
                cur[-1] += ph
            else:
                cur.append(ph)
        if len(cur) > 1 and len(cur[-1].rstrip("、。！？")) < 4:  # no tiny tail: fold it back
            tail = cur.pop()
            cur[-1] += tail
        res += cur
    return res


_G2P = {}


def spoken_weight(text, mode="chars"):
    """How long a caption chunk takes to say, relative to its siblings. 'mora' counts the kana of its reading (numbers and
    kanji are read longer than they are written) via pyopenjtalk when installed; otherwise it counts characters."""
    plain = re.sub(r"[、。！？\s]", "", text)
    n = len(plain)
    if mode == "mora":
        if "f" not in _G2P:
            try:
                import pyopenjtalk

                _G2P["f"] = lambda t: len(pyopenjtalk.g2p(t, kana=True))
            except Exception:
                _G2P["f"] = None
        if _G2P["f"]:
            try:
                n = max(1, _G2P["f"](plain))
            except Exception:
                pass
    return n + (0.5 if text.endswith("、") else 0)


POP_SCALES = (0.82, 0.9, 0.96, 1.0)


def _silence(n_frames, sr):
    return b"\x00\x00" * n_frames


def _trim_silence(data, sr, thresh=400, keep=0.04):
    """Drop the near-silent lead-in/tail TTS engines add, so the first word lands in the first split second."""
    import numpy as np

    a = np.frombuffer(data, dtype=np.int16)
    loud = np.flatnonzero(np.abs(a) > thresh)
    if not loud.size:
        return data
    k = int(keep * sr)
    return a[max(0, loud[0] - k): min(len(a), loud[-1] + k)].tobytes()


def build_audio(parts, out_wav, pause, min_total, spoken=None):
    """Concatenate mono 16-bit wavs with pauses (one number, or one per part); pad the end so the clip reaches `min_total` seconds.

    If `spoken` is a list, it receives each part's speech-only length (without its pause and without the end padding)."""
    sr = None
    frames, durations = [], []
    for i, p in enumerate(parts):
        with wave.open(p) as w:
            if sr is None:
                sr = w.getframerate()
            elif w.getframerate() != sr:
                raise RuntimeError("sample rate mismatch between TTS segments")
            data = _trim_silence(w.readframes(w.getnframes()), w.getframerate())
        if spoken is not None:
            spoken.append(len(data) / 2 / sr)
        data += _silence(int((pause[i] if isinstance(pause, (list, tuple)) else pause) * sr), sr)
        frames.append(data)
        durations.append(len(data) / 2 / sr)
    total = sum(durations)
    if total < min_total:
        extra = min_total - total
        frames[-1] += _silence(int(extra * sr), sr)
        durations[-1] += extra
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(frames))
    return durations


def caption_timeline(segs, durations, spoken, cap, v4):
    """[(segment index, kind, caption chunk, seconds on screen)] covering the whole clip.

    v4 shares each segment's speech time among its chunks by how long they take to say (the pause after it goes to the
    last chunk), then shows every caption `lead_sec` before it is spoken; v3/v3b keep the plain per-character split."""
    items = []
    for i, ((kind, text), dur) in enumerate(zip(segs, durations)):
        chunks = split_chunks(text, cap["min_chars"], cap["max_chars"])
        w = [spoken_weight(c, cap["weight"]) for c in chunks]
        if v4:
            ds = [spoken[i] * x / sum(w) for x in w]
            ds[-1] += dur - spoken[i]
        else:
            ds = [dur * x / sum(w) for x in w]
        items += [[i, kind, c, d] for c, d in zip(chunks, ds)]
    lead = min(cap["lead_sec"], items[0][3] * 0.4)
    if lead and len(items) > 1:
        items[0][3] -= lead
        items[-1][3] += lead
    return items


def outro_for(cfg, script):
    """The closing line: the follow request by default, or a comment request for the `outro:comment` experiment arm."""
    v = cfg["video"]
    if script.get("variant") == "outro:comment":
        by_cat = v.get("outro_comment") or {}
        return by_cat.get(script.get("category"), by_cat.get("default", ""))
    return v.get("outro", "")


def render(cfg, script, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    outro = outro_for(cfg, script)
    if outro:  # a closing line after the script's own call to action; script.json and the YouTube description keep the script as written
        cta = script["cta"] if script["cta"].endswith(("。", "！", "？", "!", "?")) else script["cta"] + "。"
        script = {**script, "cta": cta + outro}
    segs = [("hook", script["hook"])] + [("line", l) for l in script["lines"]] + [("cta", script["cta"])]
    pause = cfg["tts"].get("pause_sec", 0.25)
    min_total = cfg["phases"][cfg.get("phase", "growth")].get("min_duration_sec", 0)
    from . import design_scene, design_v3, qa, scenes as scene_mod

    design = cfg["video"].get("design", "v2")
    dm = design_scene if design in design_scene.DESIGNS else design_v3  # the module that draws this design
    v4 = design == "v4" or design in design_scene.DESIGNS
    if v4:  # a beat after the hook and after a question, so the viewer can take the question in
        st = dm.style(cfg)
        pauses = [st["pause"]["after_hook"] if k == "hook" else st["pause"]["after_question"] if t.rstrip().endswith(("？", "?"))
                  else pause for k, t in segs]
    else:
        pauses = [pause] * len(segs)

    def voice(speed):
        wavs, engines, secs = [], set(), 0.0
        for i, (_, text) in enumerate(segs):
            p = str(workdir / f"seg{i:02d}.wav")
            d, eng = synth(text, p, cfg, speed=speed)
            engines.add(eng)
            wavs.append(p)
            secs += d + pauses[i]
        return wavs, engines, secs

    wavs, engines, natural = voice(1.0)
    # Too short for the 1-minute minimum: slow the narration a little rather than holding a static end card.
    if min_total and natural < min_total - 4:
        speed = max(0.85, natural / (min_total - 4))
        wavs, engines, natural = voice(speed)
        log(f"narration slowed to x{speed:.2f} ({natural:.1f}s)")
    spoken = []
    durations = build_audio(wavs, str(workdir / "voice.wav"), pauses, min_total, spoken)

    lst = []
    elapsed, total = 0.0, sum(durations)
    fps = cfg["video"]["fps"]
    n = 0
    v3 = design in ("v3", "v3b", "v4") or design in design_scene.DESIGNS
    frame_issues = []
    if v3:
        cap = dm.configure(cfg)["caption"]
        items = caption_timeline(segs, durations, spoken, cap, v4)
        dock_ctx = dm.dock_ctx_for(script)  # the diagram frame remembers the last diagram across chunks
        for i, kind, c, cd in items:
            lines, n = dm.chunk_frames(cfg, script, c, kind, i + 1, len(segs), min(1.0, (elapsed + cd) / total),
                                              cd, fps, workdir, n, ctx=dock_ctx)
            lst += lines
            png = Path(lines[-1].split("'")[1])
            if v3 and design in ("v4", *design_scene.DESIGNS):  # a finished frame with text in the platform UI zones, or nothing on it
                for prob in qa.frame_problems(workdir / png):
                    frame_issues.append(f"t={elapsed:.1f}s '{c}': {prob}")
            elapsed += cd
    for i, ((kind, text), dur) in enumerate(zip(segs, durations) if not v3 else []):
        chunks = split_chunks(text)
        weights = [len(c) for c in chunks]
        for c, wgt in zip(chunks, weights):
            cd = dur * wgt / sum(weights)
            pops = POP_SCALES if cd > 0.6 else (1.0,)
            for k, sc in enumerate(pops):
                png = workdir / f"slide{n:03d}.png"
                n += 1
                make_slide(cfg, script, c, kind, i + 1, len(segs), png,
                           progress=min(1.0, (elapsed + (cd if k == len(pops) - 1 else 0)) / total), scale=sc, step=n // len(pops))
                d_ = 1 / fps if k < len(pops) - 1 else cd - (len(pops) - 1) / fps
                lst.append(f"file '{png.name}'\nduration {d_:.3f}")
            elapsed += cd
    lst.append(f"file '{png.name}'")  # concat demuxer needs the last frame repeated
    (workdir / "slides.txt").write_text("\n".join(lst), encoding="utf-8")

    audio_in = ["-i", "voice.wav"]
    filt_a = None
    bgms = sorted((ROOT / "data" / "bgm").glob("*.mp3"))
    if bgms:
        audio_in += ["-stream_loop", "-1", "-i", str(random.choice(bgms))]
        filt_a = "[2:a]volume=0.08[b];[1:a][b]amix=inputs=2:duration=first:dropout_transition=0[a]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "slides.txt", *audio_in,
           "-vf", f"fps={cfg['video']['fps']},format=yuv420p"]
    if filt_a:
        cmd += ["-filter_complex", filt_a, "-map", "0:v", "-map", "[a]"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
            "-t", f"{total:.3f}", "-movflags", "+faststart", "video.mp4"]
    subprocess.run(cmd, cwd=workdir, check=True)
    for p in [*wavs, *workdir.glob("slide*.png"), workdir / "slides.txt", workdir / "voice.wav"]:
        Path(p).unlink(missing_ok=True)
    if v3:
        dm.still(cfg, script, script["hook"], "hook", 1, len(segs), workdir / "thumb.png")
        plan = scene_mod.attach_timing(scene_mod.plan_scenes(script), items)  # what each scene was meant to say, and when
        issues = {"frames": frame_issues, "scenes": qa.scene_problems(plan, total),
                  "video": qa.video_problems(workdir / "video.mp4", total, fps), "consistency": scene_mod.consistency(script)}
        for kind_, probs in issues.items():
            for prob in probs:
                log(f"QA {kind_}: {prob}")
        (workdir / "scene_plan.json").write_text(json.dumps({"design": design, "scenes": plan, "qa": issues}, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    else:
        make_slide(cfg, script, script["hook"], "hook", 1, len(segs), workdir / "thumb.png", progress=0)
    log(f"rendered {workdir / 'video.mp4'} ({total:.1f}s, tts={','.join(sorted(engines))})")
    return workdir / "video.mp4", total, sorted(engines)
