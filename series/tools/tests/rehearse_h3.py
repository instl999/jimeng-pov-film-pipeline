#!/usr/bin/env python3
"""Rehearse the H3 engine end to end against local stand-ins (tests/mock_h3.py). Rents nothing,
spends nothing, touches no real state.

    python3 tests/rehearse_h3.py

Exits 0 when every step holds.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import env as where  # noqa: E402
FFMPEG = where.ffmpeg()
work = tempfile.mkdtemp(prefix="h3-rehearsal-")
proj, home = os.path.join(work, "film"), os.path.join(work, "home")
os.makedirs(os.path.join(proj, "cast"))
os.makedirs(home)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
env = dict(os.environ, AUTODL_API="http://127.0.0.1:%d" % port, AUTODL_TOKEN="rehearsal-token", JIMENG_SERIES_HOME=home)
failures = []


def check(what, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, "" if ok or not detail else "  -> " + detail))
    if not ok:
        failures.append(what)


def run(*args):
    done = subprocess.run([sys.executable, os.path.join(TOOLS, "film.py")] + list(args), env=env, capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


cast = {"小红": "cast/小红.默认.png", "柜员": "cast/柜员.默认.png", "证券营业部柜台": "cast/证券营业部柜台.日·竖·柜台.png"}
for n, path in enumerate(cast.values()):               # stand-in pictures; a real project's images are not needed
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1024x576:d=1,hue=h=%d" % (n * 90), "-frames:v", "1",
                    os.path.join(proj, path)], check=True)
filler = "镜头贴着柜台的前沿缓缓向右移，台面上的印台、圆珠笔和单据依次滑过画面下沿，日光灯的青色落在玻璃隔断的指印上。"
body = ("The camera drifts right along the worn counter edge at a slow walking pace while {柜员} keeps writing behind the glass and "
        "{小红} waits at the right shoulder, her red scarf the only saturated colour in {证券营业部柜台}. ") * 9


def shot(sid, seconds, chain):
    return {"id": sid, "seconds": seconds, "camera": "右移", "people": {"柜员": "默认", "小红": "默认"}, "chain": chain, "lines": [],
            "setup": ["人物的起始状态：" + filler * 45], "track": "平静 → 留意。", "hands_visible": True,
            "stages": [{"seconds": seconds - 4, "text": filler * 60}, {"seconds": 4, "text": filler * 50}], "ending": "画面最后停在：" + filler,
            "must": [], "must_not": [], "h3": {"summary": "A slow first-person drift along a bank counter in 2001.", "body": body}}


film = {"title": "rehearsal", "episode": "E01", "premise": ["排练", "不花钱"], "notice": "AI 生成", "source": "", "engine": "h3",
        "budget": 0, "reroll_rate": 0.3,
        "h3": {"app": "mockapp", "workflow": "", "gpu": "pro6000-p", "price": 8.8, "budget_yuan": 5, "minutes_per_shot": 1},
        "titles": {"premise_seconds": 7, "date_seconds": 4}, "end_card": None,
        "styles": {"default": "真人实拍的年代写实照片质感", "asset": "真人实拍的年代写实照片质感"},
        "styles_en": {"default": "Photorealistic period footage on fine-grained 35mm colour negative, desaturated grey-blue and teal."},
        "hands": {"2001": "三十岁男性的双手；深蓝色旧棉夹克的袖口。"},
        "hands_en": {"2001": "a thirty-year-old man's hands, short nails, the frayed cuffs of an old navy cotton jacket, bare wrists."},
        "lead_voice": "三十岁男声，低平，慢", "props": {},
        "people": {"小红": {"images": {"默认": cast["小红"]}, "body": "二十六岁左右的女性，披肩黑发，正红色围巾，米白呢大衣。", "voice": "年轻女声，轻", "en": "a woman of about twenty-six with shoulder-length black hair, a red knitted scarf and a cream wool coat."},
                   "柜员": {"images": {"默认": cast["柜员"]}, "en": "a bank teller of about twenty-five with a low ponytail, a white shirt and a navy uniform vest."}},
        "places": {"证券营业部柜台": {"master": "日·竖·柜台", "views": {"日·竖·柜台": {"image": cast["证券营业部柜台"]}}, "sound": "<大厅里低低的人声>",
                                 "block": ["空间：" + filler * 4, "光：" + filler, "背景里的人：" + filler], "en": "the ground-floor hall of a 1990s securities office with a long counter behind glass.",
                                 "sound_en": "Low murmur of a half-empty hall, a phone ringing far off and stopping."}},
        "line_exceptions": [], "scenes": [{"id": "P01", "title": "画面一", "date": "第一天", "place": "证券营业部柜台", "style": "default",
                                           "hands": "2001", "when": "2001年冬天上午，室内", "tone": "冷调，克制。",
                                           "shots": [shot("S01", 10, False), shot("S02", 6, True)]}]}


def write(obj):
    with open(os.path.join(proj, "film.json"), "w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=1)


clip = os.path.join(work, "mock.mp4")                 # what the stand-in "generates": 243 frames, like a 10 s H3 clip
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=768x1344:r=24:d=10.125", "-f", "lavfi", "-i",
                "sine=f=220:d=10.125", "-pix_fmt", "yuv420p", "-shortest", clip], check=True)
log = os.path.join(work, "requests.jsonl")
server = subprocess.Popen([sys.executable, os.path.join(TOOLS, "tests", "mock_h3.py"), str(port), clip, log])
time.sleep(1.0)
try:
    # 1. the 8,000 rule and the H3 prompt checks
    thin = json.loads(json.dumps(film))
    thin["scenes"][0]["shots"][0]["stages"][0]["text"] = filler
    write(thin)
    rc, out = run("check", proj)
    check("a shot under 8,000 fails the gate", rc != 0 and "under the floor of 8000" in out, out[-300:])
    bad = json.loads(json.dumps(film))
    bad["scenes"][0]["shots"][0]["lines"] = [["小红", "你疯啦"]]
    write(bad)
    rc, out = run("check", proj)
    check("a line missing from the H3 prompt is caught", rc != 0 and "word for word" in out, out[-300:])
    write(film)
    rc, out = run("check", proj)
    check("the full film passes", rc == 0, out[-600:])
    text = open(os.path.join(proj, "shots", "E01.md"), encoding="utf-8").read()
    check("the shot file carries the H3 prompt in its six parts",
          all(k in text for k in ("subject_definitions:", "summary:", "retention_analysis:", "detailed_description:", "overall_soundscape:", "non_diegetic_music:")))
    check("people and place became <Subject N> / <Picture N>", "<Subject 3> is the location in <Picture 3>" in text and "{" not in text.split("```text")[1].split("```")[0])
    check("the chained shot starts from the previous last frame", "[keyframe completion + reference generation]" in text and "<Picture 4> is the first frame" in text)
    # 2. nothing without sign-off, nothing without --run
    rc, out = run("draft", proj, "--run")
    check("no sign-off, no generation", rc != 0 and "signed off" in out and not os.path.exists(log), out[-200:])
    rc, out = run("approve", proj, "rehearsal sign-off")
    check("sign-off recorded", rc == 0, out[-200:])
    if where.skill():                                    # writing an image prompt needs the jimeng-drama skill's templates
        held = os.path.join(proj, cast["小红"])           # a planned image that has not been made yet
        os.rename(held, held + ".away")
        rc, out = run("check", proj)
        check("a reference image still to be made does not fail the check", rc == 0 and "still to be made" in out, out[-300:])
        rc, out = run("draft", proj, "--run")
        check("but no shot is generated until it exists", rc != 0 and "still to be made" in out and not os.path.exists(log), out[-300:])
        os.rename(held + ".away", held)
    rc, out = run("draft", proj)
    check("dry run lists two shots and rents nothing", rc == 0 and "S01" in out and "S02" in out and not os.path.exists(log), out[-300:])
    rc, out = run("budget", proj)
    check("budget prices the GPU route in yuan", rc == 0 and "yuan of GPU time" in out, out[-400:])
    # 3. the real path, against the stand-ins
    rc, out = run("draft", proj, "--run")
    print(out)
    check("draft --run finishes", rc == 0)
    for sid, secs in (("S01", 10), ("S02", 6)):
        path = os.path.join(proj, "out", "E01", sid + ".mp4")
        dur = float(subprocess.run([where.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                   capture_output=True, text=True).stdout.strip() or 0) if os.path.isfile(path) else 0
        check("%s is cut to %d s" % (sid, secs), abs(dur - secs) < 0.15, "%.2f s" % dur)
    state = json.load(open(os.path.join(proj, ".film", "state.json"), encoding="utf-8"))
    check("both shots are drafted with a seed and a time", all(state["shots"][s]["status"] == "drafted" and state["shots"][s].get("seed") for s in ("S01", "S02")))
    check("the last frame of S01 was taken for S02", os.path.isfile(os.path.join(proj, "out", "E01", "S01.last.png")))
    calls = [json.loads(l) for l in open(log, encoding="utf-8")]
    names = [c["path"].split("?")[0].rsplit("/", 1)[-1] for c in calls]
    check("the GPU was created, then powered off, then released", names.index("create") < names.index("power_off") < names.index("release"))
    check("the token went only to the instance API", all(c["auth"] == c["path"].startswith("/api/v1/adl_dev/") for c in calls))
    graphs = [c["body"]["prompt"] for c in calls if c["path"] == "/prompt"]
    g1, g2 = graphs[0], graphs[1]
    check("S01: 243 frames, 768x1344, 3 references, 20 steps", g1["20"]["inputs"]["length"] == 243 and (g1["20"]["inputs"]["width"], g1["20"]["inputs"]["height"]) == (768, 1344)
          and sum(k.startswith("ref_images") for k in g1["20"]["inputs"]) == 3 and g1["23"]["inputs"]["steps"] == 20)
    check("S02: 158 frames and 4 references (the last frame added)", g2["20"]["inputs"]["length"] == 158 and sum(k.startswith("ref_images") for k in g2["20"]["inputs"]) == 4)
    check("the H3 model files were picked, not the first in the list", g1["3"]["inputs"]["unet_name"].startswith("minimax_h3_ref2va") and g1["1"]["inputs"]["vae_name"].startswith("minimax_h3_video_vae")
          and g1["2"]["inputs"]["vae_name"].startswith("minimax_h3_audio_vae") and g1["4"]["inputs"]["type"] == "minimax")
    check("inputs the server requires were filled from its defaults", g1["20"]["inputs"].get("resize_mode") == "match" and g1["28"]["inputs"].get("bit_depth") == 8)
    check("nothing is held afterwards", not os.path.exists(os.path.join(home, "autodl.state.json")))
    ledger = [json.loads(l) for l in open(os.path.join(home, "autodl.ledger.jsonl"), encoding="utf-8")]
    check("the rental is in the ledger, released", len(ledger) == 1 and ledger[0]["released"] and ledger[0]["price"] == 8.8)
    rc, out = run("status", proj)
    check("status shows the GPU spend", "GPU time:" in out, out[-200:])
    # 4. a failure on the server still gives the GPU back
    broken = json.loads(json.dumps(film))
    broken["scenes"][0]["shots"][0]["seconds"] = 11
    broken["scenes"][0]["shots"][0]["stages"][0]["seconds"] = 7
    write(broken)
    with open(log, "w"):
        pass
    env["AUTODL_TOKEN"] = ""
    rc, out = run("draft", proj, "--only", "S01", "--run")
    check("without a token nothing is rented and the run stops", rc != 0 and "no AutoDL token" in out and os.path.getsize(log) == 0, out[-300:])
finally:
    server.terminate()
    time.sleep(0.5)
    left = os.path.exists(os.path.join(home, "autodl.state.json"))
    shutil.rmtree(work, ignore_errors=True)
print("\n%s" % ("all steps hold" if not failures else "%d step(s) failed: %s" % (len(failures), "; ".join(failures))))
sys.exit(1 if failures else 0)
