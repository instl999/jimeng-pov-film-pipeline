# Sound effects

Not included: bring your own files. The edit works without them and says which ones it skipped.

| File name | Used for | Notes |
|---|---|---|
| `scoreboard-click.mp3` | A soft click each time the date line changes. Added automatically | Its loudest point should be about 0.29 s in; it is mixed at −12 dB |
| any name you choose | An effect a shot asks for in `film.json`: `"sfx": [{"t": 0.15, "file": "cold-open-hit.mp3", "gain_db": -9}]` | `t` is seconds into the shot |

Keep effects few: a click on date changes and, at most, a hit under the opening action. No music is added by this pipeline.

Set `FILM_SFX` to use a folder somewhere else.
