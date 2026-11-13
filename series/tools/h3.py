#!/usr/bin/env python3
"""The second generation engine for film.py: MiniMax H3 in ComfyUI on a rented AutoDL Art GPU.

A film chooses it with "engine": "h3" in film.json (the default engine is "jimeng"). Everything
else in the film file stays as it is; the engine adds what H3 needs:

  "h3": {"app": "x3iDTgpUSm", "version": "v2", "gpu": "pro6000-p", "price": 8.8,
         "budget_yuan": 40, "steps": 20, "turbo": false}
  "styles_en": {"cold": "..."}, "hands_en": {"2001": "..."}
  people.<name>.en, places.<name>.en, places.<name>.sound_en      one or two English sentences each
  shots[].h3: {"summary": "...", "body": "..."}                   the shot in H3's own prompt language

H3 is prompted in English in a fixed six-part form (MiniMax's full-reference guide): subject
definitions, a summary, a retention analysis, a detailed description, the soundscape, the music.
The runner writes the parts that follow from the film file and takes `summary` and `body` from the
shot. In `body`, write {名字} for a person or place of the shot (it becomes its <Subject N> label),
give every voice its (S1), (S2) id, and put each spoken line, word for word, inside
<d>[Chinese] ...</d>. MiniMax's guide says a detailed description normally runs 350 to 500 English
words; nothing is gained by pushing the model's prompt far past that.

The hard rule for this engine: every scene, including its shooting script, storyboard notes and
visual prompts, totals at least 8,000 words. It is applied per
shot, like the 3,000 rule: the shot's own Chinese writing (place block, setup, stages, ending,
notes) plus its H3 summary and body, counting a Chinese character as one and an English word as
one, must reach 8,000. The Chinese layer is the shooting script and storyboard; the H3 prompt is
written from it.

Facts about the model are in comfy.py; renting and returning the GPU is autodl.py.
"""
import os
import re
import subprocess
import time

FLOOR = 8000
MAX_SECONDS = 15
SIZE = (768, 1344)
BOOT_MINUTES = 3                # instance ready in about a minute, then 44 GB of weights load on the first clip
STEP_SECONDS = 31.4             # one sampling step of a 243-frame (10 s) clip at 768x1344 on a PRO6000-96G, measured 2026-11-13
STEP_FRAMES = 243               # time per step grows with the square of the frame count: a 7 s clip measured 16 s a step
SKIP_REFS = ("预演", "主人公的声音")
CHAIN = "前段尾帧"


def words(text):
    """A Chinese character counts one, an English word or a number counts one."""
    return len(re.findall(r"[㐀-鿿豈-﫿]", text)) + len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", text))


def config(film):
    cfg = {"steps": 20, "turbo": False, "version": "latest"}
    cfg.update(film.d.get("h3", {}))
    return cfg


def spoken(body):
    """The words inside <d> tags, in order, without the language tag."""
    return [re.sub(r"^\s*\[[^\]]*\]\s*", "", m) for m in re.findall(r"<d>(.*?)</d>", body, re.S)]


def package(film, sc, sh):
    """-> (Chinese layer, H3 layer) in words for one shot."""
    place = film.d["places"][sc["place"]]
    chinese = "".join(place.get("block", []) + sh.get("setup", []) + [sh.get("track", ""), sh.get("ending", ""), sh.get("hands_note", "")]
                      + [st["text"] for st in sh.get("stages", [])] + sh.get("notes", []) + sh.get("must", []) + sh.get("must_not", []))
    if "raw" in sh:
        chinese = sh["raw"]
    spec = sh.get("h3", {})
    return words(chinese), words(spec.get("summary", "") + " " + spec.get("body", ""))


def problems(film):
    d, out = film.d, []
    cfg = config(film)
    if d.get("floor", FLOOR) < FLOOR:
        out.append("an H3 film's floor is %d (the owner's hard rule); film.json says %s" % (FLOOR, d.get("floor")))
    for key in ("app", "gpu", "price", "budget_yuan"):
        if not cfg.get(key):
            out.append("h3.%s is not set" % key)
    for sc in d["scenes"]:
        if not d.get("styles_en", {}).get(sc.get("style", "default")):
            out.append("%s: styles_en has no English style sentence for %r" % (sc["id"], sc.get("style", "default")))
        place = d["places"].get(sc.get("place"), {})
        for key in ("en", "sound_en"):
            if not place.get(key):
                out.append("%s: place %s has no \"%s\"" % (sc["id"], sc.get("place"), key))
        for sh in sc.get("shots", []):
            sid, spec = sh.get("id", "?"), sh.get("h3", {})
            if isinstance(sh.get("seconds"), int) and sh["seconds"] > MAX_SECONDS:
                out.append("%s: %d s is longer than an H3 clip can be (%d s)" % (sid, sh["seconds"], MAX_SECONDS))
            if sh.get("hands_visible", True) and sc.get("hands") and not d.get("hands_en", {}).get(sc["hands"]):
                out.append("%s: hands_en has no English description of my hands for %r" % (sid, sc["hands"]))
            for alias in sh.get("people", {}):
                if not d["people"].get(alias, {}).get("en"):
                    out.append("%s: person %s has no \"en\"" % (sid, alias))
            if not spec.get("summary") or not spec.get("body"):
                out.append("%s: no h3.summary / h3.body" % sid)
                continue
            body = spec["body"]
            for alias in re.findall(r"\{([^{}]+)\}", body):
                if alias not in sh.get("people", {}) and alias != sc.get("place"):
                    out.append("%s: h3.body names {%s}, which is not a person or the place of this shot" % (sid, alias))
            want = "".join(ch for part in film.subtitle_parts(sh) for ch in part if ch.isalnum())
            got = "".join(ch for line in spoken(body) for ch in line if ch.isalnum())
            if want != got:
                out.append("%s: the lines inside <d> in h3.body are not the shot's lines word for word" % sid)
            if re.search(r"<d>(?!\s*\[)", body):
                out.append("%s: a <d> in h3.body has no language tag, e.g. <d>[Chinese] ...</d>" % sid)
            if len(re.findall(r"[A-Za-z][A-Za-z'’\-]*", body)) < 250:
                out.append("%s: h3.body is under 250 English words; MiniMax's guide asks for 350 to 500" % sid)
    return out


def prompt(film, sc, sh, n):
    """The six-part prompt for one shot, and the reference images in <Picture N> order."""
    d = film.d
    refs = [(alias, path) for alias, path, _ in film.refs(sc, sh, n, "h3") if alias not in SKIP_REFS]
    picture = {alias: i + 1 for i, (alias, _) in enumerate(refs)}
    defs, keep, subject = [], [], {}
    for alias in sh.get("people", {}):
        subject[alias] = len(subject) + 1
        defs.append("<Subject %d> is the person in <Picture %d>: %s <Picture %d> is a character sheet showing the same person in "
                    "several views on a plain background; take the face, hair and clothing from it, not the pose or the background."
                    % (subject[alias], picture[alias], d["people"][alias]["en"].rstrip(), picture[alias]))
        keep.append("<Subject %d> (appears in [Shot 1]): fully_preserved - the face, hair and clothing are retained." % subject[alias])
    place = d["places"][sc["place"]]
    subject[sc["place"]] = len(subject) + 1
    views = [picture[sc["place"]]] + [picture[e["alias"]] for e in sh.get("extra_views", []) if e["alias"] in picture]
    defs.append("<Subject %d> is the location in %s: %s" % (subject[sc["place"]], " and ".join("<Picture %d>" % v for v in views), place["en"].rstrip()))
    keep.append("<Subject %d> (appears in [Shot 1]): partially_preserved - the layout, furnishings, materials and light are retained; "
                "the framing is new and the people in the shot are added." % subject[sc["place"]])
    task = "[reference generation]"
    if CHAIN in picture:
        defs.append("<Picture %d> is the first frame of [Shot 1]: the last frame of the previous clip, fixing where everyone stands, "
                    "what they wear and the light." % picture[CHAIN])
        keep.append("<Picture %d> ([Shot 1] first frame): fully_preserved - positions, clothing and light carry over; the camera then moves on."
                    % picture[CHAIN])
        task = "[keyframe completion + reference generation]"
    body = re.sub(r"\{([^{}]+)\}", lambda m: "<Subject %d>" % subject[m.group(1)], sh["h3"]["body"].strip())
    hands = ("only his two hands enter the frame from the bottom edge: %s" % d["hands_en"][sc["hands"]].rstrip()
             if sh.get("hands_visible", True) else "his hands stay out of frame as well.")
    pov = ("The whole clip is one continuous first-person shot with no cuts: the camera is the protagonist's own eyes at eye height, a wide "
           "field of view with slight natural head movement. His face and body never appear; %s" % hands)
    text = "\n".join([
        "subject_definitions:", "\n".join(defs), "",
        "summary:", "%s %s" % (task, sh["h3"]["summary"].strip()), "",
        "retention_analysis:", "\n".join(keep), "",
        "detailed_description:", "%s %s" % (d["styles_en"][sc.get("style", "default")].rstrip(), pov), "[Shot 1] " + body, "",
        "overall_soundscape:", place["sound_en"].strip(), "",
        "non_diegetic_music:", "N/A"])
    return text, [path for _, path in refs]


def gate(film):
    """The 8,000 rule, shot by shot. -> 0 when every shot passes."""
    floor, rc = max(FLOOR, film.d.get("floor", FLOOR)), 0
    print("\n%-4s %8s %8s %8s  %s" % ("shot", "中文", "H3", "total", "8,000 rule (H3 engine)"))
    for sc, sh, _ in film.shots():
        cn, en = package(film, sc, sh)
        ok = cn + en >= floor
        rc = rc or (0 if ok else 1)
        print("%-4s %8d %8d %8d  %s" % (sh["id"], cn, en, cn + en, "pass" if ok else "under the floor of %d" % floor))
    return rc


def shot_minutes(cfg, seconds):
    """Minutes of GPU time one take of a shot needs, from the timings measured on the first real clips."""
    if cfg.get("minutes_per_shot"):
        return float(cfg["minutes_per_shot"])
    frames = max(5, int(round(seconds * 24)))
    frames += (5 - frames % 17) % 17
    return ((4 if cfg["turbo"] else cfg["steps"]) * STEP_SECONDS * (frames / float(STEP_FRAMES)) ** 2 + 45) / 60.0


def budget_line(film):
    cfg = config(film)
    minutes = BOOT_MINUTES + sum(shot_minutes(cfg, sh["seconds"]) for _, sh, _ in film.shots()) * (1 + film.d.get("reroll_rate", 0.3))
    return minutes, minutes / 60.0 * float(cfg.get("price") or 0)


def spent_yuan(film):
    """Yuan of GPU time this film has used: the rentals it started, at their final cost where the ledger has one."""
    import autodl
    leases = dict(film.state.get("gpu_leases", {}))
    if leases and os.path.isfile(autodl.LEDGER):
        import json
        for line in open(autodl.LEDGER, encoding="utf-8"):
            entry = json.loads(line)
            if entry.get("uuid") in leases:
                leases[entry["uuid"]] = entry["yuan"]
    return round(sum(leases.values()), 2)


def trim(ffmpeg, raw, dest, seconds):
    """An H3 clip is 17k+5 frames, a little over the whole second asked for: cut it to length."""
    return subprocess.run([ffmpeg, "-v", "error", "-y", "-i", raw, "-t", str(seconds), "-c:v", "libx264", "-crf", "14", "-preset", "medium",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", dest]).returncode == 0


def draft(film, only, run, keep, tools):
    """Generate the shots that are due. tools: the film.py module (state, QC and last-frame helpers)."""
    import autodl
    import comfy
    d, cfg = film.d, config(film)
    spent = spent_yuan(film)
    left = float(cfg["budget_yuan"]) - spent
    todo = []
    for sc, sh, n in film.shots():
        st = film.shot_state(sh["id"])
        if (sh["id"] in only) if only else st["status"] not in ("drafted", "accepted"):
            todo.append((sc, sh, n))
    minutes = BOOT_MINUTES + sum(shot_minutes(cfg, sh["seconds"]) for _, sh, _ in todo)
    print("%d shot(s) on MiniMax H3; %s at %.2f yuan an hour; about %d minutes, about %.1f yuan; %.2f of %.2f yuan spent%s"
          % (len(todo), cfg["gpu"], cfg["price"], minutes, minutes / 60.0 * cfg["price"], spent, cfg["budget_yuan"], "" if run else "  (dry run)"))
    for sc, sh, n in todo:
        print("  %-4s %2ds  about %4.1f min  try %d of %d" % (sh["id"], sh["seconds"], shot_minutes(cfg, sh["seconds"]),
                                                          film.shot_state(sh["id"])["tries"] + 1, tools.MAX_TRIES))
    if not run or not todo:
        return 0
    if left <= 0:
        print("stopping: the GPU budget of %.2f yuan is used up" % cfg["budget_yuan"])
        return 1
    out_dir = film.path("out", film.episode)
    os.makedirs(out_dir, exist_ok=True)
    rc, lease = 0, None
    try:
        lease = autodl.up(cfg["app"], cfg["gpu"], float(cfg["price"]), left, name="film-" + film.episode, version=cfg["version"])
        server = comfy.Comfy(lease["comfy"])
        stats = server.wait_ready(timeout=900)
        autodl.touch()
        print("ComfyUI %s is up at %s" % (stats.get("system", {}).get("comfyui_version", "?"), lease["comfy"]))
        for sc, sh, n in todo:
            sid, st = sh["id"], film.shot_state(sh["id"])
            if st["tries"] >= tools.MAX_TRIES:
                print("  %s: three tries used; it needs a person to look at it" % sid)
                continue
            text, paths = prompt(film, sc, sh, n)
            chain = [p for p in paths if p.endswith(".last.png")]
            if chain and not os.path.isfile(film.path(chain[0])) and not tools.last_frame(film, sc["shots"][n - 1]["id"]):
                print("  %s waits for %s, which has no clip yet" % (sid, sc["shots"][n - 1]["id"]))
                continue
            raw, dest = os.path.join(out_dir, sid + ".h3.mp4"), os.path.join(out_dir, sid + ".mp4")
            print("%s  %ds" % (sid, sh["seconds"]))
            st["tries"] += 1
            try:
                _, seed, took = server.h3_clip(text, sh["seconds"], [film.path(p) for p in paths], raw, beat=autodl.touch, size=SIZE,
                                               steps=cfg["steps"], turbo=cfg["turbo"])
                ok = trim(tools.FFMPEG, raw, dest, sh["seconds"])
            except comfy.ComfyError as err:
                print("  failed: %s" % err)
                ok, seed, took = False, None, 0
            autodl.touch()
            st.update(status="drafted" if ok else "failed", seed=seed, took=round(took))
            st.pop("checks", None)
            film.save_state()
            if ok:
                print("  done in %.0f s" % took)
                tools.last_frame(film, sid)
                tools.qc_shot(film, sc, sh)
                film.save_state()
            else:
                rc = 1
    except (autodl.AutoDLError, comfy.ComfyError) as err:
        print("stopped: %s" % err)
        rc = 1
    finally:
        held = autodl.load()
        if held and lease is None:
            lease = held                                  # it was created but never came up
        if lease:
            leases = film.state.setdefault("gpu_leases", {})
            if held and keep and rc == 0:
                leases[lease["uuid"]] = autodl.cost(held)
                print("the GPU is kept, as asked; it gives itself back after 15 idle minutes (or now: autodl.py down)")
            else:
                leases[lease["uuid"]] = autodl.down(why="batch finished") if held else leases.get(lease["uuid"], autodl.cost(lease))
            film.state["gpu_yuan"] = round(sum(leases.values()), 2)
        film.save_state()
    return rc
