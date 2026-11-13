#!/usr/bin/env python3
"""Set the title on a piece of generated cover art.

    python3 cover_art.py ART.png OUT.jpg --size 1440x1920 --lines "假如你在2001年" "全仓买入英伟达"
                         [--notice "AI 生成 · 虚构剧情"] [--left 132] [--top 112] [--big 168]

Used by `film.py cover`. The art is scaled to cover the canvas. A soft dark veil comes down from the
top edge so the title reads on any picture, and the title sits on it ranged left:

  - the last line is the big one, in Songti SC Black;
  - the lines above it are set smaller and letter-spaced out to exactly the same width, so the
    title is one clean block; a run of digits such as 2001 stays together. Widths are measured
    from the rendered ink, not guessed;
  - warm white, a soft shadow, no outline, no second colour;
  - the notice is small in the bottom right corner.

Both covers of a film are set with the same proportions, so they match.
"""
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env  # noqa: E402

FFMPEG = env.ffmpeg()
SERIF, SANS = os.environ.get("FILM_SERIF", "Songti SC Black"), os.environ.get("FILM_SANS", "Hiragino Sans GB W3")
INK = "E8EEF1"                      # warm white, written BBGGRR for the subtitle renderer
VEIL = "0x081012"                   # the picture's own dark blue-green, not pure black
SMALL = 0.74                        # size of the upper lines against the big one


STYLE = "Style: %s,%s,%d,&H00%s,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1"
HEAD = ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nScaledBorderAndShadow: yes\nYCbCr Matrix: None\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "%s\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n%s\n")


def tracked(line, spacing):
    """The line with letter-spacing after every character except inside a run of digits."""
    if not spacing:
        return line
    out, tight = [], None
    for i, ch in enumerate(line):
        want = ch.isdigit() and i + 1 < len(line) and line[i + 1].isdigit()
        if want != tight:
            out.append("{\\fsp%.1f}" % (0 if want else spacing))
            tight = want
        out.append(ch)
    return "".join(out)


def gaps(line):
    return sum(1 for i in range(len(line) - 1) if not (line[i].isdigit() and line[i + 1].isdigit()))


def ink(line, size, spacing=0.0):
    """Left edge and width of the line's ink when drawn at x=200: measured by rendering it."""
    canvas = (int(size * (len(line) + 4) + spacing * len(line)) + 400, int(size * 2))
    with tempfile.TemporaryDirectory() as work:
        event = "Dialogue: 0,0:00:00.00,0:00:10.00,T,,0,0,0,,{\\an7\\pos(200,%d)}%s" % (size // 3, tracked(line, spacing))
        with open(os.path.join(work, "m.ass"), "w", encoding="utf-8") as handle:
            handle.write(HEAD % (canvas[0], canvas[1], STYLE % ("T", SERIF, size, "FFFFFF"), event))
        log = subprocess.run([FFMPEG, "-hide_banner", "-f", "lavfi", "-i", "color=c=black:s=%dx%d:d=1" % canvas, "-vf",
                              "ass=m.ass,bbox=min_val=40", "-frames:v", "1", "-f", "null", "-"], cwd=work, capture_output=True, text=True).stderr
    m = re.search(r"x1:(\d+) x2:(\d+)", log)
    if not m:
        raise SystemExit("cover_art: could not measure the line %r" % line)
    return int(m.group(1)) - 200, int(m.group(2)) - int(m.group(1)) + 1


def layout(lines, left, top, big):
    """-> [(text with tags, size, x, y)], bottom. Every line's ink starts at `left` and the upper
    lines are tracked out to the ink width of the last one."""
    off_big, measure = ink(lines[-1], big)
    out, y = [], top
    for i, line in enumerate(lines):
        last = i == len(lines) - 1
        size = big if last else int(round(big * SMALL))
        spacing = 0.0
        if not last and gaps(line):
            spacing = max(0.0, (measure - ink(line, size)[1]) / float(gaps(line)))
        off = off_big if last else ink(line, size, spacing)[0]
        out.append((tracked(line, spacing), size, left - off, y))
        y += int(size * (1.12 if last else 1.30))
    return out, y


def render(art, out, size, lines, notice="", left=None, top=None, big=None):
    W, H = size
    unit = min(W, H) / 1440.0
    big = big or int(168 * unit)
    left = left if left is not None else int(132 * unit)
    top = top if top is not None else int(112 * unit)
    rows, bottom = layout(lines, left, top, big)
    veil_h = min(H, int(bottom + 300 * unit))
    events = []
    for text, fs, x, y in rows:
        tags = "\\an7\\fs%d" % fs
        events.append("Dialogue: 0,0:00:00.00,0:00:10.00,T,,0,0,0,,{%s\\pos(%d,%d)\\1c&H000000&\\1a&H50&\\blur%d}%s"
                      % (tags, x, y + int(5 * unit), int(14 * unit), text))
        events.append("Dialogue: 1,0:00:00.00,0:00:10.00,T,,0,0,0,,{%s\\pos(%d,%d)}%s" % (tags, x, y, text))
    if notice:
        nx, ny, ns = W - int(40 * unit), H - int(36 * unit), int(27 * unit)
        events.append("Dialogue: 0,0:00:00.00,0:00:10.00,N,,0,0,0,,{\\an3\\pos(%d,%d)\\fs%d\\1c&H000000&\\1a&H40&\\blur%d}%s" % (nx, ny + 2, ns, int(6 * unit), notice))
        events.append("Dialogue: 1,0:00:00.00,0:00:10.00,N,,0,0,0,,{\\an3\\pos(%d,%d)\\fs%d\\1a&H28&}%s" % (nx, ny, ns, notice))
    ass = HEAD % (W, H, STYLE % ("T", SERIF, big, INK) + "\n" + STYLE % ("N", SANS, 27, "FFFFFF"), "\n".join(events))
    work = os.path.dirname(os.path.abspath(out))
    ass_name = os.path.basename(out) + ".ass"
    with open(os.path.join(work, ass_name), "w", encoding="utf-8") as handle:
        handle.write(ass)
    graph = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase:flags=lanczos,crop=%d:%d,format=rgba[pic];"
             "[1:v]format=rgba[veil];[pic][veil]overlay=0:0,ass=%s,format=yuvj444p"
             % (W, H, W, H, ass_name))
    veil = "gradients=s=%dx%d:c0=%sC8:c1=%s00:x0=0:y0=0:x1=0:y1=%d:d=1" % (W, veil_h, VEIL, VEIL, veil_h)
    rc = subprocess.run([FFMPEG, "-v", "error", "-y", "-i", os.path.abspath(art), "-f", "lavfi", "-i", veil,
                         "-filter_complex", graph, "-frames:v", "1", "-q:v", "2", os.path.basename(out)], cwd=work).returncode
    os.remove(os.path.join(work, ass_name))
    return rc


def main():
    argv = sys.argv[1:]
    if len(argv) < 2 or "--lines" not in argv:
        sys.exit(__doc__)

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    i = argv.index("--lines") + 1
    lines = []
    while i < len(argv) and not argv[i].startswith("--"):
        lines.append(argv[i])
        i += 1
    w, h = (int(v) for v in opt("--size", "1440x1920").split("x"))
    num = lambda name: int(opt(name)) if opt(name) else None    # noqa: E731
    sys.exit(render(argv[0], argv[1], (w, h), lines, opt("--notice", ""), num("--left"), num("--top"), num("--big")))


if __name__ == "__main__":
    main()
