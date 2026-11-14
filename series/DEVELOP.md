# From an idea to a script

Use this when the owner has only an idea ("假如2010年买了比特币", "一个外卖员突然能听见顾客心声", or just "想拍个逆袭的") and no script. You work like the story agent of a short-drama studio: ask once, decide the rest, and hand back a brief, a setting, an outline and a finished episode script that the rest of the pipeline (`AGENTS.md`, from Step 1) shoots without guessing.

The owner decides direction and pays; you decide craft. Everything you write here becomes "the owner's script" the moment they approve it, and from then on it is followed word for word.

The worked example is `examples/bitcoin-2010-develop/`: an idea in one line, the brief, the setting, a three-episode outline and the first episode's script, all as they should look.

## 0. What is fixed and what the idea supplies

Fixed for every film in this series, so never asked: first-person camera (the protagonist is never seen, only his hands), vertical 9:16, real-looking people, no voiceover, no music, short text-only narration lines, the locked text on screen (`series/text-styles.json`). A story that only works if we see the protagonist's face, or that needs a narrator, has to be reshaped until it works through his eyes; say so in one line if that changes the idea.

What first person is good at: people talking at you, reacting to you, coming round to you; a choice you make with your hands; places you walk into. Build the story out of those.

**An idea built on inner voices** (hearing thoughts, a system talking in his head, a narrator) cannot be shot as written, because there is no voiceover. Turn the inner voice into something in the scene: the person mutters the thought aloud under their breath, or it shows on their phone screen, and the protagonist answers it. Put this change to the owner as a question in the question card ("心声没法用画外音，我打算让顾客自己小声嘟囔出来，可以吗？"), not as an assumption.

The idea supplies everything else: what happens, to whom, in what world, for whom, how long.

## 1. Read the idea and start the folder

```bash
python3 series/tools/film.py develop films/<series-name> "<the owner's idea, word for word>"
```

This writes `films/<series-name>/story/brief.md`: the idea, the list of things to settle, and a price table for common lengths. Everything for the series lives in `story/`; each episode later gets its own film folder next to it.

Read the idea and write down, for yourself, what it already answers. "假如2001年全仓英伟达，身边人都看不起我，后来都来巴结" already gives the genre (逆袭爽剧), the hook, the shape (doubt, then the turn) and the era. Do not ask about anything the idea already says or plainly implies.

## 2. Ask once: the question card

Send the owner **one** message with every open question, each with 2 to 4 options and the recommended one first, and the line "不想选的我按推荐来". Paste the same text into `story/brief.md` section 2 when you send it, and the owner's reply under it when it comes. Ask only what would send the whole thing the wrong way if you guessed wrong. Typically:

| # | Question | Options (recommended first) | Skip it when |
|---|---|---|---|
| 1 | 方向 | Only when the idea is vague: three direction cards, each a name, a one-line selling point and three tags | the idea has a premise |
| 2 | 基调 | 爽燃逆袭 / 轻喜 / 温情 / 悬疑（pick from what fits the idea） | the idea implies it |
| 3 | 受众与平台 | 抖音、快手竖屏，18-40 岁，泛人群 / 女性向 / 男性向 | stated |
| 4 | 集数 × 单集时长 | see the table below; recommend from the idea's size | stated |
| 5 | 年代与地点 | the most natural reading of the idea / one alternative | the idea fixes it |
| 6 | 主人公 | 男 / 女; age; where he starts (the lower, the better the turn) | stated |
| 7 | 结局 | 完胜 / 反转 / 留个钩子做续集 | the idea fixes it |
| 8 | 一定要有的、不能有的 | free answer | never skip |

How to size it (pick the row that fits how much happens in the idea, and say the price from `brief.md` §5):

| Idea | Recommend | Why |
|---|---|---|
| One reversal, one payoff ("被看不起 → 打脸") | 1 集 × 2-3 分钟 | the example film's shape; every beat fits |
| A climb in stages over years | 1 集 × 2-3 分钟, or 3 集 × 90 秒 | three stages fall naturally into three episodes |
| A mystery or a relationship that needs time | 3-5 集 × 60-90 秒 | each episode needs its own hook |

Never recommend more than 10 episodes for a first test of an idea; offer to continue later.

If the owner says "你定" or does not answer a question, take the recommended option and list it under 「我做的假设」 in the brief. Do not ask twice.

## 3. Fill in the brief

Complete every `<<...>>` in `story/brief.md` §3 and §4. The lines `集数：` and `单集时长：… 秒` are read by the tools; keep their form. Then:

```bash
python3 series/tools/film.py develop films/<series-name>
```

prints what is filled, what is missing and what the whole series costs.

## 4. The setting: `story/setting.md`

Write it in Chinese, in this order. Numbers in brackets are minimums.

1. **一句话故事**（30-50 字）: from a concrete moment, with the protagonist, one conflict and one open question. Not "讲述了一个……的故事".
2. **卖点**（3 条）: each written as a scene you could shoot, never an adjective. Not 「爽感十足」 but 「当年骂他败家的父亲，站在新车前半天说不出话」.
3. **人物**（主要 4 个以内）: for each, one line each of 身份（带一个标志）, 想要什么, 最怕什么, 和主人公的关系, 怎么变（起点 → 转折 → 终点）, and the one garment that never changes. Give every person a name or a fixed title (父亲, 柜员, 兄弟); avoid 苏、沈、陆、顾、萧、叶、林 as surnames.
4. **主线引擎**: what the protagonist wants, what keeps producing new trouble, what failing costs. Test: remove any scene, and the next one still grows out of this engine.
5. **关系引擎**（1 组以上）: `A↔B：关系 + 现在的张力`, then at least three changes caused by events, then where it ends.
6. **规则**（1-3 条, only if the world has them）: each with its trigger and its cost. A real-world story uses real-world rules: a market, a family, a workplace.
7. **时间线**: the years or days the story jumps through; these become the date lines on screen.

First person shapes the people: everyone who matters must come to the protagonist and talk to him. A person who only exists behind his back cannot be shown.

## 5. The outline: `story/outline.md` (only for more than one episode)

One section per episode:

```
## E01 集名（4-12 字，取本集最大的反转或钩子）
- 梗概：主人公做了什么 → 阻碍 → 结果 → 局势怎么变
- 【开场钩子】第一个画面或第一句话里的冲突
- 【爽点/反转】本集真正发生的打点
- 【结尾钩子】（强 / 中 · 生命 / 目标 / 关系 / 身份 / 证据）
- 场景：地点（日/夜）……；出场：……
```

- E01 opens on the protagonist doing the thing that cannot be undone, with someone already reacting. It plants what the audience will wait for.
- Each later episode's opening is the next beat after the last episode's ending hook, never a recap.
- Every episode ends on a strong or medium hook, except the last, which closes.
- The same conflict shape (施压 → 反击 → 完胜) never runs three episodes in a row: change the opponent, the stakes, the place or the method.
- One name for each place and person in every episode; the image tools treat two names as two things.

## 6. The script: `story/E01.txt`

This is the exact format the pipeline reads. Anything else gets guessed at.

```
片头：假如你在2010年 / 买了一万块比特币
集：E01

画面一：（2010年5月　买入第一天）
地点：网吧，夜
出场：同学
△ 主人公的右手握着鼠标，屏幕上的付款按钮按下去，跳出一行绿字。
同学（凑过来看屏幕，笑出声）：你花一万块买这个？
同学：这不就是游戏币吗？
△ 主人公的手把鼠标推开，从桌上拿起半瓶冰红茶。
主人公：先放着。
【字幕：来买比特币了..】

画面二：（2010年5月　买入第一天晚上）
……
```

| Line | Rule |
|---|---|
| `片头：一行 / 二行` | The two title lines, 9 characters or fewer each, on one line with ` / ` between them. Before the first scene |
| `集：E01` | Which episode this file is. Before the first scene |
| `画面N：（日期行）` | One scene. The bracket is the date line shown on screen when the time changes ("2007年　买入第约2555天"). One time and one place per scene |
| `地点：` | Where, and 日/夜. The same name every time the place comes back |
| `出场：` | Everyone who speaks or is seen, 、-separated; `出场：无` when nobody but the protagonist |
| `△ …` | One action per line, only what can be seen or heard: a hand, an object, a door, a face changing. Never a thought or a feeling |
| `名字（how）：台词` | One spoken line. The protagonist is `主人公`. Every speaker is on the `出场` line |
| `【字幕：……..】` | A text-only narration line, 2-7 characters, ending in two dots. Never spoken |

How it should read:

- **Length.** About four spoken characters a second, plus about five seconds a scene for movement. A 2-minute episode is about 6-10 scenes and 300-400 spoken characters. `script-check` estimates the length and compares it with the brief.
- **Lines.** Short, everyday, 15 characters or fewer; a longer thought is two lines with an action between. The person's job, age and era show in their words. No exclamation of feelings ("我好难过"); say the thing that hurts.
- **The protagonist speaks little.** Others talk at him; he answers in a word or two, or with his hands. Under a third of the words are his. His few lines carry weight ("先放着", "确定", "以前他们都不来").
- **Every scene changes something**: someone leaves, someone comes round, an object changes hands, the stakes go up. A scene where nothing changes is cut.
- **A new thing to look at every 10 seconds or so**: a person, an object, a move to another part of the room.
- **Echoes.** A line or object from early on comes back changed: the friend who said 「这不就是游戏币吗」 later asks to borrow some.
- **Narration lines** only where they add a dry understatement the picture cannot: 「给我爸买了辆车..」 over the father speechless in front of the car. Most scenes have none.
- **Avoid** stock phrases (眼底闪过一丝、嘴角勾起一抹、空气仿佛凝固), anyone explaining what both already know, inner voice of any kind (os, vo, 内心), and showing the protagonist's face, back or reflection.
- **Real people and brands**: no real public figure's name anywhere; a brand may be said in a line but is never shown.

Check it:

```bash
python3 series/tools/film.py script-check films/<series-name>/story/E01.txt
```

Fix every ERROR. "ready for intake" with notes is not done: read every note and fix it unless you have a reason, and write the reason in the brief's 「我做的假设」. Then run `film.py develop films/<series-name>`: it also checks the title and one-line story lengths, the setting's sections and the outline's episodes.

## 7. Read it as the audience, then improve it once or twice

Before showing anything, go through the script against these, fix what fails, and repeat at most twice:

1. **The first three seconds** are already the conflict: the hand doing the thing, someone reacting.
2. **Every scene** has a turn: something the audience did not have at its start.
3. **The payoff** is something you see happen (the father silent in front of the car), not something someone says happened.
4. **The ending** lands: a last line or image that answers something from the start.
5. **Each person** sounds like themselves; cover the names and you can still tell who speaks.
6. **Nothing is said twice** and nobody explains what the other already knows.
7. **It can be shot in first person**: every scene happens in front of the protagonist.
8. **The length** is within the brief.

Do not report a self-score to the owner. Report what you changed.

## 8. Stop 0: show the owner, wait for their yes

Send `story/brief.md`, `story/setting.md`, `story/outline.md` (if more than one episode) and `story/E01.txt`, and say, with your numbers:

> 立项单、设定、大纲和第 1 集剧本都在这里。一句话故事：……。共 N 集，每集约 M 秒，第 1 集 K 场。我替你定了这些：……（立项单第 4 节）。按 720p 整部大约 X 积分（含重拍和角色场景图；第 1 集大约 Y）。你看看剧本，哪里要改直接说；没问题就回我一句「可以」，之后就照这一稿一字不改地拍。

Wait. When they ask for changes, make them and show the changed parts again. When they say yes, record their words exactly:

```bash
python3 series/tools/film.py develop films/<series-name> --approve "<the owner's words>"
```

`film.py intake` refuses a script from a `story/` folder until this is recorded, and again if the script changed after it.

**More than one episode:** the owner approves the outline and E01 first. Write the remaining episodes only after that, each in its own `story/E0N.txt`, run `script-check` on each, and show them together for a second yes (`--approve` again). An outline change means every later episode is rewritten.

## 9. Then make the films

Each episode is its own film folder beside `story/`:

```bash
python3 series/tools/film.py intake films/<series-name>/story/E01.txt films/<series-name>/E01
```

and from here follow `AGENTS.md` from Step 2. The decision sheet is mostly settled already, and the narration lines you wrote are listed on it. For E02 and later, take the look and the cast of the episode before, so people and places stay the same and their images are not made twice:

```bash
python3 series/tools/film.py intake films/<series-name>/story/E02.txt films/<series-name>/E02 --like films/<series-name>/E01
```
