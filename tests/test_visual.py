import copy
import json
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from PIL import Image

from sns import design_v3 as d
from sns import render

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SEEDS = json.loads((ROOT / "data/seed/scripts.json").read_text(encoding="utf-8"))


def cfg_for(design, **styles):
    c = copy.deepcopy(CFG)
    c["video"]["design"] = design
    if styles:
        c["video"].setdefault("styles", {}).setdefault(design, {})
        d._merge(c["video"]["styles"][design], styles)
    return c


def all_segments():
    for s in SEEDS:
        yield "hook", s["hook"]
        for l in s["lines"]:
            yield "line", l
        yield "cta", s["cta"]


def write_wav(path, secs, sr=16000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", 6000 if i % 40 < 20 else -6000) for i in range(int(secs * sr))))


class SplitTests(unittest.TestCase):
    def test_lossless_and_short(self):
        for _, text in all_segments():
            chunks = render.split_chunks(text, 6, 16)
            self.assertEqual("".join(chunks), text)
            self.assertTrue(all(len(c.rstrip("、。！？")) <= 20 for c in chunks), chunks)

    def test_no_bad_starts_or_tiny_tails(self):
        for _, text in all_segments():
            chunks = render.split_chunks(text, 6, 16)
            for c in chunks[1:]:
                self.assertNotIn(c[0], d.NO_LINE_START, chunks)
            if len(chunks) > 1 and len(text.rstrip("、。！？")) > 16:
                self.assertGreaterEqual(len(chunks[-1].rstrip("、。！？")), 3, chunks)

    def test_default_split_unchanged(self):
        self.assertEqual(render.split_chunks("実は、家族全員の分を合算できます。"), ["実は、家族全員の分を合算できます。"])

    def test_v4_splits_long_lines_more(self):
        old = sum(len(render.split_chunks(t)) for _, t in all_segments())
        new = sum(len(render.split_chunks(t, 6, 16)) for _, t in all_segments())
        self.assertGreater(new, old)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.cfg = cfg_for("v4")
        self.st = d.configure(self.cfg)

    def test_rows_fit_and_text_is_large(self):
        cap = self.st["caption"]
        for kind, text in all_segments():
            for c in render.split_chunks(text, cap["min_chars"], cap["max_chars"]):
                pl = d.plan(kind, c)
                for r in pl["rows"]:
                    # a closing 。 or 、 may hang one character past the column (kinsoku), never more
                    self.assertLessEqual(pl["font"].getlength(r), d.X1 - d.X0 + pl["size"], r)
                    self.assertLessEqual(d.X0 + 32 + pl["font"].getlength(r), d.W - self.st["layout"]["safe"]["right"], r)
                self.assertGreaterEqual(pl["size"], self.st["fonts"]["min"], c)
                self.assertLessEqual(len(pl["rows"]), 5)

    def test_content_inside_safe_area(self):
        sf = self.st["layout"]["safe"]
        cap = self.st["caption"]
        self.assertLessEqual(d.X1, d.W - sf["right"])
        for kind, text in all_segments():
            for c in render.split_chunks(text, cap["min_chars"], cap["max_chars"]):
                pl = d.plan(kind, c)
                top = d.CENTER_Y - pl["panel_h"] // 2
                bottom = top + pl["panel_h"] + (56 + 230 if kind == "cta" else 0)  # the CTA adds a box and a follow line below
                self.assertGreaterEqual(top, sf["top"], c)
                self.assertLessEqual(bottom, d.H - sf["bottom"], c)

    def test_rendered_pixels_stay_out_of_ui_zones(self):
        sf = self.st["layout"]["safe"]
        script = dict(SEEDS[0], variant="hook_title:show")
        with tempfile.TemporaryDirectory() as tmp:
            for kind, text in [("hook", SEEDS[0]["hook"]), ("line", "月13万7800円が、年間で約164万円になります。"), ("cta", SEEDS[0]["cta"])]:
                out = Path(tmp) / f"{kind}.png"
                d.still(self.cfg, script, text, kind, 3, 8, out)
                im = Image.open(out).convert("L")
                bright = im.point(lambda v: 255 if v > 120 else 0)
                for name, box in {"top": (0, 0, d.W, sf["top"]), "bottom": (0, d.H - sf["bottom"], d.W, d.H),
                                  "right": (d.W - sf["right"], 0, d.W, d.H)}.items():
                    self.assertIsNone(bright.crop(box).getbbox(), (kind, name))

    def test_v3_layout_unchanged(self):
        d.configure(cfg_for("v3b"))
        self.assertEqual((d.X0, d.X1, d.MARGIN, d.CENTER_Y), (72, 882, 64, 900))
        self.assertEqual(d.S["fonts"]["body"], 82)
        self.assertEqual(d.S["anim"]["stagger"], 0.0)


class StyleTests(unittest.TestCase):
    def test_config_overrides_apply(self):
        c = cfg_for("v4", colors={"gold": "#FF0000"}, fonts={"body": 90}, layout={"margin": 80})
        d.configure(c)
        self.assertEqual(d.GOLD, (255, 0, 0))
        self.assertEqual(d.S["fonts"]["body"], 90)
        self.assertEqual(d.MARGIN, 80)

    def test_motion_limits(self):
        s = d.style(cfg_for("v4", anim={"slide_px": 500, "fade_sec": 9, "stagger": 3}, caption={"lead_sec": 5}))
        self.assertLessEqual(s["anim"]["slide_px"], 48)
        self.assertLessEqual(s["anim"]["fade_sec"], 0.6)
        self.assertLessEqual(s["anim"]["stagger"], 0.5)
        self.assertLessEqual(s["caption"]["lead_sec"], 0.25)

    def test_config_has_v4_and_arm(self):
        self.assertIn("v4", CFG["video"]["design_arms"])
        self.assertEqual(d.style(cfg_for("v4")), d.style(cfg_for("v4", **{})))
        self.assertIn("v4", CFG["video"]["styles"])


class AnimTests(unittest.TestCase):
    def test_bars_appear_one_after_another(self):
        p = [d._row_p(0.4, i, 3, 0.3) for i in range(3)]
        self.assertGreater(p[0], p[1])
        self.assertGreater(p[1], p[2])
        self.assertEqual([d._row_p(1.0, i, 3, 0.3) for i in range(3)], [1.0, 1.0, 1.0])
        self.assertEqual(d._row_p(0.0, 0, 3, 0.3), 0.0)

    def _frames(self, design, text, kind, dur):
        c = cfg_for(design)
        with tempfile.TemporaryDirectory() as tmp:
            lines, n = d.chunk_frames(c, dict(SEEDS[0], variant=""), text, kind, 2, 8, 0.2, dur, 30, tmp, 0)
        secs = [float(x.split("duration ")[1]) for x in lines]
        return secs

    def test_durations_add_up(self):
        for design in ("v3b", "v4"):
            secs = self._frames(design, "約4年で2倍に膨らむ計算です。", "line", 2.0)
            self.assertAlmostEqual(sum(secs), 2.0, delta=0.05, msg=design)

    def test_v4_animates_diagrams_longer_than_v3b(self):
        old = self._frames("v3b", "約4年で2倍に膨らむ計算です。", "line", 3.0)
        new = self._frames("v4", "約4年で2倍に膨らむ計算です。", "line", 3.0)
        self.assertEqual(len(old), 13)  # 12 transition frames (0.4 s) + the held frame, as before
        self.assertGreater(len(new), len(old))
        self.assertLessEqual(len(new) / 30, 1.2 + 0.2)

    def test_hook_is_visible_from_the_first_frame(self):
        self.assertEqual(len(self._frames("v4", SEEDS[0]["hook"], "hook", 2.0)), 1)


class SyncTests(unittest.TestCase):
    def test_build_audio_reports_speech_and_pauses(self):
        with tempfile.TemporaryDirectory() as tmp:
            parts = []
            for i, secs in enumerate((1.0, 2.0, 1.5)):
                p = Path(tmp) / f"{i}.wav"
                write_wav(p, secs)
                parts.append(str(p))
            spoken = []
            dur = render.build_audio(parts, str(Path(tmp) / "o.wav"), [0.45, 0.25, 0.4], 0, spoken)
        for s, e, pz in zip(spoken, dur, (0.45, 0.25, 0.4)):
            self.assertAlmostEqual(e - s, pz, delta=0.01)

    def test_timeline_covers_the_clip_and_leads_captions(self):
        segs = [("hook", "月1万円を20年積み立てると？"), ("line", "仮に年利3パーセントなら、約328万円になります。"), ("cta", "保存してね。")]
        spoken, durs = [2.0, 3.4, 1.0], [2.45, 3.65, 1.4]
        cap = d.style(cfg_for("v4"))["caption"]
        v4 = render.caption_timeline(segs, durs, spoken, cap, True)
        self.assertAlmostEqual(sum(x[3] for x in v4), sum(durs), places=6)
        plain = render.caption_timeline(segs, durs, spoken, d.style(cfg_for("v3b"))["caption"], False)
        self.assertAlmostEqual(sum(x[3] for x in plain), sum(durs), places=6)
        self.assertAlmostEqual(v4[0][3], render.caption_timeline(segs, durs, spoken, dict(cap, lead_sec=0), True)[0][3] - cap["lead_sec"], places=6)

    def test_mora_weight_counts_reading(self):
        try:
            import pyopenjtalk  # noqa: F401
        except ImportError:
            self.skipTest("pyopenjtalk not installed")
        # 「13万7800円」は5文字だが、読みは「じゅうさんまんななひゃくえん」と長い
        self.assertGreater(render.spoken_weight("13万7800円", "mora"), render.spoken_weight("13万7800円", "chars") * 1.5)

    def test_pause_after_hook_is_longer_in_v4(self):
        st = d.style(cfg_for("v4"))["pause"]
        self.assertGreater(st["after_hook"], CFG["tts"]["pause_sec"])


if __name__ == "__main__":
    unittest.main()
