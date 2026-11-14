#!/usr/bin/env python3
"""Fail if the text layers drawn by compose_episode.py differ from the locked series spec.

    python3 series/tools/tests/text_lock.py            values only (fast; film.py check runs this)
    python3 series/tools/tests/text_lock.py --render   also draws every layer and measures where it lands

The spec is series/text-styles.json, taken from the first finished film. Change it only on the
owner's word, for the whole series at once.
"""
import json
import os
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import compose_episode as ce  # noqa: E402

SPEC = os.path.join(os.path.dirname(TOOLS), "text-styles.json")


def differences():
    lock = json.load(open(SPEC, encoding="utf-8"))
    L, out = ce.FULL_LAYERS, []
    pairs = {"notice": "notice", "premise": "premise", "date_line": "score", "subtitle": "bar", "narration": "bar", "super": "inpic"}

    def same(what, want, have):
        if want != have:
            out.append("%s: locked %r, the composer has %r" % (what, want, have))

    for name, layer in pairs.items():
        want, have = lock["layers"][name], L[layer]
        same(name + " font", want["font"], have["font"])
        same(name + " size", want["size_px"], have["size"])
        if name not in ("subtitle", "narration", "super"):
            same(name + " colour", want["colour"], "#" + have["colour"])
            same(name + " outline", want["outline_px"], have["outline"])
        pos = want["position"]
        same(name + " x", pos.get("right_edge_x", pos.get("centre_x")), have["x"])
    same("premise top", lock["layers"]["premise"]["position"]["top_y"], L["premise"]["top"])
    same("premise pitch", lock["layers"]["premise"]["position"]["line_pitch_px"], L["premise"]["pitch"])
    same("notice top", lock["layers"]["notice"]["position"]["top_y"], L["notice"]["top"])
    same("date line top", lock["layers"]["date_line"]["position"]["top_y_with_premise"], L["score"]["top"])
    same("date line alone", lock["layers"]["date_line"]["position"]["top_y_alone"], L["score"]["top_alone"])
    same("subtitle centre", lock["layers"]["subtitle"]["position"]["centre_y"], L["bar"]["mid"])
    same("strip height", lock["layers"]["subtitle"]["strip"]["height_px"], ce.STRIP_H)
    same("strip bridge", lock["layers"]["subtitle"]["strip"]["bridges_gaps_up_to_s"], ce.STRIP_BRIDGE)
    same("narration range", lock["layers"]["narration"]["position"]["may_move_to_y"], list(ce.FULL_Y_RANGE))
    same("canvas", [lock["canvas"]["width"], lock["canvas"]["height"]], [ce.W, ce.H])
    return out, lock


def render_check(lock):
    """Draw the title block and a subtitle the way the composer does and measure them."""
    ffmpeg, _ = ce.find_ffmpeg(None)
    events = [("premise", "Premise", 0, 0, 30, "假如你在2001年", None, False), ("premise", "Premise", 1, 0, 30, "全仓买入英伟达", None, False),
              ("score", "Score", 0, 0, 30, "买入第一天", None, False), ("bar", "Bar", 0, 0, 30, "确定", None, True)]
    with tempfile.TemporaryDirectory() as work:
        ce.write_ass(os.path.join(work, "t.ass"), events, "full")
        raw = os.path.join(work, "f.raw")
        subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=0x808080:s=1080x1920:r=30:d=0.5", "-vf", "ass=t.ass",
                        "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", raw], cwd=work, check=True)
        data = open(raw, "rb").read()
    rows = [data[y * 1080:(y + 1) * 1080] for y in range(1920)]
    black = [y for y, r in enumerate(rows) if max(r) < 30]
    white = [y for y, r in enumerate(rows) if sum(1 for v in r if v > 235) > 3]
    m = lock["measured_in_first_film"]
    out = []
    if not black or abs(black[0] - m["subtitle_strip_rows"][0]) > 1 or abs(black[-1] - m["subtitle_strip_rows"][1]) > 1:
        out.append("the subtitle strip is drawn at rows %s, the first film had %s" % (black[:1] + black[-1:], m["subtitle_strip_rows"]))
    for what in ("premise_line_1_rows", "premise_line_2_rows", "date_line_with_premise_rows", "subtitle_text_rows"):
        y0, y1 = m[what]
        if not any(abs(y - y0) <= 3 for y in white) or not any(abs(y - y1) <= 3 for y in white):
            out.append("%s: nothing drawn where the first film had it (rows %d-%d)" % (what, y0, y1))
    return out


if __name__ == "__main__":
    problems, lock = differences()
    if "--render" in sys.argv and not problems:
        problems = render_check(lock)
    for p in problems:
        print("TEXT LOCK: " + p)
    print("text layers match the locked series spec" if not problems else "text layers differ from series/text-styles.json")
    sys.exit(1 if problems else 0)
