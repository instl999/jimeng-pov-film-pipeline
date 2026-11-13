#!/usr/bin/env python3
"""compose_episode.py - assemble one vertical short-video episode from clips.

Reads a JSON cue file, puts each clip (scaled / centre-cropped to 1080x810) on a
black 1080x1920 canvas, burns the fixed text layers of series/FORMAT.md section 4
(notice, premise, scoreboard, in-picture narration, bar) from one generated ASS
file, mixes the sound (clip gain, mute windows, ducking under in-picture lines,
sound effects on top) and writes H.264 yuv420p 30 fps + AAC 48 kHz to MP4.
That is the "boxed" layout. With "layout": "full" the picture fills the whole
1080x1920 frame instead and the same text layers are drawn over it (see LAYOUT).

USAGE
    python3 compose_episode.py CUES.json              render to the cue file's "output"
    python3 compose_episode.py CUES.json -o OUT.mp4   render somewhere else
    python3 compose_episode.py CUES.json --check      validate, check fonts, print timeline
    options: --ffmpeg PATH   --preset medium   --crf 18   --keep-work   -v

Python 3 standard library only. Needs an ffmpeg built with libass (the "ass"
filter). Looked for in this order: --ffmpeg, $FFMPEG, /opt/homebrew/bin/ffmpeg,
ffmpeg on PATH, ~/.local/bin/ffmpeg; the first one that has the filter is used.

CUE FILE (paths are relative to the cue file; keys starting with "_" are ignored)
    {
      "output":  "E01.mp4",
      "layout":  "boxed",                                     optional: boxed (default) | full
      "loudness_lufs": -15,                                   optional, see SOUND
      "premise_seconds": 7,                                   optional: the premise leaves after this long
      "scoreboard_seconds": 4,                                optional: each scoreboard line leaves this long after it changes
      "notice":  "AI 生成 · 虚构剧情 · 不构成投资建议",
      "premise": ["假如你在2001年", "全仓买入英伟达"],          1 or 2 lines
      "items": [
        { "file": "clip.mp4",                                 a normal clip
          "trim": [0.5, 4.5],                                 optional, default whole file
          "gain_db": 0,                                       optional, clip's own audio
          "scoreboard": "买入第 1 天　10万",                   or [{"t":[s,e],"text":..}, ..]
          "bar":   [{"t": [0.6, 1.8], "text": "来买股票了.."}],
          "inpic": [{"t": [2.0, 3.5], "text": "女朋友走了..",
                     "color": "green", "duck": true,          color: green | red | white
                     "y": 900, "strip": false}],              full layout only, see LAYOUT
          "sfx":   [{"t": 3.0, "file": "ding.wav", "gain_db": -6}],
          "mute":  [[3.9, 4.2]] },
        { "flash": [{"file": "clip.mp4", "t": 1.0}, ..],      a flash recap of stills
          "each": 0.2,                                        optional, seconds per still
          "sfx": {"file": "swell.wav", "gain_db": 0},         optional, starts with the recap
          "scoreboard": ".." }                                optional, default: carried over
      ]
    }

TIME: every "t", "trim" and "mute" value of a clip is in seconds from the start of
that clip's FILE (one clock per clip). Without "trim" that is also the time since
the clip came on screen. With "trim" the cues keep their file times, so changing
the trim never shifts them; a cue outside the trim range is an error. Everything
is snapped to whole frames at 30 fps; --check prints where each item starts.

SOUND: "duck": true lowers the clip's own audio by 12 dB during that in-picture
line; "mute" takes it to silence. Both fade inside the window (0.12 s / 0.03 s),
so audio outside a window is never touched. Sound effects are not ducked; an
effect may ring on past the end of its item. A limiter at -0.45 dBFS guards the
final mix and does nothing below that level.
"loudness_lufs": N (for example -15) adds a finishing pass after the mix is
rendered: the integrated loudness of the whole mix is measured (EBU R128), one
fixed gain brings it to N LUFS, and a limiter at -3 dBFS keeps the true peak
under -1 dBTP. The picture is copied, not encoded again. The loudness and true
peak before and after are printed. Without the key there is no such pass.

LAYOUT: "boxed" is the 4:3 picture in the middle of a black canvas, premise and
scoreboard above it, "inpic" lines small at the picture's lower left, "bar"
lines under it. "full" scales every clip and flash still to cover 1080x1920
(centre-cropped, no black anywhere) and draws every layer centred on x=540 with
a dark outline and a soft shadow: the notice small in the top right corner for
the whole video; premise and scoreboard at the top (with "premise_seconds" the
premise and the first scoreboard line leave together after that long; with
"scoreboard_seconds" each later scoreboard line comes up when it changes, sits
where the premise was, and leaves after that long); and "inpic" lines as supers whose vertical centre is the
entry's "y" (pixels, 560-1420, default 900). "bar" lines are the subtitles:
plain white on a full-width black strip 124 px high centred on y=1320, one line
at a time; the strip stays up across gaps of up to 0.25 s between lines and is
gone when nobody speaks. An "inpic" line with "strip": true is narration in
that same look (strip, subtitle font and size, always white), at its own "y",
default the subtitle position; a super and a narration line may be on screen
together when their centres are 150 px or more apart. "y" and "strip" are unknown fields in the boxed
layout. In the full layout a line estimated wider than 900 px gets a warning
and is drawn smaller, on one line, so that it fits; and an "inpic" line may not
share screen time with a "bar" line of the same item when their centres are
under 150 px apart.

FONTS and positions are the constants just below. Sizes are the height of a
Chinese character in pixels. To use another font, add its two numbers to
FONT_METRICS.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata

# --------------------------------------------------------------------------- layout

W, H, FPS = 1080, 1920, 30
PIC_W, PIC_H, PIC_TOP = 1080, 810, 554          # the 4:3 picture, y 554..1364 (the design says
                                                # 555; yuv420p can only place it on an even row)
SR = 48000
SPF = SR // FPS                                 # audio samples per video frame

# The three faces are macOS's own. Elsewhere, name installed ones in FILM_SERIF / FILM_SANS /
# FILM_SANS_BOLD (for instance "Noto Serif CJK SC Black" and "Noto Sans CJK SC"); positions are
# then worked out with DEFAULT_METRICS and may sit a few pixels off.
SERIF = os.environ.get("FILM_SERIF", "Songti SC Black")
SANS = os.environ.get("FILM_SANS", "Hiragino Sans GB W3")              # stands in for PingFang SC, which
SANS_BOLD = os.environ.get("FILM_SANS_BOLD", "Hiragino Sans GB W6")    # libass cannot open on this macOS

# libass sizes a font by its line height, not by its character height, and puts
# the characters at a font-specific distance below the line top. Measured once
# per face with ffmpeg's bbox filter: "em" = character width per unit of ASS
# Fontsize, "top" = distance from line top to character box top, same unit.
FONT_METRICS = {
    "Songti SC Black":     {"em": 1.0000, "top": 0.0075},
    "Songti SC Bold":      {"em": 1.0000, "top": 0.0600},
    "Hiragino Sans GB W3": {"em": 0.8595, "top": 0.0802},
    "Hiragino Sans GB W6": {"em": 0.8045, "top": 0.1352},
}
DEFAULT_METRICS = {"em": 1.0, "top": 0.05}

# size = character height in px; x = centre (align "c") or left edge (align "l");
# top = y of the top of the characters; colour = RRGGBB.
LAYERS = {
    "notice":  {"font": SANS,      "size": 28, "x": 540, "top": 170, "align": "c",
                "colour": "C8C8C8", "outline": 0, "z": 1},
    "premise": {"font": SERIF,     "size": 78, "x": 540, "top": 250, "align": "c",
                "colour": "FFFFFF", "outline": 0, "z": 2, "pitch": 96},
    "score":   {"font": SERIF,     "size": 60, "x": 540, "top": 455, "align": "c",
                "colour": "FFFFFF", "outline": 0, "z": 3},
    # 48 px in from the picture's left edge, bottom of the text 90 px above its bottom edge
    "inpic":   {"font": SANS_BOLD, "size": 40, "x": 48, "top": PIC_TOP + PIC_H - 90 - 40,
                "align": "l", "colour": None, "outline": 1.5, "shadow": 2, "z": 4},
    # vertically centred on y=1430
    "bar":     {"font": SERIF,     "size": 64, "x": 540, "top": 1430 - 32, "align": "c",
                "colour": "FFFFFF", "outline": 0, "z": 5},
}
# The "full" layout: the picture fills the frame and every layer sits over it, centred,
# with an outline and a shadow. "mid" = y of the vertical centre of the characters.
# Nothing is drawn above y=150 or below y=1500.
FULL_LAYERS = {
    # the notice's top is y=150 counting its outline: the characters start 2 px lower, so that
    # the 1.5 px outline does not cross the y=150 line
    # small, in the top right corner, the way the narration reference carries its notice; always on
    "notice":  {"font": SANS,      "size": 22, "x": 1048, "top": 110, "align": "r",
                "colour": "D8D8D8", "outline": 1.5, "shadow": 1, "z": 1},
    "premise": {"font": SERIF,     "size": 84, "x": 540, "top": 205, "align": "c",
                "colour": "FFFFFF", "outline": 4, "shadow": 2, "z": 2, "pitch": 100},
    # "top_alone": where the line sits once the premise has left the screen
    "score":   {"font": SERIF,     "size": 64, "x": 540, "top": 420, "top_alone": 215, "align": "c",
                "colour": "FFFFFF", "outline": 3.5, "shadow": 2, "z": 3},
    # supers inside the picture (a place, a time, a figure); an entry's own "y" replaces "mid"
    "inpic":   {"font": SERIF,     "size": 72, "x": 540, "mid": 900, "align": "c",
                "colour": None, "outline": 4, "shadow": 2, "z": 4},
    # subtitles, and narration lines marked "strip": white on a full-width black strip, one line at a time
    "bar":     {"font": SERIF,     "size": 84, "x": 540, "mid": 1320, "align": "c",
                "colour": "FFFFFF", "outline": 4.5, "shadow": 2, "z": 5},
}
LAYOUTS = {"boxed": LAYERS, "full": FULL_LAYERS}
FULL_LINE_WIDTH = 900                           # full layout: warn past this, and draw the line smaller to fit
FULL_Y_RANGE = (560, 1420)                      # full layout: allowed "y" of an inpic line
FULL_MIN_GAP = 150                              # full layout: least distance between inpic and bar centres
STRIP_H = 124                                   # full layout: height of the black strip behind a subtitle line
STRIP_BRIDGE = 0.25                             # the strip stays up across gaps between lines up to this long (s)

ACCENTS = {"green": "3DDC84", "red": "F0453A", "white": "FFFFFF"}
OUTLINE_COLOUR = "101010"
SIDE_MARGIN = 40                                # warn when a line comes closer to the frame edge

DUCK_DB, DUCK_FADE, MUTE_FADE = -12.0, 0.12, 0.03
LIMIT = 0.95                                    # ceiling of the limiter on the mix, linear
FLASH_EACH = 0.2
AUDIO_OUT = ["-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-movflags", "+faststart", "-f", "mp4"]
LOUDNESS_CEILING_DB = -3.0                      # limiter of the "loudness_lufs" pass, dBFS
TRUE_PEAK_MAX_DB = -1.0                         # what that ceiling is there to guarantee, dBTP


class Fail(Exception):
    """A problem to report plainly, without a traceback."""


# --------------------------------------------------------------------------- tools

def find_ffmpeg(override):
    """Return (ffmpeg, ffprobe); the ffmpeg must have the libass "ass" filter."""
    if override:
        candidates = [override]
    else:
        candidates = [os.environ.get("FFMPEG"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg",
                      shutil.which("ffmpeg"), os.path.expanduser("~/.local/bin/ffmpeg")]
    tried, chosen = [], None
    for cand in candidates:
        if not cand or any(cand == t[0] for t in tried):
            continue
        if not (os.path.isfile(cand) and os.access(cand, os.X_OK)):
            tried.append((cand, "not found"))
            continue
        out = subprocess.run([cand, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        names = set(parts[1] for parts in (line.split() for line in out.splitlines()) if len(parts) >= 3)
        if "ass" in names:
            chosen = cand
            break
        tried.append((cand, "built without libass (no \"ass\" filter)"))
    if not chosen:
        raise Fail("no ffmpeg with libass found, so the text layers cannot be drawn. Tried:\n"
                   + "\n".join("  %s: %s" % t for t in tried)
                   + "\nPass one with --ffmpeg PATH or $FFMPEG.")
    for cand in (os.path.join(os.path.dirname(chosen), "ffprobe"), "/opt/homebrew/bin/ffprobe",
                 shutil.which("ffprobe")):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return chosen, cand
    raise Fail("ffprobe not found next to %s, in /opt/homebrew/bin or on PATH" % chosen)


class Media:
    """ffprobe, cached per file."""

    def __init__(self, ffprobe):
        self.ffprobe, self.cache = ffprobe, {}

    def probe(self, path):
        if path not in self.cache:
            self.cache[path] = self._probe(path)
        return self.cache[path]

    def _probe(self, path):
        run = subprocess.run(
            [self.ffprobe, "-v", "error", "-of", "json", "-show_entries",
             "format=duration:stream=codec_type,codec_name,width,height,pix_fmt,duration,"
             "r_frame_rate,nb_frames,sample_rate,channels", path],
            capture_output=True, text=True)
        if run.returncode != 0:
            return None
        try:
            data = json.loads(run.stdout)
        except ValueError:
            return None
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

        def seconds(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        fps = None
        if video and "/" in video.get("r_frame_rate", ""):
            num, den = video["r_frame_rate"].split("/")
            fps = float(num) / float(den) if float(den) else None
        container = seconds(data.get("format", {}).get("duration"))
        return {"video": video, "audio": audio, "fps": fps, "container": container,
                "duration": (seconds(video.get("duration")) if video else None) or container}


# --------------------------------------------------------------------------- cue file

class Report:
    """Errors and warnings, plus the layout the cue file is being checked against."""

    def __init__(self):
        self.errors, self.warnings, self.layout = [], [], "boxed"

    def err(self, where, message):
        self.errors.append("%s: %s" % (where, message))

    def warn(self, where, message):
        self.warnings.append("%s: %s" % (where, message))


def to_frames(seconds):
    return int(math.floor(seconds * FPS + 0.5 + 1e-9))


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check_keys(rep, obj, where, required, optional):
    """True when obj is an object; reports unknown and missing keys."""
    if not isinstance(obj, dict):
        rep.err(where or "cue file", "must be an object, got %s" % json.dumps(obj, ensure_ascii=False))
        return False
    prefix = where + "." if where else ""
    for key in obj:
        if not key.startswith("_") and key not in required and key not in optional:
            rep.err(prefix + key, "unknown field (known here: %s)" % ", ".join(list(required) + list(optional)))
    for key in required:
        if key not in obj:
            rep.err(prefix + key, "missing")
    return True


def get_window(rep, where, value):
    """[start, end] -> (start, end), or None after reporting what is wrong."""
    if not (isinstance(value, list) and len(value) == 2 and all(is_number(v) for v in value)):
        rep.err(where, "must be [start, end] in seconds, got %s" % json.dumps(value, ensure_ascii=False))
        return None
    start, end = float(value[0]), float(value[1])
    if start < 0:
        rep.err(where, "start %g is negative" % start)
        return None
    if end <= start:
        rep.err(where, "end %g is not after start %g" % (end, start))
        return None
    return start, end


def text_width(text, size):
    """Estimated width in px of one line at a character height of `size` px."""
    return size * sum(1.0 if unicodedata.east_asian_width(ch) in "WF" else 0.55 for ch in text)


def fitted_size(layout, spec, text):
    """Character height the line is drawn at: smaller than the layer's only when the full layout must shrink it."""
    width = text_width(text, spec["size"])
    if layout == "full" and width > FULL_LINE_WIDTH:
        return spec["size"] * FULL_LINE_WIDTH / width
    return spec["size"]


def get_text(rep, where, value, layer):
    if not isinstance(value, str) or not value.strip():
        rep.err(where, "must be a non-empty string")
        return None
    if "\n" in value or "\r" in value:
        rep.err(where, "must be a single line (no line breaks)")
        return None
    spec = LAYOUTS[rep.layout][layer]
    width = text_width(value, spec["size"])
    if rep.layout == "full":
        if width > FULL_LINE_WIDTH:
            rep.warn(where, "about %d px wide at %d px, more than the %d px a line may take; it will be drawn "
                            "smaller, at about %d px, to fit (split the line to keep the full size)"
                     % (width, spec["size"], FULL_LINE_WIDTH, fitted_size("full", spec, value)))
        return value
    room = W - 2 * SIDE_MARGIN if spec["align"] == "c" else W - spec["x"] - SIDE_MARGIN
    if width > room:
        rep.warn(where, "about %d px wide at %d px, more than the %d px available; it will run off the frame"
                 % (width, spec["size"], room))
    return value


def get_gain(rep, where, obj):
    gain = obj.get("gain_db", 0)
    if not is_number(gain):
        rep.err(where + ".gain_db", "must be a number of dB, got %s" % json.dumps(gain, ensure_ascii=False))
        return 0.0
    return float(gain)


def get_media(rep, media, base, where, value, kind):
    """Resolve a path and make sure it has a video / audio stream. -> (path, info) or (None, None)."""
    if not isinstance(value, str) or not value.strip():
        rep.err(where, "must be a file path")
        return None, None
    path = os.path.normpath(os.path.join(base, os.path.expanduser(value)))
    if not os.path.isfile(path):
        rep.err(where, "file not found: %s" % path)
        return None, None
    info = media.probe(path)
    if not info or not info[kind]:
        rep.err(where, "no %s stream that ffprobe can read in %s" % (kind, path))
        return None, None
    return path, info


def in_range(rep, where, win, rng):
    """Report a window that leaves the clip's shown range; half a frame of slack."""
    slack = 0.5 / FPS
    if rng and (win[0] < rng[0] - slack or win[1] > rng[1] + slack):
        rep.err(where, "[%g, %g] is outside the part of the clip that is shown, [%g, %g] "
                       "(times count from the start of the clip file)" % (win[0], win[1], rng[0], rng[1]))
        return False
    return True


def get_timed(rep, where, value, rng, layer, extra=(), same_place=None):
    """A list of {"t": [start, end], "text": ..} that must not overlap. -> list of dicts.

    same_place(entry, entry) -> bool narrows that: only two lines it says share a place may not overlap."""
    if not isinstance(value, list):
        rep.err(where, "must be a list of {\"t\": [start, end], \"text\": ..}")
        return []
    out = []
    for n, entry in enumerate(value):
        here = "%s[%d]" % (where, n)
        if not check_keys(rep, entry, here, ("t", "text") + tuple(k for k, req in extra if req),
                          tuple(k for k, req in extra if not req)):
            continue
        win = get_window(rep, here + ".t", entry["t"]) if "t" in entry else None
        text = get_text(rep, here + ".text", entry["text"], layer) if "text" in entry else None
        if win and not in_range(rep, here + ".t", win, rng):
            win = None
        if win and text is not None:
            out.append({"n": n, "a": win[0], "b": win[1], "text": text, "entry": entry})
    ordered = sorted(out, key=lambda e: e["a"])
    for i, cur in enumerate(ordered):
        for prev in ordered[:i] if same_place else ordered[max(0, i - 1):i]:
            if cur["a"] < prev["b"] - 0.5 / FPS and (same_place is None or same_place(prev["entry"], cur["entry"])):
                rep.err("%s[%d].t" % (where, cur["n"]), "[%g, %g] overlaps %s[%d] [%g, %g]; %s"
                        % (cur["a"], cur["b"], where, prev["n"], prev["a"], prev["b"],
                           "the two lines would be drawn over each other" if same_place
                           else "this layer shows one line at a time"))
    return ordered


def parse_clip(rep, media, base, where, item):
    check_keys(rep, item, where, ("file", "scoreboard"), ("trim", "gain_db", "bar", "inpic", "sfx", "mute"))
    path, info = get_media(rep, media, base, where + ".file", item.get("file"), "video") \
        if "file" in item else (None, None)
    length = info["duration"] if info else None
    if info and not length:
        rep.err(where + ".file", "ffprobe reports no duration for %s" % path)

    rng = (0.0, length) if length else None
    if "trim" in item:
        rng = get_window(rep, where + ".trim", item["trim"])
        if rng and length and rng[1] > length + 1.0 / FPS:
            rep.err(where + ".trim", "end %g is past the end of the file (%.3f s)" % (rng[1], length))
            rng = None
    frames = to_frames(rng[1] - rng[0]) if rng else 0
    if rng and frames < 1:
        rep.err(where + ".trim", "shorter than one frame")
        rng = None

    def local(seconds):                         # file time -> frame within the item
        return min(max(to_frames(seconds - rng[0]), 0), frames) if rng else 0

    def spans(entries, name):
        out = []
        for e in entries:
            f0, f1 = local(e["a"]), local(e["b"])
            if rng and f1 <= f0:
                rep.err("%s.%s[%d].t" % (where, name, e["n"]), "shorter than one frame")
            out.append((f0, f1, e))
        return out

    clip = {"kind": "clip", "file": path, "src": rng, "frames": frames, "gain_db": get_gain(rep, where, item),
            "has_audio": bool(info and info["audio"]), "score": [], "bar": [], "inpic": [], "env": [], "sfx": []}

    board = item.get("scoreboard", "")
    if isinstance(board, str):
        if board.strip() and get_text(rep, where + ".scoreboard", board, "score") is not None:
            clip["score"] = [(0, frames, board)]
    elif not isinstance(board, list):
        rep.err(where + ".scoreboard", "must be a string or a list of {\"t\": [start, end], \"text\": ..}")
    else:
        entries = get_timed(rep, where + ".scoreboard", board, rng, "score")
        clip["score"] = [(f0, f1, e["text"]) for f0, f1, e in spans(entries, "scoreboard")]
        if rng and len(entries) == len(board) and sum(f1 - f0 for f0, f1, _ in clip["score"]) < frames:
            rep.warn(where + ".scoreboard", "does not cover the whole clip; no scoreboard is shown in the gaps")
    clip["last_score"] = clip["score"][-1][2] if clip["score"] else ""

    bars = spans(get_timed(rep, where + ".bar", item.get("bar", []), rng, "bar"), "bar")
    clip["bar"] = [(f0, f1, e["text"]) for f0, f1, e in bars]

    full = rep.layout == "full"                 # only the full layout knows "y" and "strip"

    def height(entry):                          # where a full-layout in-picture line is drawn
        own = entry.get("y")
        return own if is_number(own) else FULL_LAYERS["bar" if entry.get("strip") is True else "inpic"]["mid"]

    def collide(one, other):                    # a super and a narration strip may be up together, apart
        return abs(height(one) - height(other)) < FULL_MIN_GAP

    for f0, f1, e in spans(get_timed(rep, where + ".inpic", item.get("inpic", []), rng, "inpic",
                                     extra=(("color", True), ("duck", False))
                                     + ((("y", False), ("strip", False)) if full else ()),
                                     same_place=collide if full else None),
                           "inpic"):
        here = "%s.inpic[%d]" % (where, e["n"])
        colour, duck = e["entry"].get("color"), e["entry"].get("duck", False)
        if "color" in e["entry"] and not (isinstance(colour, str) and colour in ACCENTS):
            rep.err(here + ".color", "unknown colour %s (use \"green\", \"red\" or \"white\")"
                    % json.dumps(colour, ensure_ascii=False))
        if not isinstance(duck, bool):
            rep.err(here + ".duck", "must be true or false")
        y, strip = None, False
        if full:
            strip = e["entry"].get("strip", False)
            if not isinstance(strip, bool):
                rep.err(here + ".strip", "must be true or false")
                strip = False
            bar_y = FULL_LAYERS["bar"]["mid"]
            y = e["entry"].get("y", bar_y if strip else FULL_LAYERS["inpic"]["mid"])
            if not is_number(y) or not FULL_Y_RANGE[0] <= y <= FULL_Y_RANGE[1]:
                rep.err(here + ".y", "must be a number from %d to %d (the vertical centre of the line, in pixels), got %s"
                        % (FULL_Y_RANGE[0], FULL_Y_RANGE[1], json.dumps(y, ensure_ascii=False)))
                y = None
            for b0, b1, b in bars if y is not None else ():
                if f0 < b1 and b0 < f1 and abs(y - bar_y) < FULL_MIN_GAP:
                    rep.err(here, "narration %s (t [%g, %g], y %g) and subtitle %s.bar[%d] %s (t [%g, %g], y %d) are on "
                                  "screen at the same time with their centres %g px apart; they need %d px or more. "
                                  "Change this line's \"y\" or its time"
                            % (json.dumps(e["text"], ensure_ascii=False), e["a"], e["b"], y, where, b["n"],
                               json.dumps(b["text"], ensure_ascii=False), b["a"], b["b"], bar_y, abs(y - bar_y),
                               FULL_MIN_GAP))
        clip["inpic"].append((f0, f1, e["text"], colour, y, strip))
        if duck is True and rng:
            clip["env"].append((e["a"] - rng[0], e["b"] - rng[0], 1 - 10 ** (DUCK_DB / 20.0), DUCK_FADE))

    mutes = item.get("mute", [])
    if not isinstance(mutes, list):
        rep.err(where + ".mute", "must be a list of [start, end] windows")
        mutes = []
    for n, value in enumerate(mutes):
        here = "%s.mute[%d]" % (where, n)
        win = get_window(rep, here, value)
        if win and in_range(rep, here, win, rng) and rng:
            clip["env"].append((win[0] - rng[0], win[1] - rng[0], 1.0, MUTE_FADE))

    effects = item.get("sfx", [])
    if not isinstance(effects, list):
        rep.err(where + ".sfx", "must be a list of {\"t\": seconds, \"file\": .., \"gain_db\": ..}")
        effects = []
    for n, entry in enumerate(effects):
        here = "%s.sfx[%d]" % (where, n)
        if not check_keys(rep, entry, here, ("t", "file"), ("gain_db",)):
            continue
        sfx_path = get_media(rep, media, base, here + ".file", entry["file"], "audio")[0] if "file" in entry else None
        at, gain = entry.get("t"), get_gain(rep, here, entry)
        if "t" in entry and not is_number(at):
            rep.err(here + ".t", "must be a time in seconds, got %s" % json.dumps(at, ensure_ascii=False))
        elif "t" in entry and rng and not (rng[0] - 0.5 / FPS <= at < rng[1]):
            rep.err(here + ".t", "%g is outside the part of the clip that is shown, [%g, %g]" % (at, rng[0], rng[1]))
        elif "t" in entry and rng and sfx_path:
            clip["sfx"].append((max(at - rng[0], 0.0), sfx_path, gain))
    return clip


def parse_flash(rep, media, base, where, item):
    check_keys(rep, item, where, ("flash",), ("each", "sfx", "scoreboard"))
    flash = {"kind": "flash", "stills": [], "sfx": [], "score_override": None}

    each = item.get("each", FLASH_EACH)
    if not is_number(each) or each <= 0:
        rep.err(where + ".each", "must be a positive number of seconds, got %s" % json.dumps(each, ensure_ascii=False))
        each = FLASH_EACH
    flash["each"] = max(to_frames(each), 1)
    if abs(each * FPS - flash["each"]) > 1e-6:
        rep.warn(where + ".each", "%g s is not a whole number of frames at %d fps; using %d frames (%.3f s)"
                 % (each, FPS, flash["each"], flash["each"] / float(FPS)))

    stills = item.get("flash")
    if not isinstance(stills, list) or not stills:
        rep.err(where + ".flash", "must be a non-empty list of {\"file\": .., \"t\": seconds}")
        stills = []
    for n, entry in enumerate(stills):
        here = "%s.flash[%d]" % (where, n)
        if not check_keys(rep, entry, here, ("file",), ("t",)):
            continue
        path, info = get_media(rep, media, base, here + ".file", entry["file"], "video") \
            if "file" in entry else (None, None)
        at = entry.get("t", 0)
        if not is_number(at) or at < 0:
            rep.err(here + ".t", "must be a time in seconds, 0 or more, got %s" % json.dumps(at, ensure_ascii=False))
        elif info and at > 0 and at > (info["duration"] or 0):
            rep.err(here + ".t", "%g is past the end of the file (%.3f s)" % (at, info["duration"] or 0))
        elif info:
            # never seek into the last frame's tail, where the decoder would return nothing
            last = (info["duration"] or 0) - 1.5 / (info["fps"] or FPS)
            flash["stills"].append((path, max(min(float(at), last), 0.0)))
    flash["frames"] = flash["each"] * len(flash["stills"])

    if "sfx" in item:
        here, entry = where + ".sfx", item["sfx"]
        if check_keys(rep, entry, here, ("file",), ("gain_db", "t")):
            sfx_path = get_media(rep, media, base, here + ".file", entry["file"], "audio")[0] if "file" in entry else None
            at, gain = entry.get("t", 0), get_gain(rep, here, entry)
            if not is_number(at) or at < 0:
                rep.err(here + ".t", "must be a time in seconds from the start of the recap, 0 or more")
            elif sfx_path:
                flash["sfx"].append((float(at), sfx_path, gain))
    if "scoreboard" in item:
        board = item["scoreboard"]
        if not isinstance(board, str):
            rep.err(where + ".scoreboard", "must be a string here (leave it out to carry the previous one over)")
        elif not board.strip() or get_text(rep, where + ".scoreboard", board, "score") is not None:
            flash["score_override"] = board
    return flash


def load_cues(cue_path, media, output_override):
    """Read and validate the cue file. -> (episode, report)."""
    try:
        with open(cue_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise Fail("cannot read cue file: %s" % exc)
    except ValueError as exc:
        raise Fail("%s is not valid JSON: %s" % (cue_path, exc))

    rep, base = Report(), os.path.dirname(os.path.abspath(cue_path))
    episode = {"premise": [], "notice": "", "items": [], "output": None, "layout": "boxed", "loudness": None,
               "premise_seconds": None, "scoreboard_seconds": None}
    if not check_keys(rep, data, "", ("premise", "notice", "items"),
                      ("output", "layout", "loudness_lufs", "premise_seconds", "scoreboard_seconds")):
        return episode, rep

    layout = data.get("layout", "boxed")        # first: every text check below depends on it
    if not (isinstance(layout, str) and layout in LAYOUTS):
        rep.err("layout", "unknown layout %s (use \"boxed\" or \"full\")" % json.dumps(layout, ensure_ascii=False))
        return episode, rep
    episode["layout"] = rep.layout = layout
    if "loudness_lufs" in data:
        target = data["loudness_lufs"]
        if not is_number(target) or not -70 <= target <= 0:
            rep.err("loudness_lufs", "must be a loudness in LUFS, a number from -70 to 0 such as -15, got %s"
                    % json.dumps(target, ensure_ascii=False))
        else:
            episode["loudness"] = float(target)

    for key in ("premise_seconds", "scoreboard_seconds"):
        if key in data:
            if not is_number(data[key]) or data[key] <= 0:
                rep.err(key, "must be a number of seconds above 0, got %s" % json.dumps(data[key], ensure_ascii=False))
            else:
                episode[key] = float(data[key])

    premise = data.get("premise")
    if "premise" in data and not (isinstance(premise, list) and 1 <= len(premise) <= 2):
        rep.err("premise", "must be a list of 1 or 2 strings")
    elif "premise" in data:
        lines = [get_text(rep, "premise[%d]" % n, line, "premise") for n, line in enumerate(premise)]
        episode["premise"] = [line for line in lines if line is not None]
    if "notice" in data:
        episode["notice"] = get_text(rep, "notice", data["notice"], "notice") or ""

    if output_override:
        episode["output"] = os.path.abspath(output_override)
    elif isinstance(data.get("output"), str) and data["output"].strip():
        episode["output"] = os.path.normpath(os.path.join(base, os.path.expanduser(data["output"])))
    else:
        rep.err("output", "missing: give an output path here or with -o")

    items = data.get("items")
    if "items" in data and (not isinstance(items, list) or not items):
        rep.err("items", "must be a non-empty list of clips and flash recaps")
        items = []
    carried = None                              # scoreboard text handed on to a flash recap
    for n, item in enumerate(items or []):
        where = "items[%d]" % n
        if not isinstance(item, dict):
            rep.err(where, "must be an object")
        elif ("file" in item) == ("flash" in item):
            rep.err(where, "must have either \"file\" (a clip) or \"flash\" (a recap of stills); it has %s"
                    % ("both" if "file" in item else "neither"))
        elif "file" in item:
            clip = parse_clip(rep, media, base, where, item)
            carried = clip["last_score"]
            episode["items"].append(clip)
        else:
            flash = parse_flash(rep, media, base, where, item)
            if flash["score_override"] is not None:
                carried = flash["score_override"]
            elif carried is None:
                rep.err(where + ".scoreboard", "no earlier clip to carry a scoreboard over from; "
                                               "give this recap its own \"scoreboard\" string")
            flash["score"] = [(0, flash["frames"], carried)] if carried else []
            episode["items"].append(flash)

    offset = 0
    for item in episode["items"]:
        item["offset"] = offset
        offset += item["frames"]
    episode["frames"] = offset
    return episode, rep


# --------------------------------------------------------------------------- text (ASS)

def ass_time(frame):
    """Half a frame early, so each change falls safely between two frame times."""
    cs = max(0, int(round((frame - 0.5) * 100.0 / FPS)))
    return "%d:%02d:%02d.%02d" % (cs // 360000, cs // 6000 % 60, cs // 100 % 60, cs % 100)


def ass_escape(text):
    """Print the text as given: stop libass reading \\N, \\h or {...} as codes."""
    return text.replace("\\", "\\⁠").replace("{", "\\{").replace("}", "\\}")


def ass_colour(rrggbb):
    return "&H00%s%s%s" % (rrggbb[4:6], rrggbb[2:4], rrggbb[0:2])


def font_size(spec, size=None):
    """ASS Fontsize that draws this layer's characters `size` px high (default: the layer's own size)."""
    return (size or spec["size"]) / FONT_METRICS.get(spec["font"], DEFAULT_METRICS)["em"]


def collect_events(episode):
    """-> [(layer, style, line_no, start_frame, end_frame, text, y, strip)] on the episode timeline.

    y is the vertical centre a full-layout "inpic" line is drawn at, None everywhere else; strip says
    the line sits on a black strip (full layout: every subtitle, and narration marked "strip")."""
    total, events, board = episode["frames"], [], []
    full = episode["layout"] == "full"
    if episode["notice"]:
        events.append(("notice", "Notice", 0, 0, total, episode["notice"], None, False))
    hold = episode.get("premise_seconds")
    premise_end = total if hold is None else min(total, to_frames(hold))
    for n, line in enumerate(episode["premise"]):
        events.append(("premise", "Premise", n, 0, premise_end, line, None, False))
    for item in episode["items"]:
        off = item["offset"]
        for f0, f1, text in item["score"]:
            if board and board[-1][2] == text and board[-1][1] == off + f0:
                board[-1] = (board[-1][0], off + f1, text)      # same line carries on: one event
            else:
                board.append((off + f0, off + f1, text))
        for f0, f1, text in item.get("bar", []):
            events.append(("bar", "Bar", 0, off + f0, off + f1, text, None, full))
        for f0, f1, text, colour, y, strip in item.get("inpic", []):
            if strip:                           # narration in the subtitle look, at its own height
                events.append(("bar", "Bar", 0, off + f0, off + f1, text, y, True))
            else:
                events.append(("inpic", "Inpic" + str(colour).capitalize(), 0, off + f0, off + f1, text, y, False))
    brief = episode.get("scoreboard_seconds")
    alone = LAYOUTS[episode["layout"]]["score"].get("top_alone")
    for f0, f1, text in board:
        if brief is not None:                   # a date line comes up when it changes, then leaves
            f1 = min(f1, f0 + to_frames(hold if (f0 == 0 and hold is not None) else brief))
        events.append(("score", "Score", 0, f0, f1, text, alone if f0 >= premise_end else None, False))
    return [e for e in events if e[4] > e[3]]


def write_ass(path, events, layout):
    layers, styles = LAYOUTS[layout], []
    for layer, name, colour in [("notice", "Notice", None), ("premise", "Premise", None),
                                ("score", "Score", None), ("bar", "Bar", None)] \
            + [("inpic", "Inpic" + key.capitalize(), value) for key, value in ACCENTS.items()]:
        spec = layers[layer]
        # BackColour is the shadow colour: black at half opacity, so a shadow reads as soft.
        styles.append("Style: %s,%s,%.2f,%s,%s,%s,&H80000000,0,0,0,0,100,100,0,0,1,%.1f,%.1f,%d,0,0,0,1"
                      % (name, spec["font"], font_size(spec), ass_colour(colour or spec["colour"]),
                         ass_colour(colour or spec["colour"]), ass_colour(OUTLINE_COLOUR), spec["outline"],
                         spec.get("shadow", 0), {"c": 8, "r": 9}.get(spec["align"], 7)))
    lines = []
    bands = {}                                  # strip centre -> merged [start_frame, end_frame] runs
    for e in sorted((e for e in events if e[7]), key=lambda e: e[3]):
        mid = layers[e[0]]["mid"] if e[6] is None else e[6]
        runs = bands.setdefault(mid, [])
        if runs and e[3] - runs[-1][1] <= STRIP_BRIDGE * FPS:
            runs[-1][1] = max(runs[-1][1], e[4])
        else:
            runs.append([e[3], e[4]])
    for mid, runs in sorted(bands.items()):
        y0, y1 = round(mid - STRIP_H / 2.0), round(mid + STRIP_H / 2.0)
        for f0, f1 in runs:
            lines.append("Dialogue: 0,%s,%s,Bar,,0,0,0,,{\\an7\\pos(0,0)\\bord0\\shad0\\1c&H000000&\\1a&H00&\\p1}"
                         "m 0 %d l %d %d %d %d 0 %d{\\p0}" % (ass_time(f0), ass_time(f1), y0, W, y0, W, y1, y1))
    for layer, style, line_no, f0, f1, text, y, strip in sorted(events, key=lambda e: (e[3], layers[e[0]]["z"], e[2])):
        spec = layers[layer]
        size = fitted_size(layout, spec, text)  # the layer's size, unless the full layout has to shrink the line
        if "mid" in spec:
            top = (spec["mid"] if y is None else y) - size / 2.0
        else:
            top = (spec["top"] if y is None else y) + line_no * spec.get("pitch", 0)
        pos_y = top - FONT_METRICS.get(spec["font"], DEFAULT_METRICS)["top"] * font_size(spec, size)
        shrink = "" if size == spec["size"] else "\\fs%.2f" % font_size(spec, size)
        if strip:
            shrink += "\\bord0\\shad0"         # on the strip the line is plain white, no outline
        lines.append("Dialogue: %d,%s,%s,%s,,0,0,0,,{\\pos(%d,%d)%s}%s"
                     % (spec["z"], ass_time(f0), ass_time(f1), style, spec["x"], round(pos_y), shrink,
                        ass_escape(text)))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\n"
                     "ScaledBorderAndShadow: yes\nYCbCr Matrix: None\n\n[V4+ Styles]\n"
                     "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                     "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
                     "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n%s\n\n[Events]\n"
                     "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n%s\n"
                     % (W, H, "\n".join(styles), "\n".join(lines)))


def check_fonts(ffmpeg, workdir, events, layout):
    """Draw every line once and read libass's log. -> (fonts used, warnings, errors)."""
    layers = LAYOUTS[layout]
    once = sorted(set((layer, style, line_no, 0, 1, text, None, False)
                      for layer, style, line_no, _, _, text, _, _ in events))
    write_ass(os.path.join(workdir, "fontcheck.ass"), once, layout)
    run = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "verbose", "-f", "lavfi",
         "-i", "color=c=black:s=%dx%d:r=%d:d=0.1" % (W, H, FPS),
         "-vf", "ass=f=fontcheck.ass", "-frames:v", "1", "-f", "null", "-"],
        capture_output=True, text=True, cwd=workdir)
    if run.returncode != 0:
        raise Fail("font check failed:\n" + run.stderr[-2000:])
    used, warnings, errors = {}, [], []
    wanted = set(spec["font"] for spec in layers.values())

    def squash(name):
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def char(code):
        return "'%s' (U+%04X)" % (chr(int(code, 16)), int(code, 16))

    for font, _, _, path, _, face in re.findall(r"fontselect: \((.+?), (\d+), (\d+)\) -> (.+), (-?\d+), (.+)", run.stderr):
        used.setdefault(font, "%s (%s)" % (face.strip(), os.path.basename(path)))
        if font in wanted and squash(font) not in squash(face):
            warnings.append("font \"%s\" was not found; libass substituted %s" % (font, face.strip()))
    for font in sorted(wanted - set(used)):
        if any(layers[e[0]]["font"] == font for e in events):
            warnings.append("font \"%s\": libass did not report which face it used" % font)
    missing = set(re.findall(r"failed to find any fallback with glyph 0x([0-9A-Fa-f]+) for font: \((.+?),", run.stderr))
    for code, font in sorted(missing):
        errors.append("font \"%s\" has no usable glyph for %s; it would be drawn as an empty box" % (font, char(code)))
    for code, font in sorted(set(re.findall(r"Glyph 0x([0-9A-Fa-f]+) not found, selecting one more font for \((.+?),",
                                            run.stderr)) - missing):
        warnings.append("font \"%s\" lacks %s; libass took it from another font" % (font, char(code)))
    return used, sorted(set(warnings)), errors


# --------------------------------------------------------------------------- render

def num(value):
    return ("%.5f" % value).rstrip("0").rstrip(".")


def gain_filter(item):
    """The clip's own level: fixed gain, with mute and duck windows faded inside themselves."""
    base = 10 ** (item["gain_db"] / 20.0)
    if not item["env"]:
        return "" if item["gain_db"] == 0 else ",volume=%s" % num(base)
    terms = [num(base)]
    for start, end, depth, fade in item["env"]:
        fade = min(fade, (end - start) / 2.0)
        terms.append("(1-%s*clip((t-%s)/%s,0,1)*clip((%s-t)/%s,0,1))"
                     % (num(depth), num(start), num(fade), num(end), num(fade)))
    expr = "*".join(terms)
    return ",aeval=exprs='val(0)*%s|val(1)*%s':c=same" % (expr, expr)


def build_command(ffmpeg, episode, out_path, preset, crf, lossless_audio=False):
    """The one ffmpeg call that renders the episode. lossless_audio: write the mix as PCM in MOV,
    for the loudness pass to encode once, instead of AAC in MP4."""
    inputs, graph, segments, effects = [], [], [], []
    full = episode["layout"] == "full"
    pic_w, pic_h = (W, H) if full else (PIC_W, PIC_H)       # scale to cover, crop the overflow evenly
    fit = ("scale=w='max(2,trunc(iw*sar/2)*2)':h=ih,setsar=1,"
           "scale=%d:%d:force_original_aspect_ratio=increase:flags=lanczos,crop=%d:%d,setsar=1,format=yuv420p"
           % (pic_w, pic_h, pic_w, pic_h))
    audio_fmt = "aformat=sample_fmts=fltp:channel_layouts=stereo"

    def add_input(path, seek=0.0, length=None):
        args = []
        if seek > 0:
            args += ["-ss", num(seek)]
        if length is not None:
            args += ["-t", num(length)]
        inputs.append(args + ["-i", path])
        return len(inputs) - 1

    def silence(frames, label):
        graph.append("anullsrc=r=%d:cl=stereo,%s,atrim=end_sample=%d[%s]" % (SR, audio_fmt, frames * SPF, label))

    for n, item in enumerate(episode["items"]):
        if item["kind"] == "clip":
            frames, samples = item["frames"], item["frames"] * SPF
            src = add_input(item["file"], item["src"][0], item["src"][1] - item["src"][0] + 0.5)
            # exactly `frames` frames: the last one is held if the file runs a little short
            graph.append("[%d:v:0]fps=%d:start_time=0,tpad=stop_mode=clone:stop=-1,trim=end_frame=%d,"
                         "setpts=PTS-STARTPTS,%s[v%d]" % (src, FPS, frames, fit, n))
            if item["has_audio"]:
                graph.append("[%d:a:0]aresample=%d:async=1:first_pts=0,%s,apad=whole_len=%d,atrim=end_sample=%d,"
                             "asetpts=N/SR/TB%s[a%d]" % (src, SR, audio_fmt, samples, samples, gain_filter(item), n))
            else:
                silence(frames, "a%d" % n)
            segments.append("[v%d][a%d]" % (n, n))
        else:
            for k, (path, at) in enumerate(item["stills"]):
                src = add_input(path, at, 1.0)
                graph.append("[%d:v:0]fps=%d,trim=end_frame=1,tpad=stop_mode=clone:stop=%d,setpts=PTS-STARTPTS,%s[v%d_%d]"
                             % (src, FPS, item["each"] - 1, fit, n, k))
                silence(item["each"], "a%d_%d" % (n, k))
                segments.append("[v%d_%d][a%d_%d]" % (n, k, n, k))
        for at, path, gain_db in item["sfx"]:
            src = add_input(path)
            delay = item["offset"] * SPF + int(round(at * SR))
            label = "s%d" % len(effects)
            graph.append("[%d:a:0]aresample=%d,%s,volume=%s%s[%s]"
                         % (src, SR, audio_fmt, num(10 ** (gain_db / 20.0)),
                            ",adelay=delays=%dS:all=1" % delay if delay else "", label))
            effects.append("[%s]" % label)

    total = episode["frames"]
    graph.append("%sconcat=n=%d:v=1:a=1[vcat][acat]" % ("".join(segments), len(segments)))
    graph.append("[vcat]fps=%d,%sass=f=cues.ass,trim=end_frame=%d[vout]"
                 % (FPS, "" if full else "pad=%d:%d:0:%d:color=black," % (W, H, PIC_TOP), total))
    mix = "[acat]%samix=inputs=%d:duration=first:dropout_transition=0:normalize=0," \
          % ("".join(effects), len(effects) + 1) if effects else "[acat]"
    graph.append("%salimiter=limit=%s:level=false:latency=true,atrim=end_sample=%d[aout]" % (mix, num(LIMIT), total * SPF))

    command = [ffmpeg, "-hide_banner", "-nostdin", "-y"]
    for args in inputs:
        command += args
    command += ["-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(FPS)]
    if lossless_audio:
        return command + ["-c:a", "pcm_f32le", "-ar", str(SR), "-ac", "2", "-f", "mov", out_path]
    return command + AUDIO_OUT + [out_path]


def measure_loudness(ffmpeg, path):
    """EBU R128 over the whole first audio stream. -> (integrated loudness in LUFS, true peak in dBTP)."""
    run = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-nostats", "-i", path, "-map", "0:a:0",
                          "-af", "ebur128=peak=true:framelog=verbose", "-f", "null", "-"],
                         capture_output=True, text=True)
    summary = run.stderr.rpartition("Summary:")[2]
    loud, peak = re.search(r"\bI:\s*(\S+) LUFS", summary), re.search(r"\bPeak:\s*(\S+) dBFS", summary)
    try:
        if run.returncode != 0 or not (loud and peak):
            raise ValueError
        return float(loud.group(1)), float(peak.group(1))
    except ValueError:
        raise Fail("could not measure the loudness of %s:\n%s" % (path, run.stderr[-1500:]))


def finish_loudness(ffmpeg, episode, mix_path, out_path, verbose):
    """Bring the rendered mix to the cue file's "loudness_lufs": measure, one fixed gain, a limiter.

    The picture is copied as it is; only the sound is encoded, once. Prints the before and after."""
    target = episode["loudness"]
    before, before_peak = measure_loudness(ffmpeg, mix_path)
    measurable = math.isfinite(before) and before > -69.0   # ebur128 reports -70 for silence
    gain = target - before if measurable else 0.0
    if not measurable:
        print("warning: the mix is silent or too short for a loudness reading; no gain applied", file=sys.stderr)
    command = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "warning" if verbose else "error",
               "-i", mix_path, "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
               "-af", "volume=%sdB,alimiter=limit=%s:level=false:latency=true,atrim=end_sample=%d"
                      % (num(gain), num(10 ** (LOUDNESS_CEILING_DB / 20.0)), episode["frames"] * SPF)]
    command += AUDIO_OUT + [out_path]
    if verbose:
        print(" ".join("'%s'" % a if re.search(r"[^\w./:=+-]", a) else a for a in command))
    if subprocess.run(command).returncode != 0:
        raise Fail("ffmpeg failed in the loudness pass (its message is above); nothing written to %s" % out_path)
    after, after_peak = measure_loudness(ffmpeg, out_path)
    print("Loudness: mix %.1f LUFS, true peak %.1f dBTP; gain %+.1f dB, limiter at %g dBFS, picture copied"
          % (before, before_peak, gain, LOUDNESS_CEILING_DB))
    print("          final %.1f LUFS, true peak %.1f dBTP (target %g LUFS)" % (after, after_peak, target))
    if measurable and abs(after - target) > 1.0:
        print("warning: the final loudness is %.1f LU from the target; one fixed gain cannot bring it closer "
              "because the limiter is holding the peaks back" % abs(after - target), file=sys.stderr)
    if after_peak > TRUE_PEAK_MAX_DB:
        print("warning: the final true peak is %.1f dBTP, above %g dBTP" % (after_peak, TRUE_PEAK_MAX_DB),
              file=sys.stderr)


def print_setup(episode):
    """The layout in use and, when there is one, the loudness target."""
    if episode["layout"] == "full":
        print("Layout: full (the picture fills %dx%d; text is drawn over it)" % (W, H))
    else:
        print("Layout: boxed (%dx%d picture at y=%d on a black %dx%d canvas)" % (PIC_W, PIC_H, PIC_TOP, W, H))
    if episode["loudness"] is not None:
        print("Loudness: the finished mix will be brought to %g LUFS (limiter at %g dBFS)"
              % (episode["loudness"], LOUDNESS_CEILING_DB))


def print_timeline(episode):
    print("Timeline (%d fps, %dx%d):" % (FPS, W, H))
    for n, item in enumerate(episode["items"]):
        if item["kind"] == "clip":
            what = "clip   %s  [%s-%s]" % (os.path.basename(item["file"]), num(item["src"][0]), num(item["src"][1]))
        else:
            what = "flash  %d stills x %d frames" % (len(item["stills"]), item["each"])
        print("  items[%d]  starts %7.3f  lasts %6.3f s (%4d frames)  %s"
              % (n, item["offset"] / float(FPS), item["frames"] / float(FPS), item["frames"], what))
    print("  total %.3f s (%d frames)" % (episode["frames"] / float(FPS), episode["frames"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assemble one episode from a JSON cue file (see the top of this file).")
    parser.add_argument("cues", help="JSON cue file")
    parser.add_argument("-o", "--output", help="output .mp4 (default: \"output\" in the cue file)")
    parser.add_argument("--check", action="store_true", help="validate, check fonts and print the timeline; no render")
    parser.add_argument("--ffmpeg", help="ffmpeg binary to use (must have libass)")
    parser.add_argument("--preset", default="medium", help="x264 preset (default medium)")
    parser.add_argument("--crf", type=int, default=18, help="x264 quality, lower is better (default 18)")
    parser.add_argument("--keep-work", action="store_true", help="keep the work folder with the generated .ass file")
    parser.add_argument("-v", "--verbose", action="store_true", help="show the ffmpeg command and its progress")
    args = parser.parse_args(argv)

    workdir = None
    try:
        ffmpeg, ffprobe = find_ffmpeg(args.ffmpeg)
        media = Media(ffprobe)
        episode, rep = load_cues(args.cues, media, args.output)
        for message in rep.warnings:
            print("warning: " + message, file=sys.stderr)
        if rep.errors:
            print("%s: %d problem(s) in the cue file, nothing rendered:" % (args.cues, len(rep.errors)), file=sys.stderr)
            for message in rep.errors:
                print("  " + message, file=sys.stderr)
            return 2

        print("ffmpeg: %s" % ffmpeg)
        print_setup(episode)
        print_timeline(episode)
        workdir = tempfile.mkdtemp(prefix="compose_episode_")
        events = collect_events(episode)
        write_ass(os.path.join(workdir, "cues.ass"), events, episode["layout"])
        used, warnings, errors = check_fonts(ffmpeg, workdir, events, episode["layout"])
        print("Fonts: " + "; ".join("%s -> %s" % pair for pair in sorted(used.items())))
        for message in warnings:
            print("warning: " + message, file=sys.stderr)
        if errors:
            raise Fail("text would not render correctly, nothing rendered:\n  " + "\n  ".join(errors))
        if args.check:
            print("Check passed; no render (--check).")
            return 0

        out_path = episode["output"]
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        part = out_path + ".part"
        # with a loudness target the render goes to a lossless-audio file first, and the loudness pass writes `part`
        mix = part if episode["loudness"] is None else os.path.join(workdir, "mix.mov")
        command = build_command(ffmpeg, episode, mix, args.preset, args.crf, lossless_audio=mix != part)
        command[2:2] = ["-loglevel", "warning", "-stats"] if args.verbose else ["-loglevel", "error"]
        if args.verbose:
            print(" ".join("'%s'" % a if re.search(r"[^\w./:=+-]", a) else a for a in command))
        started = time.time()
        try:
            if subprocess.run(command, cwd=workdir).returncode != 0:
                raise Fail("ffmpeg failed (its message is above); nothing written to %s" % out_path)
            if mix != part:
                finish_loudness(ffmpeg, episode, mix, part, args.verbose)
        except Fail:
            if os.path.exists(part):
                os.remove(part)
            raise
        finally:
            if mix != part and os.path.exists(mix):
                os.remove(mix)
        os.replace(part, out_path)

        info = Media(ffprobe).probe(out_path) or {}
        video, audio = info.get("video") or {}, info.get("audio") or {}
        print("Wrote %s in %.1f s" % (out_path, time.time() - started))
        print("  video %s %sx%s %s %s fps, %s frames; audio %s %s Hz %s ch; duration %.3f s"
              % (video.get("codec_name"), video.get("width"), video.get("height"), video.get("pix_fmt"),
                 num(info.get("fps") or 0), video.get("nb_frames"), audio.get("codec_name"),
                 audio.get("sample_rate"), audio.get("channels"), info.get("container") or 0))
        if str(video.get("nb_frames")) != str(episode["frames"]) or not audio:
            raise Fail("the file does not match the timeline (%d frames expected, audio required)" % episode["frames"])
        return 0
    except Fail as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    finally:
        if workdir and args.keep_work:
            print("work folder kept: %s" % workdir)
        elif workdir:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
