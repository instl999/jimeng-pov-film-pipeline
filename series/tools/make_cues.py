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
each line stays up from its SRT start until 0.25 s after the voice has actually died away, at least
0.7 s, and never past the next line's start or the end of the trimmed clip. A clip with no speech
needs no SRT.

Where the voice dies away: the recogniser's SRT end often lands before a quiet last syllable, which
took subtitles off while people were still talking. So each line's end is followed on the clip's own
sound (an energy check, 20 ms frames, against the clip's own floor) until it stays quiet for 0.2 s, at
most 0.9 s past the SRT end and never into the next line. A gap under 0.7 s between two lines is
closed, so the black strip does not blink off and on between them. "voice_end": false in the plan
turns the first off.
"""
import array
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env  # noqa: E402

TAIL, MIN_SHOW, GAP = 0.25, 0.7, 0.04
HEAR = 0.9          # follow a voice at most this far past the recogniser's end of a line
BRIDGE = 0.7        # close a gap shorter than this between two lines on the strip
FRAME = 0.02        # seconds per level reading


def levels(video):
    """-> the clip's sound level in dB, one value per 20 ms, voice band only (or None if it has no sound)."""
    raw = subprocess.run([env.ffmpeg(), "-v", "error", "-i", video, "-vn", "-af", "highpass=f=120,lowpass=f=4000", "-ac", "1",
                          "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    pcm = array.array("h")
    pcm.frombytes(raw[:len(raw) // 2 * 2])
    hop = int(16000 * FRAME)
    out = []
    for i in range(0, len(pcm) - hop, hop):
        frame = pcm[i:i + hop]
        rms = math.sqrt(sum(x * x for x in frame) / float(hop)) or 1e-9
        out.append(20 * math.log10(rms / 32768.0))
    return out or None


def loud(db):
    """The level above which a frame counts as voice: well above this clip's own room-sound floor."""
    s = sorted(db)
    floor, peak = s[int(len(s) * 0.1)], s[int(len(s) * 0.97)]
    return max(floor + 10, min(peak - 24, -30), -48)


def voice_end(db, thr, t, limit):
    """From time t, follow the sound until it stays under thr for 0.2 s, or until limit. -> when it died away."""
    i, quiet, end = int(t / FRAME), 0, t
    while i < len(db) and i * FRAME < limit:
        if db[i] >= thr:
            end, quiet = min(limit, (i + 1) * FRAME), 0
        else:
            quiet += 1
            if quiet >= 10:
                break
        i += 1
    return end


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
        db = levels(video) if spoken and plan.get("voice_end", True) else None
        thr = loud(db) if db else None
        for i, (text, (start, end, _)) in enumerate(zip(texts, spoken)):
            start = max(start, lo)
            following = max(spoken[i + 1][0], lo) if i + 1 < len(spoken) else hi
            if db:
                end = max(end, voice_end(db, thr, end, min(following - GAP, end + HEAR)))
            stop = max(end + TAIL, start + MIN_SHOW)
            if i + 1 < len(spoken):
                stop = min(stop, following - GAP)
                if following - GAP - stop < BRIDGE:
                    stop = following - GAP
            stop = min(stop, hi)
            if stop - start < 0.2 and i + 1 == len(spoken) and bar:   # a short last word at the very end of a clip
                start = max(hi - 0.45, bar[-1]["t"][0] + 0.3)         # takes a little time from the line before it
                bar[-1]["t"][1] = round(min(bar[-1]["t"][1], start - GAP), 2)
                stop = hi
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
