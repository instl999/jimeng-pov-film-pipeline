# film.json

One file per film, at `PROJECT/film.json`. `series/tools/film.py` reads it and generates everything else. The first topic's file (`假如2001年全仓英伟达/film.json`) is a full worked example; its first shot, S01, is in the two-layer form described here.

## Top level

| Key | What |
|---|---|
| `title` | The film's name |
| `episode` | `"E01"`. Names the generated files (`shots/E01.md`, `out/E01.mp4`) |
| `series` | `".."` for an episode of a series: the film reads `../series.json`, which supplies `camera`, `engine`, `finish`, `h3`, `notice`, `titles`, `end_card`, `floor`, `place_floor`, `reroll_rate` and (when set there) `lead_voice`; puts the series `look` in front of every style; and caps the film at what is left of the run's `budget`. Leave those keys out of the episode: one set differently fails `check`. See `series/tools/series.py` and AGENTS.md, "A run of scripts" |
| `premise` | The two title lines shown for the first seconds, e.g. `["假如你在2001年", "全仓买入英伟达"]` |
| `notice` | The AI notice, small in the top right corner for the whole video |
| `source` | The script as plain text, e.g. `"source/nvidia-2001.txt"`. Lines are checked against it |
| `camera` | `"first"` (default: the camera is the protagonist's eyes, the series' own form) or `"third"` (an ordinary drama: a cinema camera follows the action and the lead is seen like everyone else). See FORMAT.md, "Third person" |
| `engine` | `"jimeng"` (default: Seedance 2.5 through `jimeng-novel`) or `"h3"` (MiniMax H3 in ComfyUI on a rented AutoDL Art GPU). See "The H3 engine" below |
| `finish` | `"720p"` (default), `"sample"`, `"sample_up"` (480p takes, passed shots upscaled to 1080p by `film.py upscale`) or `"1080p"`; Jimeng engine only. See FORMAT.md section 8 |
| `facts` | `{"<figure as shown>": "<where it comes from>"}` for every money figure, price, multiple or percentage on screen (title, date and narration lines). `check` fails one without a source |
| `budget` | Credit cap for this film. `null` means nothing may be generated |
| `reroll_rate` | Share of shots expected to be redone, for pricing. `0.3` |
| `floor` | `3000`: the length floor, a hard rule of the series. (a) a shot's whole prompt, meaning the place block plus the shot's own layer, is at least 3,000 Chinese characters; (b) the shot's own layer (`setup`, `track`, `stages`, `ending`) is at least 2,000 of them, so a long place block cannot carry a thin shot; (c) a place whose image is still to be made has at least 3,000 in `block` plus `detail`. On the H3 engine (a) is 8,000 and (b) is 5,334. `film.py check` counts all three. |
| `titles` | `{"premise_seconds": 7, "date_seconds": 4}` |
| `end_card` | `null`, the default on both engines: the film ends on the last frame of its last shot, with no black tail. `{"seconds": 2, "text": "假如……系列"}` adds a black card after it, only when the owner asks for one |
| `styles` | Named style sentences. `asset` is the one for people and place images; a scene names one of the others |
| `hands` | My hands and cuffs by era, e.g. `{"2001": "三十岁男性的双手……"}`. A scene names one |
| `lead_voice` | The description of my voice, reused word for word |
| `lead_voice_sample` | A recording of my voice, attached on the 720p route when I speak. Optional |
| `people`, `places` | Below |
| `line_exceptions` | Subtitle parts that are deliberately not in the script (a replaced name) |
| `line_changes` | Script lines that are not in the film as the script reader found them, either reworded on purpose (a real name) or because the reader took a stage direction for speech: `{"scene": "P09", "line": 6, "now": "…", "why": "…"}`. `now` is the words actually spoken. `line` counts the scene's spoken lines as `python3 series/tools/intake.py SCRIPT.txt` lists them. The original words are not repeated here |
| `accepted` | `true` once the owner has approved the cut. Unlocks `cover`; shots are then left as they are |
| `cover` | `{"shot": "S01", "t": 7.05, "focus": 0.35, "tall": 0.6, "side_lines": ["假如你在", "2001年", "全仓买入", "英伟达"]}` |
| `scenes` | Below, in film order |

## people

```json
"小红": {
  "images": {"默认": "cast/小红.默认.png", "2020": "cast/小红.2020.png"},
  "body": "二十六七岁的女性，……（外观白描，按 jimeng-drama 角色模板的长度）",
  "voice": "年轻女声，轻，尾音不耐烦",
  "variants": {"2020": "只写和默认形象不同的部分"}
}
```

`images` maps a look to its file; a picture still to be made is always named `cast/<name>.<look>.png` (the generator saves it under that name), and a place view `cast/<place>.<view>.png`. `body`, `voice` and `variants` are only needed while an image is still to be made: `film.py build` writes `cast/<name>.md` from them, `film.py images --run` generates what is missing. I ("我") am not a person here: I have no face, only `hands`.

## places

```json
"证券营业部柜台": {
  "master": "日·竖·柜台",
  "views": {
    "日·竖·柜台": {"image": "cast/证券营业部柜台.日·竖·柜台.png", "vantage": "站在柜台前一步，眼睛高度一米六五，正对递物口"},
    "日·竖·大门": {"image": "cast/证券营业部柜台.日·竖·大门.png", "vantage": "同一位置转身一百八十度，正对玻璃门"}
  },
  "style": "cold",
  "sound": "<大厅里低低的人声，远处电话铃响了又停，持续>",
  "block": ["空间：……", "光：……", "背景里的人：……"],
  "detail": ["只进场景图提示词的补充：材质、磨损、桌上的东西……"]
}
```

- `block` is the place layer of every shot set here, word for word: exactly three paragraphs, `空间：` (the space in every direction from where I stand), `光：` (the light) and `背景里的人：` (the background people). Nothing about one particular shot goes in it. Everything else about the place goes in `detail`.
- `master` is the first image made and is upright, seen from where I stand; the other views are derived from it. `vantage` is one sentence saying where the eye is and what it faces.
- While a view's image is still to be made, `block` plus `detail` must reach the floor.

## scenes

```json
{
  "id": "P01", "title": "画面一", "date": "买入第一天",
  "place": "证券营业部柜台", "style": "cold", "hands": "2001",
  "when": "2001年1月的一个冬天上午，北方小城，室内",
  "tone": "冷调，表演克制、生活化……",
  "shots": [ … ]
}
```

`date` is the line under the title; when it changes between scenes the new one comes up alone for `date_seconds` with a click. `intake` also leaves `script` (the scene's full text) and `lines` (the spoken lines it found, a `?` after a speaker it had to guess) as working notes; the runner does not use them once shots exist.

## shots

```json
{
  "id": "S01", "seconds": 10, "camera": "上摇、右摇跟人",
  "people": {"柜员": "默认", "小红": "默认"},
  "view": "日·竖·柜台",
  "chain": false,
  "hands_visible": true, "hands_note": "",
  "setup": ["人物的起始状态：……", "道具：……", "镜头路径：……"],
  "track": "开心 → 笑容凝住 → 确认 → 质问。",
  "stages": [{"seconds": 1, "text": "……"}, {"seconds": 3, "text": "……"}],
  "ending": "画面最后停在：……",
  "lines": [["我", "全买英伟达"], ["", "确定？"], ["我", "确定"]],
  "narration": {"open": {"text": "来买股票了.."}, "close": {"text": "女朋友走了.."}},
  "sfx": [{"t": 0.15, "file": "cold-open-hit.mp3", "gain_db": -9}],
  "must": ["存折拍在台面上", "柜员抬头"],
  "must_not": ["主人公的鞋入画"]
}
```

- `seconds`: a whole number from 5 to 30; `stages` must add up to it.
- `people`: who is in the shot and in which look, in the order they first appear. At most three described precisely.
- `view`: which image of the place to attach (default: the master). `extra_views` adds a second one for a turn: `[{"alias": "证券营业部柜台·大门", "view": "日·竖·大门", "says": "转身后看到的方向"}]`.
- `chain`: every shot after the first in a scene takes the previous shot's last frame. `false` turns that off.
- `setup`, `track`, `stages`, `ending`: the shot's own layer. With the place block they must reach the floor (3,000), and on their own two thirds of it (2,000). In them the protagonist is written `主人公`.
- `lines`: `[speaker, words]` in order, each as one subtitle part of at most ten characters. The speaker is the person's name as in `people`; `"我"` marks my own lines (they set the tail sentence, the voice reference and the pitch check). The words, taken together, must equal the Chinese-quoted words in the stages.
- `narration`: text-only lines at the start (`open`) or end (`close`) of the shot; `"t": [from, to]` overrides the automatic timing. Only where it earns its place.
- `sfx`: effects from `series/sfx/`. The click on a date change is added automatically.
- `must`, `must_not`: what to look for on the frame sheet when the clip is checked.
- `previs: true` attaches a clip you supply at `previs/E01/ref/<shot>.mp4` as a camera-movement reference. Rarely worth it: it costs about half as much again and a fully written shot follows its camera path without one.
- `take`: the clip file to use in the edit when it is not `<id>.mp4`.
- `raw`: a whole prompt kept word for word, for shots written before the two-layer form. A shot with `raw` has no `setup`/`stages`.

## The H3 engine

A film made with MiniMax H3 keeps everything above and adds:

```json
"engine": "h3",
"h3": {"gpu": "pro6000-p", "price": 8.8, "budget_yuan": 40,
       "steps": 20, "turbo": false},
"styles_en": {"cold": "Photorealistic period footage with the look of fine-grained 35mm colour negative, ..."},
"hands_en": {"2001": "a thirty-year-old man's hands with short nails, the frayed cuffs of an old navy cotton jacket, bare wrists."}
```

| Key | What |
|---|---|
| `h3.app`, `h3.version` | The application on autodl.art the GPU runs. **Default `spcwDDc6XW`, app 252 "MINIMAX-H3提速500高画质"** (https://autodl.art/app/market/252), `latest`. Leave them out to use the default |
| `h3.workflow` | The workflow saved in that app that makes the clip. **Default `U22-MiniMaxH3-多参考生视频-优化版`** (U22, multi-reference to video, up to 9 reference images, 832×1440 with a built-in second pass). `""` uses the plain graph built in `comfy.py` instead (768×1344, slower) |
| `h3.gpu`, `h3.price` | The GPU type and its price in yuan an hour, as quoted on the site that day. The price actually charged is read back from the instance |
| `h3.tuning` | Changes to U22's own settings, from `TUNING` in `series/tools/comfy_workflow.py`. **Default `{"style_lora": 0}`**: U22's style LoRA off, which the bench of 2026-11-14 found better (`FORMAT.md`). `{"style_lora": 0, "turbo": false, "steps": 24, "first_steps": 18}` is a little sharper at 1.6 times the GPU time |
| `h3.tuning` knobs | `turbo` takes `false` (off) or a number (the speed LoRA's strength, U22: 1.0); `upscaler` names the model of the latent upscale between U22's two passes (U22: `minimax_h3_latent_upscaler_3d_fp16.safetensors`; the server also has `h3_upscaler_sharpness_2000steps_v0.1_fp32.safetensors`, the default since the bench of 2026-11-14; `h3_clean_latent_upscaler_film_epoch200` is listed but does not load in that node). The rest are in `TUNING` |
| `h3.post` | What is done to every H3 clip when it is fitted to its length. **Default `{"sharpen": 0.5, "grain": 5}`**: a light unsharp mask and fine moving grain, so U22's smooth skin and cloth read as 35mm film. `0` turns either off. It hides smoothing; it does not add detail |
| `h3.refs` | How the reference images reach the rented server. **Default `"jimeng"`**: each is shrunk to a JPEG of at most 1024 px, put on Jimeng as an asset (free, about 20 s each, done before the GPU is rented) and the server fetches it from Jimeng's picture CDN by its signed address (valid about 15 days, cached in `.film/state.json`). `"upload"` sends them through the server's gateway instead, which measured 1 to 3 KB/s on 2026-11-14 (a 55 KB picture took 20 to 90 s and half the sends timed out). Only the U22 workflow takes addresses |
| `h3.budget_yuan` | Cap on GPU spend for this film. The instance is given back when a run reaches it |
| `h3.steps`, `h3.turbo` | Only for the plain graph (`"workflow": ""`): 20 sampling steps, or the 4-step turbo LoRA. U22 sets its own (12 + 4, with its turbo LoRA) |
| `h3.minutes_per_shot` | Optional. Overrides the runner's own estimate of GPU minutes a take (it estimates from the shot's length) |
| `styles_en`, `hands_en` | English versions of the style sentences and of my hands, by the same keys as `styles` and `hands` |
| `people.<name>.en` | One or two English sentences on the person's face, hair and clothes |
| `people.<name>.voice_en` | Required for everyone who speaks. The voice in English: age, sex, accent, pitch, texture, pace, the habit that makes it theirs ("a woman in her late forties, Mandarin with a northern lilt, slightly hoarse, quick when anxious, her phrases falling away at the end"). The runner puts it in the prompt as "(S1) is the voice of <Subject 1>: ..." |
| `lead_voice_en` | Required when I speak. My voice in English, the same words in every shot, so the model gives me one voice through the film. Goes in as "(S2) is the protagonist's own voice, heard from just behind the camera, close and dry: ..." |
| `places.<name>.en`, `.sound_en` | The place in English, and its ambient sound in English |

and on every shot:

```json
"h3": {
  "summary": "A single first-person shot at the counter of a securities office in 2001: ...",
  "body": "The view starts tilted slightly down at the pale-grey counter of {证券营业部柜台}. ... Beyond the glass sits {柜员} (S1) ... she asks in a flat, professional young female voice, <d>[Chinese] 确定？</d> ... The protagonist (S2), unseen behind the camera, answers in an off-screen low, flat, slow male voice of about thirty, <d>[Chinese] 确定。</d> ..."
},
"notes": ["导演备注：……（分镜之外的表演、调度、衔接说明，算进 8,000 字）"]
```

- `body` is the shot in H3's own prompt language, written from the Chinese stages: English, one `[Shot 1]` (the runner adds the tag), the camera's path in plain words, each acting beat in order, and every spoken line word for word inside `<d>[Chinese] ...</d>` with its speaker's `(S1)`, `(S2)` id outside the tag. `{名字}` stands for a person or the place of the shot and becomes its `<Subject N>` label. My own lines are written as an off-screen voice. MiniMax's guide puts a description at 350 to 500 English words; under 250 is refused.
- **Voices.** The runner reads who each `(S1)`, `(S2)` is from `{名字} (S1)` and `protagonist (S2)` in `body`, and describes each voice from `voice_en` / `lead_voice_en`. A voice the body does not tie to anyone (a mother on the phone) is named in `"h3": {"voices": {"S2": "母亲"}}`. `check` refuses a voice id it cannot place, or a speaker with no English voice.
- **Delivery is written beside every line**, in the body: what the speaker is doing just before it, then how it comes out (pitch, volume, pace, breath, where it breaks or pauses, what they want from the other person), then what their face does after. "says, voice tight but not shouting, <d>...</d> pausing as if the number burns" works; "says sadly" does not.
- **One action at a time.** Erratic movement comes from beats crowded together: give each physical action its own clause and its own second or two, and say who is still while it happens.
- The runner writes the rest of the six-part prompt (subject definitions, voices, retention analysis, the style with a texture sentence, the first-person sentence, a performance and a movement paragraph, soundscape with a dialogue-mix sentence, "no music") from the film file, and numbers the reference images `<Picture 1>`, `<Picture 2>` in the order people, place, extra views, previous last frame.
- There is no negative prompt in H3. Say what should be there ("bare painted walls") instead of what should not.
- **The 8,000 rule**: the shot's Chinese layer (place block, setup, stages, ending, notes, must and must-not lists) plus its `h3.summary` and `h3.body` must reach 8,000, a Chinese character counting one and an English word one. `film.py check` prints both parts for every shot.
- A shot runs 5 to 15 seconds on this engine.

## Generated, do not edit

`shots/E01.md`, `post/lines/`, `post/E01.plan.json`, `post/E01.cues.json`, `cast/<name>.md` (written once, when missing), `.film/` (state, check sheets, cover candidates).
