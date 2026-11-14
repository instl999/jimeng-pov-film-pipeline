# MiniMax H3 tests

`prompt.txt` is the six-part prompt of one shot (the opening of the example film) exactly as it was sent. All four clips were made from it on a rented PRO6000-96G on 2026-11-13.

| Frame sheet | How it was made | GPU time |
|---|---|---|
| `u22-7s-frames.jpg`, `u22-10s-frames.jpg` | **The default**: autodl.art app 252, workflow U22, 832×1440 | 163 s, 187 s |
| `7s-frames.jpg`, `10s-frames.jpg` | The plain graph built in `series/tools/comfy.py` (`"workflow": ""`), 768×1344, 20 steps | 409 s, 652 s |

What they showed is in `series/FORMAT.md`, "The default H3 setup" and "What the first real H3 clips showed".
