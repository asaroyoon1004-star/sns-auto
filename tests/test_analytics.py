import unittest

from sns import analytics, scriptgen as g


class HookStyle(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(g.hook_style("警察を名乗る電話、暗証番号は教えないでください。"), "警告")
        self.assertEqual(g.hook_style("手取りは額面の約8割。残りの2割はどこへ？"), "疑問")
        self.assertEqual(g.hook_style("年30万円の買い物、還元率で1,500円の差。"), "数字")
        self.assertEqual(g.hook_style("電気代、使い方は同じでも会社を変えるだけで変わることがあります。"), "言い切り")

    def test_seed_without_hook_type_is_labelled_in_the_metrics_row(self):
        from pathlib import Path
        row = analytics._context(Path("20261026-000000-s999"), {"created_at": "20261026-000000"},
                                 {"category": "cashless", "hook": "年30万円の買い物、還元率で1,500円の差。"})
        self.assertEqual(row["hook_type"], "数字")
        row = analytics._context(Path("x"), {}, {"category": "cashless", "hook": "x", "hook_type": "損失回避"})
        self.assertEqual(row["hook_type"], "損失回避")


class ChannelFilter(unittest.TestCase):
    ROWS = [{"platform": "youtube", "video_id": "a", "channel_id": "UC_mine"},
            {"platform": "youtube", "video_id": "b", "channel_id": "UC_other"},
            {"platform": "youtube", "video_id": "c", "channel_id": ""},
            {"platform": "tiktok", "video_id": "d"}]

    def test_other_channels_and_unlabelled_rows_are_dropped(self):
        kept = [r["video_id"] for r in analytics.channel_rows(self.ROWS, "UC_mine")]
        self.assertEqual(kept, ["a", "d"])

    def test_without_a_known_channel_nothing_is_dropped(self):
        self.assertEqual(analytics.channel_rows(self.ROWS, None), self.ROWS)


class ReportTables(unittest.TestCase):
    def test_hook_tables_use_the_text_when_no_type_is_stored(self):
        rows = [{"hook": "手取りは額面の約8割。", "hook_type": "", "views": "10", "likes": "0", "age_hours": "30"},
                {"hook": "電気代が下がります。", "hook_type": "", "views": "20", "likes": "0", "age_hours": "30"}]
        text = "\n".join(analytics.research_sections(rows, {"categories": {}}))
        self.assertIn("数字", text)
        self.assertIn("冒頭に数字あり", text)
        self.assertIn("冒頭に数字なし", text)


if __name__ == "__main__":
    unittest.main()
