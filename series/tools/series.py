#!/usr/bin/env python3
"""series.py: a run of first-person scripts made into films that all share one look and feel.

    python3 film.py series SERIES                       every episode: where it stands, what it spent; the run against its cap
    python3 film.py series SERIES intake [SCRIPT ...]   the scripts (default: SERIES/story/E*.txt, in order) -> SERIES/E01, E02 ...
    python3 film.py series SERIES check                 the gate on every episode, and that none of them drifts from the series
    python3 film.py series SERIES budget                every episode priced; the total against the run's cap
    python3 film.py series SERIES approve "their words" [--episodes E01,E02]
                                                        the owner's one sign-off, recorded on every episode it covers
    python3 film.py series SERIES run [--run] [--episodes E01,E02]
                                                        reference images, then shots, episode by episode, until the cap
    python3 film.py series SERIES summary              RUN.md: the whole run on one page, for the owner's sign-off
    python3 film.py series SERIES upscale [--run]       finish "sample_up": every passed shot enlarged to 1080p
    python3 film.py series SERIES compose [--final] [--episodes ...]   cut every episode whose shots are all in
    python3 film.py series SERIES cover [--run] [--episodes ...]       covers for every accepted episode

The folder:

    SERIES/series.json     the series' look and the run's credit cap: the one file the look is written in
    SERIES/story/E01.txt   the scripts, one per episode, in order (or given on the command line)
    SERIES/E01/film.json   one film per script, written as usual; its "series": ".." makes it read series.json

What the series locks. Every key below that series.json sets is taken from there by every episode, at load
time; an episode's film.json that sets one of them to something else fails `check` (it would drift):

    camera, engine, finish, h3, notice, titles, end_card, floor, place_floor, reroll_rate,
    lead_voice, lead_voice_en, lead_voice_sample

and "look" (and "look_en" for H3): one sentence, the visual language every shot and every reference image
shares (medium, film stock, grain, lens, grade). It is put in front of each style an episode writes, so an
episode's styles only add what is its own (era, palette, light). The text on screen was already locked for
the whole series (series/text-styles.json).

What stays the episode's own: its title and premise lines, scenes and shots, styles, hands, people and
places. An anthology (a different "me" and world each time) writes those fresh per episode. A continuing
story sets "continuing": true, and each episode is taken in from the one before it (`intake --like`), so the
same people, places, hands and reference pictures carry over; `check` then flags a person or place whose
picture differs from an earlier episode's.

Money: series.json "budget" is the cap for the whole run. Each episode's own cap becomes what is left of it
after every other episode's spending (or its own "budget", if that is lower), so the runner's per-film stops
hold the run to the one number. Covers keep their own small per-film cap, as before.
"""
import glob
import hashlib
import json
import os
import re
import sys

LOCKED = ("camera", "engine", "finish", "h3", "notice", "titles", "end_card", "floor", "place_floor", "reroll_rate",
          "lead_voice", "lead_voice_en", "lead_voice_sample")
FILE = "series.json"
TEMPLATE = {
    "title": "",
    "look": "",
    "camera": "first",
    "engine": "jimeng",
    "finish": "720p",
    "notice": "AI 生成 · 虚构剧情",
    "titles": {"premise_seconds": 7, "date_seconds": 4},
    "end_card": None,
    "floor": 3000,
    "reroll_rate": 0.3,
    "lead_voice": "",
    "continuing": False,
    "budget": None,
}
EPISODE = re.compile(r"^E\d{2,3}$")


def die(msg):
    sys.exit("series: " + msg)


# ------------------------------------------------------------------ the series file, applied to a film
def series_dir(film_dir, d):
    return os.path.normpath(os.path.join(film_dir, d["series"]))


def read(folder):
    path = os.path.join(folder, FILE)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def is_set(s, key):
    """A key series.json leaves empty ("" for a voice) is the episode's own; null is a value (end_card: none)."""
    return key in s and s[key] != ""


def episodes(folder):
    """-> [(episode id, its folder)] in order, for every episode folder that has a film.json."""
    out = []
    for path in sorted(glob.glob(os.path.join(folder, "E*", "film.json"))):
        name = os.path.basename(os.path.dirname(path))
        if EPISODE.match(name):
            out.append((name, os.path.dirname(path)))
    return out


def spent_in(project):
    path = os.path.join(project, ".film", "state.json")
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("spent", 0)
    except (OSError, ValueError):
        return 0


def with_look(look, text):
    if not look:
        return text
    if text.startswith(look):
        return text
    return look + ("；" + text if text else "")


def apply(film):
    """Called by film.Film when film.json says "series": "..". Overlays the locked keys and the look, sets the
    run's remaining cap, and records every drift in film.series_drift (reported by Film.problems)."""
    d = film.d
    folder = series_dir(film.project, d)
    s = read(folder)
    film.series_dir, film.series = folder, s
    film.series_drift = []
    if s is None:
        film.series_drift.append("\"series\" points at %s, which has no %s" % (folder, FILE))
        return
    if not s.get("look"):
        film.series_drift.append("%s has no \"look\": one sentence every shot and image of the series shares" % os.path.join(folder, FILE))
    for key in LOCKED:
        if not is_set(s, key):
            continue
        if key in d and d[key] != s[key]:
            film.series_drift.append("\"%s\" is locked by the series (%s says %s); delete it from this film.json"
                                     % (key, FILE, json.dumps(s[key], ensure_ascii=False)))
        d[key] = s[key]
    if s.get("look"):
        d["styles"] = {name: with_look(s["look"], text or "") for name, text in (d.get("styles") or {}).items()}
    if s.get("look_en") and d.get("styles_en"):
        d["styles_en"] = {name: with_look(s["look_en"], text or "") for name, text in d["styles_en"].items()}
    if s.get("budget") is not None:
        others = sum(spent_in(p) for _, p in episodes(folder) if os.path.abspath(p) != film.project)
        left = s["budget"] - others
        d["budget"] = left if d.get("budget") is None else min(d["budget"], left)


# ------------------------------------------------------------------ commands
def films(folder, only=None):
    import film as F
    out = []
    for ep, path in episodes(folder):
        if only and ep not in only:
            continue
        out.append((ep, F.Film(path)))
    if only and set(only) - {ep for ep, _ in out}:
        die("no such episode: %s" % ", ".join(sorted(set(only) - {ep for ep, _ in out})))
    return out


def guarded(fn, *args):
    """Run one film command; a refusal (film.die) stops that episode, not the run. -> exit code."""
    try:
        return fn(*args) or 0
    except SystemExit as stop:
        if stop.code not in (None, 0):
            print(stop.code if isinstance(stop.code, str) else "stopped with code %s" % stop.code)
            return 1
        return 0


def need_series(folder):
    s = read(folder)
    if s is None:
        die("%s has no %s yet: run `film.py series %s intake` first" % (folder, FILE, folder))
    return s


def cmd_intake(folder, scripts):
    import film as F
    os.makedirs(folder, exist_ok=True)
    s = read(folder)
    if s is None:
        with open(os.path.join(folder, FILE), "w", encoding="utf-8") as handle:
            json.dump(TEMPLATE, handle, ensure_ascii=False, indent=1)
        s = dict(TEMPLATE)
        print("wrote %s: fill in \"title\" and \"look\" (and \"budget\" once the owner gives a cap)" % os.path.join(folder, FILE))
    if not scripts:
        scripts = sorted(glob.glob(os.path.join(folder, "story", "E*.txt")) + glob.glob(os.path.join(folder, "story", "E*.md"))
                         + glob.glob(os.path.join(folder, "story", "E*.docx")))
        scripts = [p for p in scripts if not re.search(r"\.v\d+\.", os.path.basename(p))]   # an older draft kept beside it
    if not scripts:
        die("no scripts: put them in %s as E01.txt, E02.txt ... or name them on the command line" % os.path.join(folder, "story"))
    taken, rc = [], 0
    for n, script in enumerate(scripts, 1):
        m = re.search(r"E(\d{2,3})", os.path.basename(script))
        ep = "E%02d" % int(m.group(1)) if m else "E%02d" % n
        project = os.path.join(folder, ep)
        if os.path.isfile(os.path.join(project, "film.json")):
            print("%s: already taken in (%s); left as it is" % (ep, os.path.relpath(script, folder)))
            continue
        if ep in taken:
            die("two scripts would both be %s; name them E01, E02 ..." % ep)
        like = None
        if s.get("continuing"):
            earlier = [(e, p) for e, p in episodes(folder) if e < ep]
            if earlier:
                prev = json.load(open(os.path.join(earlier[-1][1], "film.json"), encoding="utf-8"))
                if not prev.get("people") and not prev.get("places"):
                    print("%s: waits until %s has its people and places written, so they carry over; run intake again then" % (ep, earlier[-1][0]))
                    continue
                like = earlier[-1][1]
        print("== %s  %s%s" % (ep, os.path.relpath(script, folder), "  (carrying over %s)" % os.path.basename(like) if like else ""))
        code = guarded(F.cmd_intake, script, project, like, s.get("camera") if is_set(s, "camera") else None)
        if code:
            rc = 1
            continue
        path = os.path.join(project, "film.json")
        with open(path, encoding="utf-8") as handle:
            d = json.load(handle)
        d["episode"] = ep
        d["series"] = ".."
        for key in LOCKED + ("budget",):          # the series supplies these; an episode keeps only its own story
            if is_set(s, key) or key == "budget":
                d.pop(key, None)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(d, handle, ensure_ascii=False, indent=1)
        taken.append(ep)
    print("taken in: %s" % (", ".join(taken) or "none"))
    return rc


def fingerprint(path):
    with open(path, "rb") as handle:
        return hashlib.sha1(handle.read()).hexdigest()[:12]


def cast_drift(folder, eps):
    """For a continuing series: a person or place picture that differs from the same name in an earlier episode."""
    seen, out = {}, []
    for ep, f in eps:
        cast = f.path("cast")
        for name in sorted(os.listdir(cast)) if os.path.isdir(cast) else []:
            if not name.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            mark = fingerprint(os.path.join(cast, name))
            if name in seen and seen[name][1] != mark:
                out.append("%s: cast/%s is not the picture %s used; the same person or place must look the same" % (ep, name, seen[name][0]))
            seen.setdefault(name, (ep, mark))
    return out


def cmd_check(folder):
    import film as F
    s = need_series(folder)
    eps = films(folder)
    if not eps:
        die("no episodes yet: film.py series %s intake" % folder)
    rows, rc = [], 0
    for ep, f in eps:
        print("\n== %s" % ep)
        code = guarded(F.cmd_check, f)
        rows.append((ep, "pass" if not code else "fails", len(f.series_drift)))
        rc = rc or code
    print("\n== the series")
    problems = []
    if not s.get("look"):
        problems.append("series.json has no \"look\"")
    for ep, f in eps:
        if f.d.get("series") is None:
            problems.append("%s: its film.json has no \"series\": \"..\", so it does not read the series look" % ep)
        problems += ["%s: %s" % (ep, line) for line in f.series_drift]
    if s.get("continuing"):
        problems += cast_drift(folder, eps)
    looks = {ep: (f.camera, f.engine, f.d.get("finish"), f.d.get("notice"), json.dumps(f.d.get("titles"), sort_keys=True)) for ep, f in eps}
    if len(set(looks.values())) > 1:
        problems.append("episodes differ in camera, engine, finish, notice or titles: %s" % looks)
    for line in problems:
        print("series: " + line)
    for ep, gate, drift in rows:
        print("%-4s %-6s %s" % (ep, gate, "drifts from the series" if drift else "matches the series"))
    print("%d episode(s), %d failing the gate, %d series problem(s)" % (len(rows), sum(1 for r in rows if r[1] != "pass"), len(problems)))
    return 1 if rc or problems else 0


def cmd_budget(folder):
    import film as F
    s = need_series(folder)
    total, rc, spent = 0, 0, 0
    for ep, f in films(folder):
        print("\n== %s" % ep)
        guarded(F.cmd_budget, f)
        total += price(F, f)
        spent += f.state.get("spent", 0)
    cap = s.get("budget")
    print("\nthe run: about %d credits for every episode still to make (chosen finish, re-takes and images included); spent %d; cap %s"
          % (total, spent, cap if cap is not None else "not set"))
    if cap is None:
        print("no cap yet: put the owner's number in \"budget\" in series.json once they have given one (nothing can be generated before that)")
    elif spent + total > cap:
        print("the run is over its cap")
        rc = 1
    return rc


def price(F, f):
    """Credits the chosen finish needs for what is still to make in one episode (re-takes and images included)."""
    d = f.d
    todo = [sh for _, sh, _ in f.shots() if f.shot_state(sh["id"])["status"] not in ("drafted", "accepted")]
    seconds = sum(sh["seconds"] for sh in todo)
    r = d.get("reroll_rate", 0.3)
    images = len(F.missing_images(f)) * F.PRICE["image"]
    per = {"sample": F.PRICE["draft"] * (1 + r), "720p": F.PRICE["720p"] * (1 + r),
           "1080p": F.PRICE["draft"] * (1 + r) + F.PRICE["1080p"],
           "sample_up": F.PRICE["draft"] * (1 + r) + F.PRICE["upscale"]}.get(d.get("finish", F.DEFAULT_FINISH), F.PRICE["720p"] * (1 + r))
    return int(round(per * seconds + images)) if f.engine != "h3" else images


FINISH_ZH = {"720p": "720p 直出，合成时放大到 1080", "sample": "480p 样片，合成时放大到 1080", "1080p": "480p 样片，通过后导出 1080p",
             "sample_up": "480p 样片，看过通过的镜头用即梦快速超分到 1080p"}


def cmd_summary(folder):
    """RUN.md: the whole run on one page, for the owner's one sign-off. The full shot lists stay in each
    episode's shots/<episode>.md; the first episode's (the pilot) is sent in full as well."""
    import film as F
    s = need_series(folder)
    eps = films(folder)
    if not eps:
        die("no episodes yet: film.py series %s intake" % folder)
    out = ["# %s · 整批开拍前的一页" % (s.get("title") or os.path.basename(os.path.abspath(folder))), "",
           "## 全系列统一的东西（series.json）", "",
           "- 观感：%s" % (s.get("look") or "（还没写）"),
           "- 规格：%s" % FINISH_ZH.get(s.get("finish"), s.get("finish")),
           "- 角标：%s" % s.get("notice", ""),
           "- 主人公的声音：%s" % (s.get("lead_voice") or "每集各自写"),
           "- %s" % ("同一个故事连着拍：人物、场景和参考图一集接一集带下去" if s.get("continuing") else "每集独立：各自的主人公、人物和场景"),
           "- 整批积分上限：%s" % (s.get("budget") if s.get("budget") is not None else "还没定"), "",
           "| 集 | 片头 | 场 | 镜头 | 时长 | 台词 | 旁白 | 新做的图 | 约多少积分 | 进度 |", "|---|---|---|---|---|---|---|---|---|---|"]
    total, body = 0, []
    for ep, f in eps:
        d, written = f.d, not f.problems()
        shots = f.shots() if all(sc.get("shots") for sc in d.get("scenes", [])) else []
        seconds = sum(sh["seconds"] for _, sh, _ in shots)
        lines = sum(len(f.subtitle_parts(sh)) for _, sh, _ in shots)
        narr = [(sh["id"], sh["narration"][k]["text"]) for _, sh, _ in shots for k in ("open", "close") if sh.get("narration", {}).get(k)]
        images = [section for _, section, _, _, _ in F.missing_images(f)] if written else []
        cost = price(F, f) if written else 0
        total += cost
        out.append("| %s | %s | %d | %d | %d 分 %02d 秒 | %d 段 | %d | %d | %s | %s |" % (
            ep, " / ".join(d.get("premise") or []) or "（没写）", len(d.get("scenes", [])), len(shots), seconds // 60, seconds % 60,
            lines, len(narr), len(images), cost if written else "—", stage(F, f)))
        body += ["", "## %s　%s" % (ep, " / ".join(d.get("premise") or [])), ""]
        if not written:
            body += ["film.json 还在写（%d 处没过）；写完再看。" % len(f.problems())]
            continue
        for sc in d["scenes"]:
            n = len(sc.get("shots", []))
            body.append("- %s（%s）%s：%d 个镜头，%d 秒，台词 %d 段" % (sc.get("title", sc["id"]), sc.get("date", ""), sc.get("place", ""), n,
                                                              sum(sh["seconds"] for sh in sc.get("shots", [])),
                                                              sum(len(f.subtitle_parts(sh)) for sh in sc.get("shots", []))))
        changed = d.get("line_changes", [])
        body += ["", "改过的台词（真实人名换成描述等）：" if changed else "台词：照原稿一字不改。"]
        body += ["- %s 第 %d 句 → 「%s」（%s）" % (c["scene"], c["line"], c["now"], c.get("why", "")) for c in changed]
        body += ["", "只出字的旁白（可以删）：" + ("、".join("%s「%s」" % x for x in narr) if narr else "没有")]
        facts = d.get("facts") or {}
        if facts:
            body += ["", "屏幕上的数字和出处："] + ["- %s：%s" % kv for kv in facts.items()]
        if images:
            body += ["", "要新做的图：" + "、".join(images)]
        body.append("")
        body.append("完整分镜：%s/shots/%s.md" % (ep, ep))
    cap = s.get("budget")
    out += ["", "合计约 %d 积分（按上面的规格，含 30%% 重拍和新做的图），整批上限 %s。" % (total, cap if cap is not None else "还没定")]
    if cap is not None and total > cap:
        out.append("**超过上限了**：要么提高上限，要么先拍一部分。")
    out += body
    out += ["", "---", "", "确认就回一句话（比如「可以，开拍」），我会原话记下来；没确认之前什么都不生成。"]
    path = os.path.join(folder, "RUN.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")
    print("wrote %s: %d episode(s), about %d credits" % (path, len(eps), total))
    return 0


def cmd_approve(folder, words, only):
    import film as F
    need_series(folder)
    if not words.strip():
        die("approve needs the owner's own words, in quotes: it records their sign-off, it does not replace it")
    eps = films(folder, only)
    failing = []
    for ep, f in eps:
        if f.d.get("accepted"):
            continue
        print("\n== %s" % ep)
        if guarded(F.cmd_check, f) or f.series_drift:
            failing.append(ep)
    if failing:
        die("not signed: %s %s not pass the gate. Fix them, or sign the others with --episodes"
            % (", ".join(failing), "does" if len(failing) == 1 else "do"))
    for ep, f in eps:
        print("%s: " % ep, end="")
        guarded(F.cmd_approve, f, words)
    return 0


def cmd_run(folder, run, only):
    """Images, then shots, one episode after another. A refusal stops that episode; reaching the cap stops the run."""
    import film as F
    s = need_series(folder)
    if run and s.get("budget") is None:
        die("series.json has no \"budget\": nothing is generated before the owner has given a cap for the run")
    rc = 0
    for ep, _ in films(folder, only):
        f = F.Film(os.path.join(folder, ep))           # read again: the episodes before it have spent
        if f.d.get("accepted"):
            print("\n== %s  accepted; left as it is" % ep)
            continue
        print("\n== %s  (credits left for the run: %s)" % (ep, f.d.get("budget")))
        bad = f.problems()
        if bad:
            print("%s: film.json is not finished (%d problem(s): film.py check %s); skipped" % (ep, len(bad), f.project))
            rc = 1
            continue
        why = F.not_signed_off(f)
        if why:
            print("%s: not signed off as it stands (%s); skipped" % (ep, why[0]))
            rc = 1
            continue
        if guarded(F.cmd_images, f, run):
            print("%s: images stopped; its shots wait" % ep)
            rc = 1
            if run and stopped_on_cap(f, F):
                break
            continue
        if guarded(F.cmd_draft, f, set(), run, False):
            rc = 1
            if run and stopped_on_cap(f, F):
                print("the run's cap is reached; stopping here")
                break
    if run:
        print()
        cmd_status(folder)
    return rc


def stopped_on_cap(f, F):
    cap = f.d.get("budget")
    return cap is not None and f.state.get("spent", 0) + F.PRICE["image"] > cap


def cmd_upscale(folder, run, only):
    """Finish "sample_up": every passed shot of every episode enlarged to 1080p, until the run's cap."""
    import film as F
    s = need_series(folder)
    if s.get("finish") != "sample_up":
        die("upscale is for a series with \"finish\": \"sample_up\" in series.json")
    rc = 0
    for ep, _ in films(folder, only):
        f = F.Film(os.path.join(folder, ep))
        print("\n== %s" % ep)
        rc = guarded(F.cmd_upscale, f, run) or rc
    return rc


def cmd_compose(folder, final, only):
    import film as F
    need_series(folder)
    rc = 0
    for ep, f in films(folder, only):
        if final and not f.d.get("accepted"):
            print("%s: not accepted by the owner yet; no final cut" % ep)
            continue
        print("\n== %s" % ep)
        rc = guarded(F.cmd_compose, f, final, None) or rc
    return rc


def cmd_cover(folder, run, only):
    import film as F
    need_series(folder)
    rc = 0
    for ep, f in films(folder, only):
        if not f.d.get("accepted"):
            print("%s: covers wait until the owner accepts the cut" % ep)
            continue
        print("\n== %s" % ep)
        rc = guarded(F.cmd_cover, f, run) or rc
    return rc


def stage(F, f):
    """One phrase: where an episode stands."""
    ep = f.episode
    if f.d.get("accepted"):
        covers = all(os.path.isfile(f.path("out", "%s.cover.%s.jpg" % (ep, k))) for k in ("3x4", "4x3"))
        final = os.path.isfile(f.path("out", ep + ".mp4"))
        return "accepted%s%s" % (", final cut" if final else ", final cut to make", ", covers" if covers else "")
    if f.problems():
        return "film.json being written (%d problem(s))" % len(f.problems())
    if not f.state.get("signoff"):
        return "written; waiting for the owner's sign-off"
    shots = f.shots()
    done = sum(1 for _, sh, _ in shots if f.shot_state(sh["id"])["status"] in ("drafted", "accepted"))
    failed = sum(1 for _, sh, _ in shots if f.shot_state(sh["id"])["status"] == "failed")
    if F.missing_images(f):
        return "signed off; %d reference image(s) to make" % len(F.missing_images(f))
    if done < len(shots):
        return "shots %d of %d in%s" % (done, len(shots), ", %d failed" % failed if failed else "")
    looked = sum(1 for _, sh, _ in shots if f.shot_state(sh["id"]).get("checks", {}).get("look") == "pass")
    if looked < len(shots):
        return "all shots in; %d of %d looked at and passed" % (looked, len(shots))
    if os.path.isfile(f.path("out", ep + ".draft.mp4")):
        return "cut made; waiting for the owner"
    return "all shots passed; ready to compose"


def cmd_status(folder):
    import film as F
    s = need_series(folder)
    eps = films(folder)
    print("%s%s" % (s.get("title") or os.path.basename(os.path.abspath(folder)), "  (continuing story)" if s.get("continuing") else ""))
    print("look: %s" % (s.get("look") or "(not written yet)"))
    total = 0
    for ep, f in eps:
        spent = f.state.get("spent", 0)
        total += spent
        print("%-4s %6d credits  %-44s %s" % (ep, spent, stage(F, f), "".join(f.d.get("premise") or []) or f.d.get("title") or ""))
    waiting = [os.path.basename(p) for p in sorted(glob.glob(os.path.join(folder, "story", "E*.*")))
               if re.search(r"E(\d{2,3})", os.path.basename(p)) and not re.search(r"\.v\d+\.", os.path.basename(p))
               and "E%02d" % int(re.search(r"E(\d{2,3})", os.path.basename(p)).group(1)) not in {e for e, _ in eps}]
    if waiting:
        print("scripts not taken in yet: %s" % ", ".join(waiting))
    print("the run: spent %d of %s" % (total, s.get("budget") if s.get("budget") is not None else "no cap"))
    return 0


def main(rest):
    pos, flags, i = [], set(), 0
    opts = {}
    while i < len(rest):
        a = rest[i]
        if a in ("--episodes",):
            opts[a] = rest[i + 1] if i + 1 < len(rest) else ""
            i += 2
            continue
        if a.startswith("--"):
            flags.add(a)
        else:
            pos.append(a)
        i += 1
    if not pos:
        sys.exit(__doc__)
    folder, verb, args = pos[0], (pos[1] if len(pos) > 1 else "status"), pos[2:]
    only = [e.strip() for e in opts.get("--episodes", "").split(",") if e.strip()] or None
    if verb == "status":
        return cmd_status(folder)
    if verb == "intake":
        return cmd_intake(folder, args)
    if verb == "check":
        return cmd_check(folder)
    if verb == "budget":
        return cmd_budget(folder)
    if verb == "approve":
        return cmd_approve(folder, args[0] if args else "", only)
    if verb == "run":
        return cmd_run(folder, "--run" in flags, only)
    if verb == "upscale":
        return cmd_upscale(folder, "--run" in flags, only)
    if verb == "summary":
        return cmd_summary(folder)
    if verb == "compose":
        return cmd_compose(folder, "--final" in flags, only)
    if verb == "cover":
        return cmd_cover(folder, "--run" in flags, only)
    sys.exit(__doc__)
