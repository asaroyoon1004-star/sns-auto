"""Render a 1080x1920 caption-style short from a script: one slide per sentence, synced to its narration."""
import random
import re
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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


def _gradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    t, b = _hex(top), _hex(bottom)
    d = ImageDraw.Draw(img)
    for y in range(h):
        r = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(t[i] + (b[i] - t[i]) * r) for i in range(3)))
    return img


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


def make_slide(cfg, script, text, kind, idx, total, out_png, progress=0.0):
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
    d.text((SAFE_X[0], 320), script["title"], font=f_title, fill=WHITE, stroke_width=4, stroke_fill=(0, 0, 0))

    # body
    size = 92 if kind == "hook" else 80
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


def build_audio(parts, out_wav, pause, min_total):
    """Concatenate mono 16-bit wavs with pauses; pad the end so the clip reaches `min_total` seconds."""
    sr = None
    frames, durations = [], []
    for p in parts:
        with wave.open(p) as w:
            if sr is None:
                sr = w.getframerate()
            elif w.getframerate() != sr:
                raise RuntimeError("sample rate mismatch between TTS segments")
            data = _trim_silence(w.readframes(w.getnframes()), w.getframerate())
        data += _silence(int(pause * sr), sr)
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


def render(cfg, script, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    segs = [("hook", script["hook"])] + [("line", l) for l in script["lines"]] + [("cta", script["cta"])]
    pause = cfg["tts"].get("pause_sec", 0.25)
    min_total = cfg["phases"][cfg.get("phase", "growth")].get("min_duration_sec", 0)

    def voice(speed):
        wavs, engines, secs = [], set(), 0.0
        for i, (_, text) in enumerate(segs):
            p = str(workdir / f"seg{i:02d}.wav")
            d, eng = synth(text, p, cfg, speed=speed)
            engines.add(eng)
            wavs.append(p)
            secs += d + pause
        return wavs, engines, secs

    wavs, engines, natural = voice(1.0)
    # Too short for the 1-minute minimum: slow the narration a little rather than holding a static end card.
    if min_total and natural < min_total - 4:
        speed = max(0.85, natural / (min_total - 4))
        wavs, engines, natural = voice(speed)
        log(f"narration slowed to x{speed:.2f} ({natural:.1f}s)")
    durations = build_audio(wavs, str(workdir / "voice.wav"), pause, min_total)

    lst = []
    elapsed, total = 0.0, sum(durations)
    for i, ((kind, text), dur) in enumerate(zip(segs, durations)):
        png = workdir / f"slide{i:02d}.png"
        elapsed += dur
        make_slide(cfg, script, text, kind, i + 1, len(segs), png, progress=elapsed / total)
        lst.append(f"file '{png.name}'\nduration {dur:.3f}")
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
    make_slide(cfg, script, script["hook"], "hook", 1, len(segs), workdir / "thumb.png", progress=0)
    log(f"rendered {workdir / 'video.mp4'} ({total:.1f}s, tts={','.join(sorted(engines))})")
    return workdir / "video.mp4", total, sorted(engines)
