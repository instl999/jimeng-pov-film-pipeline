#!/usr/bin/env python3
"""Offline test of a series: a run of scripts taken in together, every episode reading one locked look.
Generates nothing, spends nothing.

    python3 tests/test_series.py        ends with "all steps hold"
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
sys.path.insert(0, TOOLS)
EXAMPLE = os.path.join(ROOT, "examples", "nvidia-2001")
BITCOIN = os.path.join(ROOT, "examples", "bitcoin-2010-develop", "story", "E01.txt")
work = tempfile.mkdtemp(prefix="series-")
S = os.path.join(work, "假如系列")
failures = []
LOOK = "真人实拍的年代写实照片质感，35mm 彩色负片细颗粒，镜头略广，暗部有颗粒不发黑"


def check(what, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, "" if ok or not detail else "  -> " + detail[-600:]))
    if not ok:
        failures.append(what)


def run(*args):
    done = subprocess.run([sys.executable, os.path.join(TOOLS, "film.py")] + list(args), capture_output=True, text=True,
                          env=dict(os.environ, JIMENG_SERIES_HOME=os.path.join(work, "home")))
    return done.returncode, done.stdout + done.stderr


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save(path, obj):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=1)


# 1. two scripts in, two episodes out, and the series file written once
os.makedirs(os.path.join(S, "story"))
shutil.copyfile(os.path.join(EXAMPLE, "source", "script.txt"), os.path.join(S, "story", "E01.txt"))
shutil.copyfile(BITCOIN, os.path.join(S, "story", "E02.txt"))
rc, out = run("series", S, "intake")
check("intake takes in every script in story/ and writes series.json", rc == 0 and os.path.isfile(os.path.join(S, "series.json"))
      and all(os.path.isfile(os.path.join(S, e, "film.json")) for e in ("E01", "E02")), out)
e2 = load(os.path.join(S, "E02", "film.json"))
check("an episode reads the series and keeps none of the locked keys itself",
      e2.get("series") == ".." and e2.get("episode") == "E02" and not any(k in e2 for k in ("finish", "notice", "titles", "floor", "budget")), str(sorted(e2)))
rc, out = run("series", S, "intake")
check("taking in again leaves the episodes as they are", rc == 0 and "already taken in" in out, out)

# 2. the look: an episode that sets a locked key differently drifts and fails
s = load(os.path.join(S, "series.json"))
s.update({"title": "假如系列", "look": LOOK, "budget": 1000})
save(os.path.join(S, "series.json"), s)
shutil.rmtree(os.path.join(S, "E01"))
shutil.copytree(EXAMPLE, os.path.join(S, "E01"), ignore=shutil.ignore_patterns("out", "stills", "post", "shots"))
e1 = load(os.path.join(S, "E01", "film.json"))
e1["series"] = ".."
save(os.path.join(S, "E01", "film.json"), e1)                 # the example says "finish": "sample"; the series says 720p
rc, out = run("check", os.path.join(S, "E01"))
check("a film that sets a locked key to something else fails check", rc != 0 and "locked by the series" in out and "finish" in out, out)
for key in ("finish", "notice", "titles", "end_card", "floor", "reroll_rate", "lead_voice", "budget", "engine"):
    e1.pop(key, None)
save(os.path.join(S, "E01", "film.json"), e1)
rc, out = run("check", os.path.join(S, "E01"))
check("with the locked keys left to the series, the episode passes", rc == 0 and "0 failed" in out, out)
shots = open(os.path.join(S, "E01", "shots", "E01.md"), encoding="utf-8").read()
check("every written shot opens on the series look, then the episode's own style",
      ("基础视觉风格：" + LOOK + "；") in shots, shots[:400])

import film as F                                               # noqa: E402
f = F.Film(os.path.join(S, "E01"))
check("the series supplies finish, notice and titles", f.d["finish"] == "720p" and f.d["notice"] == s["notice"] and f.d["titles"] == s["titles"])
check("the look goes in front of the image style too", f.d["styles"]["asset"].startswith(LOOK))

# 3. one cap for the run: an episode may spend only what the others have left
os.makedirs(os.path.join(S, "E02", ".film"))
save(os.path.join(S, "E02", ".film", "state.json"), {"shots": {}, "images": {}, "spent": 300})
f = F.Film(os.path.join(S, "E01"))
check("an episode's cap is the run's cap less what the others spent", f.d["budget"] == 700, str(f.d.get("budget")))
rc, out = run("series", S, "budget")
check("series budget prices every episode and the run", "the run:" in out and "cap 1000" in out, out)

# 4. status, the one sign-off, the run
rc, out = run("series", S)
check("status shows each episode and the run against its cap", rc == 0 and "E01" in out and "E02" in out and "spent 300 of 1000" in out, out)
rc, out = run("series", S, "approve", "好，开始做")
check("the one sign-off refuses while an episode fails the gate", rc != 0 and "E02" in out and "not signed" in out, out)
rc, out = run("series", S, "approve", "好，开始做", "--episodes", "E01")
check("--episodes signs the ones that are ready (an accepted film needs none)", rc == 0, out)
rc, out = run("series", S, "run")
check("a dry run goes episode by episode without stopping on a refusal", rc != 0 and "== E01" in out and "== E02" in out, out)
del s["budget"]
save(os.path.join(S, "series.json"), s)
rc, out = run("series", S, "run", "--run")
check("a real run refuses without a cap for the run", rc != 0 and "budget" in out, out)
s["budget"] = 1000
save(os.path.join(S, "series.json"), s)

# 5. a film outside any series is untouched
rc, out = run("check", EXAMPLE)
check("a film without \"series\" checks exactly as before", rc == 0 and "0 failed" in out, out[-300:])

# 6. a continuing story: the cast carries over, and a changed face is caught
C = os.path.join(work, "连续剧")
os.makedirs(os.path.join(C, "story"))
shutil.copyfile(BITCOIN, os.path.join(C, "story", "E01.txt"))
shutil.copyfile(BITCOIN, os.path.join(C, "story", "E02.txt"))
save(os.path.join(C, "series.json"), dict(json.load(open(os.path.join(S, "series.json"), encoding="utf-8")), continuing=True))
rc, out = run("series", C, "intake")
check("a continuing episode waits until the one before has its people", "E02: waits until E01" in out and not os.path.isdir(os.path.join(C, "E02")), out)
c1 = load(os.path.join(C, "E01", "film.json"))
c1["people"] = {"老周": {"images": {"默认": "cast/老周.默认.png"}, "body": "五十岁男性"}}
save(os.path.join(C, "E01", "film.json"), c1)
os.makedirs(os.path.join(C, "E01", "cast"), exist_ok=True)
with open(os.path.join(C, "E01", "cast", "老周.默认.png"), "wb") as handle:
    handle.write(b"face one")
rc, out = run("series", C, "intake")
c2 = load(os.path.join(C, "E02", "film.json"))
check("then it is taken in from the one before: same people, same pictures",
      "老周" in c2.get("people", {}) and os.path.isfile(os.path.join(C, "E02", "cast", "老周.默认.png")), out)
with open(os.path.join(C, "E02", "cast", "老周.默认.png"), "wb") as handle:
    handle.write(b"face two")
rc, out = run("series", C, "check")
check("a person whose picture changed between episodes is caught", rc != 0 and "老周.默认.png is not the picture E01 used" in out, out)

shutil.rmtree(work, ignore_errors=True)
print("\n" + ("all steps hold" if not failures else "%d step(s) failed: %s" % (len(failures), "; ".join(failures))))
sys.exit(1 if failures else 0)
