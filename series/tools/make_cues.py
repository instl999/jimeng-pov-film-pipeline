#!/usr/bin/env python3
"""Turn an episode plan plus per-clip speech timings into a cue file for compose_episode.py.

    python3 make_cues.py PLAN.json            # writes the cue file named by the plan's "cues"
    python3 make_cues.py PLAN.json --print    # print it instead

The plan says what is shown; the SRT files say when each spoken line happens. Paths in the
plan are relative to the plan file.

    { "cues": "E01.cues.json",                 # where to write the cue file
      "output": "../out/E01.mp4",              # passed through, re-based for the cue file
      "notice": "...", "premise": ["...", "..."],
      "layout": "full", "loudness_lufs": -15,  # optional; passed through to compose_episode.py
      "clips": "../out/E01",                   # folder holding S01.mp4, S02.mp4, ...
      "srt": ".",                              # folder holding S01.srt, ... (from `jimeng-novel transcribe --srt`)
      "sfx": "../../series/sfx",               # folder holding the effect files
      "items": [
        { "clip": "S01",
          "scoreboard": "买入第 1 天　10万",    # or [{"t": [0, 3], "text": ".."}, ...]
          "bar": ["来买股票了..", "全买英伟达"],  # shown text, in spoken order; times come from S01.srt
          "trim": [0, 7.4],                     # optional
          "inpic": [{"t": [6.0, 7.5], "text": "女朋友走了..", "color": "green", "duck": true}],
          "sfx": [{"t": 0.1, "file": "cold-open-hit.mp3", "gain_db": -9}],
          "mute": [[6.3, 8.0]], "gain_db": 0 },
        { "flash": [["S02", 6.5], ["S04", 3.0]], "each": 0.2,
          "sfx": {"file": "recap-flash.mp3", "gain_db": -6} }
      ] }

A line longer than "split_bar_over" characters (default 10 in the full layout, off otherwise)
that contains a space is shown in parts, split at its spaces, sharing the line's time by length.

Rules for bar lines: the number of texts must equal the number of SRT entries for that clip;
each line stays up from its SRT start until 0.25 s after its SRT end, at least 0.7 s, and never
past the next line's start or the end of the trimmed clip. A clip with no speech needs no SRT.
"""
import json
import os
import re
import subprocess
import sys

TAIL, MIN_SHOW, GAP = 0.25, 0.7, 0.04


def fail(msg):
    sys.exit("make_cues: " + msg)


def read_srt(path):
    if not os.path.exists(path):
        return []
    out = []
    stamp = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
    for block in re.split(r"\n\s*\n", open(path, encoding="utf-8-sig").read().strip()):
        m = stamp.search(block)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        text = " ".join(l.strip() for l in block[m.end():].strip().splitlines())
        out.append((start, end, re.sub(r"</?i>", "", text)))
    return out


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        fail("cannot read the duration of %s" % path)


def fit_narration(entry, bar, lo, hi):
    """A narration line on the strip shares the subtitle's place, so it gives way to speech: an
    opening line ends before the first subtitle that would overlap it, a closing line starts
    after the last. If that leaves under 0.9 s, it keeps its time and moves up clear of the strip."""
    if not entry.get("strip"):
        return entry
    a, b = entry["t"]
    clash = [x["t"] for x in bar if x["t"][0] < b and a < x["t"][1]]
    if not clash:
        return entry
    first, last = min(c[0] for c in clash), max(c[1] for c in clash)
    if a < first - 0.9:
        entry["t"] = [a, round(first - 0.08, 2)]
    elif b > last + 0.9:
        entry["t"] = [round(last + 0.08, 2), b]
    elif "y" not in entry:
        entry["y"] = 1120
    return entry


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    plan_path = os.path.abspath(args[0])
    base = os.path.dirname(plan_path)
    plan = json.load(open(plan_path, encoding="utf-8"))
    cue_path = os.path.join(base, plan["cues"])
    cue_dir = os.path.dirname(cue_path)

    def rel(*parts):
        return os.path.relpath(os.path.join(base, *parts), cue_dir)

    cues = {"output": rel(plan["output"]), "notice": plan["notice"], "premise": plan["premise"]}
    for key in ("layout", "loudness_lufs", "premise_seconds", "scoreboard_seconds"):   # passed through to compose_episode.py
        if key in plan:
            cues[key] = plan[key]
    cues["items"] = []
    split_over = plan.get("split_bar_over", 10 if plan.get("layout") == "full" else 0)
    for n, item in enumerate(plan["items"]):
        where = "items[%d]" % n
        if "flash" in item:
            out = {"flash": [{"file": rel(plan["clips"], c + ".mp4"), "t": t} for c, t in item["flash"]]}
            if "each" in item:
                out["each"] = item["each"]
            if "scoreboard" in item:
                out["scoreboard"] = item["scoreboard"]
            if "sfx" in item:
                out["sfx"] = dict(item["sfx"], file=rel(plan["sfx"], item["sfx"]["file"]))
            cues["items"].append(out)
            continue
        clip = item["clip"]
        video = os.path.join(base, plan["clips"], clip + ".mp4")
        if not os.path.exists(video):
            fail("%s: clip not found: %s" % (where, video))
        lo, hi = item.get("trim", [0.0, duration(video)])
        spoken = read_srt(os.path.join(base, plan["srt"], clip + ".srt"))
        texts = item.get("bar", [])
        if len(texts) != len(spoken):
            fail("%s (%s): the plan has %d bar lines but %s.srt has %d spoken lines: %s"
                 % (where, clip, len(texts), clip, len(spoken), [s[2] for s in spoken]))
        bar = []
        for i, (text, (start, end, _)) in enumerate(zip(texts, spoken)):
            start = max(start, lo)
            stop = max(end + TAIL, start + MIN_SHOW)
            if i + 1 < len(spoken):
                stop = min(stop, max(spoken[i + 1][0], lo) - GAP)
            stop = min(stop, hi)
            if stop - start < 0.2:
                fail("%s (%s): line %d %r has no room on screen (%.2f-%.2f); check the trim" % (where, clip, i + 1, text, start, stop))
            parts = text.split(" ") if split_over and len(text.replace(" ", "")) > split_over and " " in text else [text]
            weight = [len(p) for p in parts]
            at = start
            for p, w in zip(parts, weight):
                nxt = at + (stop - start) * w / sum(weight)
                bar.append({"t": [round(at, 2), round(nxt - (GAP if p is not parts[-1] else 0), 2)], "text": p})
                at = nxt
        out = {"file": rel(plan["clips"], clip + ".mp4"), "scoreboard": item["scoreboard"]}
        if "trim" in item:
            out["trim"] = item["trim"]
        if bar:
            out["bar"] = bar
        for key in ("inpic", "mute", "gain_db"):
            if key in item:
                out[key] = item[key]
        if "inpic" in out:
            out["inpic"] = [fit_narration(dict(e), bar, lo, hi) for e in out["inpic"]]
        if "sfx" in item:
            out["sfx"] = [dict(s, file=rel(plan["sfx"], s["file"])) for s in item["sfx"]]
        cues["items"].append(out)

    text = json.dumps(cues, ensure_ascii=False, indent=2) + "\n"
    if "--print" in sys.argv:
        sys.stdout.write(text)
    else:
        open(cue_path, "w", encoding="utf-8").write(text)
        print("wrote %s (%d items)" % (cue_path, len(cues["items"])))


if __name__ == "__main__":
    main()
