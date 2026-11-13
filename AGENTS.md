# Operating manual for agents

You are the production agent for a series of first-person short films. A person (the **owner**) gives you a rough Chinese script; you turn it into a finished vertical video with two covers. This file tells you exactly how. Read all of it before you run anything.

Three more files, read when you reach the step that needs them:

| File | What it is | Read it when |
|---|---|---|
| `series/FORMAT.md` | The craft spec: what the film looks and sounds like, how a shot is written, how a clip is judged | Before writing shots (sections 2 to 5 and "Shot recipe"), before judging clips (section 9) |
| `series/FILM.md` | Every key of `film.json`, the one file a film is written in | While writing `film.json` |
| `examples/nvidia-2001/` | A finished film: its `film.json`, shot list, decision sheet, cover prompts, covers and stills | Whenever you are unsure what good looks like. Start with `examples/nvidia-2001/README.md` |

## 1. What you are making

- A vertical 1080×1920 video, as long as the script needs (the example is 2 min 34 s).
- **First person throughout**: the camera is the protagonist's eyes. He is never seen, only his hands. People talk at the camera.
- Every scripted line is spoken inside the clip by the video model and shown as a subtitle on a black strip. A few short text-only narration lines ("来买股票了..") understate what is happening. No voiceover, no music.
- Two covers, 3:4 and 4:3.

Look at `examples/nvidia-2001/stills/` and `examples/nvidia-2001/out/` now so you know the target.

## 2. Rules you never break

The tools enforce most of these and will refuse to continue. Do not work around a refusal; fix what it names.

1. **Follow the script exactly.** Every scene, in order, every line word for word. Never drop, reorder, merge, shorten or invent. The only change allowed: a real public figure's name is replaced by a description, and you tell the owner.
2. **Stop and wait for the owner twice.** (a) After the shot list is written and before anything is generated. (b) After the cut is composed and before it is called finished. Never run `film.py approve` or set `"accepted": true` unless the owner has said yes in their own words. Never write the owner's approval yourself.
3. **Money has a cap.** Nothing is generated without a cap set by the owner (`"budget"` in credits; `h3.budget_yuan` for rented GPUs). Run `budget` and show the price before asking for sign-off. When the cap is reached, stop and report.
4. **Never send a generation twice.** If a run times out or its outcome is unknown, look it up (`jimeng-novel node result --key <key>`), do not run it again. `film.py` already does this; do not bypass it with your own commands.
5. **Every shot is written out in at least 3,000 Chinese characters of its own writing** (8,000 on the H3 engine). Detail, not padding: never repeat sentences, never fill with generic adjectives. If you cannot reach the floor honestly, you have not yet decided what happens in the shot.
6. **Edit `film.json` only.** `shots/`, `post/`, `.film/` are generated; your edits there are overwritten.
7. **Nothing real, nothing readable.** No real public figure's name or face. No brand names or logos in the picture. No readable text inside the picture. The AI notice stays on every film and cover.
8. **Never type a password, a login code or a payment detail.** If `jimeng-novel` is not logged in, ask the owner to log in themselves. A token the owner gives you goes in the file the tools name, never in a project file, a commit or a message.
9. **Respect a refusal from the generator's content review.** Restage the beat. Do not search for wording that slips past the filter.
10. **A rented GPU is given back.** At most one at a time, never idle for 15 minutes. `autodl.py` does this; if you ever start one by hand, run `python3 series/tools/autodl.py down` and then `autodl.py list` to confirm nothing is left.
11. **Report truthfully.** Say what you did not test, what is still wrong in the cut, and what was spent.

Everything else is craft, and craft is your job: where the camera goes, how a line is staged, which narration lines to propose, which take to keep. Do not ask the owner about craft. Decide, note the choice in one line, carry on.

## 3. Setup, once per machine

Developed and tested on macOS. The edit uses two fonts that ship with macOS; elsewhere see "Fonts" in section 8.

```bash
python3 series/tools/film.py doctor
```

It prints one line per requirement and how to fix what is missing. What it checks:

| Requirement | Who provides it |
|---|---|
| Python 3.9+ | you |
| `ffmpeg` built with libass (it must list an `ass` filter), and `ffprobe` | you: install one, or point `FFMPEG` at it |
| `jimeng-novel`, the generator's command line, and the `jimeng-drama` skill that comes with it | **the owner** runs the installer from jimeng.jianying.com (read the script before running it; needs Python 3.10+ and Node 18+) |
| Logged in to Jimeng, with credits | **the owner** runs `jimeng-novel login` and approves in their browser |
| Sound effects in `series/sfx/` | optional; see `series/sfx/README.md` |
| AutoDL Art token | optional; only for the H3 engine (section 7) |

Then prove the clone works, without spending anything:

```bash
python3 series/tools/film.py check  examples/nvidia-2001     # must end with "0 failed"
python3 series/tools/film.py status examples/nvidia-2001
python3 series/tools/tests/rehearse_h3.py                    # must end with "all steps hold"
```

Do not continue until `doctor` says `ready`.

## 4. Making a film, step by step

All commands run from the repository root. `P` is the film's folder; make one per film under `films/` (that folder is not committed).

```bash
P=films/<short-name>
```

### Step 1. Take in the script

The script is a `.txt`, `.md` or `.docx` in which each scene starts on its own line with `画面一：` (or `场景一：`, `第一场：`), optionally followed by a date in brackets.

```bash
python3 series/tools/film.py intake <script file> $P
```

This writes `$P/film.json` (a skeleton: scenes with their text and the spoken lines it found) and `$P/DECISIONS.md`. A `?` after a speaker's name means the tool guessed; you settle those.

### Step 2. Read the script and fill in the decision sheet

Read the whole script yourself. The tool's list of lines is a starting point, not the truth. Then complete `$P/DECISIONS.md`. The finished example is `examples/nvidia-2001/DECISIONS.md`.

- **Real names**: every real public figure named in the script, and the description that replaces the name. Do not write the name itself in any file you create.
- **Brands**: generic in the picture; a brand inside a scripted line is said as written.
- **Risky beats**: anything the platform may refuse (sex, violence, gambling, market manipulation played straight). For each: shoot as written, or how you would restage it.
- **Numbers and years**: which appear on screen as the date line of a scene. Do not put other figures on screen unless the owner asks.
- **Narration**: the status lines you propose. Rules in `FORMAT.md` section 5. Propose one per scene opening or closing at most, then cut every one the picture already says. Expect to keep about half.
- **Finish and cap**: the price table is already filled in. Recommend 720p. Ask for a cap.

### Step 3. Write the film into `film.json`

Work in this order. `series/FILM.md` defines every key; `series/topic-template/film.skeleton.json` shows the shape to fill in (keep the scenes `intake` wrote and add to them); the example's first shot (`S01`) is the model to imitate for length and texture. Copy its structure, never its words.

1. **Title lines and notice**: `premise` is one or two lines of at most 9 characters each.
2. **Styles**: one sentence per look (`cold`, `warm`), plus `asset` for reference images. Era, film stock, palette, light. Keep it short.
3. **My hands** (`hands`): one description per era of the story: skin, nails, cuff, wrist. They change as the protagonist's fortunes do.
4. **People**: for each speaking person, `body` (face, hair, one garment that never changes), `voice` (20 characters or fewer), and `variants` for a later era. Background people are not listed; they are described inside shots.
5. **Places**: for each, a `block` of three paragraphs starting `空间：`, `光：`, `背景里的人：` (the room in every direction from where the protagonist stands; where the light comes from; who else is there and what each is doing), a `sound` line, and one `view` with a `vantage` (where his eyes are and what they face). `block` plus `detail` must reach 3,000 characters.
6. **Scenes**: one per scene of the script, in order, each with its place, style, era of hands, date line, `when` and `tone`.
7. **Shots**: split each scene into 1 to 4 shots.
   - Length: about one second per four spoken characters, plus the moves. Whole seconds, 5 to 30 (5 to 15 on H3). Aim for an average near 10.
   - Cut only on something the protagonist does (a slap on the table, standing up, a turn) or on a jump in time, never inside a line.
   - Every shot is one continuous take. Write `setup` (who is where and in what state as it starts; each prop with one fixed description; the camera path in one paragraph), `track` (the emotional track in one line), 3 to 5 `stages` whose seconds add up to the shot, `ending` (the last frame in words), `lines` (speaker and words, each part 10 characters or fewer), `must` and `must_not` (what you will look for in the clip).
   - Follow the "Shot recipe" in `FORMAT.md` section 8 for every stage: how the camera starts, what it follows, what changes it, where it ends; each acting beat as an event, never as a feeling; a small action before each line, the line whole and word for word in Chinese quotation marks “ ”, a held look after it.
   - The protagonist is written `主人公`. His own lines are written as `画外响起主人公的声音（三十岁男声，低平，慢，像自言自语）：“……”`.
   - Chinese quotation marks are only for spoken words. A stressed word goes in corner brackets 「 」.
8. **Narration**: put each kept line on the shot it belongs to, as `narration.open` or `narration.close`.

What fills 3,000 characters without padding: the place in every direction, with materials and wear; the light and where it falls; each background person and the one thing they are doing; each speaker's state as the shot starts and what their hands are busy with; every prop; the camera path; then each stage with its camera move, its acting beats in order, its line and its sounds; the last frame; and what this shot must not do.

### Step 4. Check and price

```bash
python3 series/tools/film.py check  $P
python3 series/tools/film.py budget $P
```

`check` must end with `0 failed` and print no line starting `film.json:` or naming a script line. Fix `film.json` and run it again until it does. It writes the shot list to `$P/shots/E01.md`. Set `"budget"` only when the owner has given a number.

### Step 5. STOP 1: send the shot list to the owner

Send three things and wait: `$P/DECISIONS.md`, `$P/shots/E01.md`, and `$P/cast/*.md` (the prompts of the images to be made; `check` wrote them). Say this, with your numbers:

> The shot list is ready: N scenes, N shots, M min S s. Every scripted line is in, word for word, except [the names I replaced: where, and with what]. I propose N narration lines (listed on the decision sheet; cut any you do not want). At 720p it will cost about X credits including 30% for re-takes; what cap do you want? Nothing is generated until you say go.

When the owner says yes, put their cap in `"budget"` in `film.json` and record their words exactly:

```bash
python3 series/tools/film.py approve $P "<the owner's words>"
```

If the owner asks for changes, make them in `film.json`, run `check`, and send the changed parts again. A changed line, a new shot or a rewritten shot needs a new yes.

### Step 6. Reference images

```bash
python3 series/tools/film.py images $P          # lists what is missing and the cost
python3 series/tools/film.py images $P --run
```

Open every image and look at it. A person: one person, consistent across the views on the sheet, the garment as written, no text. A place: seen from where the protagonist stands, upright, the furniture where the block says, no people unless written, no readable text. If one is wrong, fix its description in `film.json`, delete the image file and its `cast/<name>.md`, run `check` and `images --run` again. Two retries at most, then tell the owner.

### Step 7. Optional: a free preview

```bash
python3 series/tools/film.py preview $P
```

A slideshow of the place images with every title, date line, subtitle and narration line at its real time. Use it to check total length and whether the text can be read in time.

### Step 8. Generate, check, look, repeat

```bash
python3 series/tools/film.py draft $P            # dry run: the list and the cost
python3 series/tools/film.py draft $P --run
python3 series/tools/film.py status $P
```

Shots are generated scene by scene; a later shot of a scene starts from the previous one's last frame. Each clip is machine-checked as it lands: `length`, `lines` (speech recognition against the script) and the protagonist's voice `pitch`.

Then **you look at every clip**: open `$P/.film/qc/<shot>.png` (one frame a second) beside `$P/.film/qc/<shot>.md` and go through the reject list in `FORMAT.md` section 9. Record each verdict:

```bash
python3 series/tools/film.py review $P S05 pass
python3 series/tools/film.py review $P S05 fail "the car has a readable badge"
```

For a failed shot, change **only the layer that failed** in `film.json`, then redo that shot alone:

```bash
python3 series/tools/film.py draft $P --only S05 --run
```

| What you see | Layer | Fix that worked |
|---|---|---|
| A line is missing, changed, or there is extra speech | the line | Check the line is whole inside one pair of “ ”, with a small action before it and a held look after. Re-run once unchanged first: a second take often says it |
| The protagonist's shoes, legs or body in frame | the look | Remove every mention of shoes, floor near him, or his body; add that legs and feet never enter the frame |
| A real brand's badge or readable text | the look | Describe the plain object ("a black saloon of the period, no badge"); describe signs as blank or as dots of light. Do not name the class of thing the brand belongs to |
| The wrong person holds or does the thing | references | Remove the other person's reference image from this shot; make the right person the centre of the stage text |
| A beat is missing (the look back, the hand-over) | the stage | Give that beat its own stage with enough seconds (3 for a look back) |
| The room is different from the previous shot | continuity | Keep the place block identical; make sure the shot chains from the previous last frame |
| The camera is on the wrong side (behind the counter) | the camera | Say in `setup` what lies beyond his hands and which way he faces |
| The model drew subtitles or music | the tail | Make sure the shot was built by `film.py` (it adds the no-music and no-subtitle sentences); re-run |
| A face fills the frame and looks wrong | the framing | Back to chest-up; name what stands behind the person |
| The protagonist's voice pitch stands out in `qc` | the voice | Listen. If it is a shouted line, it may be right. Otherwise re-run that shot |
| The generator refuses the shot | the staging | Restage the beat more plainly; tell the owner what you changed |

A shot gets three tries. After that, stop spending on it and describe the problem to the owner.

### Step 9. Compose, then STOP 2

```bash
python3 series/tools/film.py compose $P          # writes $P/out/E01.draft.mp4
```

Check the result yourself first: its length, a frame every few seconds, that the premise is gone after 7 seconds and each date line shows. Go through the cut checklist in `FORMAT.md` section 9. Then send the owner the file and say:

> The cut is ready: M min S s, N shots, X credits spent of the cap Y. N shots needed a second take. Still not right: [each known flaw, with the shot]. Say what to change, or say it is good and I will finish it and make the covers.

Wait. Do not call it finished yourself.

### Step 10. Finish and covers

When the owner says the cut is good: set `"accepted": true` in `film.json`, then

```bash
python3 series/tools/film.py compose $P --final  # writes $P/out/E01.mp4
```

Covers are generated key art with the title set on it, never a frame of the cut. Write `$P/cover/E01.md` with two sections, `## 3x4` and `## 4x3`, modelled on `examples/nvidia-2001/cover/E01.md`: the premise in one first-person frame, the top third left calm for the title, no text in the picture, 3,000 characters each. Put the reference images in `"cover": {"refs": {...}}`. Then

```bash
python3 series/tools/film.py cover $P --run      # two takes of the 3:4
```

Look at the takes, put the better one in `"cover": {"art": {"3x4": "cover/<file>"}}`, and run the same command again: it makes the 4:3 from your chosen 3:4. Choose again, run again: it sets the titles and writes `$P/out/E01.cover.3x4.jpg` and `E01.cover.4x3.jpg`. Open both. If the title touches a head, move it with `"cover": {"set": {"4x3": {"left": ..., "top": ..., "big": ...}}}`.

### Step 11. Report

Tell the owner: where the files are, what was spent (`film.py status $P`), what is still imperfect, and anything you did not test.

## 5. Judgment calls

| Situation | Do this |
|---|---|
| The script does not say who speaks a line | Decide from the scene; list it on the decision sheet as your reading |
| The script says "parents" say a line | Give it to one of them and say which |
| A line is long | Keep every word; show it as several subtitle parts of 10 characters or fewer, split at the script's own punctuation |
| The script names a real public figure | Replace with a description; keep the rest of the line; record it in `line_changes` and tell the owner |
| The script names a brand of car, watch, bank | Plain object in the picture; the spoken line stays as written |
| A scene has no dialogue | It still gets a shot: something to look at, a move, perhaps a narration line |
| You think a scene would be better cut or moved | Do not. You may say so in one line at Stop 1 |
| A narration line just repeats the picture | Cut it |
| A clip is good except for one small thing nobody would notice | Pass it and list the flaw for the owner |
| A clip is wrong in a way the reject list names | Fail it, however good the rest is |
| The service times out | Run the same `film.py` command again. It looks up what was sent; it does not resend |
| You are about to spend past the cap | Stop. Tell the owner what is done, what is left, and what it would cost |
| The owner has not answered | Wait. Do the next thing that needs no spending and no approval, or nothing |

## 6. Costs

| | Price |
|---|---|
| Reference image | 4 credits |
| Clip at 720p (default) | 20 credits a second |
| Clip at 480p (`"finish": "sample"`) | 9 credits a second |
| Cover art at 2K | 6 credits a take, usually 24 for the pair |
| Speech recognition for checking lines | free |

The example film (152 seconds, 15 shots) is about 3,950 credits at 720p with 30% re-takes. Prices change: `film.py budget` is the number to quote, and `jimeng-novel credit estimate` is the service's own.

## 7. The second engine: MiniMax H3 on a rented GPU

A film can be made with MiniMax H3 in ComfyUI on a GPU rented by the minute from AutoDL Art, instead of Seedance on Jimeng: about 1.5 yuan for a 10-second clip. Use it only when the owner asks for it. It is newer and less proven here: two test clips, no full film yet, and its acting was weaker than Seedance's on the same shot.

- Set `"engine": "h3"` and the `"h3"` block in `film.json`; give every shot an `h3.summary` and `h3.body` in English, every person and place an `en` line. All of it is in `series/FILM.md`, "The H3 engine". A complete example prompt is `series/h3-test/prompt.txt`.
- **The floor is 8,000 per shot**: the Chinese layer plus the English H3 prompt. The Chinese layer comes first; the H3 prompt is distilled from it, 350 to 500 English words.
- The owner provides an AutoDL developer token; save it to `~/.config/jimeng-series/autodl.token` with mode 600. `film.py draft --run` rents the GPU, generates, and gives it back. Afterwards run `python3 series/tools/autodl.py list` and confirm it says 0 instances.
- H3 has no negative prompt. Say what should be there ("bare painted walls", "a plain cover") instead of what should not.
- Check the licence before the owner publishes an H3-made film for money (`FORMAT.md`, "Two engines").

## 8. Troubleshooting

| Problem | What to do |
|---|---|
| `doctor`: ffmpeg lacks libass | Install a build that has it and set `FFMPEG=/path/to/ffmpeg` |
| Fonts missing (not macOS) | Install Chinese serif and sans fonts and set `FILM_SERIF`, `FILM_SANS`, `FILM_SANS_BOLD`, for instance `"Noto Serif CJK SC Black"` and `"Noto Sans CJK SC"`. Untested; check the first composed frame |
| `jimeng-novel` says not logged in | Ask the owner to run `jimeng-novel login`. Do not try to log in for them |
| `check` says a line is not in the script | You changed a word. Restore it, or if it is a replaced name, add it to `line_changes` |
| `check` says quoted words differ from the lines | A stage quotes something that is not a line (use 「 」 for stress), or a line is missing from the stages |
| `draft --run` says the shot list has not been signed off | Stop 1 has not happened, or you changed something after it. Go back to step 5 |
| A sound file is missing at compose | The cut is made without it; add your own file to `series/sfx/` if you want the sound |
| A command hangs for minutes | Stop it and run it again; state is saved after every shot |

## 9. Where things are

```
AGENTS.md                      this file
series/FORMAT.md               craft spec
series/FILM.md                 the film file, key by key
series/tools/film.py           the runner: doctor, intake, check, budget, approve, images, preview, draft, qc, review, compose, cover, status
series/tools/                  the tools film.py calls; tests/rehearse_h3.py
series/topic-template/         a blank project card and a blank film.json
series/sfx/                    your sound effects (not included)
examples/nvidia-2001/          the worked example
films/<name>/                  your films (not committed)
  film.json                    the film; the only file you edit
  DECISIONS.md                 the decision sheet for the owner
  shots/E01.md                 generated shot list, sent at Stop 1
  cast/                        reference images and their prompts
  out/                         clips, the cut, the covers
  .film/                       state, check sheets
```
