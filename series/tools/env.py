#!/usr/bin/env python3
"""Where things are on this machine: ffmpeg, the jimeng-drama skill, the sound effects.

Nothing here is specific to one computer. Every lookup can be overridden with a variable:
FFMPEG (path to an ffmpeg built with libass), JIMENG_DRAMA_SKILL (the skill's folder),
FILM_SFX (folder of sound effects), FILM_SERIF / FILM_SANS / FILM_SANS_BOLD (font names).
"""
import os
import shutil
import subprocess

TOOLS = os.path.dirname(os.path.abspath(__file__))
SERIES = os.path.dirname(TOOLS)
_cache = {}


def has_ass(path):
    try:
        out = subprocess.run([path, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(len(p) >= 3 and p[1] == "ass" for p in (line.split() for line in out.splitlines()))


def ffmpeg():
    """An ffmpeg that can draw text (libass). Falls back to any ffmpeg when none has it; the steps
    that draw text (compose, preview, cover) then stop with their own message."""
    if "ffmpeg" not in _cache:
        found = [c for c in (os.environ.get("FFMPEG"), os.path.expanduser("~/.local/bin/ffmpeg"), "/opt/homebrew/bin/ffmpeg",
                             "/usr/local/bin/ffmpeg", shutil.which("ffmpeg")) if c and os.path.isfile(c) and os.access(c, os.X_OK)]
        _cache["ffmpeg"] = next((c for c in found if has_ass(c)), found[0] if found else "ffmpeg")
    return _cache["ffmpeg"]


def ffprobe():
    beside = os.path.join(os.path.dirname(ffmpeg()), "ffprobe")
    return beside if os.path.isfile(beside) else (shutil.which("ffprobe") or "ffprobe")


def skill():
    """The jimeng-drama skill folder (installed with jimeng-novel), or "" when it is not found."""
    for cand in (os.environ.get("JIMENG_DRAMA_SKILL"), "~/.claude/skills/jimeng-drama", "~/.agents/skills/jimeng-drama",
                 os.path.join(os.environ.get("CODEX_HOME", "~/.codex"), "skills", "jimeng-drama")):
        if cand and os.path.isfile(os.path.join(os.path.expanduser(cand), "SKILL.md")):
            return os.path.expanduser(cand)
    return ""


def sfx():
    return os.environ.get("FILM_SFX") or os.path.join(SERIES, "sfx")
