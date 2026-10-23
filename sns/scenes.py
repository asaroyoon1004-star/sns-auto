"""Scene plan: one record per narrated segment (hook, each line, call to action), built from the script before rendering.

The renderers read these records instead of re-deriving what a caption means; the plan is also saved next to the video
(scene_plan.json) so a finished video can be checked against what it was meant to say.

Fields: index, role, narration, caption, key_message, visual_type, visual_data, emphasis, transition, source, caveat,
and (filled in after the audio exists) start / duration. Roles are inferred from wording and position, so treat them as a
description of the video, not as something the script author declared.
"""
import re

from . import design_v3

CAVEAT = re.compile(r"ただし|注意|元本割れ|保証され|あくまで|とは限らない|わけではありません|対象外")
EXAMPLE = re.compile(r"例えば|たとえば|仮に|として")
REVEAL = re.compile(r"^(それが|答えは|実は|つまり|その一言とは)")


def _emphasis(text):
    """The numbers and amounts worth emphasising in a caption (short ones only; long ones are sentences, not figures)."""
    out = []
    for m in design_v3.NUM_RE.finditer(text):
        if len(m.group(0)) <= 8 and m.group(0) not in out:
            out.append(m.group(0))
    return out


def _role(i, n, text, hook_is_question):
    if i == 0:
        return "hook"
    if i == n - 1:
        return "cta"
    if CAVEAT.search(text):
        return "caveat"
    if i == 1 and (hook_is_question or REVEAL.search(text)):
        return "reveal"
    if EXAMPLE.search(text) or design_v3.visual_spec(text):
        return "example"
    return "explanation"


def plan_scenes(script, transition="cut"):
    """Scene records for a script (without timing)."""
    segs = [("hook", script["hook"])] + [("line", l) for l in script["lines"]] + [("cta", script["cta"])]
    vis = script.get("visual")
    hook_q = script["hook"].rstrip().endswith(("？", "?"))
    scenes = []
    for i, (kind, text) in enumerate(segs):
        new_rows = []
        if vis and kind == "line":
            new_rows = [r for r in vis["rows"] if r["line"] == i]
        hero = None
        if kind == "line":
            m = design_v3.HERO_RE.search(text)
            hero = m.group(0) if m and len(m.group(0)) <= 8 else None
        spec = design_v3.visual_spec(text) if kind == "line" else None
        if new_rows:
            vtype, vdata = vis["type"], {"title": vis["title"], "rows": new_rows}
        elif hero:
            vtype, vdata = "number", {"hero": hero}
        elif spec:
            vtype, vdata = spec["type"], spec
        else:
            vtype, vdata = "text", {}
        scenes.append({
            "index": i,
            "role": _role(i, len(segs), text, hook_q),
            "narration": text,
            "caption": text,
            "key_message": new_rows[0]["label"] if new_rows else text.rstrip("。！？"),
            "visual_type": vtype,
            "visual_data": vdata,
            "emphasis": _emphasis(text),
            "transition": "cut" if kind == "hook" else transition,
            "source": script.get("fact_check_notes", ""),
            "caveat": text if CAVEAT.search(text) else "",
        })
    return scenes


def attach_timing(scenes, items):
    """Add start/duration (seconds) to the scenes from the caption timeline [(segment index, kind, chunk, seconds), ...]."""
    t, starts, ends = 0.0, {}, {}
    for i, _, _, d in items:
        starts.setdefault(i, t)
        t += d
        ends[i] = t
    for s in scenes:
        s["start"] = round(starts.get(s["index"], 0.0), 3)
        s["duration"] = round(ends.get(s["index"], 0.0) - s["start"], 3)
    return scenes


def _numbers(text):
    return re.findall(r"\d+(?:\.\d+)?", text.replace(",", "").replace("，", ""))


def consistency(script):
    """Problems where the diagram and the narration disagree: a row whose numbers the narration never says on that line
    (or in the hook), or bars whose lengths are not in the proportion of the amounts they print."""
    vis = script.get("visual")
    if not vis:
        return []
    out = []
    for r in vis["rows"]:
        said = set(_numbers(script["hook"] + script["lines"][r["line"] - 1]))
        for num in _numbers(r.get("label", "") + r.get("text", "")):
            if num not in said:
                out.append(f"row '{r['label']}': number {num} is not said on line {r['line']}")
    if vis["type"] == "bars" and not any("〜" in r["text"] for r in vis["rows"]):
        amounts = []
        for r in vis["rows"]:
            m = design_v3.NUM_RE.search(r["text"] + " ") if r["text"] else None
            amounts.append(design_v3._parse_amount(m.group(0)) if m else None)
        if all(a for a in amounts):
            base = vis["rows"][0]["value"] / amounts[0]
            for r, a in zip(vis["rows"], amounts):
                if abs(r["value"] / a - base) > 0.05 * base:
                    out.append(f"bar '{r['label']}': length {r['value']} is not in proportion to {r['text']}")
    return out
