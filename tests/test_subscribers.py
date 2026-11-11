import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from sns import analytics, design_scene, render, upload_youtube

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SEEDS = json.loads((ROOT / "data/seed/scripts.json").read_text(encoding="utf-8"))


class SubscribeOutro(unittest.TestCase):
    def test_sub_arm_uses_the_category_line_and_follow_keeps_the_old_line(self):
        sub = render.outro_for(CFG, {"variant": "outro_sub:sub", "category": "scam_guard"})
        self.assertIn("チャンネル登録", sub)
        self.assertIn("だまされない", sub)
        self.assertEqual(render.outro_for(CFG, {"variant": "outro_sub:sub", "category": "unknown"}),
                         CFG["video"]["outro_arms"]["sub"]["default"])
        self.assertEqual(render.outro_for(CFG, {"variant": "outro_sub:follow", "category": "scam_guard"}), CFG["video"]["outro"])

    def test_every_category_has_a_sub_line(self):
        for cat in CFG["categories"]:
            self.assertIn(cat, CFG["video"]["outro_arms"]["sub"])

    def test_experiment_arms_have_outros(self):
        exp = CFG["experiment"]
        self.assertTrue(exp["name"].startswith("outro"))
        for arm in exp["arms"]:
            line = render.outro_for(CFG, {"variant": f"{exp['name']}:{arm}", "category": "saving_habit"})
            self.assertTrue(line)

    def test_subscribe_button_only_on_the_sub_arm_and_above_the_diagram(self):
        c = copy.deepcopy(CFG)
        c["video"]["design"] = "sb"
        seed = next(s for s in SEEDS if s.get("visual"))
        top = design_scene.style(c)["layout"]["diagram_top"]
        red = design_scene.SUB_RED
        with tempfile.TemporaryDirectory() as tmp:
            for arm, want in [("sub", True), ("follow", False)]:
                out = Path(tmp) / f"{arm}.png"
                text = "固定費を下げるコツを、毎日1つ。チャンネル登録で見逃さないで"  # three caption rows: the tallest case
                design_scene.still(c, dict(seed, variant=f"outro_sub:{arm}"), text, "cta", 8, 8, out, 1.0)
                im = Image.open(out).convert("RGB")
                ys = [y for y in range(0, im.height, 4) for x in range(80, 400, 20)
                      if all(abs(a - b) < 30 for a, b in zip(im.getpixel((x, y)), red))]
                self.assertEqual(bool(ys), want, arm)
                if ys:
                    self.assertLess(max(ys), top - 20)


class Description(unittest.TestCase):
    SCRIPT = {"title": "t", "hook": "h", "lines": ["a"], "cta": "c", "hashtags": ["お金"], "affiliate": None, "category": "scam_guard"}

    def test_subscribe_and_playlist_links(self):
        _, desc, _ = upload_youtube.build_metadata(CFG, self.SCRIPT, {"scam_guard": "PL123"})
        self.assertIn(f"https://www.youtube.com/channel/{CFG['upload']['youtube']['channel_id']}?sub_confirmation=1", desc)
        self.assertIn("https://www.youtube.com/playlist?list=PL123", desc)
        self.assertIn("詐欺対策", desc)

    def test_no_playlist_link_before_the_playlist_exists(self):
        _, desc, _ = upload_youtube.build_metadata(CFG, self.SCRIPT, {})
        self.assertNotIn("playlist?list=", desc)
        self.assertIn("sub_confirmation=1", desc)


class Playlist(unittest.TestCase):
    def test_missing_scope_never_breaks_the_upload(self):
        err = upload_youtube.requests.HTTPError("403")
        err.response = mock.Mock(text='{"error": {"code": 403, "message": "Request had insufficient authentication scopes."}}')
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(upload_youtube, "PLAYLISTS", Path(tmp) / "p.json"), \
                mock.patch.object(upload_youtube.requests, "post", side_effect=err):
            out = upload_youtube.add_to_playlist(CFG, {"category": "scam_guard"}, "vid", "tok")
        self.assertIn("insufficient", out["playlist_error"])

    def test_creates_the_playlist_once_then_reuses_it(self):
        calls = []

        def post(url, **kw):
            calls.append(url)
            r = mock.Mock()
            r.raise_for_status = lambda: None
            r.json = lambda: {"id": "PLnew"}
            return r

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(upload_youtube, "PLAYLISTS", Path(tmp) / "p.json"), \
                mock.patch.object(upload_youtube.requests, "post", side_effect=post):
            self.assertEqual(upload_youtube.add_to_playlist(CFG, {"category": "scam_guard"}, "v1", "tok"), {"playlist": "PLnew"})
            self.assertEqual(upload_youtube.add_to_playlist(CFG, {"category": "scam_guard"}, "v2", "tok"), {"playlist": "PLnew"})
        self.assertEqual(sum(u.endswith("/playlists") for u in calls), 1)
        self.assertEqual(sum(u.endswith("/playlistItems") for u in calls), 2)


class Trend(unittest.TestCase):
    def test_daily_row_and_report_section(self):
        status = {"checked_at": "2026-11-11T00:00:00+00:00",
                  "channel_7d": {"views": 5000, "subs_gained": 10, "subs_lost": 1, "avg_view_pct": 70},
                  "traffic_28d": {"PLAYLIST": 40, "YT_CHANNEL": 100}}
        items = [(None, {"uploads": [{"platform": "youtube", "playlist": "PL1"}]}, {}),
                 (None, {"uploads": [{"platform": "youtube", "playlist_error": "403 insufficient scopes"}]}, {})]
        row = analytics.channel_day_row(status, items, "2026-11-11")
        self.assertEqual(row["subs_per_1000_7d"], "2.00")
        self.assertEqual(row["videos_in_playlists"], 1)
        self.assertEqual(row["playlist_error"], "権限なし")
        rows = [{"variant": "outro_sub:sub", "views": "6000", "subs_gained": "12", "age_hours": "48"}] * 20 + \
               [{"variant": "outro_sub:follow", "views": "6000", "subs_gained": "6", "age_hours": "48"}] * 20
        text = "\n".join(analytics.subscriber_sections(rows, CFG, days=[{k: str(v) for k, v in row.items()}]))
        self.assertIn("| sub | 20 | 120,000 | 240 | 2.00 |", text)
        self.assertIn("各群が20本・5,000再生に届いた", text)
        self.assertIn("権限なし", text)


if __name__ == "__main__":
    unittest.main()
