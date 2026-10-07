# animation

Construction-paper cutout cartoons of the family, written as text files and
rendered to video.

- `characters/<name>.yaml` holds one character: skin, hair, facial hair,
  outfit colors, and voice.
- `episodes/<name>.md` holds an episode script in markdown.
- `toon/` holds the renderer: SVG puppets, backgrounds, script parser,
  audio and lip flap, and the frame and ffmpeg pipeline.

## Render

```sh
pip install cairosvg pyyaml numpy
sudo apt install ffmpeg espeak-ng
python3 -m toon.render episodes/pilot.md        # writes out/pilot.mp4
```

Animation runs at 12 fps, and each cutout gets re-seated by a pixel or so every
other frame. Together they give the stop-motion look.

## Script format

```markdown
---
title: The Homelab
subtitles: true
---

## Scene 1: server room
> JEFF enters from left to center
JEFF (surprised): Wait. The router logs are actually in Loki?
> pause 0.5
JEFF (happy, wave): Fourteen days of retention!
JEFF: Recorded line. [audio: voices/jeff/line1.m4a]
> JEFF exits right
```

- Scenes: `## Scene N: <background>`. Backgrounds are `outside`,
  `living room`, and `server room`, defined in `toon/scenes.py`.
- Stage directions start with `>`:
  - `NAME enters from left|right to <pos>`
  - `NAME walks to <pos>`
  - `NAME exits left|right`
  - `NAME stands <pos>`
  - `pause <seconds>`

  Positions are `far left`, `left`, `center`, `right`, and `far right`.
- Dialogue: `NAME (modifiers): text`. The modifiers are optional:
  - expressions: `neutral`, `happy`, `surprised`, `angry`, `sad`
  - arms: `down`, `wave`, `up`, `point`, `shrug`
- Voices: espeak-ng is a robot placeholder. Add `[audio: path]` to a line
  to use a real recording in any format ffmpeg reads. The mouth moves with
  the loudness of the audio either way.

## Adding a character

Copy `characters/jeff.yaml` and change the fields. Hair styles are
`pompadour`, `short`, `long`, and `bald`. Facial hair is `chevron_mustache` or
`none`. New hair or clothing styles go in `toon/puppet.py`.
