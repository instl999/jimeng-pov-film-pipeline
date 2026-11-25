#!/usr/bin/env python3
"""Offline test of the changes made for long series runs. Uses a stand-in for jimeng-novel; spends nothing.

    python3 tests/test_hardening.py     ends with "all steps hold"

- subtitles stay up until the voice dies away, and short gaps between lines are closed;
- reference pictures are uploaded once, as small JPEGs, and reused by asset id;
- the sample_up finish: only passed takes are upscaled, once; the final cut waits for all of them;
- money figures on screen need a source; time-travel payoffs are flagged as risky;
- an episode's cover prompt carries the series look; the run summary is written.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
sys.path.insert(0, TOOLS)
import env as where  # noqa: E402
FFMPEG = where.ffmpeg()
EXAMPLE = os.path.join(ROOT, "examples", "nvidia-2001")
work = tempfile.mkdtemp(prefix="hardening-")
failures = []


def check(what, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, "" if ok or not detail else "  -> " + str(detail)[-600:]))
    if not ok:
        failures.append(what)


def run(*args, **kw):
    done = subprocess.run([sys.executable, os.path.join(TOOLS, "film.py")] + list(args), capture_output=True, text=True,
                          env=dict(os.environ, JIMENG_SERIES_HOME=os.path.join(work, "home"), PATH=fake + os.pathsep + os.environ["PATH"]))
    return done.returncode, done.stdout + done.stderr


# a stand-in for jimeng-novel: logs every call; uploads answer with an asset id; upscale copies the clip
fake = os.path.join(work, "bin")
os.makedirs(fake)
LOG = os.path.join(work, "calls.log")
with open(os.path.join(fake, "jimeng-novel"), "w") as handle:
    handle.write("""#!/usr/bin/env python3
import os, shutil, sys
a = sys.argv[1:]
open(%r, "a").write(" ".join(a) + "\\n")
if a[:2] == ["resource", "upload"]:
    print('{"status": "ok", "data": {"assetId": "asset%%04d", "type": "image", "status": "ready"}}' %% len(open(%r).readlines()))
elif a[:1] == ["upscale"]:
    shutil.copyfile(a[a.index("--video") + 1], a[a.index("--out") + 1])
    print("超分完成 实扣 6 积分")
else:
    print("ok")
""" % (LOG, LOG))
os.chmod(os.path.join(fake, "jimeng-novel"), os.stat(os.path.join(fake, "jimeng-novel")).st_mode | stat.S_IEXEC)
os.environ["PATH"] = fake + os.pathsep + os.environ["PATH"]


def calls(word):
    return [l for l in open(LOG).read().splitlines() if word in l] if os.path.isfile(LOG) else []


# ------------------------------------------------------------------ 1. when a subtitle leaves
cut = os.path.join(work, "cut")
os.makedirs(os.path.join(cut, "clips"))
os.makedirs(os.path.join(cut, "srt"))
# room sound throughout; a voice 1.0-2.6 s and 3.0-4.0 s; the recogniser ends the lines early, at 2.2 and 3.7
voice = "0.3*sin(2*PI*220*t)*(between(t,1.0,2.6)+between(t,3.0,4.0))+0.004*sin(2*PI*1500*t)"
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=270x480:r=24:d=6", "-f", "lavfi", "-i",
                "aevalsrc='%s':s=16000:d=6" % voice, "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                os.path.join(cut, "clips", "S01.mp4")], check=True)
with open(os.path.join(cut, "srt", "S01.srt"), "w", encoding="utf-8") as handle:
    handle.write("1\n00:00:01,000 --> 00:00:02,200\n第一句\n\n2\n00:00:03,000 --> 00:00:03,700\n第二句\n")
plan = {"cues": "S.cues.json", "output": "out.mp4", "notice": "n", "premise": ["p"], "layout": "full", "clips": "clips", "srt": "srt",
        "sfx": "sfx", "items": [{"clip": "S01", "scoreboard": "d", "bar": ["第一句", "第二句"]}]}


def bar_times(**extra):
    with open(os.path.join(cut, "plan.json"), "w", encoding="utf-8") as handle:
        json.dump(dict(plan, **extra), handle, ensure_ascii=False)
    out = subprocess.run([sys.executable, os.path.join(TOOLS, "make_cues.py"), os.path.join(cut, "plan.json"), "--print"],
                         capture_output=True, text=True)
    return [b["t"] for b in json.loads(out.stdout)["items"][0]["bar"]] if out.returncode == 0 else out.stderr


on, off = bar_times(), bar_times(voice_end=False)
check("a gap under 0.7 s between two lines is closed (the strip does not blink)", isinstance(on, list) and abs(on[0][1] - 2.96) < 0.03, on)
check("the last line stays up until the voice has died away, not where the recogniser ended it",
      isinstance(on, list) and isinstance(off, list) and on[1][1] >= 4.15 and off[1][1] <= 3.96, (on, off))

# ------------------------------------------------------------------ 2-3. uploads once; sample_up
proj = os.path.join(work, "film")
shutil.copytree(EXAMPLE, proj, ignore=shutil.ignore_patterns("out", "stills", "post", "shots"))
os.makedirs(os.path.join(proj, ".jimeng"))
with open(os.path.join(proj, ".jimeng", "config.json"), "w") as handle:
    handle.write("{}")
import film as F  # noqa: E402
f = F.Film(proj)
pic = sorted(p for p in os.listdir(os.path.join(proj, "cast")) if p.endswith((".jpg", ".png")))[0]
first, second = F.ref_source(f, "cast/" + pic), F.ref_source(F.Film(proj), "cast/" + pic)
small = [n for n in os.listdir(os.path.join(proj, ".film", "refs"))]
check("a reference picture is uploaded once and then reused by its asset id",
      first.startswith("resource:asset") and first == second and len(calls("resource upload")) == 1, (first, second, calls("resource")))
check("it goes up as a JPEG of at most 1280 pixels", small and small[0].endswith(".jpg") and
      max(int(x) for x in subprocess.run([where.ffprobe(), "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                                           os.path.join(proj, ".film", "refs", small[0])], capture_output=True, text=True).stdout.strip().split(",")) <= 1280)
check("a video reference still goes with the request", F.ref_source(f, "previs/E01/ref/S01.mp4") == "file:previs/E01/ref/S01.mp4")

d = json.load(open(os.path.join(proj, "film.json"), encoding="utf-8"))
d.update(finish="sample_up", budget=1000)
json.dump(d, open(os.path.join(proj, "film.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
rc, out = run("budget", proj)
check("budget prices the 480p + upscale route", "sample_up" in out and "<- chosen" in out.split("sample_up")[1].splitlines()[0], out)
os.makedirs(os.path.join(proj, "out", "E01"), exist_ok=True)
shutil.copyfile(os.path.join(cut, "clips", "S01.mp4"), os.path.join(proj, "out", "E01", "S01.mp4"))
rc, out = run("approve", proj, "好")
run("review", proj, "S01", "pass")
rc, out = run("upscale", proj)
check("a dry run lists only passed takes and what they cost", "S01" in out and "dry run" in out and "S02" in out.split("not passed yet")[1], out)
rc, out = run("upscale", proj, "--run")
up = os.path.join(proj, "out", "E01", "up", "S01.mp4")
state = json.load(open(os.path.join(proj, ".film", "state.json"), encoding="utf-8"))
check("--run upscales the passed take into out/E01/up/ and books what it cost",
      os.path.isfile(up) and state["shots"]["S01"]["upscaled"]["credits"] == 6 and state["spent"] == 6, out)
rc, out = run("upscale", proj, "--run")
check("a take already upscaled is not paid for again", len([c for c in calls("upscale") if c.startswith("upscale")]) == 1, calls("upscale"))
rc, out = run("compose", proj, "--final")
check("the final cut waits until every shot has its 1080p take", rc != 0 and "not upscaled yet" in out and "S02" in out, out)

# ------------------------------------------------------------------ 4. figures on screen, risky payoffs
d = json.load(open(os.path.join(proj, "film.json"), encoding="utf-8"))
d["accepted"] = False
d["scenes"][1]["date"] = "2016年　身家3000万"
json.dump(d, open(os.path.join(proj, "film.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
f = F.Film(proj)
check("a money figure in a date line without a source is caught", [x[2] for x in F.unsourced_figures(f)] == ["3000万"], F.unsourced_figures(f))
d["facts"] = {"3000万": "故事里的数：1984 年存下的两千元，按剧本里每一步的倍数算到 2016 年"}
json.dump(d, open(os.path.join(proj, "film.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
check("with its source in facts it passes; years and day counts are not figures", F.unsourced_figures(F.Film(proj)) == [])
script = os.path.join(work, "lottery.txt")
with open(script, "w", encoding="utf-8") as handle:
    handle.write("片头：假如回到2002年 / 我知道头奖号码\n集：E01\n\n画面一：（2002年　开奖前一天）\n地点：彩票站，日\n出场：老板\n"
                 "△ 主人公的手把一张纸条推过柜台。\n老板：又来买彩票？\n主人公：这一注。\n")
rc, out = run("intake", script, os.path.join(work, "lottery"))
sheet = open(os.path.join(work, "lottery", "DECISIONS.md"), encoding="utf-8").read()
check("lottery and betting payoffs land on the decision sheet as risky", "彩票" in sheet.split("## 3.")[1].split("## 4.")[0], sheet[:600])
check("the decision sheet prices the 480p + upscale route", "480p+超分" in sheet)

# ------------------------------------------------------------------ 5. series: cover look, run summary
S = os.path.join(work, "series")
os.makedirs(os.path.join(S, "story"))
shutil.copyfile(os.path.join(EXAMPLE, "source", "script.txt"), os.path.join(S, "story", "E01.txt"))
run("series", S, "intake")
s = json.load(open(os.path.join(S, "series.json"), encoding="utf-8"))
s.update(title="假如系列", look="真人实拍的年代写实照片质感，35mm 彩色负片细颗粒", budget=5000)
json.dump(s, open(os.path.join(S, "series.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
shutil.rmtree(os.path.join(S, "E01"))
shutil.copytree(EXAMPLE, os.path.join(S, "E01"), ignore=shutil.ignore_patterns("out", "stills", "post", "shots"))
e1 = json.load(open(os.path.join(S, "E01", "film.json"), encoding="utf-8"))
for key in ("finish", "notice", "titles", "end_card", "floor", "reroll_rate", "lead_voice", "budget", "engine"):
    e1.pop(key, None)
e1["series"] = ".."
json.dump(e1, open(os.path.join(S, "E01", "film.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ep = F.Film(os.path.join(S, "E01"))
made = F.cover_prompt_file(ep, F.cover_sections(ep))
text = open(os.path.join(ep.project, made), encoding="utf-8").read()
check("an episode's cover prompt carries the series look, section by section",
      made.startswith(".film") and text.count("整体视觉风格：" + s["look"]) == 2 and "## 3x4" in text and "## 4x3" in text, text[:300])
rc, out = run("series", S, "summary")
summary = open(os.path.join(S, "RUN.md"), encoding="utf-8").read() if os.path.isfile(os.path.join(S, "RUN.md")) else ""
check("the run summary is one page: the look, every episode, the price against the cap",
      rc == 0 and s["look"] in summary and "| E01 |" in summary and "5000" in summary and "完整分镜：E01/shots/E01.md" in summary, out + summary[:500])

shutil.rmtree(work, ignore_errors=True)
print("\n" + ("all steps hold" if not failures else "%d step(s) failed: %s" % (len(failures), "; ".join(failures))))
sys.exit(1 if failures else 0)
