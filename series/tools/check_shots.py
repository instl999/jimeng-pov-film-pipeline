#!/usr/bin/env python3
"""Gate for an episode's shot file: nothing is generated from a file that fails this.

    python3 check_shots.py PROJECT_DIR EPISODE [--min 3000] [--exempt S02,S03] [--pending FILE,FILE] [--places NAME,NAME | --places all]

Checks every `## Sxx` section of PROJECT_DIR/shots/<EPISODE>.md:

  length   the shot's own writing is at least --min characters (default 3000, the owner's hard
           floor). Own writing = the section without the blocks every prompt repeats: the style
           sentence, the reference lines, the no-music sentence, the first-person sentence, the
           hands sentence from cast/我.md, and the fixed last line. Spaces are not counted.
  timing   the stages' seconds add up to the length in the table, and the stage count is right.
  refs     every {{alias}} in the prompt has its reference line, and every file the table names
           exists (the grey-box clip is optional; a previous shot's last frame is made during the run).
  lines    the words in Chinese quotation marks, taken together and in order, are exactly the
           shot's lines in post/lines/<shot>.txt. Quotation marks are for spoken words only; a
           stressed word goes in corner brackets.

--exempt names shots of a finished film that were written before the floor existed: they are still
checked for everything else, and listed as kept, but their length does not fail the run.

--pending names reference images that are planned but not made yet (before `film.py images --run`):
their absence is not a failure.

With --places it also counts each named place's description in cast/<place>.md (the paragraph
before the fixed layout block) against the same floor; `--places all` lists every place and fails
none, for places made before the rule.

Exit status 0 when everything passes, 1 otherwise.
"""
import os
import re
import sys

NO_MUSIC = "全片没有音乐、背景音乐、配乐、器乐、旋律和氛围铺底音，只有人声、环境声和动作音效。"
POV = ("全程第一人称主观视角单镜头、无剪辑，竖屏画面，镜头就是主人公的眼睛，视角宽，带轻微的头部晃动；"
       "以下分镜是同一条连续镜头路径上的阶段，不是切镜，不换机位。")
POV_TAILS = ["主人公的脸和身体不入画，只有主人公的双手从画面下沿正中伸入：",
             "主人公的脸和身体不入画；这一段主人公的双手垂在身侧或插在兜里，也不入画。"]
TAILS = ["画面中主人公全程不说话。",
         "声音只有角色台词、画外的主人公的声音、环境声和动作音效；不要生成 BGM，不要生成旁白字幕、台词字幕或对白字幕。",
         "声音只有角色台词、环境声和动作音效；不要生成 BGM，不要生成旁白字幕、台词字幕或对白字幕。"]
MEDIA = "整张画面是真人实拍的写实照片质感。"


def count(text):
    return len(re.sub(r"\s", "", text))


def spoken(text):
    return "".join(ch for ch in text if ch.isalnum())


def hands(project):
    path = os.path.join(project, "cast", "我.md")
    out = []
    if os.path.isfile(path):
        for line in open(path, encoding="utf-8"):
            m = re.match(r"\s+- [^：]*年[^：]*：(.+)", line)
            if m:
                out.append(m.group(1).strip())
    return out


def own_writing(section, fixed):
    keep = []
    for line in section.splitlines():
        if line.startswith("基础视觉风格：") or line.startswith("画面具体需要展示的内容") or line.startswith("{{"):
            continue
        keep.append(line)
    text = "\n".join(keep)
    for block in fixed:
        text = text.replace(block, "")
    return text


def main():
    argv = sys.argv[1:]
    takes_value = ("--min", "--places", "--exempt", "--pending")
    args = [a for i, a in enumerate(argv) if not a.startswith("--") and not (i and argv[i - 1] in takes_value)]
    if len(args) != 2:
        sys.exit(__doc__)
    project, episode = os.path.abspath(args[0]), args[1]

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    floor = int(opt("--min", "3000"))
    places = opt("--places")
    exempt = set((opt("--exempt") or "").split(",")) - {""}
    pending = set((opt("--pending") or "").split(",")) - {""}
    text = open(os.path.join(project, "shots", episode + ".md"), encoding="utf-8").read()
    fixed = [NO_MUSIC, POV] + POV_TAILS + hands(project) + TAILS

    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and re.fullmatch(r"S\d\d", cells[0]):
            rows[cells[0]] = (int(re.match(r"(\d+)", cells[2]).group(1)),
                              [tuple(part.split("=", 1)) for part in cells[4].split("；") if "=" in part])
    pieces = re.split(r"(?m)^## (S\d\d)\s*$", text)[1:]
    sections = {pieces[i]: pieces[i + 1] for i in range(0, len(pieces), 2)}

    failed = 0
    total = 0
    print("%-4s %4s %8s  %s" % ("shot", "sec", "own", "result"))
    for sid in sorted(rows):
        seconds, refs = rows[sid]
        notes = []
        if sid not in sections:
            print("%-4s %4d %8s  no prompt section" % (sid, seconds, "-"))
            failed += 1
            continue
        sec = sections[sid]
        own = count(own_writing(sec, fixed))
        total += own
        kept = own < floor and sid in exempt
        if own < floor and not kept:
            notes.append("own writing %d is under the floor of %d" % (own, floor))
        stages = [int(x) for x in re.findall(r"(?m)^分镜\d+：(\d+)秒：", sec)]
        said = re.search(r"生成一个由以下(\d+)个分镜组成的视频", sec)
        if sum(stages) != seconds:
            notes.append("stages add up to %d s, the table says %d s" % (sum(stages), seconds))
        if not said or int(said.group(1)) != len(stages):
            notes.append("the prompt announces %s stages, there are %d" % (said.group(1) if said else "no", len(stages)))
        used = set(re.findall(r"\{\{([^}]+)\}\}", sec))
        declared = set(re.findall(r"(?m)^\{\{([^}]+)\}\}", sec))
        if used - declared:
            notes.append("no reference line for %s" % "、".join(sorted(used - declared)))
        for alias, path in refs:
            if alias not in ("预演", "前段尾帧") and path not in pending and not os.path.isfile(os.path.join(project, path)):   # the last frame is made during the run
                notes.append("reference file missing: %s" % path)
        lines_path = os.path.join(project, "post", "lines", sid + ".txt")
        if os.path.isfile(lines_path):
            want = spoken(open(lines_path, encoding="utf-8").read())
            got = spoken("".join(re.findall(r"“([^”]*)”", sec)))
            if want != got:
                n = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b), min(len(want), len(got)))
                notes.append("quoted words differ from post/lines/%s.txt from character %d: lines …%s… prompt …%s…"
                             % (sid, n, want[max(0, n - 6):n + 8], got[max(0, n - 6):n + 8]))
        else:
            notes.append("no line file post/lines/%s.txt" % sid)
        failed += bool(notes)
        print("%-4s %4d %8d  %s" % (sid, seconds, own, "; ".join(notes) or ("kept as written (older than the floor)" if kept else "pass")))
    print("%d shots, %d s, %d characters of own writing; %d failed" % (len(rows), sum(r[0] for r in rows.values()), total, failed))

    if places:
        print("\n%-16s %8s  %s" % ("place", "own", "result"))
        names = None if places == "all" else set(places.split(","))
        cast = os.path.join(project, "cast")
        for name in sorted(f[:-3] for f in os.listdir(cast) if f.endswith(".md")):
            body = open(os.path.join(cast, name + ".md"), encoding="utf-8").read()
            if "- 锚点物：" not in body or (names is not None and name not in names):
                continue
            paras = [p for p in body.split("\n\n") if p.strip().endswith(MEDIA) and not p.lstrip().startswith(("{{", "#"))]
            own = count(paras[0].replace(MEDIA, "")) if paras else 0
            short = own < floor
            if short and names is not None:
                failed += 1
            print("%-16s %8d  %s" % (name, own, "pass" if not short else
                                      ("under the floor of %d" % floor) + ("" if names is not None else " (listed only)")))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
