# Series format

One presentation, any topic. This file is the craft spec: what the finished film looks and sounds like, how a shot is written, and how a clip is judged. `AGENTS.md` at the top of the repository is the operating manual and says what to run; `FILM.md` describes the film file.

**In this document "I", "me" and "my" mean the protagonist, 我: the person behind the camera.** The viewer sees through his eyes and never sees him.

**The aim:** a first-person short film in which ordinary people talk at the camera and small white lines of text understate what is happening. The topic changes from film to film; the presentation does not.

## 1. What is fixed and what a film supplies

| Fixed for every film | Supplied by the film |
|---|---|
| First-person camera; I am never seen, only my hands | The script, followed scene by scene at whatever length it needs |
| Full-frame vertical 9:16, 1080×1920, no bars | The premise: one or two short lines for the top of the frame |
| Shots of 5 seconds or more, about 10 on average, camera always moving (section 3) | The date line of each scene ("买入第一天", "2007年　买入第约2555天") |
| The text layers and where each sits (section 4) | The people, with one garment each that never changes |
| No voiceover and no music; narration is text only (section 5) | The places |
| One film file and one runner; shot list signed off before anything is generated; two covers (section 8) | A style sentence for the era and place; how my hands and cuffs look in each era |

## 2. Story

### The script is the owner's

The script is followed exactly: which scenes exist, their order, who says what, each line as written. Nothing is dropped, reordered, compressed or replaced, and no twist is added. `film.py check` compares every spoken line with the script.

- **The one exception is a real public figure's name.** It never goes into the film file, a prompt or a subtitle. Replace it with a description ("那个做聊天软件的") and list the change on the decision sheet for the owner.
- **Narration lines are additions**, not script: short status lines in the style below. They are listed on the decision sheet so the owner can cut them.
- Punctuation is the only thing touched in a line: exclamation marks and ellipses are dropped in subtitles, and a long line is shown in parts.

### How a scene runs

1. **The date line changes** when the time has moved on.
2. **A status line may open it**, text only: what I have come to do. "来买股票了.."
3. **Hands first, then the face.** The shot opens on my hands or what I am holding, then lifts to whoever is there.
4. **They talk at me.** I answer in a word or two, or not at all, exactly as the script has it.
5. **Someone's action ends it.** They walk out, take something away, hand something over. That action is the cut.
6. **An outcome line may close it**, text only. "女朋友走了.."

### The hook

The first three seconds: my hand does the thing that cannot be undone and someone is already reacting to it. The premise is on screen from the first frame.

### Something new every ten seconds

A new place, person or thing to look at every 9 to 12 seconds. A shot that runs 15 seconds needs a second thing to look at inside it: a prop changing hands, someone in the background, a turn to another part of the room.

### Echoes

Where the script allows it, a line or gesture from someone's exit is answered when they return, and one object is carried through. In the first film the passbook slapped down in the first second is the thing the whole story hangs on; the friend who walks away along the river later bends over my chair with a glass.

## 3. Picture

### How a shot is built

1. **First person, always.** The lens is my eyes. Only my hands and forearms are ever seen. No image is made of my face.
2. **Three planes.** Foreground: my hands, entering from the bottom edge, holding or touching the thing that matters. Middle: the person. Background: the room, with a bright opening (a window, a doorway, the end of a corridor).
3. **People come in by turning or leaning toward the lens and leave by walking away.**
4. **One take, several actions.** A shot is one continuous take with three to five timed stages written into it, then a hard cut.
5. **Cuts are caused by something in the frame**: a door closing, an object handed over, a look down, my own turn or sitting down. No decorative transitions.
6. **Chest-up while someone speaks.** The video model only syncs a mouth reliably from the chest up. Wide to arrive and to leave.
7. **Keep the speaker on the centre line.** Two people share a frame in depth, not side by side at the same distance.

### Shot length and camera movement

Every shot runs 5 seconds or longer, about 10 on average, and the camera moves far more than it rests.

- **A scene is one to four shots.** Cut on something I do or on a jump in time, never in the middle of someone's line.
- **Open a scene moving**: walking up to the counter, down a corridor, out of a door, along a river.
- **The head goes to whoever speaks**, and tilts with them when they stand, sit or come down a step.
- **Lean in while being talked at**; pull back when a crowd closes in.
- **Glance away mid-line** at the thing that matters (the glass in his hand, the car key in mine) and come back.
- **Follow exits**: watch them go, then take a step after them or turn to what is left.
- **Never a locked-off frame.** Even a held look has a slow drift.

`film.py check` refuses a shot that is not a whole number of seconds from 5 to 30 and prints the shortest, the longest and the average.

### Light and height

- **Light says whose side someone is on.** A person against me stands in front of the light, half in silhouette. A person with me is lit softly from the front or side.
- **While I am losing, they stand over me. Once I have won, I stand and they bend or sit.**
- **One light source per place**, described the same way in every shot there.

### Look

- **Cold base, warm where life is.** A desaturated blue-grey base in the hard years; warm colour for what is alive or wanted, and for the scenes where things have come good.
- **Worn, specific surfaces** and two or three period objects in every shot.
- **The background is alive**: other people getting on with their own business, none of them looking at the lens.
- **No readable text inside the picture.** Signs, screens and papers are described as blank, as dots of light, or as plain colour; the model garbles anything longer than a few characters. No brand names or logos: describe the plain object ("a black saloon car of the period with no badge").
- **One garment per person never changes**, so they are the same person decades apart.
- **My hands age and dress with the story.** Cuff, wrist and what I hold change with the era: a frayed cotton cuff in 2001, a shirt cuff and a steel watch in 2018. The viewer reads how I am doing from my sleeve.

## 4. Text on screen

All text is white and centred, set in a bold serif (Songti SC Black). Nothing goes above y=150 or below y=1500 on the 1080×1920 frame; a phone app draws its own buttons there. `series/tools/compose_episode.py` draws all of it; nothing is ever written into a video prompt. Stills of the finished look are in `examples/nvidia-2001/stills/`.

| Layer | Carries | Where and when | Look |
|---|---|---|---|
| Notice | "AI 生成 · 虚构剧情" (for money topics add "· 不构成投资建议") | Top right corner, for the whole film | Small sans, 22 px |
| Premise | The film's one or two title lines | Top, from y=205. **The first 7 seconds only** | Bold serif, 84 px, dark outline |
| Date line | The date or day count of the scene | The first one sits under the premise and leaves with it. Each later one comes up alone at y=215 when it changes, with a soft click, and leaves after 4 seconds | Bold serif, 64 px, dark outline |
| Subtitles | Every spoken line, one at a time. No punctuation except a question mark where the words alone would not read as a question. A line over 10 characters is shown in parts | Low-centre: a full-width black strip 124 px high centred on y=1320, gone when nobody speaks | Bold white serif, 84 px, no outline |
| Narration | Status and outcome lines, text only | The same strip and look as a subtitle, while nobody is speaking | Bold white serif, 84 px |

Nothing stays on screen for the whole film except the notice.

## 5. Words and sound

### Narration

- **A narration line is a status line ending in two dots, two to seven characters**: "来买股票了..", "兄弟回来了..".
- **One size smaller than what happened.** Bought my father a luxury car: "给我爸买了辆车..". Met the ex outside the mall: "碰见个熟人..".
- **Keep one only where it earns its place**: a joke or an understatement the picture does not give by itself. A line that only says what is on screen goes. In the first film nine of eighteen drafted lines stayed.
- **A loss and its return use the same words turned round**: "兄弟也走了.." comes back as "兄弟回来了..".
- Narration is never spoken.

### Voices

- **No voiceover.** Nobody is heard who is not in the scene.
- **The script's lines are spoken, by the video model inside the clip**: other people with their lips in sync, me as a voice from behind the lens. Nothing is recorded or dubbed afterwards.
- **My voice is described the same way in every prompt**: `三十岁男声，低平，慢，像自言自语`. On the first film it held between 85 and 105 Hz across all scenes from that description alone; `film.py qc` measures it and names any shot that stands out.
- **Each other person has one voice description of twenty characters or fewer**, reused word for word.
- Everyday Mandarin unless the film is set somewhere that calls for something else.

### Sound

- **No music.** Clips are generated with music excluded, and none is added in the edit; the owner adds their own afterwards if they want it.
- **One continuous room sound per place**, worded identically in every shot of that place, plus sounds tied to things seen happening: a door, a bowl, a palm on a counter.
- **Sound added in the edit**: a soft click when the date line changes (`scoreboard-click.mp3`), and at most a hit under the opening action if the clip's own sound is weak. Effects are your own files in `series/sfx/`; a missing file is skipped with a note.
- The finished mix is lifted to about −15 LUFS.

## 6. Truth and safety rules

- **No real public figure's name or likeness** in the film file, prompts, subtitles or covers.
- **Every film carries the AI-generated notice.** The platform's own AI mark is never cropped or covered.
- **A number shown on screen has a source** written in the project's README, checked before the film is composed. A number a character says as a boast is dialogue, not a fact.
- **Brands and logos are generic in the picture.** A brand a character names in a scripted line is said as written.
- **Follow the platform's content review.** When a generation is refused, change how the beat is staged; do not hunt for wording that slips past the filter.
- **Reference videos you study are style references only**: never feed someone else's footage or a real person's face to the generator.

## 7. The owner decides, the agent proposes

The owner's script, the owner's money and the owner's sign-off are not the agent's to change. Everything else is craft and is the agent's job: where the camera goes, how a line is staged, which narration lines to propose, which take to keep. Make the call, write down what you chose and why in one line, and carry on.

## 8. Making a film

The aim: a rough script goes in and a finished video comes out, with two stops for the owner. Work is done with the `jimeng-drama` skill and the `jimeng-novel` command; follow that skill's own references at each step. `dreamina-canvas` is also installed but is not used for this series: clips made outside `jimeng-novel` do not land on the project's canvas or in its price quotes.

### One file, one runner

- **`PROJECT/film.json` is the only place the film is written down**: the title lines, the notice, the styles, my hands by era, every person and place, and every scene and shot with its length, stages, lines and narration. The shot file (`shots/E01.md`), the line files, the image prompts and the edit plan are all generated from it. Edit `film.json`, never the generated files. (Before this, a shot's length lived in three files and drifted.) Every key is described in `series/FILM.md`.
- **`python3 series/tools/film.py <command> PROJECT` runs every step.** Tries, credits and verdicts are kept in `PROJECT/.film/state.json`, so a restart or a dropped connection loses nothing. `film.py status PROJECT` shows where every shot stands.

| Step | Command | What it does |
|---|---|---|
| 0 | `doctor` | Checks the machine: ffmpeg, fonts, `jimeng-novel`, login |
| 1 | `intake SCRIPT PROJECT` | Splits the rough script (`.txt`, `.md` or `.docx`) into scenes and spoken lines (each scene starts 画面一：, 画面二： …). Writes a `film.json` skeleton and `DECISIONS.md`: lines whose speaker had to be guessed, brands, beats the platform may block, numbers and years, and the three finishes priced from the script's length |
| 2 | by hand | Read the script. Settle the marked lines, fill in the decision sheet (real names and what replaces them, the narration lines proposed, finish, credit cap) and write the film into `film.json`, shots in the two-layer form below |
| 3 | `check` | Validates `film.json`, writes the shot file and runs the gate: 3,000 characters of own writing a shot, stages add up, references exist, quoted words equal the lines. Also: every line of the script is in its scene's shots as written (`line_changes` lists the ones reworded on purpose), and a place still to be drawn has 3,000 characters of description |
| 4 | `budget` | What each finish costs against the cap, before anything is spent |
| | **Stop 1** | The written shot list goes to the owner for review: the decision sheet, `shots/E01.md` and the `cast/` prompt files of the images to be made. **Nothing is generated until they sign off** |
| 4a | `approve "their words"` | Records the sign-off. Without it `images --run`, `draft --run` and `preview` refuse. It is only ever run with words the owner actually said in reply to the shot list |
| 5 | `images --run` | Makes the images still missing. A place's first image is the upright view from where I stand |
| 6 | `preview` | Optional and free: a paper animatic from the place images with every title, date line, subtitle and narration line at its real time, to check length and reading speed. |
| 7 | `draft --run` | Generates the shots scene by scene. A later shot of a scene takes the earlier one's last frame. Each clip is checked as it lands (step 8). Stops at the cap; a shot gets three tries, then waits for a person |
| 8 | `qc`, then `review S05 pass` or `review S05 fail "why"` | Machine checks: length, every line spoken and nothing extra (speech recognition), the pitch of my voice against the other shots. Then a frame sheet and a checklist per shot in `.film/qc/`, looked through by eye against section 9 and the shot's own must and must-not lists. A failed shot: change only the layer that failed in `film.json`, then `draft --only S05 --run` |
| 9 | `compose` | Builds the edit plan and the cue file and renders `out/E01.draft.mp4` |
| | **Stop 2** | The owner watches the cut |
| 10 | `compose --final`, `cover` | Once the owner says the cut is clean, set `"accepted": true` in `film.json`. The finished film is `out/E01.mp4`; `cover` writes the two covers |

Without `--run`, `images` and `draft` only list what they would make and what it would cost.

What the sign-off covers: the shots in their order, each with its length, its lines and narration and its full prompt; the title and date lines; the prompt of every image still to be made. After it, a shot that has already had a take may be redone with changed wording or length (a fix to a failed take, reported afterwards). Everything else needs a new sign-off: a shot added, removed or moved, changed lines or narration, a changed title or date line, a rewritten shot that has not had a take yet, a new or changed image prompt.

### Finish

**The default is 720p clips, enlarged to the 1080×1920 canvas in the edit.** `"finish"` in `film.json` chooses the route:

| `finish` | Route | Credits a second |
|---|---|---|
| `720p` (default) | `Seedance_2.5` at 720p, every shot generated straight at 720p; no 480p pass first, because a 720p clip is a fresh take whatever was drafted before | 20 |
| `sample` | `Seedance_2.5_draft` at 480p, enlarged in the edit. The first film was finished this way | 9 (14 with a reference video) |
| `1080p` | 480p drafts, then `jimeng-novel node finalize` on each approved draft. The export inherits the draft exactly and costs as much as generating 1080p directly. The runner prices this route but does not run the export; it is done by hand, within 7 days of the draft | 9 + 64 |

Images are 4 credits each (Seedream 5.5). `budget` adds 30% for re-rolls (`reroll_rate`). `"budget"` in `film.json` is the cap in credits; with no cap set, nothing is generated. Always price the whole job first: on the first film the 1080p export was quoted only after the drafts were made, and turned out to cost five times the drafts.

The full model takes an audio reference. If `lead_voice_sample` is set in `film.json`, every 720p shot in which I speak takes it as a reference for my voice. It is off unless set, and not yet tried on a real shot: on the first film my voice held steady across all scenes from its written description alone, so add the recording only if the pitch check shows drift.

### Two engines

A film is made with one of two engines, named in `film.json` as `"engine"`. Images, checks, the edit and the covers are the same for both; only the clips come from different places.

| | `jimeng` (default) | `h3` |
|---|---|---|
| Model | Seedance 2.5, through `jimeng-novel` | MiniMax H3 (open weights, released 2026-08-03), reference-to-video, in ComfyUI |
| Where it runs | Jimeng's service | A GPU rented by the minute on AutoDL Art (autodl.art), started and given back by the runner |
| Paid in | Credits: 20 a second at 720p, 200 for a 10-second clip | Yuan of GPU time: about 1.5 for a 10-second clip (PRO6000-96G at 8.36 an hour, 2026-11-13) |
| Prompt | Chinese, the drama skill's form, up to 15,000 characters | English, MiniMax's six-part form; its guide puts the description at 350 to 500 words |
| Clip | 4 to 30 s, 720p | 5 to 15 s, 768×1344 at 24 fps, picture and sound in one pass |
| Floor per shot | 3,000 characters | **8,000**, hard rule |
| Tools | `film.py` | `film.py` with `h3.py` (prompt and gate), `comfy.py` (the workflow), `autodl.py` (the GPU) |

**How the 8,000 is counted.** Per shot, like the 3,000: the shot's Chinese layer (place block, setup, stages, ending, notes, must and must-not lists) plus its H3 summary and body, a Chinese character counting one and an English word one. The Chinese layer is the shooting script and storyboard; the H3 prompt is written from it. The model itself is given only the H3 prompt: MiniMax trained it on descriptions of 350 to 500 English words, so the extra depth goes into the planning the prompt is distilled from, into the look-through checklist, and into fixing a failed take, not into a longer model prompt.

**The GPU.** `autodl.py` holds at most one instance. It is never created without an hourly price and a cap in yuan (`h3.budget_yuan`). A watchdog process on your machine gives it back (power off, then release, so nothing keeps billing) after 15 idle minutes or at the cap, even if the runner has died; `film.py draft --run` gives it back itself when the batch ends unless `--keep` is passed. Every rental is a line in `~/.config/jimeng-series/autodl.ledger.jsonl`. The token is in `~/.config/jimeng-series/autodl.token` (mode 600), outside every project, and is sent only to autodl.art. `python3 series/tools/autodl.py status` shows what is held; `autodl.py down` gives it back now.

**What the H3 prompt looks like** is in `series/FILM.md`, "The H3 engine". The essentials, from MiniMax's own guides (read 2026-11-13): six parts in English (`subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`); people and places are `<Subject N>` tied to `<Picture N>`; spoken lines stay in Chinese inside `<d>[Chinese] ...</d>` with speaker ids `(S1)`, `(S2)`; no negative prompt, so say what should be there; `N/A` for music.

**Licence.** H3's weights are under MiniMax's community licence. Comfy's documentation says commercial use of clips generated on your own or rented hardware needs a commercial licence from MiniMax (sold through Comfy). The licence text itself was not reviewed when this was written. Check it before publishing an H3-made film for money.

**Rehearsal.** `python3 series/tools/tests/rehearse_h3.py` runs the whole H3 path against local stand-ins for both services: the gates, the rental, the workflow, the download, the trim, the give-back. It rents nothing. Run it after changing any of the four tools.

### What the first real H3 clips showed (2026-11-13)

Two test clips of the first film's opening, 7 and 10 seconds, from one prompt: my hand on the passbook, tilt up to the teller, her line, my line from behind the camera, pan right to the girlfriend gripping my sleeve. References: the two character sheets and the upright counter image already made for the Seedance version. The prompt and a frame sheet of each clip are in `series/h3-test/`.

- **It followed the shot**: first person held, the tilt and the pan came in the written order, both people matched their sheets, and the hand, cuff and passbook were as described.
- **Both Chinese lines were spoken**, at the right moments, by the right voices, nothing extra (checked by speech recognition on the 7-second clip).
- **The acting was the weak part.** The girlfriend was written as disbelief with the last trace of a smile; both takes gave a plain smile. Seedance landed this beat on the same description. This is the gap the 8,000-word planning has to close, and it is not closed yet.
- **It adds things**: posters with pseudo-text on a wall that should be bare, a desk calculator, an emblem on the passbook. There is no negative prompt, so describe the bare wall, the empty counter and the plain cover.
- **Things that had to be fixed to get there**: the instance API takes GET parameters in the query string although its docs show a body; 4 MB reference images time out on upload, so they are sent as JPEGs of 1536 pixels at most; the save node needs its format chosen explicitly. All three are now covered by the code, the first two by the rehearsal as well.

Time and cost, on a PRO6000-96G at 8.36 yuan an hour, 768×1344, 20 steps:

| Clip | On the server | GPU cost |
|---|---|---|
| 7 s (175 frames), cold: 44 GB of weights loading first | 409 s | 0.95 yuan |
| 10 s (243 frames), warm | 652 s, 31 s a step | 1.51 yuan |
| 5 s, estimated | about 3.5 min | about 0.5 yuan |
| 15 s, estimated | about 24 min | about 3.3 yuan |
| The first film's 15 shots (152 s), estimated | about 3 hours | about 26 yuan; about 34 with 30% re-rolls |
| The same with the 4-step turbo LoRA, estimated, quality not yet looked at | about 46 min | about 9 yuan with re-rolls |

Time per step grows with the square of the clip's length, so two 5-second shots cost a third of one 10-second shot. The instance was ready about a minute after it was created. The whole test session, from creation to release, was 32.7 minutes and about 4.5 yuan.

### Two-layer prompts

A shot in `film.json` is written in two layers and the runner joins them:

- **The place block** (`places.<name>.block`): the space in every direction from where I stand, the light, the people in the background. It is repeated word for word in every shot set there, which is what keeps a room the same from shot to shot.
- **The shot itself**: `setup` (who is where and in what state as it starts, the props, the camera path in one paragraph), `track` (the emotional track), `stages`, `ending`, and the `must` / `must_not` lists used when the clip is checked.

Together they must reach 3,000 characters, and the shot's own layer at least 2,000, so the place block cannot carry a thin shot. The place block is exactly its three paragraphs; a place also has `detail`, used only in its image prompt, for everything else.

### A place is drawn from where I stand

The first image of a place (`master`) is upright, 9:16, seen from the spot and height my eyes are at in the scene, and every other view of the place is derived from it. On the first film the masters were wide establishing views, and the upright view of the mall kept facing the building through three tries because the master outweighed the words.

### Covers

`film.py cover PROJECT [--run]`, once the cut is approved. Two files: `out/E01.cover.3x4.jpg` (1440×1920) and `out/E01.cover.4x3.jpg` (1920×1440).

**A cover is generated key art with the title set on it, never a frame of the cut.** The first film's first covers were a 480p frame on a black band, and were rejected.

- **The picture** is made with the image model at 2K (6 credits a take), from prompts in `cover/E01.md`, sections `3x4` and `4x3`, each written out to the 3,000-character floor like any other visual prompt. It shows the film's premise in one first-person frame, with the people and place of the film attached as references so they match. On the first film: my hand on the passbook, the teller looking up behind the glass, the girlfriend turned to the lens with both hands on my sleeve.
- **Leave the top third calm** (plain wall, out of focus, no faces, no lamps): the title goes there. No text of any kind in the picture.
- **Matching pair**: the 3:4 is generated first, two takes, and one is chosen by eye; the 4:3 is then generated with the chosen 3:4 attached as "the same instant, recomposed", so people, clothes, light and moment are the same.
- **The title** is set by `cover_art.py`, top left on a soft dark veil that fades down from the top edge: Songti SC Black in warm white; the last line large, the line above it smaller and letter-spaced out to exactly the same width, so the two make one block (the widths are measured from the rendered ink; a run of digits such as 2001 stays together); a soft shadow, no outline, no second colour. The AI notice is small at the bottom right. Both covers use the same proportions.
- **In `film.json`**: `"cover": {"art": {"3x4": "cover/E01.3x4.a.png", "4x3": "cover/E01.4x3.a.png"}, "refs": {alias: image, ...}, "takes": 2, "budget": 40, "set": {"4x3": {"left": 176, "top": 84, "big": 150}}}`. `art` names the chosen takes; `set` moves or resizes the title on one cover when a head sits in its way. Run `cover --run` again after each choice: it does the next thing that is missing.
- The first film's pair cost 24 credits (two takes of each).

### The compose tool

`film.py compose` calls `make_cues.py` and `compose_episode.py`. To run the last by hand: `python3 series/tools/compose_episode.py post/E01.cues.json`; add `--check` to validate the cue file and print the timeline without rendering. The cue format is described at the top of the script.

- It needs an ffmpeg built with subtitle rendering (libass). Not every build has it; the stock Homebrew one may not. The tools look in `$FFMPEG`, `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` and on PATH, use the first that has it, and stop with a plain message if there is none. `film.py doctor` shows which one was found.
- Fonts: Songti SC Black for everything except the notice, which is Hiragino Sans GB (the subtitle renderer cannot open macOS's PingFang). Both come with macOS. Elsewhere set `FILM_SERIF`, `FILM_SANS` and `FILM_SANS_BOLD` to installed Chinese fonts.
- In the full layout a line holds 10 characters at full size. A longer one is drawn smaller with a warning; split it into parts instead.
- Clips smaller than the canvas are enlarged with a Lanczos filter to cover 1080×1920.

### When the service misbehaves

`jimeng-novel` drops connections and stalls. The runner submits a generation once and after that only looks it up (`node result`); it never sends a job again whose outcome is unknown. Creating a node is retried only after checking that it is not already there. If the runner itself is killed, run the same command again: finished shots are skipped.

### Shot recipe: writing a shot

Where this comes from: the drama skill's own references, which win wherever sources disagree, and what the first film showed.

0. **The shot file comes first and every shot is written out in full. This is a hard requirement.** `shots/E01.md` is sent to the owner before anything is generated.
   - **The length floor, stated once:** (a) a shot's whole prompt, meaning the place block plus the shot's own layer, is at least 3,000 Chinese characters; (b) the shot's own layer (`setup`, `track`, `stages`, `ending`) is at least 2,000 of them, so a long place block cannot carry a thin shot; (c) a place whose image is still to be made has at least 3,000 in `block` plus `detail`. On the H3 engine (a) is 8,000 and (b) is 5,334. `film.py check` counts all three.
   - What is counted is your writing: the prompt without the fixed sentences the runner adds (style sentence, reference lines, the no-music sentence, the first-person sentence and hands, the last line).
   - `film.py check` is the gate. It fails a shot under the floor, a shot whose stages do not add up to its length, a missing reference, and any quoted word that is not in the shot's lines. Nothing is generated from a film that fails.
   - What fills 3,000 characters without padding: the place in every direction from where I stand, with materials and wear; the light and where it falls; each background person and the one thing they are doing; each speaking person's state as the shot starts and what their hands are busy with; every prop with one fixed description; the camera path in one paragraph; then each stage with how the camera starts, what it follows, what changes it and where it ends, the acting beats in order, the line, and the sounds; the last frame; and the two or three things this shot must not do.
   - Tested on the first topic's opening shot: 3,275 characters against 1,515. Same price, all lines spoken, and the written-in props appeared (a pen on its string, an ink pad, a bystander who looks up). The model did not choke on the length.
   - The same floor holds for a new place's image prompt: 3,000 characters of the place's own description before the fixed layout block (`film.py check` counts `block` plus `detail`). This overrides the drama skill's 200 to 350. A relit or upright version of an existing place reuses that place's paragraph so it still matches its master. Character sheets are not scenes and stay at the length the skill's sheet template is built for.
1. **One clip per shot in `film.json`**, in whole seconds. Do not re-cut at prompt time.
2. **No reference video for the camera.** Tested on the first film's opening shot: with a grey-box clip of the camera move attached the take cost 140 credits, without it 90, and both takes followed the written camera path and spoke all five lines. A reference video adds about half again to the price and, with a shot written out in full, bought nothing visible. Write the camera path in words.
3. **The clip is one take.** The runner says so in every prompt (`全程第一人称主观视角单镜头、无剪辑；以下分镜是同一条连续镜头路径上的阶段，不是切镜。`), because numbered stages can otherwise be read as cuts, and a cut to a reverse angle would show me. Write your stages as phases of one continuous camera path, never as separate shots.
4. **Each stage has one job and a chain of cause**: something triggers, someone reacts, a body or a prop moves, the distance or framing changes, and it ends in a result or in movement still under way. Not a list of unrelated actions, and not a held pose.
5. **Write the camera in four parts**: how it starts (still, already moving, or carrying on from the last stage), what it follows, what makes it change, where it ends. One main move per stage, in the drama skill's own camera wording, with speed, distance and the framing at each end. "缓慢推进" alone is not enough.
6. **A spoken line has a before, a middle and an after.** Before: one small thing (a short breath in, a hand that stops). Middle: the line, word for word, in Chinese quotation marks, whole; name the stressed word, and the breath between two sentences. After: the look is held or slides away for half a second. A long line is said in several breaths, split only at the script's own punctuation, each piece in its own quotation marks with a small action between. A word quoted only to mark stress goes in corner brackets (「务实」), never in quotation marks, or the model and the skill's counter take it for another line.
7. **Acting is written as events, never as a feeling.** No "震惊", "尴尬", "后悔" on their own.
   - News lands, is weighed, then shows: the old expression lingers (the smile stays on the mouth while the eyes change first); say what happens inside the half-second freeze.
   - Two to four body signals a stage, three at most on the face, in order (先、随后、最后), at light strength. A small action happens once.
   - A forced smile is partial and lopsided: say which part is the mask and which part leaks (the mouth holds the smile, the eyes do not follow).
   - What the hands are busy with is the punctuation: chopsticks stop in mid-air, a glass hangs, a pen keeps writing.
   - Several people react like a ripple, one after another and differently, never together.
   - One line gives the clip's emotional track: `情绪轨迹：开心 → 笑容凝住 → 确认 → 质问`.
   - No muscle codes, no millimetres. A "do not" line is added only for a failure actually seen in a draft.
8. **Continuity between shots.**
   - The first stage restates where the last shot ended: positions, facing, posture, gaze, what my hands hold. Take it from the previous shot's `ending`.
   - The last stage states the final second in words, so the next clip can be written to match.
   - A cut lands on a visibly different frame and sits on something I do: standing up, turning, sitting down, looking down.
   - Shots in one place share one sentence saying where everyone is, word for word. A prop keeps one description. Each person keeps their side of me and their one garment. My cuff and wrist change only when the count has moved on.
   - Inside a scene every shot after the first takes the last frame of the one before it (`前段尾帧`); the runner extracts it and attaches it, and generates a scene's shots in order for that reason. Set `"chain": false` on a shot that starts somewhere new within the scene.
9. **The room behind me.** In a scene where I turn right round (the car behind me, the door behind me, from the window back into the room), the model has to know all four walls. The place block describes every direction from where I stand; add a second upright view of the place facing the other way (`extra_views` on the shot) for the turn.
10. **References are bound by name and bounded**: say what each one controls and what it does not. Do not describe again what the image already shows; text and image then fight. At most three people are described precisely in a clip; the rest are background doing something specific.
11. **Timings are whole seconds**, stages follow one another with no gaps.
12. **The person behind the lens is written 主人公, never “我” in quotation marks.** Chinese quotation marks are only for words spoken aloud.
13. **No music, no drawn subtitles.** The runner puts the no-music sentence at the start of every prompt and the fixed last line at the end. Do not describe music anywhere in a shot.
14. **Keep the style sentence short.** The acting and the camera need the weight.
15. **When a draft fails, change only the layer that failed** (camera, acting, the line, the look), not everything at once.
16. **A place image made as a wide room view outweighs the words about where I stand.** Draw the place from my spot in the first place (see "A place is drawn from where I stand").

**What you write and what the runner adds.** A prompt is assembled from `film.json` in this order; you write only the parts in the right-hand column. `shots/E01.md` shows the result for every shot.

| Part of the prompt | Comes from |
|---|---|
| `基础视觉风格：…` | `styles`, by the scene's `style` |
| The reference lines (`{{小红}} 是角色小红的形象参考…`, `{{场景}} 是场景参考…`, the previous last frame) | written by the runner from the shot's `people`, the scene's `place`, `extra_views` and `chain` |
| The no-music sentence; `本片段场景设定在：{{场景}}。…；<环境声>。整体电影感基调：…` | the scene's `when` and `tone`, the place's `sound` |
| The place: `空间：…` `光：…` `背景里的人：…` | the place's `block`, word for word in every shot there |
| The first-person sentence and my hands | written by the runner from `hands`, by the scene's era; `hands_note` adds what the hands hold in this shot |
| `人物的起始状态：…` `道具：…` `镜头路径：…` | the shot's `setup` |
| `情绪轨迹：…生成一个由以下N个分镜组成的视频。` | the shot's `track` |
| `分镜1：3秒：…` | the shot's `stages` |
| `画面最后停在：…` | the shot's `ending` |
| The last line (voices and sounds only, no BGM, no drawn subtitles) | written by the runner; it differs when I speak in the shot, which it knows from `lines` |

One stage, as you would write it in `stages[].text` (from the example's S01):

```
镜头向上摇，从台面和手抬到玻璃后面{{柜员}}的脸，停在她胸口以上的近景。她手里的圆珠笔还在单据上写，笔尖没有停；听见存折拍在台面上的声音，她先是笔停住，随后才抬眼，眉毛抬高一点，嘴还闭着。画外响起主人公的声音（三十岁男声，低平，慢，像自言自语）：“全买英伟达”她的目光从存折移到镜头，停了半秒，吸了一小口气后说：“确定？”重音落在「定」字上；说完嘴唇合拢，眼睛没有移开。
```

- A person or place of the shot is written `{{名字}}` the first time it appears in a stage, and by name or 她/他 after that.
- My own line, said to someone in the scene: `画外响起主人公的声音（<lead_voice 的原话>）：“<台词原文>”`.
- Every spoken word, and only spoken words, sits in Chinese quotation marks “ ”; taken together and in order they must equal the shot's `lines`. `film.py check` compares them.
- Narration lines never go in a stage: they are text added in the edit.

### What the first full film showed (2026-11-13)

The first topic at full length: 15 shots, 152 seconds, made in sample mode (480p) and accepted as finished.

- **Eleven of fifteen shots were usable on the first take.** The four re-drafts: my shoes in frame (fixed by removing every mention of shoes and saying legs and feet never enter), a real maker's badge on a car (fixed by describing a plain saloon of the year instead of naming a class of car), the wrong woman holding a prop (fixed by removing the other woman's reference image from that shot), a missing look back (fixed by giving that stage three seconds).
- **Prompts of 1,000 to 1,500 characters held the camera without the grey-box clip.** One shot redone at 3,275 characters cost the same and added the written-in small props.
- **My voice held between 85 and 105 Hz across all scenes from the description alone**; one shouted line came out an octave up. The runner now measures this.
- **Known flaws left in the accepted cut**: a shaped badge on the car in S05, the glass changes type between S09 and S10, my hand lifts a glass in S12, a waiter's face is cut by the top edge in S14, a face very close in S06.
- **A face-filling close-up is the risky shot.** An early take came back with a subtitle drawn by the model and the wrong room behind the face; attaching a frame of the same person from an earlier clip and naming what stands behind her fixed both.
- **Watch which side of things I am on.** In early takes the model put the lens on the far side of the counter. Say what lies beyond my hands in every shot.
- **Cost: 2,008 credits for this version** (drafts 1,499, re-drafts 369, images 140).

### Seedance 2.5 notes

From ByteDance's own prompt guides, read on 2026-11-12. Not all of these have been tested here.

- 2.5 honours whole-second timings; 2.0 ignores them. Do not mix the two models in one episode: they look visibly different.
- Attach references in the order the people first appear.
- A line re-quoted with tone notes after it leaks subtitles. Write each line once.
- Strong emotion words give glowing eyes; water, wave and echo words put bubbling or echo into the sound.
- A voice reference drifts unless the spoken lines stay close in tone to the recording; recordings of 5–10 seconds are the most stable.
- Characters with more than one reading can be mispronounced; 行 is one. If recognition shows a misreading, swap in a homophone.
- A first frame can be attached as an ordinary reference by writing that it is the first frame; other references stay attached.
- Reference images with real human faces are rejected; faces generated on the same account are accepted.

## 9. Judging a clip and a cut

Look at every clip's frame sheet (`.film/qc/<shot>.png`, one frame a second) next to its checklist (`.film/qc/<shot>.md`) before recording `review <shot> pass`. Look at the frames themselves; do not pass a clip because its machine checks passed.

**Reject a clip outright if any of these is true:**

- my face, body, legs or feet appear, or the camera drifts into third person;
- a speaker's mouth does not move with their line, or someone speaks who should be silent;
- a line is missing, changed or added (the machine check says so);
- the model has drawn subtitles or added music;
- readable text or a real brand's mark is in the picture;
- a person does not match their reference image, or the place does not match the other shots of the scene;
- the wrong person holds or does the thing the shot is about;
- the last frame is not the ending the shot describes (the next shot starts from it).

When a clip fails, change only the layer that failed (the camera, the acting, the line, the look) in `film.json` and redo that shot. A shot gets three tries; after that, describe the problem to the owner instead of spending more.

**Then, for the whole cut:**

- [ ] Is every scene of the script there, in order, with every line as written?
- [ ] Am I never seen, and does each scene open on my hands or a move before a face?
- [ ] Is every shot 5 seconds or longer, the average near 10, and is the camera moving in each one?
- [ ] Is there something new to look at every 9 to 12 seconds?
- [ ] Does each cut land on something that happens in the frame, onto a visibly different frame?
- [ ] Do my cuff and wrist match the era of the scene?
- [ ] Does each person keep their garment, their face and their side of me across shots?
- [ ] Is every spoken line a subtitle on the strip, and every narration line text only, never over a subtitle?
- [ ] Is each narration line smaller than what the picture shows, and is every one of them worth keeping?
- [ ] Is the premise gone after 7 seconds, each date line up for 4, and the notice there throughout?
- [ ] Is there no music, and no sound from anyone who is not in the scene?
- [ ] Is every number on screen sourced?

Tell the owner what is still wrong in the cut you hand over. A short list of known flaws is part of the delivery.

## 10. Known limits and untested paths

| Item | State |
|---|---|
| H3: a whole film | Two test clips made; no film has gone through `film.py draft --run` on the H3 engine yet. Open: whether the 4-step turbo is good enough, whether a cheaper 32 GB card has the memory for 10-second clips, the commercial licence |
| The 720p Jimeng route on real shots | Priced and wired into the runner and the default, but the first film was finished from 480p samples, so no shot has yet been generated at 720p through `film.py draft --run`. The first shot of the next film is the test |
| A recording as my voice reference | Supported on the 720p route by setting `lead_voice_sample`; off by default and untried. The written description alone held on the first film |
| The 1080p route | Priced by `budget`; the export step (`jimeng-novel node finalize` on each approved draft) is not automated |
| Fonts outside macOS | The edit uses macOS's Songti SC and Hiragino Sans GB. Elsewhere set `FILM_SERIF`, `FILM_SANS`, `FILM_SANS_BOLD`; untested |
| Script intake | Tried on one script. It marks every line whose speaker it had to guess; read the script yourself |
