#!/usr/bin/env python3
"""The second generation engine for film.py: MiniMax H3 in ComfyUI on a rented AutoDL Art GPU.

A film chooses it with "engine": "h3" in film.json (the default engine is "jimeng"). Everything
else in the film file stays as it is; the engine adds what H3 needs:

  "h3": {"gpu": "pro6000-p", "price": 8.8,
         "budget_yuan": 40, "steps": 20, "turbo": false}
  "styles_en": {"cold": "..."}, "hands_en": {"2001": "..."}
  people.<name>.en, places.<name>.en, places.<name>.sound_en      one or two English sentences each
  people.<name>.voice_en, lead_voice_en                           every speaking voice, in English
  shots[].h3: {"summary": "...", "body": "..."}                   the shot in H3's own prompt language

H3 is prompted in English in a fixed six-part form (MiniMax's full-reference guide): subject
definitions, a summary, a retention analysis, a detailed description, the soundscape, the music.
The runner writes the parts that follow from the film file and takes `summary` and `body` from the
shot. In `body`, write {名字} for a person or place of the shot (it becomes its <Subject N> label),
give every voice its (S1), (S2) id, and put each spoken line, word for word, inside
<d>[Chinese] ...</d>. Each voice id is described from people.<name>.voice_en and lead_voice_en, so a
person (and the unseen lead above all) keeps one voice from shot to shot; the runner also adds fixed
performance, movement and texture paragraphs (PERFORMANCE, MOTION, TEXTURE). MiniMax's guide says a detailed description normally runs 350 to 500 English
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
MAX_REFS = 9                    # U22's image slots
SIZE = (768, 1344)              # the graph built in comfy.py; U22 makes 832x1440 itself (0.5 MP, then a 1.5x second pass)
DEFAULT_APP = "spcwDDc6XW"      # autodl.art app 252, "MINIMAX-H3提速500高画质" (zealman); the default since 2026-11-13
DEFAULT_WORKFLOW = "U22-MiniMaxH3-多参考生视频-优化版"   # its saved workflow U22 (YZ金鱼); "" builds the plain graph instead
# U22 without its style LoRA (MysticXXX at 0.5). Bench of 2026-11-14, 4 shots x 3 settings against the
# Seedance 2.5 clips: with the LoRA the protagonist's knees and lap came into frame twice in four shots
# and shock was played as a grin; without it, as good as 24 full steps at 60% of the GPU time.
# Second bench, 2026-11-14 evening (S02, S03, same seeds): U22's sharpness-trained latent upscaler between
# the passes is a little crisper at the same GPU time; 16 steps, or the turbo LoRA at 0.8, cost 20-35% more
# and looked no better. The "clean film" upscaler on the same server does not load in that node.
SHARP_UPSCALER = "h3_upscaler_sharpness_2000steps_v0.1_fp32.safetensors"
DEFAULT_TUNING = {"style_lora": 0, "upscaler": SHARP_UPSCALER}
U22_PER_SECOND = 19.0            # GPU seconds per second of clip, U22 on a PRO6000-96G: 163 s for 7 s, 187 s for 10 s (2026-11-13)
U22_OVERHEAD = 120               # seconds a shot also spends on uploads, queueing and the download over the rental's link
BOOT_MINUTES = 3                # instance ready in about a minute, then 44 GB of weights load on the first clip
STEP_SECONDS = 31.4             # one sampling step of a 243-frame (10 s) clip at 768x1344 on a PRO6000-96G, measured 2026-11-13
STEP_FRAMES = 243               # time per step grows with the square of the frame count: a 7 s clip measured 16 s a step
# Applied to every H3 clip when it is fitted to length: U22's 4-step refine pass leaves skin and cloth
# waxy, and a light unsharp mask plus fine moving grain (the series' own 35mm look) reads as film
# rather than as smoothing. It cannot add detail the model did not make. 0 switches either off.
DEFAULT_POST = {"sharpen": 0.5, "grain": 5}
LEAD = "我"
# Fixed series text the builder adds to every H3 prompt (not counted in the 8,000 rule: it is the same
# in every shot). Written as what should be there, since H3 has no negative prompt.
PERFORMANCE = ("Performance: grounded, natural acting, as in a quiet realist film. Every line is spoken in full by its own speaker, "
               "at a natural conversational pace, and the feeling written beside it is carried in the voice itself: the breath before "
               "it, the pause inside it, a tightening throat, a crack, a voice that drops or lifts. Faces react in small, true ways: "
               "the eyes, brows and mouth move a little and then hold.")
MOTION = ("Movement: everything moves at real-life speed, smoothly and continuously. Each person does one thing at a time, finishes "
          "it, and is still between actions; hands move with weight and purpose; the camera turns and drifts slowly and steadily, "
          "like a person's head.")
TEXTURE = ("Image: sharp and finely detailed, natural skin with visible pores, fine lines and small blemishes, single strands of hair, "
           "the weave of fabric, real wear on every surface, and a fine, even film grain.")
DIALOGUE_MIX = ("The dialogue is recorded close and clear, well above the room sound, with the room's natural reverberation; every "
                "word is intelligible.")
SKIP_REFS = ("预演", "主人公的声音")
CHAIN = "前段尾帧"


def words(text):
    """A Chinese character counts one, an English word or a number counts one."""
    return len(re.findall(r"[㐀-鿿豈-﫿]", text)) + len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", text))


def config(film):
    cfg = {"steps": 20, "turbo": False, "version": "latest", "app": DEFAULT_APP, "workflow": DEFAULT_WORKFLOW, "refs": "jimeng",
           "tuning": dict(DEFAULT_TUNING), "post": dict(DEFAULT_POST)}
    cfg.update(film.d.get("h3", {}))
    return cfg


def spoken(body):
    """The words inside <d> tags, in order, without the language tag."""
    return [re.sub(r"^\s*\[[^\]]*\]\s*", "", m) for m in re.findall(r"<d>(.*?)</d>", body, re.S)]


def voices(film, sh):
    """-> {"S1": alias, ...}: who each voice id in h3.body is. Read from "{名字} (S1)" and "protagonist (S2)"
    in the body; h3.voices ({"S2": "母亲"}) names a voice the body does not tie to a person (a phone call)."""
    body = sh.get("h3", {}).get("body", "")
    out = {}
    for alias, sid in re.findall(r"\{([^{}]+)\}\s*\((S\d+)\)", body):
        out.setdefault(sid, alias)
    for sid in re.findall(r"protagonist\s*\((S\d+)\)", body, re.I):
        out.setdefault(sid, LEAD)
    out.update(sh.get("h3", {}).get("voices", {}))
    return out


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
    for key in ("app", "gpu", "price"):                 # the yuan cap is the owner's to give at Stop 1; draft --run asks for it
        if not cfg.get(key):
            out.append("h3.%s is not set" % key)
    for sc in d["scenes"]:
        for n, sh in enumerate(sc.get("shots", [])):
            try:
                count = len(prompt(film, sc, sh, n)[1])
            except Exception:                           # an incomplete shot; the checks below name what is missing
                count = 0
            if count > MAX_REFS:
                out.append("%s: %d reference images; U22 takes at most %d (drop an extra view)" % (sh.get("id", "?"), count, MAX_REFS))
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
            who = voices(film, sh)
            for sid_ in sorted(set(re.findall(r"\((S\d+)\)", body))):
                alias = who.get(sid_)
                if alias is None:
                    out.append("%s: h3.body uses voice %s but does not say whose it is (write \"{名字} (%s)\" or \"protagonist (%s)\", "
                               "or set h3.voices)" % (sid, sid_, sid_, sid_))
                elif alias == LEAD and not d.get("lead_voice_en"):
                    out.append("%s: the protagonist speaks but film.json has no \"lead_voice_en\" (his voice in English, the same "
                               "words in every shot)" % sid)
                elif alias != LEAD and not d["people"].get(alias, {}).get("voice_en"):
                    out.append("%s: %s speaks but has no \"voice_en\" (the voice in English: age, pitch, accent, pace)" % (sid, alias))
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
    for vid, alias in sorted(voices(film, sh).items(), key=lambda kv: int(kv[0][1:])):
        if alias == LEAD and d.get("lead_voice_en"):
            defs.append("(%s) is the protagonist's own voice, heard from just behind the camera, close and dry: %s"
                        % (vid, d["lead_voice_en"].rstrip()))
        elif alias in subject and d["people"].get(alias, {}).get("voice_en"):
            defs.append("(%s) is the voice of <Subject %d>: %s" % (vid, subject[alias], d["people"][alias]["voice_en"].rstrip()))
        elif d["people"].get(alias, {}).get("voice_en"):
            defs.append("(%s) is a voice heard but not seen: %s" % (vid, d["people"][alias]["voice_en"].rstrip()))
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
    pov = ("The whole clip is one continuous first-person shot with no cuts: the camera is the protagonist's own eyes at eye height, the "
           "natural, undistorted view of a 35mm lens, straight lines staying straight and faces keeping their true proportions, with "
           "slight natural head movement. His face and body never appear; %s" % hands)
    text = "\n".join([
        "subject_definitions:", "\n".join(defs), "",
        "summary:", "%s %s" % (task, sh["h3"]["summary"].strip()), "",
        "retention_analysis:", "\n".join(keep), "",
        "detailed_description:", "%s %s %s" % (d["styles_en"][sc.get("style", "default")].rstrip(), TEXTURE, pov), "[Shot 1] " + body,
        PERFORMANCE + " " + MOTION, "",
        "overall_soundscape:", place["sound_en"].strip() + " " + DIALOGUE_MIX, "",
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
    if cfg.get("workflow"):                         # U22: 12 steps at 0.5 MP, then 4 more at 1.5x
        return (U22_PER_SECOND * seconds + U22_OVERHEAD) / 60.0
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


def post_filter(post):
    """-> the ffmpeg video filter for DEFAULT_POST-style settings, or "" when both are off."""
    post = dict(DEFAULT_POST, **(post or {}))
    parts = []
    if float(post.get("sharpen") or 0) > 0:
        parts.append("unsharp=5:5:%.2f:5:5:0.0" % float(post["sharpen"]))
    if int(post.get("grain") or 0) > 0:
        parts.append("noise=c0s=%d:c0f=t+u" % int(post["grain"]))
    return ",".join(parts)


def trim(ffmpeg, raw, dest, seconds, post=None):
    """An H3 clip is 17k+5 frames, up to 0.4 s over the whole second asked for, and the model uses all
    of it: a last line often ends in that overhang. So the clip is not cut but played up to 3% faster
    (pitch kept) to fit the length exactly; the last word and the written last frame both survive. Most
    lengths need up to 5% (6 s needs 9.7%); post adds DEFAULT_POST's sharpening and grain."""
    import env
    probe = subprocess.run([env.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", raw], capture_output=True, text=True)
    try:
        have = float(probe.stdout.strip())
    except ValueError:
        have = float(seconds)
    rate = have / float(seconds)
    look = post_filter(post)
    if 1.0 < rate <= 1.10:                          # 6 s comes back as 158 frames (6.58 s); every other length is within 5%
        speed = ["-filter_complex", "[0:v]setpts=PTS/%.6f%s[v];[0:a]atempo=%.6f[a]" % (rate, "," + look if look else "", rate),
                 "-map", "[v]", "-map", "[a]", "-r", "24"]
    else:
        speed = ["-vf", look] if look else []
    return subprocess.run([ffmpeg, "-v", "error", "-y", "-i", raw] + speed + ["-t", str(seconds), "-c:v", "libx264", "-crf", "14", "-preset", "medium",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", dest]).returncode == 0


def ref_addresses(film, paths, tools, log=print):
    """The references as addresses the rented server fetches itself. Uploading straight to a rented
    server goes through its gateway at 1-3 KB/s (measured 2026-11-14: a 55 KB picture took 20-90 s
    and timed out half the time), while the server pulls from Jimeng's picture CDN at full speed. So
    each reference is shrunk to a JPEG of at most 1024 px, put on Jimeng as an asset (free, about
    20 s), and its signed address (valid about 15 days) kept in the state, keyed by the file's hash.
    -> list of addresses, or of the plain paths where an asset could not be made (those are then
    uploaded the slow way)."""
    import hashlib
    import json
    import shutil
    import tempfile
    cache = film.state.setdefault("ref_urls", {})
    out = []
    for path in paths:
        with open(path, "rb") as handle:
            digest = hashlib.sha1(handle.read()).hexdigest()
        hit = cache.get(digest)
        if hit and hit.get("expires", 0) > time.time() + 6 * 3600:
            out.append(hit["url"])
            continue
        work = tempfile.mkdtemp(prefix="h3-ref-")
        small = os.path.join(work, digest[:12] + ".jpg")
        try:
            subprocess.run([tools.FFMPEG, "-v", "error", "-y", "-i", path, "-vf",
                            "scale='min(1024,iw)':'min(1024,ih)':force_original_aspect_ratio=decrease", "-q:v", "3", small], check=False)
            rc, text = tools.cli(film, ["resource", "upload", "--file", small if os.path.isfile(small) else os.path.abspath(path), "--wait", "60", "-j"], timeout=180, tries=2)
            try:
                data = json.JSONDecoder().raw_decode(text[text.index("{"):])[0]["data"]
                url = data["previewUrl"]
            except (ValueError, KeyError, TypeError):
                url = None
        finally:
            shutil.rmtree(work, ignore_errors=True)
        if rc != 0 or not url or not url.startswith("https://"):
            log("  %s: could not put it on Jimeng; it will be uploaded to the server directly" % os.path.basename(path))
            out.append(path)
            continue
        m = re.search(r"x-expires=(\d+)", url)
        cache[digest] = {"url": url, "expires": int(m.group(1)) if m else int(time.time()) + 86400, "file": os.path.basename(path)}
        film.save_state()
        out.append(url)
    return out


def draft(film, only, run, keep, tools):
    """Generate the shots that are due. tools: the film.py module (state, QC and last-frame helpers)."""
    import autodl
    import comfy
    d, cfg = film.d, config(film)
    if run and not cfg.get("budget_yuan"):
        print("stopping: no GPU cap. The owner gives one at Stop 1; it goes in h3.budget_yuan")
        return 1
    spent = spent_yuan(film)
    left = float(cfg.get("budget_yuan") or 0) - spent
    todo, due = [], set()
    for sc, sh, n in film.shots():
        st = film.shot_state(sh["id"])
        if not ((sh["id"] in only) if only else st["status"] not in ("drafted", "accepted")):
            continue
        if st["tries"] >= tools.MAX_TRIES:
            print("  %s: three tries used; it needs a person to look at it" % sh["id"])
            continue
        before = sc["shots"][n - 1]["id"] if n > 0 else None
        if sh.get("chain", n > 0) and before and before not in due and not os.path.isfile(film.path("out", film.episode, before + ".mp4")):
            print("  %s waits for %s, which has no clip yet" % (sh["id"], before))
            continue
        todo.append((sc, sh, n))
        due.add(sh["id"])
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
    if cfg.get("workflow") and cfg.get("refs") == "jimeng":    # the references go up before the GPU is rented
        ready = sorted({film.path(p) for sc, sh, n in todo for p in prompt(film, sc, sh, n)[1]
                        if not p.endswith(".last.png") and os.path.isfile(film.path(p))})
        print("putting %d reference image(s) on Jimeng's picture CDN for the server to fetch" % len(ready))
        ref_addresses(film, ready, tools)
    rc, lease = 0, None
    autodl.LAST.clear()
    try:
        lease = autodl.up(cfg["app"], cfg["gpu"], float(cfg["price"]), left, name="film-" + film.episode, version=cfg["version"])
        server = comfy.Comfy(lease["comfy"])
        stats = server.wait_ready(timeout=900)
        autodl.touch()
        print("ComfyUI %s is up at %s" % (stats.get("system", {}).get("comfyui_version", "?"), lease["comfy"]))
        for sc, sh, n in todo:
            sid, st = sh["id"], film.shot_state(sh["id"])
            now = autodl.load()
            if not now or now.get("uuid") != lease["uuid"]:
                print("stopping: the GPU was given back (the cap or 15 idle minutes); %s and the rest wait" % sid)
                rc = 1
                break
            if autodl.cost(now) + shot_minutes(cfg, sh["seconds"]) / 60.0 * float(now["price"]) > now["cap"]:
                print("stopping: %s would take the GPU past the cap of %.2f yuan" % (sid, now["cap"]))
                rc = 1
                break
            text, paths = prompt(film, sc, sh, n)
            chain = [p for p in paths if p.endswith(".last.png")]
            if chain and not os.path.isfile(film.path(chain[0])) and not tools.last_frame(film, sc["shots"][n - 1]["id"]):
                print("  %s waits for %s, which has no clip yet" % (sid, sc["shots"][n - 1]["id"]))
                continue
            raw, dest = os.path.join(out_dir, sid + ".h3.mp4"), os.path.join(out_dir, sid + ".mp4")
            print("%s  %ds" % (sid, sh["seconds"]))
            st["tries"] += 1
            try:
                if cfg.get("workflow"):
                    refs = [film.path(p) for p in paths]
                    if cfg.get("refs") == "jimeng":
                        refs = ref_addresses(film, refs, tools)
                        autodl.touch()
                    _, seed, took = server.u22_clip(cfg["workflow"], text, sh["seconds"], refs, raw, beat=autodl.touch, tuning=cfg.get("tuning"))
                else:
                    _, seed, took = server.h3_clip(text, sh["seconds"], [film.path(p) for p in paths], raw, beat=autodl.touch, size=SIZE,
                                                   steps=cfg["steps"], turbo=cfg["turbo"])
                ok = trim(tools.FFMPEG, raw, dest, sh["seconds"], cfg.get("post"))
            except comfy.ComfyError as err:
                print("  failed: %s" % err)
                ok, seed, took = False, None, 0
                generated = any(k in str(err) for k in ("generation failed", "refused the workflow", "without a saved video", "no output"))
                if not generated:                       # the link or the server failed, not the take: the try is given back
                    st["tries"] -= 1
                    st.update(status=st.get("status") if st.get("status") in ("drafted", "accepted") else "failed")
                    film.save_state()
                    if not autodl.load():
                        print("stopping: the GPU is gone")
                        rc = 1
                        break
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
        if held and held.get("pid") != os.getpid():
            held = None                                   # another program's GPU: never ours to give back
        if lease is None and autodl.LAST.get("pid") == os.getpid():
            lease = dict(autodl.LAST)                     # created by this run but never came up (already given back)
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
