#!/usr/bin/env python3
"""film.py: one runner for one film in the series, from a rough script to the finished cut.

    python3 film.py doctor                          is this machine ready: ffmpeg, fonts, jimeng-novel, login
    python3 film.py intake  SCRIPT PROJECT          rough script (.txt, .md or .docx) -> film.json skeleton + DECISIONS.md
    python3 film.py check   PROJECT                 validate film.json, write the shot file, run the gate
    python3 film.py budget  PROJECT                 what each finish costs, against the cap
    python3 film.py approve PROJECT "their words"   record the owner's sign-off on the shot list
    python3 film.py build   PROJECT                 shot file, line files, prompt files for missing images
    python3 film.py preview PROJECT                 free paper animatic from the place images (optional)
    python3 film.py images  PROJECT [--run]         the images still missing; --run generates them
    python3 film.py draft   PROJECT [--only S01,S02] [--run] [--keep]
                                                    generate shots scene by scene, chained; dry run without --run
                                                    (--keep: on the H3 engine, hold the GPU for the next 15 minutes)
    python3 film.py qc      PROJECT [--only S01]    lines, length, the lead's pitch, a frame sheet and checklist
    python3 film.py review  PROJECT S05 pass|fail ["why"]   record the look-through of a shot's frame sheet
    python3 film.py compose PROJECT [--final] [--out NAME]  edit plan -> cues -> video
    python3 film.py cover   PROJECT [--run]         3:4 and 4:3 covers: generated key art with the title set on it
    python3 film.py status  PROJECT                 every shot: state, tries, credits; total against the cap

PROJECT/film.json is the single source for the film: titles, people, places, props, and every scene
and shot with its length, stages, lines and narration. Everything else is generated from it:
shots/<episode>.md, post/lines/, the edit plan, the prompt files for images. Edit film.json, never
the generated files. State (tries, credits, verdicts) is kept in PROJECT/.film/state.json, so a
restart loses nothing.

Two engines make the clips; a film names one in "engine": "jimeng" (the default: Seedance 2.5 through
jimeng-novel, paid in credits) or "h3" (MiniMax H3 in ComfyUI on a rented AutoDL Art GPU, paid in yuan
by the minute; see h3.py, comfy.py, autodl.py). Images, checks, the edit and covers are the same.

Rules the runner enforces (see series/FORMAT.md):
  - the written shot list goes to the owner first: no image, clip or preview is made until their
    sign-off is recorded with `approve`, and anything they have not seen needs a new sign-off;
  - every shot's own writing is 3,000 characters or more (check_shots.py), and 8,000 or more when
    the film is made with MiniMax H3 (h3.py); nothing is generated from a film that fails the gate;
  - spending stops at the film's "budget"; a shot gets at most three tries;
  - shots of one scene are generated in order, and a later shot takes the earlier one's last frame;
  - a submission whose outcome is unknown is looked up, never sent again.
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import check_shots as gate  # noqa: E402  (the fixed blocks live there, once)
import env                  # noqa: E402  (where ffmpeg, the skill and the sound effects are)

PRICE = {"image": 4, "draft": 9, "draft_with_video_ref": 14, "720p": 20, "1080p": 64}   # credits; video per second
MODELS = {"sample": "Seedance_2.5_draft", "720p": "Seedance_2.5", "1080p": "Seedance_2.5_draft"}
MAX_TRIES = 3
ENGINES = ("jimeng", "h3")      # Seedance 2.5 through jimeng-novel; MiniMax H3 in ComfyUI on a rented GPU (h3.py)
DEFAULT_FINISH = "720p"        # generated at 720p, enlarged to the 1080x1920 canvas in the edit
SKILL = env.skill()
FFMPEG = env.ffmpeg()
FFPROBE = env.ffprobe()
REF_PERSON = "{{%s}} 是角色%s的形象参考（长相、发型、服装以此为准）。"
REF_PLACE = "{{%s}} 是场景参考（空间结构、陈设、光线以此为准）。"
REF_TAIL = "{{前段尾帧}}：作为本段之前的画面状态，只承接空间状态、人物站位、服装与光线，不锁构图。"
REF_PREVIS = "{{预演}}：仅参考镜头运动轨迹、景别变化与节奏，不继承其画面、人物造型、颜色和文字。"
REF_VOICE = "{{主人公的声音}}：仅参考音色与语速，不继承内容。"
LEAD = "我"
NOISE = ("哼", "哈", "嗯", "啊", "呵", "唉", "哦", "嘿")
MEDIA = "整张画面是真人实拍的写实照片质感。"


def die(msg):
    sys.exit("film: " + msg)


# ------------------------------------------------------------------ the film file
class Film:
    def __init__(self, project):
        self.project = os.path.abspath(project)
        path = os.path.join(self.project, "film.json")
        if not os.path.isfile(path):
            die("no film.json in %s (start with: film.py intake SCRIPT.txt PROJECT)" % self.project)
        with open(path, encoding="utf-8") as handle:
            self.d = json.load(handle)
        self.episode = self.d.get("episode", "E01")
        self.state_path = os.path.join(self.project, ".film", "state.json")
        self.state = {"shots": {}, "images": {}, "spent": 0}
        if os.path.isfile(self.state_path):
            with open(self.state_path, encoding="utf-8") as handle:
                self.state.update(json.load(handle))

    def path(self, *parts):
        return os.path.join(self.project, *parts)

    def save_state(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(self.state, handle, ensure_ascii=False, indent=1)

    @property
    def engine(self):
        return self.d.get("engine", "jimeng")

    def floor(self):
        """Characters of own writing a shot needs: 3,000, or 8,000 when it is made with MiniMax H3."""
        import h3
        return max(h3.FLOOR, self.d.get("floor", h3.FLOOR)) if self.engine == "h3" else self.d.get("floor", 3000)

    def shots(self):
        """-> [(scene, shot, index in scene)] in film order."""
        return [(sc, sh, n) for sc in self.d["scenes"] for n, sh in enumerate(sc.get("shots", []))]

    def shot_state(self, sid):
        return self.state["shots"].setdefault(sid, {"status": "pending", "tries": 0, "credits": 0})

    # ---- validation ---------------------------------------------------------------
    def problems(self):
        d, out, seen = self.d, [], set()
        for key in ("title", "premise", "scenes", "people", "places"):
            if key not in d:
                out.append("film.json has no \"%s\"" % key)
        if out:
            return out
        if d.get("finish", DEFAULT_FINISH) not in MODELS:
            out.append("finish must be one of %s" % ", ".join(MODELS))
        if self.engine not in ENGINES:
            out.append("engine must be one of %s" % ", ".join(ENGINES))
        for sc in d["scenes"]:
            where = sc.get("id", "?")
            if sc.get("place") not in d["places"]:
                out.append("%s: place %r is not in places" % (where, sc.get("place")))
            if not sc.get("shots"):
                out.append("%s: no shots yet" % where)
            for sh in sc.get("shots", []):
                sid = sh.get("id", "?")
                if sid in seen:
                    out.append("%s: shot id used twice" % sid)
                seen.add(sid)
                secs = sh.get("seconds")
                if not isinstance(secs, int) or not 5 <= secs <= 30:
                    out.append("%s: seconds must be a whole number from 5 to 30 (the owner's floor is 5)" % sid)
                for alias in sh.get("people", {}):
                    if alias not in d["people"]:
                        out.append("%s: %r is not in people" % (sid, alias))
                if "raw" not in sh:
                    stages = sh.get("stages", [])
                    if not stages:
                        out.append("%s: no stages" % sid)
                    elif sum(s["seconds"] for s in stages) != secs:
                        out.append("%s: stages add up to %d s, the shot is %s s" % (sid, sum(s["seconds"] for s in stages), secs))
                view = sh.get("view") or d["places"].get(sc.get("place"), {}).get("master")
                if sc.get("place") in d["places"] and view not in d["places"][sc["place"]].get("views", {}):
                    out.append("%s: place view %r is not in places.%s.views" % (sid, view, sc.get("place")))
        for alias, place in d["places"].items():
            for view, spec in place.get("views", {}).items():
                if not os.path.isfile(self.path(spec.get("image", ""))) and not spec.get("vantage"):
                    out.append("place %s, view %s: its image is still to be made, so it needs a \"vantage\" (where my eyes are and what they face)" % (alias, view))
        if self.engine == "h3" and not out:
            import h3
            out += h3.problems(self)
        return out

    # ---- references ---------------------------------------------------------------
    def refs(self, sc, sh, n, model):
        """-> [(alias, path relative to the project, reference line)] in prompt order."""
        d, out = self.d, []
        for alias, look in sh.get("people", {}).items():
            out.append((alias, d["people"][alias]["images"][look], REF_PERSON % (alias, alias)))
        place = d["places"][sc["place"]]
        view = sh.get("view") or place.get("master")
        out.append((sc["place"], place["views"][view]["image"], REF_PLACE % sc["place"]))
        for extra in sh.get("extra_views", []):
            out.append((extra["alias"], place["views"][extra["view"]]["image"],
                        "{{%s}} 是场景参考（%s）。" % (extra["alias"], extra["says"])))
        if sh.get("chain", n > 0) and n > 0:
            prev = sc["shots"][n - 1]["id"]
            out.append(("前段尾帧", "out/%s/%s.last.png" % (self.episode, prev), REF_TAIL))
        if sh.get("previs"):
            out.append(("预演", "previs/%s/ref/%s.mp4" % (self.episode, sh["id"]), REF_PREVIS))
        if self.lead_speaks(sh) and d.get("lead_voice_sample") and not model.endswith("_draft"):
            out.append(("主人公的声音", d["lead_voice_sample"], REF_VOICE))
        return out

    @staticmethod
    def lead_speaks(sh):
        if "lines" in sh:
            return any(speaker == LEAD for speaker, _ in sh["lines"])
        return "画外响起主人公的声音" in sh.get("raw", "")

    # ---- the prompt ---------------------------------------------------------------
    def prompt(self, sc, sh, n, model=None):
        d = self.d
        model = model or MODELS[d.get("finish", DEFAULT_FINISH)]
        if "raw" in sh:                                 # a shot written before the two-layer form
            return sh["raw"].strip()
        place = d["places"][sc["place"]]
        lines = ["基础视觉风格：" + d["styles"][sc.get("style", "default")], "", "画面具体需要展示的内容："]
        lines += [line for _, _, line in self.refs(sc, sh, n, model)]
        lines.append("%s本片段场景设定在：{{%s}}。%s；%s。整体电影感基调：%s"
                     % (gate.NO_MUSIC, sc["place"], sc["when"], place["sound"], sc["tone"]))
        lines += [""] + place["block"] + [""]            # the place, word for word in every shot there
        hands = d["hands"][sc["hands"]]
        pov = gate.POV + (gate.POV_TAILS[0] + hands if sh.get("hands_visible", True) else gate.POV_TAILS[1])
        lines.append(pov + sh.get("hands_note", ""))
        lines += [""] + sh.get("setup", []) + [""]
        lines.append("情绪轨迹：%s生成一个由以下%d个分镜组成的视频。" % (sh["track"], len(sh["stages"])))
        for i, stage in enumerate(sh["stages"], 1):
            lines.append("分镜%d：%d秒：%s" % (i, stage["seconds"], stage["text"]))
        if sh.get("ending"):
            lines.append(sh["ending"])
        speaks = self.lead_speaks(sh)
        lines.append(gate.TAILS[1] if speaks else gate.TAILS[0] + gate.TAILS[2])
        text = "\n".join(lines)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def subtitle_parts(self, sh):
        if "lines" in sh:
            return [part for _, parts in sh["lines"] for part in ([parts] if isinstance(parts, str) else parts)]
        return []


# ------------------------------------------------------------------ build
def cmd_build(film, quiet=False):
    d, ep = film.d, film.episode
    model = MODELS[d.get("finish", DEFAULT_FINISH)]
    os.makedirs(film.path("shots"), exist_ok=True)
    os.makedirs(film.path("post", "lines"), exist_ok=True)
    rows, sections, total = [], [], 0
    for sc, sh, n in film.shots():
        refs = film.refs(sc, sh, n, model)
        narr = sh.get("narration", {})
        told = "　".join(x for x in ("开：" + narr["open"]["text"] if narr.get("open") else "",
                                    "收：" + narr["close"]["text"] if narr.get("close") else "") if x) or "无"
        rows.append("| %s | %s | %ds | %s | %s | %s |" % (sh["id"], sc.get("title", sc["id"]), sh["seconds"], sh.get("camera", ""),
                                                        "；".join("%s=%s" % (a, p) for a, p, _ in refs), told))
        section = "## %s\n\n%s\n" % (sh["id"], film.prompt(sc, sh, n, model))
        if film.engine == "h3":
            import h3
            section += "\n### %s · 发给 MiniMax H3 的提示词（英文，由上面的分镜稿写成）\n\n```text\n%s\n```\n" % (sh["id"], h3.prompt(film, sc, sh, n)[0])
        sections.append(section)
        total += sh["seconds"]
        with open(film.path("post", "lines", sh["id"] + ".txt"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(film.subtitle_parts(sh)) + "\n")
    head = ("# %s 分镜（由 film.json 生成，不要直接改这个文件）\n\n"
            "模型 %s，比例 9:16；每个镜头是一条连续的第一人称长镜头，时长是整秒。台词逐字照原稿；"
            "只出字的旁白、顶部大字和日期行在合成时加，不写进提示词。\n\n"
            "| 段 | 画面 | 时长 | 主运镜 | 参考（别名=路径） | 只出字的旁白 |\n|---|---|---|---|---|---|\n%s\n\n"
            "合计 %d 秒（%d 分 %02d 秒），%d 个镜头。\n\n" % (ep, model, "\n".join(rows), total, total // 60, total % 60, len(rows)))
    with open(film.path("shots", ep + ".md"), "w", encoding="utf-8") as handle:
        handle.write(head + "\n".join(sections))
    made = write_image_prompts(film)
    if not quiet:
        print("wrote shots/%s.md (%d shots, %d s), post/lines/, %d image prompt file(s)" % (ep, len(rows), total, made))


def skill_blocks():
    if not SKILL:
        die("the jimeng-drama skill was not found; it comes with jimeng-novel (see AGENTS.md, Setup), or set JIMENG_DRAMA_SKILL")
    ctpl = open(os.path.join(SKILL, "templates", "cast-character.photoreal.md"), encoding="utf-8").read()
    char_fixed = ctpl[ctpl.index("【交付形态】"):ctpl.index("【标志性身份特征·解剖坐标锚定】")].rstrip() + "\n"
    stpl = open(os.path.join(SKILL, "templates", "cast-scene.photoreal.md"), encoding="utf-8").read()
    vert = stpl[stpl.index("\n## 日·主机位\n"):]
    return char_fixed, vert[vert.index("【交付形态】"):].rstrip() + "\n"


def write_image_prompts(film):
    """cast/<name>.md for people and places that have no prompt file yet. A place's first image is
    the view from where I stand (9:16); its other views are derived from that one."""
    d, made = film.d, 0
    os.makedirs(film.path("cast"), exist_ok=True)
    char_fixed = vert_fixed = None
    for alias, person in d["people"].items():
        path = film.path("cast", alias + ".md")
        if os.path.exists(path) or "body" not in person or all(os.path.isfile(film.path(p)) for p in person.get("images", {}).values()):
            continue
        if char_fixed is None:
            char_fixed, vert_fixed = skill_blocks()
        text = "# %s\n\n## 设定\n\n- 外观白描：%s\n- 音色简述（视频里逐字复用）：%s\n" % (alias, person["body"], person.get("voice", ""))
        text += "\n## 默认\n\n%s\n\n%s%s\n\n%s" % (d["styles"]["asset"], person["body"], MEDIA, char_fixed)
        for look, change in person.get("variants", {}).items():
            text += ("\n## %s\n\n%s\n\n{{%s}}是同一角色的基础形象，本图仍是同一个人。保留五官的辨识特征与身份标记；只把以下部分换成当前形象：%s"
                     "上文没有提到的部分与基础形象一致。\n\n%s" % (look, d["styles"]["asset"], alias, change, char_fixed))
        open(path, "w", encoding="utf-8").write(text)
        made += 1
    for alias, place in d["places"].items():
        path = film.path("cast", alias + ".md")
        if os.path.exists(path) or "block" not in place or all(os.path.isfile(film.path(v["image"])) for v in place.get("views", {}).values()):
            continue                                    # a prompt file is only needed for an image still to be made
        if vert_fixed is None:
            char_fixed, vert_fixed = skill_blocks()
        body = "".join(place["block"] + place.get("detail", [])) + MEDIA
        scene_style = next((sc.get("style") for sc in d["scenes"] if sc.get("place") == alias), None)
        style = d["styles"].get(place.get("style") or scene_style) or d["styles"].get("asset", "")
        master = place["master"]
        text = "# %s\n\n## 设定\n\n- 第一张图是从主人公所在位置看出去的竖版（%s），其余朝向都从它派生。\n" % (alias, master)
        for view, spec in place["views"].items():
            block = vert_fixed.replace("【视角与构图】\n", "【视角与构图】\n- " + spec["vantage"] + "\n") if spec.get("vantage") else vert_fixed
            lead_in = "" if view == master else ("{{%s}}是同一空间的母版画面：材质、光源方向、色调、年代与陈设保持一致，不新增母版里不存在的大件陈设。\n\n" % alias)
            text += "\n## %s\n\n%s\n\n%s%s\n\n%s" % (view, style, lead_in, body, block)
        open(path, "w", encoding="utf-8").write(text)
        made += 1
    return made


# ------------------------------------------------------------------ check
def cmd_check(film):
    bad = film.problems()
    for line in bad:
        print("film.json: " + line)
    if bad:
        return 1
    cmd_build(film, quiet=True)
    floor = film.floor()
    args = [sys.executable, os.path.join(TOOLS, "check_shots.py"), film.project, film.episode, "--min", str(0 if film.engine == "h3" else floor)]
    legacy = [sh["id"] for _, sh, _ in film.shots() if "raw" in sh] if film.d.get("accepted") else []
    if legacy:                                          # a finished film keeps the shots written before the floor
        args += ["--exempt", ",".join(legacy)]
    rc = subprocess.run(args).returncode
    if film.engine == "h3":                             # the 8,000 rule counts the Chinese layer and the H3 prompt together
        import h3
        rc = h3.gate(film) or rc
    for sc, sh, _ in film.shots():                      # the shared place block must not carry the shot
        if "raw" not in sh:
            own = gate.count("".join(sh.get("setup", []) + [sh.get("track", ""), sh.get("ending", "")] + [st["text"] for st in sh["stages"]]))
            if own < floor * 2 // 3:
                print("%s: only %d characters are about this shot itself (want %d or more beyond the place block)" % (sh["id"], own, floor * 2 // 3))
                rc = 1
    for alias, place in film.d["places"].items():       # a place still to be drawn needs its full description
        if any(not os.path.isfile(film.path(v["image"])) for v in place.get("views", {}).values()):
            own, need = gate.count("".join(place.get("block", []) + place.get("detail", []))), film.d.get("place_floor", 3000)
            print("place %-14s %6d  %s" % (alias, own, "pass" if own >= need else "under the floor of %d (block + detail)" % need))
            rc = rc or (0 if own >= need else 1)
    lengths = [sh["seconds"] for _, sh, _ in film.shots()]
    print("shots run %d to %d s, %.1f s on average (the rule: 5 or more, about 10 on average)"
          % (min(lengths), max(lengths), sum(lengths) / float(len(lengths))))
    if legacy:
        print("note: this film is finished; %d shot(s) written before the 3,000 rule are kept as they are" % len(legacy))
    src = film.d.get("source")
    if src and os.path.isfile(film.path(src)):
        script = "".join(ch for ch in open(film.path(src), encoding="utf-8").read() if ch.isalnum())
        allowed = set(film.d.get("line_exceptions", []))
        for sc, sh, _ in film.shots():
            for part in film.subtitle_parts(sh):
                if "".join(ch for ch in part if ch.isalnum()) not in script and part not in allowed:
                    print("%s: line not in the script and not listed in line_exceptions: %s" % (sh["id"], part))
                    rc = 1
        rc = script_lines_kept(film, open(film.path(src), encoding="utf-8").read()) or rc
    return rc


def script_lines_kept(film, script_text):
    """Every line the script gives a scene is in that scene's shots, in the script's words.
    "line_changes" in film.json lists the lines that were reworded on purpose, by scene and
    line number, so that the replaced words need not be repeated in the film file."""
    import intake
    _, found = intake.parse(script_text)
    scenes = film.d["scenes"]
    if len(found) != len(scenes):
        print("note: the script has %d scenes and the film %d, so lines were not matched scene by scene" % (len(found), len(scenes)))
        return 0
    changes = {(c["scene"], c["line"]): c["now"] for c in film.d.get("line_changes", [])}
    rc = 0
    for sc, src in zip(scenes, found):
        have = "".join(ch for sh in sc["shots"] for part in film.subtitle_parts(sh) for ch in part if ch.isalnum())
        for k, (who, said) in enumerate(src["lines"], 1):
            want = "".join(ch for ch in changes.get((sc["id"], k), said) if ch.isalnum())
            if want not in have:
                print("%s: line %d of the script is not in this scene's shots as written: %s%s" % (sc["id"], k, said, "" if (sc["id"], k) not in changes else " (changed to: %s)" % changes[(sc["id"], k)]))
                rc = 1
    return rc


# ------------------------------------------------------------------ budget and status
def missing_images(film):
    d, out = film.d, []
    for alias, person in d["people"].items():
        for look, path in person.get("images", {}).items():
            if not os.path.isfile(film.path(path)):
                out.append(("cast/%s.%s" % (alias, look), "%s#%s" % (alias, look), "16:9", path,
                            [] if look == "默认" else [(alias, person["images"]["默认"])]))
    for alias, place in d["places"].items():
        for view, spec in place.get("views", {}).items():
            if not os.path.isfile(film.path(spec["image"])):
                master = place.get("master")
                refs = [] if view == master else [(alias, place["views"][master]["image"])]
                out.append(("cast/%s.%s" % (alias, view), "%s#%s" % (alias, view), "9:16", spec["image"], refs))
    return out


def cmd_budget(film):
    d = film.d
    seconds = sum(sh["seconds"] for _, sh, _ in film.shots())
    r = d.get("reroll_rate", 0.3)
    images = len(missing_images(film)) * PRICE["image"]
    routes = [
        ("sample", "480p samples, enlarged to 1080 in the edit", PRICE["draft"] * seconds * (1 + r)),
        # a 720p clip is a fresh take whatever was drafted before, so drafting first only adds cost
        ("720p", "generate straight at 720p, enlarge to 1080 in the edit (the default)", PRICE["720p"] * seconds * (1 + r)),
        ("1080p", "draft all, then export the approved drafts", PRICE["draft"] * seconds * (1 + r) + PRICE["1080p"] * seconds),
    ]
    cap, spent = d.get("budget"), film.state.get("spent", 0)
    print("%d shots, %d s; %d image(s) still to make (%d credits); re-roll rate assumed %d%%"
          % (len(film.shots()), seconds, images // PRICE["image"], images, r * 100))
    if film.engine == "h3":
        import h3
        cfg = h3.config(film)
        minutes, yuan = h3.budget_line(film)
        used = h3.spent_yuan(film)
        print("  h3      about %6.1f yuan of GPU time (%d minutes of %s at %.2f yuan an hour, from the timings measured on 2026-11-13)  <- chosen"
              % (yuan, minutes, cfg.get("gpu"), float(cfg.get("price") or 0)))
        print("  GPU cap %s yuan, used so far %.2f; images still go through Jimeng: %d credits against a cap of %s"
              % (cfg.get("budget_yuan"), used, images, cap))
        if not cfg.get("budget_yuan") or used + yuan > float(cfg["budget_yuan"]):
            print("the H3 route has no GPU cap or is over it")
            return 1
        return 0 if not images or (cap is not None and spent + images <= cap) else 1
    for key, what, cost in routes:
        mark = "  <- chosen" if key == d.get("finish", DEFAULT_FINISH) else ""
        print("  %-7s about %6d credits  %s%s" % (key, round(cost + images), what, mark))
    chosen = dict((k, c) for k, _, c in routes)[d.get("finish", DEFAULT_FINISH)] + images
    print("cap %s, spent so far %d, this route needs about %d" % (cap if cap is not None else "not set", spent, round(chosen)))
    if cap is None:
        print("no budget set in film.json: generation will refuse to run")
        return 1
    if chosen > cap:
        print("the chosen route is over the cap")
        return 1
    return 0


def cmd_status(film):
    print("%-5s %-9s %5s %7s  %s" % ("shot", "state", "tries", "credits", "checks"))
    for _, sh, _ in film.shots():
        st = film.shot_state(sh["id"])
        checks = "; ".join("%s=%s" % kv for kv in sorted(st.get("checks", {}).items()))
        print("%-5s %-9s %5d %7d  %s" % (sh["id"], st["status"], st["tries"], st["credits"], checks))
    print("spent %d of %s" % (film.state.get("spent", 0), film.d.get("budget", "no cap")))
    if film.engine == "h3":
        import h3
        print("GPU time: %.2f of %s yuan" % (h3.spent_yuan(film), h3.config(film).get("budget_yuan", "no cap")))
    signed = film.state.get("signoff")
    print("shot list signed off %s: \"%s\"" % (signed["when"], signed["said"]) if signed else
          "shot list not signed off by the owner%s" % (" (film made before this rule)" if film.d.get("accepted") else ": nothing can be generated"))
    return 0


# ------------------------------------------------------------------ the owner's sign-off
def sha(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def shown(film):
    """What the owner is shown at the first stop, reduced to what must not change behind their back:
    the shots in order, each with its length, its words on screen and its full prompt; the title and
    date lines; and the prompt file of every image still to be made."""
    d = film.d
    model = MODELS[d.get("finish", DEFAULT_FINISH)]
    shots = {}
    for sc, sh, n in film.shots():
        words = film.subtitle_parts(sh) + [sh.get("narration", {}).get(k, {}).get("text", "") for k in ("open", "close")]
        text = film.prompt(sc, sh, n, model)
        if film.engine == "h3":
            import h3
            text += "\n" + h3.prompt(film, sc, sh, n)[0]
        shots[sh["id"]] = {"scene": sc["id"], "seconds": sh["seconds"], "words": sha("|".join(words)), "prompt": sha(text)}
    images = {}
    for key, section, _, _, _ in missing_images(film):
        name = section.split("#")[0]
        path = film.path("cast", name + ".md")
        images[name] = sha(open(path, encoding="utf-8").read()) if os.path.isfile(path) else ""
    return {"order": [sh["id"] for _, sh, _ in film.shots()], "shots": shots, "images": images,
            "titles": sha(json.dumps([d.get("premise"), [sc.get("date") for sc in d["scenes"]]], ensure_ascii=False))}


def not_signed_off(film, shots=None, images=None):
    """-> reasons why generation may not start; empty when the owner's sign-off covers it.
    shots / images: the shot ids and image names about to be made (None: all of them)."""
    signed = film.state.get("signoff")
    if not signed:
        return ["the shot list has not been signed off. Send the owner DECISIONS.md, shots/%s.md and the cast/ prompt files of "
                "the images to be made; when they say yes, record it: film.py approve PROJECT \"their words\"" % film.episode]
    now, out = shown(film), []
    if now["order"] != signed["order"]:
        out.append("shots were added, removed or reordered since the sign-off")
    if now["titles"] != signed["titles"]:
        out.append("the title or a date line changed since the sign-off")
    for sid in now["order"]:
        if shots is not None and sid not in shots:
            continue
        was, cur = signed["shots"].get(sid), now["shots"][sid]
        if was is None:
            continue
        if cur["words"] != was["words"]:
            out.append("%s: its lines or narration changed since the sign-off" % sid)
        elif (cur["prompt"], cur["seconds"]) != (was["prompt"], was["seconds"]) and not film.shot_state(sid)["tries"]:
            out.append("%s: rewritten since the sign-off and never shown" % sid)   # a fix to a failed take is allowed
    for name, digest in now["images"].items():
        if images is not None and name not in images:
            continue
        tried = any(k.startswith("cast/%s." % name) for k in film.state.get("images", {}))
        if signed["images"].get(name) != digest and not tried:
            out.append("image prompt for %s is new or changed since the sign-off" % name)
    return out


def cmd_approve(film, words):
    if not words.strip():
        die("approve needs the owner's own words, in quotes: it records their sign-off, it does not replace it")
    if cmd_check(film) != 0 and not film.d.get("accepted"):
        die("the film does not pass the gate, so there is nothing to sign off yet")
    film.state["signoff"] = dict(shown(film), when=time.strftime("%Y-%m-%d %H:%M"), said=words.strip())
    film.save_state()
    print("sign-off recorded for %d shots and %d image prompt file(s): \"%s\"" % (len(film.state["signoff"]["order"]),
                                                                              len(film.state["signoff"]["images"]), words.strip()))
    return 0


def refuse_unsigned(film, run, shots=None, images=None):
    """Stops a real run that the sign-off does not cover; on a dry run only says so."""
    why = not_signed_off(film, shots, images)
    if not why:
        return
    if run:
        die("nothing is generated before the owner has signed off on the shot list.\n  - " + "\n  - ".join(why))
    print("note: a real run would refuse: " + "; ".join(why))


# ------------------------------------------------------------------ talking to the generator
def cli(film, args, timeout=180, tries=1):
    """Run jimeng-novel inside the project. -> (exit code, text). Read-only calls may be retried."""
    out = ""
    for attempt in range(tries):
        try:
            done = subprocess.run(["jimeng-novel"] + args, cwd=film.project, capture_output=True, text=True, timeout=timeout)
            out = done.stdout + done.stderr
            if done.returncode == 0:
                return 0, out
        except subprocess.TimeoutExpired:
            out = "timed out after %d s" % timeout
        if attempt + 1 < tries:
            time.sleep(5 * (attempt + 1))
    return 1, out


def node_status(film, key):
    rc, out = cli(film, ["node", "list", "--key", key, "--json"], tries=3)
    try:                                                # the tool prints a note around the JSON
        items = json.JSONDecoder().raw_decode(out[out.index("{"):])[0]["data"]["items"]
        return items[0]["status"] if items else "missing"
    except (ValueError, KeyError, TypeError, IndexError):
        return "unknown"


def ensure_node(film, key, kind, model, prompt_ref, params, refs):
    cmd = ["node", "create", "--key", key, "--type", kind, "--model", model, "--prompt-file", prompt_ref]
    for k, v in params:
        cmd += ["--param", "%s=%s" % (k, v)]
    for alias, path in refs:
        cmd += ["--ref", "%s=file:%s" % (alias, path)]
    for attempt in range(3):
        rc, out = cli(film, cmd, timeout=600)
        if rc == 0 or "RESULT_READ_FAILED" in out:       # saved; only the read-back failed
            return True
        if node_status(film, key) not in ("missing", "unknown") and attempt:
            return True
        time.sleep(10)
    print("  could not create %s: %s" % (key, out.strip().splitlines()[-1][:160] if out.strip() else "no output"))
    return False


def run_node(film, key, out_dir, wait=540):
    """Submit once, then only look. -> (ok, credits)."""
    rc, out = cli(film, ["node", "run", "--key", key, "--wait", str(wait), "--out", out_dir], timeout=wait + 50)
    for _ in range(12):
        m = re.search(re.escape(key) + r"\s+成功\s+实扣\s+(\d+)", out)
        if m:
            if "node result" in out and "localPath" not in out and not re.search(re.escape(key) + r"\s+成功\s+实扣\s+\d+\s+\S+\.(mp4|png)", out):
                cli(film, ["node", "result", "--key", key, "--wait", "120", "--out", out_dir], timeout=200)
            return True, int(m.group(1))
        if re.search(re.escape(key) + r"\s+(失败|failed)", out) or "SUBMIT_REJECTED" in out:
            return False, 0
        rc, out = cli(film, ["node", "result", "--key", key, "--wait", "120", "--out", out_dir], timeout=200)   # never run again
    return False, 0


def cmd_images(film, run):
    todo = missing_images(film)
    if not todo:
        print("no images missing")
        return 0
    cap = film.d.get("budget")
    refuse_unsigned(film, run, shots=[])
    for key, section, ratio, path, refs in todo:
        cost = PRICE["image"]
        print("%-34s %s  %d credits%s" % (key, ratio, cost, "" if run else "  (dry run)"))
        if not run:
            continue
        if cap is None or film.state["spent"] + cost > cap:
            print("  stopping: the cap of %s would be passed" % cap)
            return 1
        name, look = section.split("#")
        if not ensure_node(film, key, "image", "seedream_5.5", "cast/%s.md#%s" % (name, look),
                           [("ratio", ratio), ("resolution", "1.5K")], refs):
            continue
        ok, credits = run_node(film, key, os.path.dirname(path) + "/", wait=240)
        film.state["spent"] += credits
        film.state["images"][key] = {"ok": ok, "credits": credits}
        film.save_state()
    return 0


def cmd_draft(film, only, run, keep=False):
    d = film.d
    if cmd_check(film) != 0 and not d.get("accepted"):
        die("the film does not pass the gate; fix film.json first")
    model = MODELS[d.get("finish", DEFAULT_FINISH)]
    cap = d.get("budget")
    todo = [sh["id"] for _, sh, _ in film.shots()
            if (sh["id"] in only if only else film.shot_state(sh["id"])["status"] not in ("drafted", "accepted"))]
    refuse_unsigned(film, run, shots=todo, images=[])
    if film.engine == "h3":
        import h3
        return h3.draft(film, only, run, keep, sys.modules[__name__])
    out_dir = "out/%s/" % film.episode
    os.makedirs(film.path(out_dir), exist_ok=True)
    for sc, sh, n in film.shots():
        sid, st = sh["id"], film.shot_state(sh["id"])
        if only and sid not in only:
            continue
        if not only and st["status"] in ("drafted", "accepted"):
            continue
        refs = film.refs(sc, sh, n, model)
        rate = PRICE["720p"] if model == "Seedance_2.5" else (PRICE["draft_with_video_ref"] if sh.get("previs") else PRICE["draft"])
        cost = rate * sh["seconds"]
        chain = [p for a, p, _ in refs if a == "前段尾帧"]
        note = ""
        if chain and not os.path.isfile(film.path(chain[0])):
            prev = sc["shots"][n - 1]["id"]
            if not run:
                note = "  after %s" % prev
            elif not last_frame(film, prev):
                print("%s  waits for %s, which has no clip yet" % (sid, prev))
                continue
        print("%-4s %2ds  %4d credits  try %d of %d%s%s" % (sid, sh["seconds"], cost, st["tries"] + 1, MAX_TRIES, note, "" if run else "  (dry run)"))
        if not run:
            continue
        if st["tries"] >= MAX_TRIES:
            print("  stopping on %s: three tries used; it needs a person to look at it" % sid)
            continue
        if cap is None or film.state["spent"] + cost > cap:
            print("  stopping: the cap of %s would be passed (spent %d)" % (cap, film.state["spent"]))
            return 1
        key = "%s/%s" % (film.episode, sid)
        params = [("duration", sh["seconds"]), ("ratio", "9:16")] + ([("resolution", "720p")] if model == "Seedance_2.5" else [])
        if not ensure_node(film, key, "video", model, "shots/%s.md#%s" % (film.episode, sid), params, [(a, p) for a, p, _ in refs]):
            continue
        ok, credits = run_node(film, key, out_dir)
        st["tries"] += 1
        st["credits"] += credits
        film.state["spent"] += credits
        st["status"] = "drafted" if ok else "failed"
        st.pop("checks", None)
        film.save_state()
        if ok:
            last_frame(film, sid)
            qc_shot(film, sc, sh)
            film.save_state()
    return 0


def last_frame(film, sid):
    clip = film.path("out", film.episode, sid + ".mp4")
    out = film.path("out", film.episode, sid + ".last.png")
    if not os.path.isfile(clip):
        return False
    subprocess.run([FFMPEG, "-v", "error", "-y", "-sseof", "-0.15", "-i", clip, "-frames:v", "1", out])
    return os.path.isfile(out)


# ------------------------------------------------------------------ checking a clip
def clip_of(film, sh):
    return film.path("out", film.episode, sh.get("take", sh["id"]) + ".mp4")


def read_srt(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    stamp = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
    for block in re.split(r"\n\s*\n", open(path, encoding="utf-8-sig").read().strip()):
        m = stamp.search(block)
        if m:
            g = [int(x) for x in m.groups()]
            rows.append((g[1] * 60 + g[2] + g[3] / 1000.0, g[5] * 60 + g[6] + g[7] / 1000.0, block[m.end():].strip()))
    return rows


def pitch_of(clip, start, end):
    """Median pitch in Hz of a stretch of speech, by autocorrelation; None if too little voice."""
    import array
    raw = subprocess.run([FFMPEG, "-v", "error", "-ss", "%.2f" % start, "-t", "%.2f" % max(0.3, end - start), "-i", clip,
                          "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
    data = array.array("h")
    data.frombytes(raw[:len(raw) // 2 * 2])
    rate, n, found = 8000, 320, []
    for i in range(0, len(data) - n, n // 2):
        x = data[i:i + n]
        mean = sum(x) / float(n)
        x = [v - mean for v in x]
        energy = sum(v * v for v in x)
        if energy / n < 300 * 300:
            continue
        best, best_lag = 0.0, 0
        for lag in range(rate // 300, rate // 70):
            ac = sum(x[j] * x[j + lag] for j in range(n - lag))
            if ac > best:
                best, best_lag = ac, lag
        if best_lag and best > 0.35 * energy:
            found.append(rate / float(best_lag))
    found.sort()
    return found[len(found) // 2] if len(found) >= 3 else None


def qc_shot(film, sc, sh):
    """Machine checks for one clip: length, lines, the lead's pitch; plus a frame sheet and checklist."""
    sid, st = sh["id"], film.shot_state(sh["id"])
    clip = clip_of(film, sh)
    checks = st.setdefault("checks", {})
    if not os.path.isfile(clip):
        checks["clip"] = "missing"
        return checks
    checks.pop("clip", None)
    dur = float(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", clip],
                               capture_output=True, text=True).stdout.strip() or 0)
    checks["length"] = "pass" if abs(dur - sh["seconds"]) <= 0.3 else "fail(%.1fs)" % dur
    name = sh.get("take", sid)
    srt = film.path("post", "srt", name + ".srt")
    os.makedirs(os.path.dirname(srt), exist_ok=True)
    parts = film.subtitle_parts(sh)
    if parts:
        rc, out = cli(film, ["transcribe", os.path.relpath(clip, film.project), "--text-file", "post/lines/%s.txt" % sid,
                             "--srt", os.path.relpath(srt, film.project), "--wait", "150"], timeout=240, tries=2)
        m = re.search(r"(\d+) 行对上，(\d+) 行没对上，(\d+) 段多出来的语音", out)
        digits = str.maketrans("0123456789", "零一二三四五六七八九")      # the recogniser writes numbers out
        said = "".join(c for c in "".join(parts) if c.isalnum()).translate(digits)
        extras = [e for e in re.findall(r"多出来的语音 \[[^\]]*\] (.+?)（", out)
                  if not all(ch in NOISE for ch in e) and "".join(c for c in e if c.isalnum()).translate(digits) not in said]
        if not m:
            checks["lines"] = "unknown"
        elif int(m.group(2)):
            checks["lines"] = "fail(%s missing)" % m.group(2)
        else:
            checks["lines"] = "pass" if not extras else "extra(%s)" % "、".join(extras)[:40]
    else:
        checks["lines"] = "none"
    mine = [p for speaker, ps in sh.get("lines", []) if speaker == LEAD for p in ([ps] if isinstance(ps, str) else ps)]
    pitches = [pitch_of(clip, a, b) for a, b, text in read_srt(srt) if text in mine and b - a >= 0.5]
    pitches = sorted(p for p in pitches if p)
    if pitches:
        checks["pitch"] = int(round(pitches[len(pitches) // 2]))
    qc_dir = film.path(".film", "qc")
    os.makedirs(qc_dir, exist_ok=True)
    n = max(1, int(dur))
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", clip, "-vf", "fps=1,scale=216:-1,tile=%dx1" % n, "-frames:v", "1",
                    "-fps_mode", "passthrough", os.path.join(qc_dir, sid + ".png")])
    always = ["主人公的脸、身体、腿、脚没有入画，只有手", "画面里没有可读的文字、数字和真实品牌的标志", "说话的是该说话的人，嘴在动",
              "人物的长相、衣服和参考图一致", "场所和同一场的其他镜头一致", "最后一帧停在这一段写的结尾状态"]
    with open(os.path.join(qc_dir, sid + ".md"), "w", encoding="utf-8") as handle:
        handle.write("# %s 看图清单\n\n图：%s.png（一秒一格）\n\n必须有：\n%s\n\n不能有：\n%s\n\n每条都要看：\n%s\n"
                     % (sid, sid, "\n".join("- " + x for x in sh.get("must", [])) or "- （没写）",
                        "\n".join("- " + x for x in sh.get("must_not", [])) or "- （没写）", "\n".join("- " + x for x in always)))
    return checks


def cmd_qc(film, only):
    for sc, sh, _ in film.shots():
        if only and sh["id"] not in only:
            continue
        checks = qc_shot(film, sc, sh)
        print("%-4s %s" % (sh["id"], "  ".join("%s=%s" % kv for kv in sorted(checks.items()))))
    film.save_state()
    pitches = sorted(st["checks"]["pitch"] for st in film.state["shots"].values() if isinstance(st.get("checks", {}).get("pitch"), int))
    if len(pitches) >= 3:
        mid = pitches[len(pitches) // 2]
        off = [sid for sid, st in film.state["shots"].items()
               if isinstance(st.get("checks", {}).get("pitch"), int) and abs(st["checks"]["pitch"] - mid) > 0.35 * mid]
        print("the lead's voice sits around %d Hz%s" % (mid, "; listen to: " + ", ".join(sorted(off)) if off else "; no shot stands out"))
    print("frame sheets and checklists are in .film/qc/ ; record each look-through with: film.py review PROJECT SHOT pass|fail [why]")
    return 0


def cmd_review(film, sid, verdict, why):
    if verdict not in ("pass", "fail"):
        die("review takes pass or fail")
    st = film.shot_state(sid)
    st.setdefault("checks", {})["look"] = verdict + ("(%s)" % why if why else "")
    st["status"] = "accepted" if verdict == "pass" else "failed"
    film.save_state()
    print("%s: %s" % (sid, st["checks"]["look"]))
    return 0


# ------------------------------------------------------------------ the edit
def narration_window(text, where, seconds):
    hold = max(1.3, len(text) * 0.2 + 0.5)
    return [0.1, round(0.1 + hold, 2)] if where == "open" else [round(seconds - 0.1 - hold, 2), round(seconds - 0.1, 2)]


def build_plan(film, final, out_name=None):
    d, ep = film.d, film.episode
    shots = film.shots()
    items = []
    sfx_dir, missing_sfx = film.path("post", d["sfx_dir"]) if d.get("sfx_dir") else env.sfx(), []
    for i, (sc, sh, _) in enumerate(shots):
        item = {"clip": sh.get("take", sh["id"]), "scoreboard": sc["date"], "bar": film.subtitle_parts(sh)}
        narr = []
        for where in ("open", "close"):
            entry = sh.get("narration", {}).get(where)
            if entry:
                narr.append({"t": entry.get("t") or narration_window(entry["text"], where, sh["seconds"]), "text": entry["text"],
                             "color": "white", "strip": True, "duck": False})
        if narr:
            item["inpic"] = narr
        sfx = [dict(e) for e in sh.get("sfx", [])]
        if i + 1 < len(shots) and shots[i + 1][0]["date"] != sc["date"]:
            sfx.append({"t": round(sh["seconds"] - 0.29, 2), "file": "scoreboard-click.mp3", "gain_db": -12})
        for entry in [e for e in sfx if not os.path.isfile(os.path.join(sfx_dir, e["file"]))]:
            if entry["file"] not in missing_sfx:
                missing_sfx.append(entry["file"])
            sfx.remove(entry)
        if sfx:
            item["sfx"] = sfx
        items.append(item)
    card = d.get("end_card")
    if card:
        end = film.path("out", ep, "END.mp4")
        if not os.path.isfile(end):
            subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=540x960:r=24:d=%s" % card.get("seconds", 2),
                            "-pix_fmt", "yuv420p", end])
        items.append({"clip": "END", "scoreboard": card.get("text", ""), "bar": []})
    titles = d.get("titles", {})
    name = out_name or (ep + (".mp4" if final else ".draft.mp4"))
    plan = {"cues": "%s.cues.json" % ep, "output": "../out/" + name, "notice": d["notice"], "premise": d["premise"], "layout": "full",
            "loudness_lufs": -15, "premise_seconds": titles.get("premise_seconds", 7), "scoreboard_seconds": titles.get("date_seconds", 4),
            "clips": "../out/%s" % ep, "srt": "srt", "sfx": sfx_dir, "items": items}
    if missing_sfx:
        print("note: no sound file for %s in %s; the cut is made without %s" % (", ".join(missing_sfx), sfx_dir, "it" if len(missing_sfx) == 1 else "them"))
    os.makedirs(film.path("post"), exist_ok=True)
    with open(film.path("post", ep + ".plan.json"), "w", encoding="utf-8") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=1)
    return film.path("post", ep + ".plan.json")


def cmd_compose(film, final, out_name):
    for sc, sh, _ in film.shots():
        name = sh.get("take", sh["id"])
        if not os.path.isfile(clip_of(film, sh)):
            die("no clip for %s (out/%s/%s.mp4)" % (sh["id"], film.episode, name))
        if film.subtitle_parts(sh) and not os.path.isfile(film.path("post", "srt", name + ".srt")):
            die("no speech timing for %s: run film.py qc first" % sh["id"])
    plan = build_plan(film, final, out_name)
    for tool, arg in (("make_cues.py", plan), ("compose_episode.py", film.path("post", film.episode + ".cues.json"))):
        rc = subprocess.run([sys.executable, os.path.join(TOOLS, tool), arg]).returncode
        if rc:
            return rc
    return 0


# ------------------------------------------------------------------ paper animatic
def cmd_preview(film):
    """A free preview from the place images: each shot is its place's view with a slow push, the lines
    spread over the stages they belong to, narration and date lines as in the final edit."""
    ep = film.episode
    if not film.d.get("accepted"):
        refuse_unsigned(film, True)
    work = film.path(".film", "preview")
    os.makedirs(work, exist_ok=True)
    items = []
    for sc, sh, n in film.shots():
        place = film.d["places"][sc["place"]]
        image = film.path(place["views"][sh.get("view") or place["master"]]["image"])
        clip = os.path.join(work, sh["id"] + ".mp4")
        frames = sh["seconds"] * 24
        source = ["-loop", "1", "-i", image] if os.path.isfile(image) else ["-f", "lavfi", "-i", "color=c=0x30343a:s=540x960"]
        vf = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "zoompan=z='1+0.06*on/%d':d=%d:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=540x960:fps=24" % (frames, frames)
              if os.path.isfile(image) else "null")
        subprocess.run([FFMPEG, "-v", "error", "-y"] + source + ["-vf", vf, "-frames:v", str(frames), "-r", "24", "-pix_fmt", "yuv420p", clip])
        item = {"file": clip, "scoreboard": sc["date"]}
        bar, at, todo = [], 0.0, list(film.subtitle_parts(sh))
        for stage in sh.get("stages", []) or [{"seconds": sh["seconds"], "text": sh.get("raw", "")}]:
            said = "".join(ch for q in re.findall(r"“([^”]*)”", stage["text"]) for ch in q if ch.isalnum())
            here = []
            while todo and said.startswith("".join(ch for ch in todo[0] if ch.isalnum())):
                said = said[len("".join(ch for ch in todo[0] if ch.isalnum())):]
                here.append(todo.pop(0))
            a, b = at + min(0.4, stage["seconds"] * 0.2), at + stage["seconds"] - 0.1
            weight = float(sum(len(p) for p in here)) or 1.0
            t = a
            for p in here:
                nxt = t + (b - a) * len(p) / weight
                bar.append({"t": [round(t, 2), round(nxt - 0.04, 2)], "text": p})
                t = nxt
            at += stage["seconds"]
        if todo:                                        # shots kept as one block of text: spread evenly
            step = (sh["seconds"] - 0.6) / len(todo)
            bar = [{"t": [round(0.4 + i * step, 2), round(0.4 + (i + 1) * step - 0.04, 2)], "text": p} for i, p in enumerate(todo)]
        if bar:
            item["bar"] = bar
        narr = []
        for where in ("open", "close"):
            entry = sh.get("narration", {}).get(where)
            if entry:
                t = entry.get("t") or narration_window(entry["text"], where, sh["seconds"])
                clash = [x for x in bar if x["t"][0] < t[1] and t[0] < x["t"][1]]
                narr.append(dict({"t": t, "text": entry["text"], "color": "white", "strip": True, "duck": False}, **({"y": 1120} if clash else {})))
        if narr:
            item["inpic"] = narr
        items.append(item)
    cues = {"layout": "full", "output": film.path("out", ep + ".preview.mp4"), "notice": "纸上预演 · 只看顺序和节奏 · 画面不是成片",
            "premise": film.d["premise"], "premise_seconds": 7, "scoreboard_seconds": 4, "items": items}
    path = os.path.join(work, "preview.cues.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(cues, handle, ensure_ascii=False, indent=1)
    return subprocess.run([sys.executable, os.path.join(TOOLS, "compose_episode.py"), path]).returncode


# ------------------------------------------------------------------ covers
COVERS = {"3x4": ((1440, 1920), "3:4"), "4x3": ((1920, 1440), "4:3")}
COVER_PRICE = 6                  # credits for one 2K image
COVER_FIRST = "竖版封面"          # alias under which the chosen 3:4 art is handed to the 4:3 prompt


def cover_sections(film):
    path = film.path("cover", film.episode + ".md")
    if not os.path.isfile(path):
        return {}
    pieces = re.split(r"(?m)^## (\S+)\s*$", open(path, encoding="utf-8").read())[1:]
    return {pieces[i]: pieces[i + 1] for i in range(0, len(pieces), 2)}


def cmd_cover(film, run):
    """Covers are generated key art with the title set on it, never a frame of the cut (frame
    covers were tried and rejected). Prompts live in cover/<episode>.md, sections 3x4
    and 4x3; the 4:3 is generated from the chosen 3:4 so the two match. Run it again after each
    choice: it does the next thing that is missing."""
    import cover_art
    d, ep = film.d, film.episode
    if not d.get("accepted"):
        die("covers are made once the cut is approved: set \"accepted\": true in film.json")
    spec = d.setdefault("cover", {})
    art = spec.get("art", {})
    sections = cover_sections(film)
    floor = d.get("floor", 3000)
    for name, ((W, H), ratio) in COVERS.items():
        if art.get(name) and os.path.isfile(film.path(art[name])):
            continue
        made = sorted(f for f in os.listdir(film.path("cover")) if f.startswith("%s.%s." % (ep, name)) and f.endswith(".png")) \
            if os.path.isdir(film.path("cover")) else []
        if made:
            print("%s: look at %s and put the one you choose in film.json: \"cover\": {\"art\": {\"%s\": \"cover/<file>\"}}"
                  % (name, ", ".join("cover/" + f for f in made), name))
            return 1
        if name not in sections:
            print("%s: write the art prompt first, as section \"## %s\" of cover/%s.md (see FORMAT.md, Covers)" % (name, name, ep))
            return 1
        own = gate.count("\n".join(l for l in sections[name].splitlines() if not l.startswith("{{")))
        if own < floor:
            print("%s: the art prompt has %d characters of its own writing; the floor is %d" % (name, own, floor))
            return 1
        refs = [(a, p) for a, p in spec.get("refs", {}).items()]
        if name == "4x3":
            refs.insert(0, (COVER_FIRST, art["3x4"]))
        takes = spec.get("takes", 2)
        cap, spent = spec.get("budget", 40), film.state.get("cover_spent", 0)
        print("%s: %d take(s) at %s, %d credits each%s" % (name, takes, ratio, COVER_PRICE, "" if run else "  (dry run)"))
        if not run:
            return 0
        for n in range(takes):
            if spent + COVER_PRICE > cap:
                print("  stopping: the cover budget of %d would be passed" % cap)
                break
            key = "cover/%s.%s.%s" % (ep, name, "abcdefgh"[n])
            if not ensure_node(film, key, "image", "seedream_5.5", "cover/%s.md#%s" % (ep, name),
                               [("ratio", ratio), ("resolution", "2K")], refs):
                continue
            ok, credits = run_node(film, key, "cover/", wait=240)
            spent += credits
            film.state["cover_spent"] = spent
            film.save_state()
        return cmd_cover(film, False)
    lines = spec.get("lines") or [l for l in d["premise"] if l.strip()]
    made = []
    for name, ((W, H), _) in COVERS.items():
        out = film.path("out", "%s.cover.%s.jpg" % (ep, name))
        look = spec.get("set", {}).get(name, {})
        if cover_art.render(film.path(art[name]), out, (W, H), lines, d.get("notice", ""), look.get("left"), look.get("top"), look.get("big")):
            die("cover: could not write %s" % out)
        made.append(os.path.relpath(out, film.project))
    print("wrote " + " and ".join(made))
    return 0


# ------------------------------------------------------------------ doctor
def cmd_doctor():
    """Is this machine ready? Prints one line per requirement and how to fix what is missing."""
    rows = []

    def row(ok, what, detail, fix="", needed=True):
        rows.append((bool(ok), what, detail, fix, needed))

    v = sys.version_info
    row(v >= (3, 9), "Python 3.9 or newer", "%d.%d.%d" % v[:3], "install Python 3.9+")
    ff = FFMPEG if os.path.isfile(FFMPEG) else (shutil.which(FFMPEG) or "")
    row(ff and env.has_ass(ff), "ffmpeg that can draw text (libass)", ff or "no ffmpeg found",
        "install an ffmpeg that lists an \"ass\" filter in `ffmpeg -filters`, and set FFMPEG to its path if it is not on PATH")
    row(os.path.isfile(FFPROBE) or shutil.which(FFPROBE), "ffprobe", FFPROBE, "it comes with ffmpeg")
    if ff and env.has_ass(ff):
        import compose_episode as ce
        with tempfile.TemporaryDirectory() as work:
            style = "Style: %s,%s,40,&H00FFFFFF,&H0,&H0,&H0,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1"
            faces = [ce.SERIF, ce.SANS, ce.SANS_BOLD]
            with open(os.path.join(work, "f.ass"), "w", encoding="utf-8") as handle:
                handle.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, "
                             "PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, "
                             "Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n%s\n\n[Events]\nFormat: Layer, Start, "
                             "End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n%s\n"
                             % ("\n".join(style % ("S%d" % i, f) for i, f in enumerate(faces)),
                                "\n".join("Dialogue: 0,0:00:00.00,0:00:01.00,S%d,,0,0,0,,假如2001年" % i for i in range(len(faces)))))
            log = subprocess.run([ff, "-hide_banner", "-nostdin", "-loglevel", "verbose", "-f", "lavfi", "-i", "color=c=black:s=640x360:d=0.1",
                                  "-vf", "ass=f=f.ass", "-frames:v", "1", "-f", "null", "-"], capture_output=True, text=True, cwd=work).stderr
        squash = lambda name: re.sub(r"[^a-z0-9]", "", name.lower())     # noqa: E731
        got = {font: face.strip() for font, face in re.findall(r"fontselect: \((.+?), \d+, \d+\) -> .+, -?\d+, (.+)", log)}
        for face in faces:
            ok = face in got and squash(face) in squash(got[face])
            row(ok, "font %s" % face, got.get(face, "not found") if not ok else "found",
                "these are macOS fonts; elsewhere set FILM_SERIF / FILM_SANS / FILM_SANS_BOLD to installed Chinese fonts, "
                "for instance \"Noto Serif CJK SC Black\" and \"Noto Sans CJK SC\"")
    tool = shutil.which("jimeng-novel")
    row(tool, "jimeng-novel (the generator's command line)", tool or "not on PATH",
        "a person installs it: curl -s https://jimeng.jianying.com/novel-cli | bash  (read the script first; needs Python 3.10+ and Node 18+)")
    if tool:
        try:
            out = subprocess.run([tool, "credit", "get"], capture_output=True, text=True, timeout=90)
            text = out.stdout + out.stderr
        except subprocess.SubprocessError:
            text = "no answer"
        m = re.search(r"可用积分[:：]\s*(\d+)", text)
        row(m, "logged in to Jimeng", "%s credits available" % m.group(1) if m else text.strip().splitlines()[-1][:80] if text.strip() else "no answer",
            "ask the person to run `jimeng-novel login` and approve it in their browser; never type their password yourself")
    row(SKILL, "jimeng-drama skill (prompt templates)", SKILL or "not found", "it is installed with jimeng-novel; or set JIMENG_DRAMA_SKILL to its folder")
    have = sorted(f for f in os.listdir(env.sfx())) if os.path.isdir(env.sfx()) else []
    row("scoreboard-click.mp3" in have, "sound effects", "%d file(s) in %s" % (len(have), env.sfx()),
        "optional: put scoreboard-click.mp3 (the click on a date change) and any effect a film names into that folder; without them the cut is made silent at those points", needed=False)
    import autodl
    row(os.path.isfile(autodl.TOKEN_FILE) or os.environ.get("AUTODL_TOKEN"), "AutoDL Art token (only for the H3 engine)",
        autodl.TOKEN_FILE if os.path.isfile(autodl.TOKEN_FILE) else "not set",
        "optional: the person creates a developer token at autodl.com (控制台 > 设置 > 开发者Token) and saves it to that file, mode 600", needed=False)
    for ok, what, detail, fix, needed in rows:
        print("%-8s %-44s %s" % ("ok" if ok else ("MISSING" if needed else "optional"), what, detail))
        if not ok and fix:
            print("         -> %s" % fix)
    bad = [what for ok, what, _, _, needed in rows if needed and not ok]
    print("\n%s" % ("ready" if not bad else "not ready: %s" % "; ".join(bad)))
    return 1 if bad else 0


# ------------------------------------------------------------------ intake
BRANDS = "宾利 奔驰 宝马 劳斯莱斯 保时捷 法拉利 兰博基尼 特斯拉 茅台 五粮液 苹果 华为 微信 支付宝 高盛 摩根 劳力士 爱马仕 香奈儿 路易威登 腾讯 阿里".split()
RISKY = "房卡 开房 做空 空单 出货 割韭菜 内幕 放消息 赌博 赌场 裸体 鲜血 自杀 毒品 吸毒 砍 枪".split()


def estimate_seconds(line_chars, scenes):
    """About four spoken characters a second plus five and a half seconds of action a scene
    (the first film: 388 characters, ten scenes, 152 seconds)."""
    return int(round((line_chars / 4.0 + 5.5 * scenes) / 5.0) * 5)


def cmd_intake(script_path, project):
    import intake
    project = os.path.abspath(project)
    os.makedirs(os.path.join(project, "source"), exist_ok=True)
    kept = os.path.join(project, "source", os.path.basename(script_path))
    if os.path.abspath(script_path) != kept:
        shutil.copyfile(script_path, kept)
    if script_path.lower().endswith(".docx"):           # a Word file is a zip; its text is in word/document.xml
        xml = zipfile.ZipFile(script_path).read("word/document.xml").decode("utf-8")
        paras = [re.sub(r"<[^>]+>", "", re.sub(r"<w:(?:br|cr)[^>]*/>", "\n", re.sub(r"<w:tab[^>]*/>", " ", p)))
                 for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)]
        text = "\n".join(p.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"') for p in paras)
        kept = os.path.splitext(kept)[0] + ".txt"       # the plain text the lines are checked against
        with open(kept, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        text = open(script_path, encoding="utf-8").read()
    head, found = intake.parse(text)
    if not found:
        die("no scenes found: each scene must start on its own line with 画面一： (or 场景一：, 第一场：), then 画面二： and so on")
    scenes = []
    for n, sc in enumerate(found, 1):
        scenes.append({"id": "P%02d" % n, "title": sc["title"], "date": sc["date"], "place": "", "style": "default", "hands": "",
                       "when": "", "tone": "", "script": sc["script"], "lines": sc["lines"], "shots": []})
    total_chars = sum(len(re.sub(r"\W", "", said)) for sc in scenes for _, said in sc["lines"])
    seconds = estimate_seconds(total_chars, len(scenes))
    film = {"title": "", "episode": "E01", "premise": [], "notice": "AI 生成 · 虚构剧情", "script_head": head,
            "source": os.path.relpath(kept, project), "finish": DEFAULT_FINISH, "budget": None, "reroll_rate": 0.3, "floor": 3000,
            "titles": {"premise_seconds": 7, "date_seconds": 4}, "end_card": None, "styles": {"default": "", "asset": ""},
            "hands": {}, "lead_voice": "", "props": {}, "people": {}, "places": {}, "line_exceptions": [], "scenes": scenes}
    out = os.path.join(project, "film.json")
    if os.path.exists(out):
        out = os.path.join(project, "film.intake.json")      # never write over a film in progress
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(film, handle, ensure_ascii=False, indent=1)
    brands = sorted({b for b in BRANDS if b in text})
    risky = sorted({w for w in RISKY if w in text})
    figures = sorted(set(re.findall(r"\d{4}年|\d+(?:亿|万|天|倍)|[一二三四五六七八九十]+(?:亿|万)", text)))
    speakers = sorted({s.rstrip("?") for sc in scenes for s, _ in sc["lines"]} - {""})
    unsure = ["%s　%s：%s" % (sc["title"], who.rstrip("?") or "谁", said) for sc in scenes for who, said in sc["lines"] if who.endswith("?")]
    quoted = ["%s　“%s”" % (sc["title"], q) for sc in found for q in sc["quoted"]]
    sheet = ["# 开拍前要你定的事", "",
             "脚本：%s，%d 个画面，台词 %d 句、约 %d 字，照原稿一句不删大约 %d 秒。" % (
                 os.path.basename(script_path), len(scenes), sum(len(sc["lines"]) for sc in scenes), total_chars, seconds), "",
             "## 1. 真实人物的名字", "工具不让真实公众人物的名字进提示词和文件。读稿后填：原文、建议的换法。", "- （读稿后填）", "",
             "## 2. 品牌和商标", "画面里一律做成不带字、不带标的；台词里出现的照原稿说。查到：%s" % ("、".join(brands) or "没有"), "",
             "## 3. 可能被平台拦的情节", "查到：%s" % ("、".join(risky) or "没有"), "每一处：照拍，还是换一种拍法。", "",
             "## 4. 数字和年份", "%s" % ("、".join(figures) or "没有"), "哪些上屏，哪些只留在故事里。", "",
             "## 5. 说话的人", "%s" % "、".join(speakers), "主人公的台词由视频模型在片段里说出来；旁白只出字，不配音。", "",
             "## 6. 只出字的旁白", "只在画面自己说不清、或者能添一句冷幽默的地方留。拟好后列在这里。", "- （拟好后填）", "",
             "## 7. 成片规格和积分上限", "| 规格 | 做法 | 大约积分 |", "|---|---|---|",
             "| 720p（默认） | 直接按 720p 生成，合成时放大到 1080 | %d |" % round(PRICE["720p"] * seconds * 1.3),
             "| 480p | 样片直接合成，放大到 1080 | %d |" % round(PRICE["draft"] * seconds * 1.3),
             "| 1080p | 先出样片，通过后逐条导出 | %d |" % round(PRICE["draft"] * seconds * 1.3 + PRICE["1080p"] * seconds), "",
             "按 30% 重做估的。不说就按 720p；给一个积分上限，到上限就停下来问。", "",
             "## 我要先看一眼的句子", "下面这些是脚本里没用冒号写明、或者没写清谁说的；我读稿后定，不用你管，除非我在上面问到。"]
    sheet += ["- " + u for u in unsure] or ["- 没有"]
    if quoted:
        sheet += ["", "引号里的内容（是台词、画面里的字，还是电视里的声音）："] + ["- " + q for q in quoted]
    with open(os.path.join(project, "DECISIONS.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(sheet) + "\n")
    print("wrote %s and DECISIONS.md: %d scenes, %d lines by %d speakers (%d to settle), about %d s"
          % (os.path.relpath(out, project), len(scenes), sum(len(s["lines"]) for s in scenes), len(speakers), len(unsure), seconds))
    return 0


# ------------------------------------------------------------------ main
def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    flags = [a for a in rest if a.startswith("--")]
    pos = [a for i, a in enumerate(rest) if not a.startswith("--") and not (i and rest[i - 1] in ("--only", "--out"))]

    def opt(name):
        return rest[rest.index(name) + 1] if name in rest else None

    if cmd == "doctor":
        sys.exit(cmd_doctor())
    if cmd == "intake":
        if len(pos) != 2:
            sys.exit(__doc__)
        sys.exit(cmd_intake(pos[0], pos[1]))
    if not pos:
        sys.exit(__doc__)
    film = Film(pos[0])
    only = set((opt("--only") or "").split(",")) - {""}
    if cmd == "check":
        rc = cmd_check(film)
    elif cmd == "build":
        bad = film.problems()
        if bad:
            die("; ".join(bad))
        rc = cmd_build(film) or 0
    elif cmd == "budget":
        rc = cmd_budget(film)
    elif cmd == "approve":
        rc = cmd_approve(film, pos[1] if len(pos) > 1 else "")
    elif cmd == "status":
        rc = cmd_status(film)
    elif cmd == "images":
        rc = cmd_images(film, "--run" in flags)
    elif cmd == "draft":
        rc = cmd_draft(film, only, "--run" in flags, "--keep" in flags)
    elif cmd == "qc":
        rc = cmd_qc(film, only)
    elif cmd == "review":
        rc = cmd_review(film, pos[1], pos[2], pos[3] if len(pos) > 3 else "")
    elif cmd == "compose":
        rc = cmd_compose(film, "--final" in flags, opt("--out"))
    elif cmd == "preview":
        rc = cmd_preview(film)
    elif cmd == "cover":
        rc = cmd_cover(film, "--run" in flags)
    else:
        sys.exit(__doc__)
    sys.exit(rc)


if __name__ == "__main__":
    main()
