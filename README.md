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
  - `NAME sits at <pos>` (use the `sofa` background, seats `sofa left` and `sofa right`)
  - `NAME is <activity> [at <pos>]`: keeps going under everything else that
    happens. Activities: `playing ipad`, `doing gymnastics` (a looping
    cartwheel, backflip and handstand routine), `ignoring everything`
    (bored, holding a mug), `nothing`.
  - `pause <seconds>`

  Positions are `far left`, `left`, `center`, `right`, `far right`, or an x
  value in pixels (0 to 1280).
- Dialogue: `NAME (modifiers): text`. The modifiers are optional:
  - expressions: `neutral`, `happy`, `surprised`, `angry`, `sad`, `silly`,
    `manic`, `bored`, `yelling` (shakes, flushes, and gets a louder delivery)
  - arms: `down`, `wave`, `up`, `point`, `shrug`
- Voices: see below. Add `[audio: path]` to a line to use a real recording
  in any format ffmpeg reads. The mouth moves with the loudness of the audio
  either way.

## Voices

Each line is spoken by the first of these that's available:

1. A recording, if the line has `[audio: path]`.
2. A clone of the character's voice, made with
   [Chatterbox](https://github.com/resemble-ai/chatterbox) from
   `voices/<name>/reference.wav`.
3. The espeak-ng robot placeholder.

To clone a voice:

```sh
# Without an NVIDIA GPU, install the CPU-only torch first (~180 MB instead of several GB):
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
pip install chatterbox-tts
mkdir -p voices/jeff
ffmpeg -i memo.m4a -ac 1 -ar 24000 voices/jeff/reference.wav
python3 -m toon.render episodes/pilot.md
```

- The first run downloads the model weights from huggingface.co. If a
  machine can't reach it, copy the weights folder over and set
  `CHATTERBOX_CKPT=/path/to/weights`.
- Generated lines are cached in `out/voice_cache/`, so a re-render only
  speaks lines that changed.
- It runs on CPU at a few seconds per line, and uses a CUDA GPU if one is
  present.
- `exaggeration` in the character YAML sets how animated the delivery is.
- `TOON_PREVIEW=1 python3 -m toon.render ...` renders a fast draft with the
  robot voices, which is handy for checking staging before cloning.
- `pitch_shift` (semitones) moves a cloned voice up or down while keeping
  its timbre. Use it to separate similar voices, for example siblings.
- To choose a reference clip, take the 10 to 15 seconds of the memo that
  sounds most like that person. The two kids sound alike, so their clips
  were picked to be as different from each other as possible.

Reference sample: 20 to 60 seconds of natural, conversational speech in a
quiet room with the phone about 20 cm away, and nobody else talking.
`voices/` is git-ignored so voice samples never get committed.

## Adding a character

The cast is `jeff`, `valentina`, `eric`, and `elisa`. To add a character,
copy one of their YAML files and change the fields:

- `build: kid` gives a smaller body under a full-size head.
- Hair styles: `pompadour`, `textured_short`, `long_wavy`,
  `long_straight`, `short`, `long`, `bald`
- Tops: `track_jacket`, `quarter_zip`, `sweatshirt` (optional
  `graphic: soccer_ball`), `tee`
- Extras: `freckles`, `ears`, `eyes.lashes`, `smile: teeth`, and
  `facial_hair: chevron_mustache`

New hair or clothing styles go in `toon/puppet.py`.
