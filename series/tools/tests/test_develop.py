#!/usr/bin/env python3
"""Replay the idea-to-script flow on a copy of examples/bitcoin-2010-develop. Spends nothing.

    python3 series/tools/tests/test_develop.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(TOOLS))
EXAMPLE = os.path.join(REPO, "examples", "bitcoin-2010-develop")
failures = []


def run(*args):
    done = subprocess.run([sys.executable, os.path.join(TOOLS, "film.py")] + list(args), capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def check(what, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, "" if ok else "  -> " + detail[-300:]))
    if not ok:
        failures.append(what)


work = tempfile.mkdtemp(prefix="develop-test-")
try:
    s = os.path.join(work, "s")
    shutil.copytree(EXAMPLE, s)
    script = os.path.join(s, "story", "E01.txt")
    rc, out = run("script-check", script)
    check("the example script is ready for intake", rc == 0 and "ready for intake" in out, out)
    rc, out = run("intake", script, os.path.join(s, "E01"))
    check("intake refuses a developed script the owner has not approved", rc != 0 and "not approved" in out, out)
    rc, out = run("develop", s, "--approve", "")
    check("an approval needs the owner's words", rc != 0, out)
    rc, out = run("develop", s, "--approve", "可以")
    check("the owner's yes is recorded", rc == 0, out)
    rc, out = run("intake", script, os.path.join(s, "E01"))
    check("intake takes the approved script", rc == 0 and "0 to settle" in out, out)
    film = json.load(open(os.path.join(s, "E01", "film.json"), encoding="utf-8"))
    check("title lines and episode come from the script's header", film["premise"] == ["假如你在2010年", "买了一万块比特币"] and film["episode"] == "E01")
    check("narration lines are proposed, not taken as speech",
          any(sc.get("narration_proposed") for sc in film["scenes"]) and not any(w == "旁白" for sc in film["scenes"] for w, _ in sc["lines"]))
    with open(script, "a", encoding="utf-8") as handle:
        handle.write("△ 一个后加的动作。\n")
    rc, out = run("intake", script, os.path.join(s, "E01b"))
    check("a script changed after the yes is refused", rc != 0 and "changed since" in out, out)
    bad = os.path.join(work, "bad.txt")
    with open(bad, "w", encoding="utf-8") as handle:
        handle.write("画面一：（今天）\n△ 主人公的脸出现在镜子里。\n主人公（os）：我好累。\n小王：你来了\n")
    rc, out = run("script-check", bad)
    check("script-check catches a missing header, place, cast, a seen face, an inner voice and an unlisted speaker",
          rc != 0 and all(k in out for k in ("片头", "集", "地点", "出场", "never seen", "no voiceover", "not on the 出场")), out)
finally:
    shutil.rmtree(work, ignore_errors=True)
print("all steps hold" if not failures else "%d failed" % len(failures))
sys.exit(1 if failures else 0)
