import json
import unittest
from pathlib import Path

from sns import scriptgen as g

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def script(hook, lines, cta="保存して、あとで見返してね。", **kw):
    return {"hook": hook, "lines": lines, "cta": cta, "category": "saving_habit", **kw}


GOOD = [
    script("毎月1万円を20年積み立てると、いくらになる？",
           ["貯金だけなら、元本は240万円です。", "仮に年利3パーセントで運用できたとします。",
            "その場合、20年後は約328万円になります。", "差額の約88万円が、運用で増えた分です。",
            "ただし年利は約束されたものではなく、元本割れもあります。", "続けるほど差が開く、これが複利の仕組みです。"],
           fact_check_notes="金融庁 つみたてNISA資料。年利3%固定は仮定。328万円は計算値"),
    script("電気代の3割は、実は待機電力ではない。",
           ["家庭の電力で、待機電力の割合は約5パーセントです。", "資源エネルギー庁の調査では、この数字が出ています。",
            "大きいのはエアコンと冷蔵庫です。", "まず、古い冷蔵庫の買い替えを見直しましょう。",
            "コンセントを抜くより、効果が大きいことがあります。"], fact_check_notes="資源エネルギー庁 省エネ性能カタログ"),
    script("医療費が100万円かかっても、全額は払わない。",
           ["高額療養費制度という仕組みがあるからです。", "上限額は、年齢と所得で決まります。",
            "たとえば、一般的な所得の70歳未満なら月に約9万円前後です。", "加入している健康保険に申請します。",
            "事前に限度額適用認定証をもらうと、窓口の支払いも抑えられます。"], fact_check_notes="厚生労働省 高額療養費制度。9万円前後は目安"),
]
BAD = {
    "preamble": script("こんにちは、今日はNISAの話です。", ["NISAは非課税の制度です。", "年間の投資枠があります。", "長く続けるのが基本です。", "元本割れもあります。"]),
    "hook_no_device": script("投資のタイミングに迷う人のための、シンプルな方法。", ["ずっと同じ金額を積み立てます。", "高いときは少なく買えます。", "安いときは多く買えます。", "元本割れもあります。"]),
    "hype": script("絶対に失敗しない貯金の方法。", ["毎月1万円を貯めます。", "ボーナスも全部貯めます。", "それだけで絶対に増えます。", "元本割れはありません。"]),
    "repeat": script("固定費を見直すと、いくら変わる？",
                     ["固定費を見直すと、毎月の支出が減ります。", "固定費を見直すことで、毎月の支出が減ります。", "まずスマホの料金を確認します。", "次に保険を確認します。"]),
    "projection_no_condition": script("1万円を預けたら、どうなる？",
                                      ["年利5パーセントで、10年後には1万6千円になります。", "20年後には2万6千円になります。", "放っておくだけで増えます。", "元本割れはありません。"]),
    "long_hook": script("毎月の支払いが一定で安心、それが実は一番危ないかもしれない理由。", ["支払いが固定だと見直しません。", "気づくと高いままです。", "年1回は見直します。", "元本割れはありません。"]),
}


class LintTests(unittest.TestCase):
    def test_good_scripts_are_clean(self):
        for s in GOOD:
            self.assertEqual(g.lint(s), [], s["hook"])

    def test_each_bad_script_is_caught(self):
        expect = {"preamble": "preamble", "hook_no_device": "no question", "hype": "hype", "repeat": "repeats",
                  "projection_no_condition": "projection", "long_hook": "hook"}
        for name, s in BAD.items():
            self.assertTrue(any(expect[name] in p for p in g.lint(s)), (name, g.lint(s)))

    def test_validate_includes_lint(self):
        s = GOOD[0]
        self.assertEqual([p for p in g.validate(s, CFG) if "length" not in p and "lines=" not in p], [])
        self.assertTrue(g.validate(BAD["hype"], CFG))

    def test_empty_notes_flagged(self):
        s = dict(GOOD[1], fact_check_notes="")
        self.assertIn("fact_check_notes empty", g.lint(s))


class SeedTests(unittest.TestCase):
    def test_seed_schema_unchanged(self):
        for x in json.loads((ROOT / "data/seed/scripts.json").read_text(encoding="utf-8")):
            for k in ("id", "category", "title", "hook", "lines", "cta", "hashtags", "affiliate"):
                self.assertIn(k, x)

    def test_prompt_formats(self):
        out = g.SYSTEM_PROMPT.format(affiliates="a, b", cmin=120, cmax=220)
        self.assertIn("120〜220", out)


if __name__ == "__main__":
    unittest.main()
