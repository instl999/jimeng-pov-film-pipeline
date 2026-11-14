#!/usr/bin/env python3
"""From a vague idea to a script the pipeline can shoot: the development stage.

Used by film.py:

    film.py develop SERIES "the owner's idea, in their words"   start: story/brief.md with the question card
    film.py develop SERIES                                       where it stands, what is missing, what it costs
    film.py develop SERIES --approve "the owner's words"         record the owner's yes to the brief, outline and scripts
    film.py script-check SCRIPT                                  is this script ready for intake

A series folder holds the story work in story/ and one film folder per episode:

    SERIES/story/brief.md      the brief: the idea, the owner's answers, the choices made
    SERIES/story/setting.md    premise, people, engine, rules
    SERIES/story/outline.md    one section per episode (only for more than one episode)
    SERIES/story/E01.txt       the script of episode 1, in the format of series/DEVELOP.md section 6
    SERIES/story/approved.json the owner's yes, with a fingerprint of every file it covers
    SERIES/E01/                the film of episode 1 (film.py intake SERIES/story/E01.txt SERIES/E01)

The method is series/DEVELOP.md. The tools here do the bookkeeping and the checks; the writing is
the agent's.
"""
import hashlib
import json
import os
import re
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import intake  # noqa: E402

PRICE_720P, PRICE_IMAGE, REROLL = 20, 4, 0.3
OPTIONS = [(1, 60), (1, 120), (1, 150), (3, 60), (3, 90), (5, 60), (10, 60)]
CLICHES = ("眼底闪过一丝", "嘴角勾起一抹", "一字一顿", "目光微动", "这一次，换我", "空气仿佛凝固", "时间仿佛静止", "五味杂陈",
           "千言万语化作", "意味深长地", "不知为何", "莫名的情绪", "声音很轻", "眼神复杂")
VOICEOVER = re.compile(r"[（(]\s*(?:os|OS|vo|VO|V\.O\.|内心|心声|画外音|独白)\s*[）)]")
SEEN = ("主人公的脸", "主人公的背影", "主人公的侧脸", "主人公的全身", "看见主人公的", "主人公的表情", "主人公照镜子", "镜子里的主人公")
LEAD_LABELS = ("主人公", "男主", "女主", "主角", "我")


def fingerprint(path):
    with open(path, "rb") as handle:
        return hashlib.sha1(handle.read()).hexdigest()[:16]


def target_seconds(text):
    """'单集时长：60-90 秒' or '单集时长：120 秒' in a brief -> (low, high) or None."""
    m = re.search(r"单集时长\s*[：:]\s*(\d+)\s*(?:[-~～到至]\s*(\d+))?\s*秒", text)
    if not m:
        return None
    low = int(m.group(1))
    return low, int(m.group(2) or low)


def episodes_of(text):
    m = re.search(r"集数\s*[：:]\s*(\d+)", text)
    return int(m.group(1)) if m else None


def estimate(chars, scenes, actions=0):
    """Seconds for a script. Four spoken characters a second; then, for a script that marks its
    actions with △, two and a half seconds an action and three a scene; for one that does not, five
    and a half a scene (the measured rate of the first film: 388 characters, ten scenes, 152 s)."""
    if actions:
        return int(round((chars / 4.0 + 2.5 * actions + 3 * scenes) / 5.0) * 5)
    return int(round((chars / 4.0 + 5.5 * scenes) / 5.0) * 5)


def price(seconds_total, people=6, places=5):
    return round(PRICE_720P * seconds_total * (1 + REROLL) + PRICE_IMAGE * (people * 1.5 + places))


# ------------------------------------------------------------------ start
BRIEF = """# 立项单

> 由 `film.py develop` 生成。照 `series/DEVELOP.md` 一步一步填。带「:」的几行工具会读，格式别改。

## 1. 片主的原话

{idea}

## 2. 要问片主的（一次问完，每题给推荐项）

问题和选项照 `series/DEVELOP.md` 第 2 节写好后发给片主，原样贴在这里。片主说「你定」的，取推荐项，记进第 4 节「我做的假设」。

## 3. 定下来的

- 片名：<<4-12 字>>
- 一句话故事：<<30-50 字，从一个具体时刻写起，有主人公、一个冲突瞬间和一个悬念>>
- 题材与核心梗：<<>>
- 受众与平台：<<>>
- 基调：<<爽燃 / 轻喜 / 甜宠 / 悬疑 / 治愈 / 虐 ……选一个，全剧不换>>
- 集数：<<数字>>
- 单集时长：<<例：90-120>> 秒
- 年代与地点：<<>>
- 画面风格：第一人称主观镜头、竖屏 9:16、写实真人（系列固定）；色调：<<冷底暖点 / 全暖 / ……>>
- 主人公：<<性别、年龄、起点处境；声音一句话，例：三十岁男声，低平，慢，像自言自语>>
- 结局：<<怎么收：完胜 / 反转 / 开放 / 温情>>
- 片头两行：<<每行 9 个字以内，例：假如你在2001年 / 全仓买入英伟达>>
- 一定要有的：<<>>
- 不能有的：<<>>

## 4. 我做的假设

- <<片主没说、我按推荐项或最朴素的理解定下的，每条一行>>

## 5. 大概花多少（720p，含 30% 重拍，另加角色和场景图）

| 集数 × 单集 | 成片总长 | 大约积分 |
|---|---|---|
{prices}

## 6. 片主确认

<<片主看过立项单、设定、大纲和第 1 集剧本后的原话；由 `film.py develop <系列目录> --approve "原话"` 记录，不要手写>>
"""


def start(series, idea):
    story = os.path.join(series, "story")
    os.makedirs(story, exist_ok=True)
    path = os.path.join(story, "brief.md")
    if os.path.exists(path):
        print("story/brief.md already exists; not writing over it")
        return status(series)
    rows = "\n".join("| %d × %d 秒 | %d 分 %02d 秒 | %d |" % (n, s, n * s // 60, n * s % 60, price(n * s)) for n, s in OPTIONS)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(BRIEF.format(idea=idea.strip(), prices=rows))
    print("wrote %s\nnext: series/DEVELOP.md section 1 (read the idea), then section 2 (the question card for the owner)" % os.path.relpath(path))
    return 0


# ------------------------------------------------------------------ checking a script
def check_script(path, quiet=False):
    """-> (errors, warnings, facts). The rules of series/DEVELOP.md section 6 and 7."""
    text = open(path, encoding="utf-8").read()
    head, scenes = intake.parse(text)
    meta = intake.header(head)
    errors, warnings = [], []
    if not scenes:
        errors.append("no scenes: each scene starts on its own line with 画面一：（<date line>）")
        return errors, warnings, {}
    if not meta.get("premise"):
        errors.append("no 片头 line before the first scene, e.g. 片头：假如你在2010年 / 买了一万块比特币")
    elif any(len(p) > 9 for p in meta["premise"]):
        warnings.append("a 片头 line is longer than 9 characters: %s" % " / ".join(meta["premise"]))
    if not meta.get("episode"):
        errors.append("no 集 line before the first scene, e.g. 集：E01")
    spoken_total = lead_total = 0
    for sc in scenes:
        where = sc["title"]
        if not sc["date"]:
            errors.append("%s: no date line in brackets after the heading, e.g. 画面一：（2010年5月　买入第一天）" % where)
        if not sc.get("place_hint"):
            errors.append("%s: no 地点： line" % where)
        if "cast" not in sc:
            errors.append("%s: no 出场： line (write 出场：无 when nobody but the protagonist is there)" % where)
        cast = set(sc.get("cast", [])) - {"无"}
        if not sc["lines"] and not re.search(r"(?m)^\s*[△▲]", sc["script"]):
            errors.append("%s: no action and no lines" % where)
        for who, said in sc["lines"]:
            name = who.rstrip("?")
            if who.endswith("?") or not name:
                errors.append("%s: who says this is not clear: %s (write it as its own line, 名字：台词)" % (where, said))
            elif name != intake.LEAD and name not in cast:
                errors.append("%s: %s speaks but is not on the 出场 line" % (where, name))
            n = len(re.sub(r"\W", "", said))
            spoken_total += n
            if name == intake.LEAD:
                lead_total += n
            if n > 15:
                warnings.append("%s: a line of %d characters; keep lines short (15 or fewer), or split it into two lines with an action between: %s" % (where, n, said))
        for raw in sc["script"].splitlines():
            if VOICEOVER.search(raw):
                errors.append("%s: os / vo / inner voice is not used in this series (no voiceover): %s" % (where, raw.strip()[:40]))
            if "闪回" in raw:
                warnings.append("%s: a flashback; it must still be first person and be shot as its own scene with its own date line" % where)
            for word in SEEN:
                if word in raw:
                    errors.append("%s: the protagonist is never seen (first person): %s" % (where, raw.strip()[:40]))
            for word in CLICHES:
                if word in raw:
                    warnings.append("%s: stock phrase 「%s」; write the concrete action instead" % (where, word))
            if re.match(r"\s*[△▲]", raw) and re.search(r"(?:心里|内心|觉得|想到|意识到|感到)", raw):
                warnings.append("%s: an action line describes a thought; only what can be seen or heard can be shot: %s" % (where, raw.strip()[:40]))
        for line in sc.get("narration", []):
            if not line.endswith(".."):
                warnings.append("%s: a narration line usually ends with two dots: %s" % (where, line))
            if len(re.sub(r"\W", "", line)) > 8:
                warnings.append("%s: a narration line over 8 characters: %s" % (where, line))
    if spoken_total and lead_total > 0.35 * spoken_total:
        warnings.append("the protagonist says %d%% of all words; in first person he speaks little and others talk at him" % round(100.0 * lead_total / spoken_total))
    actions = len(re.findall(r"(?m)^\s*[△▲]", text))
    seconds = estimate(spoken_total, len(scenes), actions)
    facts = {"scenes": len(scenes), "lines": sum(len(sc["lines"]) for sc in scenes), "spoken": spoken_total, "seconds": seconds,
             "episode": meta.get("episode"), "premise": meta.get("premise"), "narration": sum(len(sc.get("narration", [])) for sc in scenes), "actions": actions}
    brief = os.path.join(os.path.dirname(os.path.abspath(path)), "brief.md")
    if os.path.isfile(brief):
        want = target_seconds(open(brief, encoding="utf-8").read())
        if want and not (want[0] * 0.85 <= seconds <= want[1] * 1.15):
            warnings.append("estimated %d s; the brief asks for %d-%d s an episode: %s" % (seconds, want[0], want[1],
                            "add scenes, lines or action" if seconds < want[0] else "cut what does not turn the story"))
    if not quiet:
        print("%s: %d scenes, %d spoken lines (%d characters), %d action lines, %d narration lines; about %d s" % (
            os.path.basename(path), facts["scenes"], facts["lines"], spoken_total, actions, facts["narration"], seconds))
        for e in errors:
            print("ERROR  " + e)
        for w in warnings:
            print("note   " + w)
        print("ready for intake" if not errors else "not ready: %d error(s)" % len(errors))
    return errors, warnings, facts


# ------------------------------------------------------------------ approval
def covered(series):
    story = os.path.join(series, "story")
    names = [n for n in ("brief.md", "setting.md", "outline.md") if os.path.isfile(os.path.join(story, n))]
    names += sorted(n for n in os.listdir(story) if re.fullmatch(r"E\d+\.(?:txt|md)", n))
    return {n: fingerprint(os.path.join(story, n)) for n in names}


def approve(series, words):
    if not words.strip():
        sys.exit("develop: --approve needs the owner's own words in quotes; it records their yes, it does not replace it")
    story = os.path.join(series, "story")
    scripts = [n for n in os.listdir(story) if re.fullmatch(r"E\d+\.(?:txt|md)", n)]
    if not scripts:
        sys.exit("develop: there is no script yet (story/E01.txt)")
    for n in scripts:
        errors, _, _ = check_script(os.path.join(story, n), quiet=True)
        if errors:
            sys.exit("develop: story/%s does not pass script-check yet; fix it before asking the owner" % n)
    record = {"when": time.strftime("%Y-%m-%d %H:%M"), "said": words.strip(), "files": covered(series)}
    path = os.path.join(story, "approved.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else {"history": []}
    old.setdefault("history", []).append(record)
    old.update(record)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(old, handle, ensure_ascii=False, indent=1)
    print("recorded the owner's yes for %s: \"%s\"" % (", ".join(record["files"]), record["said"]))
    return 0


def approval_of(script_path):
    """For a script inside a series' story/ folder: -> None when the owner's yes covers it as it is
    now, else the reason. Scripts from anywhere else are the owner's own and need no record."""
    story = os.path.dirname(os.path.abspath(script_path))
    if os.path.basename(story) != "story" or not os.path.isfile(os.path.join(story, "brief.md")):
        return None
    path = os.path.join(story, "approved.json")
    if not os.path.isfile(path):
        return "the owner has not approved this script yet (series/DEVELOP.md, Stop 0: film.py develop <series> --approve \"<their words>\")"
    record = json.load(open(path, encoding="utf-8"))
    name = os.path.basename(script_path)
    if record.get("files", {}).get(name) != fingerprint(script_path):
        return "story/%s has changed since the owner approved it (or was never shown); show it again and record their yes" % name
    return None


# ------------------------------------------------------------------ status
def status(series):
    story = os.path.join(series, "story")
    if not os.path.isfile(os.path.join(story, "brief.md")):
        print("no story/brief.md: start with film.py develop %s \"<the owner's idea>\"" % series)
        return 1
    brief = open(os.path.join(story, "brief.md"), encoding="utf-8").read()
    todo = brief.split("## 6.")[0].count("<<")          # section 6 is the owner's yes, recorded by --approve
    n_eps, want = episodes_of(brief), target_seconds(brief)
    print("brief      %s" % ("%d place(s) still to fill (<<...>>)" % todo if todo else "filled in"))
    print("           %s episode(s) of %s s" % (n_eps or "?", "%d-%d" % want if want else "?"))
    for name, need in (("setting.md", True), ("outline.md", (n_eps or 1) > 1)):
        there = os.path.isfile(os.path.join(story, name))
        print("%-10s %s" % (name.split(".")[0], "written" if there else ("missing" if need else "not needed (one episode)")))
    scripts = sorted(n for n in os.listdir(story) if re.fullmatch(r"E\d+\.(?:txt|md)", n))
    total = 0
    for n in scripts:
        errors, warnings, facts = check_script(os.path.join(story, n), quiet=True)
        total += facts.get("seconds", 0)
        print("%-10s about %d s; %s" % (n, facts.get("seconds", 0), "ready" if not errors else "%d error(s) (film.py script-check)" % len(errors)))
    if not scripts:
        print("scripts    none yet")
    if n_eps and want:
        secs = n_eps * (want[0] + want[1]) / 2.0
        print("cost       the whole series, %d s at 720p: about %d credits" % (secs, price(secs)))
    path = os.path.join(story, "approved.json")
    if os.path.isfile(path):
        record = json.load(open(path, encoding="utf-8"))
        changed = [n for n, fp in covered(series).items() if record.get("files", {}).get(n) != fp]
        print("approved   %s: \"%s\"%s" % (record["when"], record["said"], "; changed since: " + ", ".join(changed) if changed else ""))
    else:
        print("approved   not yet (Stop 0)")
    return 0
