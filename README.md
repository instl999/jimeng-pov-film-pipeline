# First-person short films, from a rough script to a finished video

A pipeline an AI agent can run end to end: you hand it a rough Chinese script, it writes the shot list, waits for your yes, generates the clips, checks them, edits the film and makes two covers.

<p>
<img src="examples/nvidia-2001/out/E01.cover.3x4.jpg" width="270" alt="3:4 cover of the example film">
<img src="examples/nvidia-2001/out/E01.cover.4x3.jpg" width="480" alt="4:3 cover of the example film">
</p>

- **The format**: vertical 1080×1920, first person throughout (the camera is the protagonist's eyes), every scripted line spoken inside the clip and subtitled on a black strip, short text-only narration, no voiceover, no music. Stills: [`examples/nvidia-2001/stills/`](examples/nvidia-2001/stills/).
- **The generator**: Seedance 2.5 through Jimeng's `jimeng-novel` command line (default), or MiniMax H3 in ComfyUI on a GPU rented by the minute.
- **The guard rails**: the script is followed word for word; nothing is generated until you have signed off the written shot list; spending stops at a cap you set; every clip is checked for its lines by speech recognition and looked at before it is used.

## Give it to an agent

Any coding agent with a shell and the ability to look at images will do. Tell it:

> Clone this repository and read `AGENTS.md` from start to finish, then follow it. My script is at `<path>`. Stop and show me the shot list and the price before generating anything.

Everything the agent needs is in three files and one example:

| | |
|---|---|
| [`AGENTS.md`](AGENTS.md) | The operating manual: rules, setup, every step with its command, what to do when a clip fails |
| [`series/FORMAT.md`](series/FORMAT.md) | The craft: how a shot is written, what the film looks and sounds like, how a clip is judged |
| [`series/FILM.md`](series/FILM.md) | The one file a film is written in, key by key |
| [`examples/nvidia-2001/`](examples/nvidia-2001/) | A finished film to learn from: script, decision sheet, film file, shot list, cover prompts, covers |

## What you need to provide

- A Mac (developed and tested on macOS; other systems need their own Chinese fonts set, see `AGENTS.md`).
- `ffmpeg` built with libass, Python 3.9+.
- A Jimeng account with credits, and `jimeng-novel` installed and logged in **by you**: the agent never handles your login.
- Your script: each scene starting on its own line with `画面一：`, `画面二：` and so on.
- Two answers when the agent stops to ask: "go" on the shot list with a credit cap, and "good" on the cut.

`python3 series/tools/film.py doctor` checks all of it.

## What it costs

The example film, 2 min 34 s in 15 shots, is about 3,950 credits at 720p including re-takes (it was actually finished from 480p samples for about 2,000). On the H3 engine a 10-second clip is about 1.5 yuan of GPU time.

## What is not proven yet

Stated plainly in `series/FORMAT.md`, section 10: one film has been made, at 480p; the 720p route and the H3 engine are wired and rehearsed but have not carried a whole film; the fonts are macOS's.

No licence has been chosen for this repository yet.
