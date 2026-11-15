# MiniMax H3 tests

`prompt.txt` is the six-part prompt of one shot (the opening of the example film) exactly as it was sent. All four clips were made from it on a rented PRO6000-96G on 2026-11-13.

| Frame sheet | How it was made | GPU time |
|---|---|---|
| `u22-7s-frames.jpg`, `u22-10s-frames.jpg` | **The default**: autodl.art app 252, workflow U22, 832×1440 | 163 s, 187 s |
| `7s-frames.jpg`, `10s-frames.jpg` | The plain graph built in `series/tools/comfy.py` (`"workflow": ""`), 768×1344, 20 steps | 409 s, 652 s |

What they showed is in `series/FORMAT.md`, "The default H3 setup" and "What the first real H3 clips showed".

## Bench of 2026-11-14: three U22 settings against Seedance 2.5

Four shots of the example film (S01 at the counter, S02 the family dinner, S06 the old friend's toast, S10 the woman with the card), each made once with three settings of U22 from the same English prompt and the same reference images, then set beside the Seedance 2.5 clip of the film. Sheets: `bench/S01.jpg` … `bench/S10.jpg`, one row per clip (top to bottom: Seedance 2.5, then H3 `base`, `full`, `nostyle`), one frame a second. Made with `series/tools/h3_bench.py`.

| Setting | What it changes | GPU time (8 / 10 / 14 s shot) | What it did |
|---|---|---|---|
| `base` | U22 as saved: style LoRA MysticXXX at 0.5, turbo, 12 steps | 121 / 170 / 284-291 s | The protagonist's knees or lap in frame in two of four shots (S06, S10); the girlfriend's alarm in S01 played as a grin |
| **`nostyle`** (now the default) | style LoRA off | 117 / – / 281 s | Hands only in every shot; the acting beats land (S01's alarm, S02's father pointing at the door, S06's toast); the closest to 2.5 |
| `full` | style LoRA off, no turbo, 24 steps | 191 / 356 / 466-477 s | As good as `nostyle`, a little sharper, at about 1.6 times the GPU time |

Every one of the 12 H3 takes said every scripted line word for word (speech recognition, `jimeng-novel transcribe` on the sound alone). The staging of every shot followed the Seedance clip beat for beat. H3 is still a little wider in angle and softer in faces than 2.5; the 2.5 clip of S06 had a readable banner that no H3 take drew.

How the time went on a take (after the fixes below): setup 0 s, sending the job 15-25 s (more when a reference fetch had to be retried), rendering 117-477 s, downloading the clip 20-85 s.

What the link to the rented server taught (all now handled by the runner): uploads to the server crawl at 1 to 3 KB/s, so the references go to Jimeng's picture CDN and the server fetches them (`h3.refs`); the fetching node gives up after 5 s, so a job that failed only on a fetch is sent again and ComfyUI keeps what it already fetched; a status request now and then fails on an SSL handshake, so the wait loop rides it out; downloads break off, so they resume; the saved workflow and the node definitions are kept on disk between rentals (they took 230 s to fetch).

## Second bench (2026-11-14, evening)

Two shots of the Bitcoin episode, a fixed seed each, so rows differ only by the setting: `bench2/S03.jpg` (the dinner table) and `bench2/S02.jpg` (the café). Rows top to bottom: the old prompt; the new prompt (voices, performance, movement, texture); plus the sharpness-trained upscaler; plus the undistorted-lens sentence, which is now the default. Results are in `series/FORMAT.md`, "Smoothing, jerky movement and flat lines on H3".
