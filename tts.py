"""Japanese text-to-speech. edge-tts (natural neural voice, needs network) with an offline pyopenjtalk fallback."""
import asyncio
import os
import subprocess
import wave

from .common import log

_ENGINE_OK = {}


def _edge(text, out_wav, voice, rate):
    import edge_tts

    mp3 = out_wav + ".mp3"
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    async def run():
        await edge_tts.Communicate(text, voice, rate=rate, proxy=proxy).save(mp3)

    try:
        asyncio.run(run())
    finally:
        pass
    if not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
        raise RuntimeError("edge-tts produced no audio")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ar", "48000", "-ac", "1", out_wav], check=True)
    os.remove(mp3)


def _openjtalk(text, out_wav, speed=1.15):
    import numpy as np
    import pyopenjtalk

    x, sr = pyopenjtalk.tts(text, speed=speed)
    x = np.clip(x, -32768, 32767).astype(np.int16)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(x.tobytes())


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _edge_rate(base, speed):
    pct = int(base.rstrip("%")) if base else 0
    new = round((1 + pct / 100) * speed * 100 - 100)
    return f"{new:+d}%"


def synth(text, out_wav, cfg, speed=1.0):
    """Write speech for `text` to `out_wav`; returns (seconds, engine_name). `speed` scales the configured pace."""
    tcfg = cfg["tts"]
    order = ["edge", "openjtalk"] if tcfg.get("engine", "auto") in ("auto", "edge") else ["openjtalk"]
    for eng in order:
        if _ENGINE_OK.get(eng) is False:
            continue
        try:
            if eng == "edge":
                _edge(text, out_wav, tcfg["edge_voice"], _edge_rate(tcfg.get("edge_rate", "+0%"), speed))
            else:
                _openjtalk(text, out_wav, speed=1.15 * speed)
            _ENGINE_OK[eng] = True
            return duration(out_wav), eng
        except Exception as e:
            if os.path.exists(out_wav + ".mp3"):
                os.remove(out_wav + ".mp3")
            log(f"TTS engine {eng} unavailable ({type(e).__name__}); trying next")
            _ENGINE_OK[eng] = False
    raise RuntimeError("no TTS engine available (pip install edge-tts pyopenjtalk-plus)")
