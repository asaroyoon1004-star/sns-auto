import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from sns import design_scene as ds
from sns import qa, render, scenes

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SEEDS = json.loads((ROOT / "data/seed/scripts.json").read_text(encoding="utf-8"))
STYLES = ("v4", "sb", "sc")


def cfg_for(design, **styles):
    c = copy.deepcopy(CFG)
    c["video"]["design"] = design
    if styles:
        c["video"].setdefault("styles", {}).setdefault(design, {})
        from sns import design_v3

        design_v3._merge(c["video"]["styles"][design], styles)
    return c


def seed(sid):
    return dict(next(s for s in SEEDS if s["id"] == sid), variant="")


class ScenePlanTests(unittest.TestCase):
    def test_every_scene_has_its_fields(self):
        keys = {"index", "role", "narration", "caption", "key_message", "visual_type", "visual_data", "emphasis", "transition",
                "source", "caveat"}
        for s in SEEDS:
            plan = scenes.plan_scenes(s)
            self.assertEqual(len(plan), len(s["lines"]) + 2)
            for sc in plan:
                self.assertTrue(keys <= set(sc), s["id"])
            self.assertEqual([p["role"] for p in plan][0], "hook")
            self.assertEqual(plan[-1]["role"], "cta")

    def test_roles_and_visuals_follow_the_script(self):
        plan = scenes.plan_scenes(seed("s011"))
        roles = [p["role"] for p in plan]
        self.assertEqual(roles[1], "reveal")  # "それが72の法則です。" answers the hook's question
        self.assertEqual(roles[8], "caveat")  # "ただし、投資の利回りは保証されたものではない…"
        self.assertEqual(plan[3]["visual_type"], "bars")
        self.assertEqual(plan[3]["visual_data"]["rows"][0]["label"], "年利1%")
        self.assertIn("72年", plan[3]["emphasis"])
        self.assertTrue(plan[8]["caveat"])

    def test_timing_covers_the_clip_without_gaps(self):
        s = seed("s011")
        segs = [("hook", s["hook"])] + [("line", l) for l in s["lines"]] + [("cta", s["cta"])]
        durs = [2.0 + 0.1 * i for i in range(len(segs))]
        cap = ds.style(cfg_for("sb"))["caption"]
        items = render.caption_timeline(segs, durs, [d - 0.2 for d in durs], cap, True)
        plan = scenes.attach_timing(scenes.plan_scenes(s), items)
        self.assertEqual(qa.scene_problems(plan, sum(durs)), [])
        plan[3]["start"] += 0.3
        self.assertTrue(qa.scene_problems(plan, sum(durs)))


class ConsistencyTests(unittest.TestCase):
    def test_no_seed_diagram_disagrees_with_its_narration(self):
        for s in SEEDS:
            self.assertEqual(scenes.consistency(s), [], s["id"])

    def test_detects_a_number_the_narration_never_says(self):
        s = seed("s011")
        s["visual"] = copy.deepcopy(s["visual"])
        s["visual"]["rows"][1]["text"] = "約25年"
        self.assertTrue(any("25" in p for p in scenes.consistency(s)))

    def test_detects_bars_out_of_proportion(self):
        s = seed("s011")
        s["visual"] = copy.deepcopy(s["visual"])
        s["visual"]["rows"][1]["value"] = 40  # prints 約24年 but is drawn as 40 against 72
        self.assertTrue(any("proportion" in p for p in scenes.consistency(s)))

    def test_row_on_the_wrong_line_is_caught(self):
        s = seed("s011")
        s["visual"] = copy.deepcopy(s["visual"])
        s["visual"]["rows"][2]["line"] = 2  # 12年 is said on line 5
        self.assertTrue(scenes.consistency(s))


class QaTests(unittest.TestCase):
    def _img(self, tmp, marks):
        im = Image.new("RGB", (1080, 1920), (0, 0, 0))
        for x, y in marks:
            for dx in range(30):
                for dy in range(30):
                    im.putpixel((x + dx, y + dy), (255, 255, 255))
        p = Path(tmp) / "f.png"
        im.save(p)
        return p

    def test_flags_blank_and_ui_zones(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("blank frame", qa.frame_problems(self._img(tmp, [])))
            self.assertTrue(any("top" in p for p in qa.frame_problems(self._img(tmp, [(500, 60), (100, 900), (200, 1000), (300, 1100)] * 3))))
            self.assertTrue(any("bottom" in p for p in qa.frame_problems(self._img(tmp, [(100, 1700), (300, 1700), (500, 1700), (700, 1700)] * 2))))
            self.assertTrue(any("right" in p for p in qa.frame_problems(self._img(tmp, [(980, 1000), (980, 1100), (980, 1200), (980, 1300)] * 2))))
            self.assertEqual(qa.frame_problems(self._img(tmp, [(100, 600), (300, 600), (500, 600), (700, 600)] * 2)), [])


class StyleTests(unittest.TestCase):
    def test_three_styles_render_clean_frames_for_the_same_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            for design in STYLES:
                cfg = cfg_for(design)
                mod = ds if design in ds.DESIGNS else __import__("sns.design_v3", fromlist=["x"])
                cap = mod.configure(cfg)["caption"]
                for sid in ("s003", "s011", "s012", "s024", "s027"):
                    s = seed(sid)
                    n_lines = len(s["lines"])
                    segs = [("hook", s["hook"])] + [("line", l) for l in s["lines"]] + [("cta", s["cta"])]
                    ctx = mod.dock_ctx_for(s)
                    for i, (kind, text) in enumerate(segs):
                        for c in render.split_chunks(text, cap["min_chars"], cap["max_chars"]):
                            lines, n = mod.chunk_frames(cfg, s, c, kind, i + 1, n_lines + 2, 0.5, 0.1, 30, tmp, 0, ctx=ctx)
                            last = Path(tmp) / lines[-1].split("'")[1]
                            self.assertEqual(qa.frame_problems(last), [], (design, sid, c))

    def test_hook_is_complete_on_the_first_frame_in_every_style(self):
        for design in STYLES:
            cfg = cfg_for(design)
            mod = ds if design in ds.DESIGNS else __import__("sns.design_v3", fromlist=["x"])
            s = seed("s011")
            with tempfile.TemporaryDirectory() as tmp:
                lines, _ = mod.chunk_frames(cfg, s, s["hook"], "hook", 1, 10, 0.0, 2.0, 30, tmp, 0, ctx=mod.dock_ctx_for(s))
                self.assertEqual(len(lines), 1, design)  # no fade-in frames: the hook is final from the start
                self.assertEqual(qa.frame_problems(Path(tmp) / lines[0].split("'")[1]), [])

    def test_rendering_is_deterministic(self):
        for design in ("sb", "sc"):
            hashes = []
            for _ in range(2):
                cfg = cfg_for(design)
                s = seed("s011")
                with tempfile.TemporaryDirectory() as tmp:
                    lines, _ = ds.chunk_frames(cfg, s, s["lines"][3], "line", 4, 10, 0.4, 2.0, 30, tmp, 0, ctx=ds.dock_ctx_for(s))
                    h = hashlib.sha256()
                    for ln in lines:
                        h.update((Path(tmp) / ln.split("'")[1]).read_bytes())
                    hashes.append(h.hexdigest())
            self.assertEqual(hashes[0], hashes[1], design)

    def test_styles_differ_and_are_configurable(self):
        sb, sc = ds.style(cfg_for("sb")), ds.style(cfg_for("sc"))
        self.assertNotEqual(sb["colors"]["bg"], sc["colors"]["bg"])
        self.assertGreater(sb["fonts"]["caption"], sc["fonts"]["caption"])  # B has the larger caption
        self.assertGreater(sc["layout"]["row_pitch"], sb["layout"]["row_pitch"])  # C draws the larger chart
        over = ds.style(cfg_for("sb", fonts={"caption": 90}, colors={"accent": "#00FF00"}))
        self.assertEqual(over["fonts"]["caption"], 90)
        self.assertEqual(over["rgb"]["accent"], (0, 255, 0))

    def test_motion_is_bounded_in_every_style(self):
        for design in ("sb", "sc"):
            st = ds.style(cfg_for(design, anim={"slide_px": 900, "fade_sec": 9, "stagger": 5}, caption={"lead_sec": 3}))
            self.assertLessEqual(st["anim"]["slide_px"], 48)
            self.assertLessEqual(st["anim"]["fade_sec"], 0.6)
            self.assertLessEqual(st["anim"]["stagger"], 0.5)
            self.assertLessEqual(st["caption"]["lead_sec"], 0.25)

    def test_new_row_grows_in_and_diagram_is_there_from_the_start(self):
        for design in ("sb", "sc"):
            cfg = cfg_for(design)
            s = seed("s011")
            ctx = ds.dock_ctx_for(s)
            with tempfile.TemporaryDirectory() as tmp:
                first, _ = ds.chunk_frames(cfg, s, s["hook"], "hook", 1, 10, 0.0, 2.0, 30, tmp, 0, ctx=ctx)
                grow, _ = ds.chunk_frames(cfg, s, s["lines"][2], "line", 4, 10, 0.3, 3.0, 30, tmp, 50, ctx=ctx)
                self.assertEqual(ctx["shown"], {0})
                a = Image.open(Path(tmp) / grow[0].split("'")[1]).convert("RGB")
                b = Image.open(Path(tmp) / grow[-1].split("'")[1]).convert("RGB")
                self.assertNotEqual(a.tobytes(), b.tobytes())
                self.assertGreater(len(grow), 10)


class RenderIntegrationTests(unittest.TestCase):
    def test_short_script_renders_in_each_style_with_a_clean_qa_report(self):
        try:
            import pyopenjtalk  # noqa: F401
        except ImportError:
            self.skipTest("pyopenjtalk not installed")
        script = {"id": "t1", "category": "saving_habit", "title": "テスト", "hook": "毎月1万円を貯めると、1年でいくら？",
                  "lines": ["答えは12万円です。", "年利3パーセントなら、約12万2千円です。", "ただし、運用には元本割れの可能性があります。"],
                  "cta": "保存して、あとで見返してね。", "hashtags": [], "affiliate": None, "variant": "",
                  "visual": {"type": "bars", "title": "1年後の金額", "rows": [
                      {"label": "貯金だけ", "value": 12, "text": "12万円", "line": 1},
                      {"label": "年利3%", "value": 12.2, "text": "12万2千円", "line": 2}]}}
        for design in STYLES:
            cfg = cfg_for(design)
            cfg["tts"]["engine"] = "openjtalk"
            with tempfile.TemporaryDirectory() as tmp:
                out, total, _ = render.render(cfg, dict(script), tmp)
                rep = json.loads((Path(tmp) / "scene_plan.json").read_text(encoding="utf-8"))
                self.assertEqual(rep["qa"]["video"], [], design)
                self.assertEqual(rep["qa"]["scenes"], [], design)
                self.assertEqual(rep["qa"]["frames"], [], design)
                self.assertEqual(rep["qa"]["consistency"], [], design)
                self.assertAlmostEqual(sum(s["duration"] for s in rep["scenes"]), total, delta=0.05)
                self.assertTrue((Path(tmp) / "thumb.png").exists())


if __name__ == "__main__":
    unittest.main()
