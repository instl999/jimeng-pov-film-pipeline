# Worked example: 假如2001年全仓买入英伟达

A finished film made with this pipeline: ten scenes, 15 shots, 2 min 34 s, first person throughout. Use it to see what each file looks like when it is done. The finished video and the full-size clips are not in the repository; the covers and six stills are.

| File | What to learn from it |
|---|---|
| `source/script.txt` | The rough script as the owner wrote it (two lines that named real people are already reworded) |
| `DECISIONS.md` | A filled-in decision sheet: what was put to the owner before anything was made |
| `film.json` | The whole film. **Shot `S01` is the model to imitate**: it is in the current two-layer form at 3,275 characters. Its place, `证券营业部柜台`, shows a place `block` |
| `shots/E01.md` | The shot list generated from `film.json`: this is what the owner signs off |
| `cover/E01.md` | The two cover-art prompts, 3,000+ characters each |
| `out/E01.cover.3x4.jpg`, `out/E01.cover.4x3.jpg` | The finished covers |
| `stills/` | Frames of the finished cut: the title block, a subtitle on its strip, a date line, a narration line |
| `cast/` | The reference images, shrunk to small JPEGs |

## Read this before you copy anything

- **Shots `S02` to `S15` are older and shorter than today's rule.** They were written at 1,000 to 1,500 characters, before the 3,000-character floor, and are kept word for word as `"raw"` prompts because the film was already finished. `film.py check` lists them as "kept as written". Do not imitate their length or their one-block form. Write new shots like `S01`.
- **The film was finished from 480p samples** (`"finish": "sample"`). New films default to 720p.
- **`"accepted": true` and `"budget": 0`** mark it as finished: nothing more can be generated in this folder. That is deliberate.
- Copy structure and level of detail. Never copy sentences: every room, person and beat in your film is its own.

## Try the tools on it

```bash
python3 series/tools/film.py check  examples/nvidia-2001      # ends with "0 failed"
python3 series/tools/film.py budget examples/nvidia-2001      # what each finish would cost (says "over the cap": the cap is 0)
python3 series/tools/film.py cover  examples/nvidia-2001      # sets the titles on the cover art again
python3 series/tools/film.py intake examples/nvidia-2001/source/script.txt /tmp/try-intake   # what step 1 gives you
```

## What happened when it was made

- Eleven of fifteen shots were usable on the first take. The four that were redone: the protagonist's shoes in frame; a real maker's badge on a car; the wrong woman holding a prop; a missing look back. The fixes are in the table in `AGENTS.md`, step 8.
- Known flaws left in the finished cut, all told to the owner: a shaped badge on the car in S05; a glass changes type between S09 and S10; the protagonist's hand lifts a glass by itself in S12; a waiter's face is cut by the top edge in S14; a face very close to the lens in S06; one shouted line an octave higher than his other lines in S02.
- Cost: about 2,000 credits for the clips and images of this version, plus 24 for the two covers.
