#!/usr/bin/env python3
"""Read a rough script into scenes and spoken lines.

    python3 intake.py SCRIPT.txt        print what was found, scene by scene

Used by `film.py intake`. A rough script mixes stage directions and speech freely, for example

    男主一拍桌子站起来：好，我再也不回这个家！
    其他美女也走过来搭讪，男主笑着喝下一口酒说道：无聊
    男主将存折拍在柜台上，说全买英伟达，柜员震惊，问确定？

so the reader works clause by clause. Speech is what follows a colon, up to the next clause that
names who speaks next; the speaker is the nearest clause before the colon that starts with a
person. A line whose speaker had to be guessed carries a "?" after the name, and a line that was
reported without a colon ("说全买英伟达") is always marked that way, because its wording is the
writer's summary and may need a look. Nothing is dropped or reworded here: the scene keeps its
full text under "script", and whoever fills in film.json settles the marked lines.
"""
import re
import sys

LEAD = "我"
LEAD_NAMES = ("男主", "女主", "主角", "主人公")
ROLES = ("父母 父亲 母亲 爸爸 妈妈 兄弟 哥们儿 哥们 姐妹 闺蜜 妻子 老婆 丈夫 老公 前女友 女朋友 女友 前男友 男朋友 男友 "
         "朋友 同学 同事 邻居 儿子 女儿 孙子 孙女 亲戚 老板 经理 服务员 柜员 店员 司机 秘书 助理 美女 帅哥 保安 医生 "
         "护士 老师 记者 客户 路人 房东 领导").split()
GROUPS = ("父母",)                                  # one word, two people: a line needs one of them
MANY = ("几个", "一群", "一帮", "们", "众人", "大家", "都")  # the clause speaks of several people
FILLER = ("随后", "然后", "接着", "这时", "这时候", "最后", "于是", "同时")
DESCRIBES = ("画面", "场景", "镜头", "环境", "背景", "地点", "时间")      # a label for description, not a speaker
TEXT_ONLY = ("字幕", "旁白", "大字", "屏幕上")                            # words shown on screen, nobody says them
BESIDE = ("身边的", "旁边的", "对面的", "身后的", "门外的", "身边", "旁边", "对面", "身后", "门外", "一旁")
SOMEONE = ("其中一个", "其中一位", "另一个", "另一位", "另外一个", "有一个", "一个", "一位", "有人", "其他", "几个")
SAYS = ("说道", "问道", "喊道", "说", "问", "喊")
END = "。！？!?…"
SCENE = r"(?:画面|场景)[一二三四五六七八九十百\d]+|第[一二三四五六七八九十百\d]+[场幕]"


def strip_notes(text):
    """Drop bracketed stage directions; they stay in the scene's full text."""
    return re.sub(r"[（(][^（()）]*[）)]", "", text)


def clauses(text):
    return re.findall(r"[^，,。！？!?；;…]+[，,。！？!?；;…]*|[，,。！？!?；;…]+", text)


def bare(clause):
    return clause.strip().strip("，,。！？!?；;…").strip()


def names_in(script):
    """Role words plus the short labels the script itself puts at the start of a line."""
    found = set(ROLES)
    for raw in strip_notes(script).splitlines():
        m = re.match(r"\s*([^，,。！？!?：:\s]{1,6})[：:]", raw)
        if not m:
            continue
        label = m.group(1)
        for lead in LEAD_NAMES:
            if label.startswith(lead):
                label = label[len(lead):].lstrip("的")
        if label and label not in FILLER + DESCRIBES + TEXT_ONLY and not re.match("(?:%s)$" % SCENE, label) and not any(s in label for s in SAYS):
            found.add(label)
    return sorted(found, key=len, reverse=True)


def person(clause, names):
    """Who the clause starts with. -> (name, sure, rest of the clause) or None."""
    t = bare(clause)
    for word in BESIDE:
        if t.startswith(word):
            t = t[len(word):]
            break
    for lead in LEAD_NAMES:
        if t.startswith(lead):
            rest = t[len(lead):].lstrip("的")
            role = next((n for n in names if rest.startswith(n)), None)
            if role:
                return role, role not in GROUPS and not any(m in rest.replace(role, "") for m in MANY), rest[len(role):]
            return LEAD, True, rest
    role = next((n for n in names if t.startswith(n)), None)
    if role:
        return role, role not in GROUPS and not any(m in t.replace(role, "") for m in MANY), t[len(role):]
    return None


def spoken_part(parts, names):
    """Speech at the end of a script line may be followed by more stage direction with no colon:
    「先放着。同学摇摇头，回自己座位继续打游戏。」 The speech ends where a later sentence starts with
    a person doing something. A person followed by a comma is being spoken to, and stays speech."""
    start = 0
    for j, clause in enumerate(parts):
        if j and start == j:                            # first clause of a sentence after the first
            t = bare(clause)
            hit = person(clause, names) or next(((n, True, t[len(n):]) for n in LEAD_NAMES if t.startswith(n)), None)
            if hit and hit[2] and not clause.strip().endswith(("，", ",", "！", "!", "？", "?")) or (hit and hit[2] and len(hit[2]) >= 2 and hit[2][0] not in "，,！!？?、"):
                return parts[:j], parts[j:]
        if clause.rstrip().endswith(tuple(END)):
            start = j + 1
    return parts, []


def speaker_of(parts, names):
    """parts: the clauses before a colon, last one nearest the colon. Walks back inside the last
    sentence. -> (index of the clause where the label starts, name, sure)."""
    start = len(parts) - 1
    while start > 0 and not parts[start - 1].rstrip().endswith(tuple(END)):
        start -= 1
    for j in range(len(parts) - 1, start - 1, -1):
        t = bare(parts[j])
        some = next((w for w in SOMEONE if t.startswith(w)), None)
        if some:
            hit = person(t[len(some):], names)
            if hit and hit[0] != LEAD:
                return j, hit[0], False
            earlier = "".join(parts[start:j])
            role = next((n for n in names if n in earlier), None)
            return (start if role else j), role or "", False
        hit = person(t, names)
        if hit:
            return j, hit[0], hit[1]
    return (start if start > 0 else len(parts) - 1), "", False


def reported(parts, names):
    """Speech reported without a colon inside narrative clauses: 说X / 主角说X."""
    out = []
    for j, clause in enumerate(parts):
        t = bare(clause)
        m = re.match(r"(.{0,8}?)(%s)(.{2,})$" % "|".join(SAYS), t)
        if not m or m.group(3).startswith(("话", "法", "明", "起", "到", "着", "了", "过", "的", "不")):
            continue
        who = None
        if m.group(1):
            hit = person(m.group(1), names)
            if hit and not hit[2]:
                who = hit[0]
            else:
                continue
        else:
            for k in range(j - 1, -1, -1):
                hit = person(parts[k], names)
                if hit:
                    who = hit[0]
                    break
                if parts[k].rstrip().endswith(tuple(END)):
                    break
        end = clause.strip()[-1] if clause.strip()[-1] in "？?！!" else ""
        out.append([(who or "") + "?", m.group(3) + end])
    return out


def lines_of(raw, names):
    """One line of a scene -> [[speaker, words], ...] in order."""
    raw = strip_notes(raw).strip()
    segs = re.split(r"[：:]", raw)
    out = []
    narrative = clauses(segs[0])
    for i in range(1, len(segs)):
        out += reported(narrative, names)
        j, who, sure = speaker_of(narrative, names) if narrative else (0, "", False)
        label = bare(narrative[-1]) if narrative else ""
        parts = clauses(segs[i])
        if label in DESCRIBES:                          # "画面：..." introduces description
            narrative = parts
            continue
        if label in TEXT_ONLY:
            who, sure = "旁白", True
        if i < len(segs) - 1:                           # the tail of this piece names the next speaker
            k, _, _ = speaker_of(parts, names)
            speech, narrative = parts[:k], parts[k:]
        else:
            speech, narrative = spoken_part(parts, names)
        said = "".join(speech).strip().rstrip("，,；;")
        if any(ch.isalnum() for ch in said):
            out.append([who + ("" if sure and who else "?"), said])
    out += reported(narrative, names)
    return out


def parse(text):
    """-> (head, scenes). A scene: title, date, script (its full text), lines, quoted."""
    blocks = re.split(r"(?m)^(?=(?:%s)[：:])" % SCENE, text)
    names = names_in(text)
    scenes = []
    for block in blocks[1:]:
        m = re.match(r"(%s)[：:]\s*(?:[（(]([^）)]*)[）)])?" % SCENE, block)
        body = block[m.end():]
        lines = []
        for raw in body.splitlines():
            if raw.strip():
                lines += lines_of(raw, names)
        scenes.append({"title": m.group(1), "date": (m.group(2) or "").strip(), "script": body.strip(), "lines": lines,
                       "quoted": re.findall(r"[“\"]([^”\"]+)[”\"]", body)})
    return blocks[0].strip(), scenes


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    head, scenes = parse(open(sys.argv[1], encoding="utf-8").read())
    print(head, "\n")
    for sc in scenes:
        print("%s  [%s]" % (sc["title"], sc["date"]))
        for who, said in sc["lines"]:
            print("   %-8s %s" % (who, said))
        for q in sc["quoted"]:
            print("   (quoted)  %s" % q)
