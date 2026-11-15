#!/usr/bin/env python3
"""Offline test of "camera": "third" (an ordinary drama instead of the protagonist's eyes), on both engines.
Rents nothing, spends nothing.

    python3 tests/test_third.py         ends with "all steps hold"
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import env as where  # noqa: E402
FFMPEG = where.ffmpeg()
work = tempfile.mkdtemp(prefix="third-")
proj = os.path.join(work, "film")
os.makedirs(os.path.join(proj, "cast"))
failures = []


def check(what, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, "" if ok or not detail else "  -> " + detail[-500:]))
    if not ok:
        failures.append(what)


def run(*args):
    done = subprocess.run([sys.executable, os.path.join(TOOLS, "film.py")] + list(args), capture_output=True, text=True,
                          env=dict(os.environ, JIMENG_SERIES_HOME=os.path.join(work, "home")))
    return done.returncode, done.stdout + done.stderr


def write(obj):
    with open(os.path.join(proj, "film.json"), "w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=1)


cast = {"林夏": "cast/林夏.默认.png", "张经理": "cast/张经理.默认.png", "会议室": "cast/会议室.日·竖·主机位.png"}
for n, path in enumerate(cast.values()):
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=576x1024:d=1,hue=h=%d" % (n * 90), "-frames:v", "1",
                    os.path.join(proj, path)], check=True)
filler = "张经理站在投影幕布左边，右手捏着一支没开盖的白板笔，林夏站在桌子另一头，两只手攥着一个黑色U盘，长桌上的纸杯冒着热气。"
body = ("The camera holds a medium shot across the long meeting table in {会议室}: {林夏} (S1) stands at the far end gripping a black "
        "memory stick in both hands, and {张经理} (S2) stands by the screen with a capped marker. ") * 7 + \
       "{林夏} (S1) steps forward and asks, voice tight and low, <d>[Chinese] 方案是谁写的？</d> {张经理} (S2) does not look up."
film = {"title": "third", "episode": "E01", "premise": ["第三人称", "测试"], "notice": "AI 生成", "source": "", "camera": "third",
        "budget": 0, "reroll_rate": 0.3, "titles": {"premise_seconds": 7, "date_seconds": 4}, "end_card": None,
        "styles": {"default": "真人实拍的现代写实质感", "asset": "真人实拍的现代写实质感"},
        "styles_en": {"default": "Photorealistic present-day footage, cool office light."},
        "people": {"林夏": {"images": {"默认": cast["林夏"]}, "voice": "二十三岁女声，清楚，压着火", "en": "a woman of twenty-three in a grey blazer.",
                           "voice_en": "a clear young woman's voice, holding back anger."},
                   "张经理": {"images": {"默认": cast["张经理"]}, "voice": "四十岁男声，油", "en": "a man of forty in a navy suit.",
                            "voice_en": "a smooth forty-year-old man's voice."}},
        "places": {"会议室": {"master": "日·竖·主机位", "views": {"日·竖·主机位": {"image": cast["会议室"]}}, "sound": "<空调低鸣>",
                           "block": ["空间：" + filler * 4, "光：" + filler, "背景里的人：" + filler], "en": "a glass-walled meeting room.",
                           "sound_en": "The low hum of air conditioning."}},
        "line_exceptions": [], "props": {},
        "scenes": [{"id": "P01", "title": "画面一", "date": "第一天", "place": "会议室", "style": "default", "when": "上午，室内", "tone": "冷。",
                    "script": "林夏：方案是谁写的？", "lines": [["林夏", "方案是谁写的？"]],
                    "shots": [{"id": "S01", "seconds": 10, "camera": "固定", "people": {"林夏": "默认", "张经理": "默认"}, "lines": [["林夏", "方案是谁写的？"]],
                               "setup": ["人物的起始状态：" + filler * 45], "track": "压着 → 顶上去。",
                               "stages": [{"seconds": 6, "text": filler * 60}, {"seconds": 4, "text": "林夏往前走一步：“方案是谁写的？”" + filler * 50}],
                               "ending": "画面最后停在：" + filler, "must": [], "must_not": [],
                               "h3": {"summary": "A tense meeting-room standoff.", "body": body}}]}]}
try:
    # 1. Seedance engine, third person
    write(film)
    rc, out = run("check", proj)
    shots = open(os.path.join(proj, "shots", "E01.md"), encoding="utf-8").read() if os.path.isfile(os.path.join(proj, "shots", "E01.md")) else ""
    check("a third-person film needs no hands and passes check", rc == 0 and "0 failed" in out, out)
    check("its prompt frames a following cinema camera, not the protagonist's eyes",
          "一台电影摄影机在人物视线高度跟着人物拍" in shots and "第一人称" not in shots.split("## S01")[1] and "主人公的双手" not in shots, shots[:600])
    check("its shot list says 跟拍, not 第一人称", "一条连续的跟拍长镜头" in shots, shots[:300])
    bad = json.loads(json.dumps(film))
    bad["scenes"][0]["shots"][0]["lines"] = [["我", "方案是谁写的？"]]
    write(bad)
    rc, out = run("check", proj)
    check("a third-person film refuses a line by 我", rc != 0 and "third-person film has no" in out, out)
    first = json.loads(json.dumps(film))
    del first["camera"]
    write(first)
    rc, out = run("check", proj)
    check("the same film in first person still asks for the protagonist's hands", rc != 0 and "\"hands\" is empty" in out, out)

    # 2. H3 engine, third person
    h3film = json.loads(json.dumps(film))
    h3film.update({"engine": "h3", "h3": {"app": "mockapp", "workflow": "", "gpu": "pro6000-p", "price": 8.8}})
    write(h3film)
    rc, out = run("check", proj)
    shots = open(os.path.join(proj, "shots", "E01.md"), encoding="utf-8").read()
    h3part = shots.split("```text")[1] if "```text" in shots else ""
    check("on H3 a third-person film passes check without hands_en", rc == 0 and "pass" in out, out)
    check("the H3 prompt frames a cinema camera and describes each voice",
          "filmed by a cinema camera at the characters' eye level" in h3part and "first-person" not in h3part
          and "(S1) is the voice of <Subject 1>: a clear young woman's voice" in h3part, h3part[:900])

    # 3. script-check
    script = os.path.join(work, "E01.txt")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("片头：第三人称 / 测试\n集：E01\n\n画面一：（第一天）\n地点：会议室，日\n出场：林夏、张经理\n"
                     "△ 主人公的脸贴近玻璃，林夏站起来。\n林夏：方案是谁写的？\n张经理：组里的。\n")
    rc, out = run("script-check", script)
    check("script-check in first person refuses a seen protagonist", rc != 0 and "never seen" in out, out)
    rc, out = run("script-check", script, "--camera", "third")
    check("script-check --camera third allows it", rc == 0 and "never seen" not in out, out)
    rc, out = run("intake", script, os.path.join(work, "taken"), "--camera", "third")
    taken = json.load(open(os.path.join(work, "taken", "film.json"), encoding="utf-8")) if rc == 0 else {}
    check("intake --camera third writes it into film.json", taken.get("camera") == "third", out)
finally:
    shutil.rmtree(work, ignore_errors=True)

print("\n%s" % ("all steps hold" if not failures else "%d step(s) failed: %s" % (len(failures), "; ".join(failures))))
sys.exit(1 if failures else 0)
