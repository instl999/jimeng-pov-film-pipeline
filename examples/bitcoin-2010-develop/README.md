# Worked example: from a one-line idea to a script

The owner's whole input was one line: 「假如2010年用一万块买了比特币，身边人都笑我，后来他们都后悔了」. This folder is what `series/DEVELOP.md` turns that into, up to Stop 0, the point where the owner reads it and says yes.

| File | What it shows |
|---|---|
| `story/brief.md` | The question card exactly as sent (one message, recommended options first), the owner's reply 「你定吧，一定要有家里人那段，别拍成炒币广告」, every decision that followed, and the assumptions made on the owner's behalf |
| `story/setting.md` | One-line story, four selling points written as scenes, the people (with the one garment each keeps), the engine that keeps trouble coming, two relationship lines, the timeline that becomes the date lines |
| `story/outline.md` | Three episodes, each with its opening hook, payoff and ending hook |
| `story/E01.txt` | Episode 1 in the series' script format: five scenes, 31 spoken lines, 19 action lines, two narration lines, about 110 seconds |

```bash
python3 series/tools/film.py script-check examples/bitcoin-2010-develop/story/E01.txt   # "ready for intake"
python3 series/tools/film.py develop      examples/bitcoin-2010-develop                 # where it stands and what it costs
```

The owner's yes is deliberately not recorded here, so `film.py intake` refuses this script: that is Stop 0 working. In a real series the next steps are `--approve` with the owner's words, then E02 and E03, then one film folder per episode.

Things to notice:

- The owner's two wishes became rules the script keeps: the family line runs through all three episodes, and the protagonist never says why bitcoin is good or tells anyone to buy (E03 ends with him refusing to give a tip).
- No price or return ever appears on screen; how much the coin is worth is told by people: the roommate pulling up a chair, the father reading the paid bill.
- The protagonist has six short lines in the whole episode. 「先放着」 opens the series and comes back at the end of E03.
- Every scene ends on a change: the roommate tells the whole café, the father leaves the table, the coin crashes, the father pushes a glass across, the phone rings.
