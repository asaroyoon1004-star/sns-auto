"""Checks on a rendered video: frames (blank, text in the platform's UI zones or cut at the edge) and the file (audio/video
length, frame count). Problems are reported, not raised, so one odd scene never stops the daily run."""
import subprocess

SAFE = {"top": 150, "bottom": 420, "right": 140, "left": 40, "right_from": 900}  # px of the 1080x1920 frame kept free of text and
# diagrams; the right-hand button column of Shorts starts around y=900, so the right band is checked from there down
BRIGHT = 120  # luminance above which a pixel counts as text or a drawn mark (backgrounds and panels are darker)


def frame_problems(png, safe=None, size=(1080, 1920)):
    """Problems in one finished frame: nothing drawn, or marks inside the top/bottom/right UI zones or at the left edge."""
    import numpy as np
    from PIL import Image

    safe = {**SAFE, **(safe or {})}
    a = np.asarray(Image.open(png).convert("L"))
    h, w = a.shape
    bright = a > BRIGHT
    out = []
    if bright.sum() < 400:
        out.append("blank frame")
    for name, region in (("top", bright[:safe["top"], :]), ("bottom", bright[h - safe["bottom"]:, :]),
                         ("right", bright[safe["right_from"]:, w - safe["right"]:]), ("left", bright[:, :safe["left"]])):
        if region.any():
            out.append(f"marks in the {name} zone ({int(region.sum())} px)")
    return out


def _probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error", *(["-select_streams", stream] if stream else []), "-show_entries", entries, "-of", "csv=p=0", str(path)]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.split()


def video_problems(path, expected_sec, fps):
    """Problems in the finished file: audio and video lengths disagree with each other or with the plan, or frames are missing."""
    out = []
    v = float(_probe(path, "stream=duration", "v:0")[0])
    a = float(_probe(path, "stream=duration", "a:0")[0])
    if abs(v - a) > 0.15:
        out.append(f"audio {a:.2f}s and video {v:.2f}s differ")
    if abs(v - expected_sec) > 0.2:
        out.append(f"video {v:.2f}s, planned {expected_sec:.2f}s")
    frames = int(_probe(path, "stream=nb_frames", "v:0")[0])
    if abs(frames - round(expected_sec * fps)) > 3:
        out.append(f"{frames} frames, expected about {round(expected_sec * fps)}")
    return out


def scene_problems(plan, total):
    """Problems in the scene plan's timing: gaps, overlaps, a scene too short to read, or a total that is off."""
    out, t = [], 0.0
    for s in plan:
        if abs(s["start"] - t) > 0.01:
            out.append(f"scene {s['index']} starts at {s['start']}, expected {t:.2f}")
        if s["duration"] < 0.5:
            out.append(f"scene {s['index']} is only {s['duration']}s")
        t = s["start"] + s["duration"]
    if abs(t - total) > 0.05:
        out.append(f"scenes end at {t:.2f}s, video is {total:.2f}s")
    return out
