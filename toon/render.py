"""Render an episode markdown file to MP4.

    python3 -m toon.render episodes/pilot.md            # -> out/pilot.mp4
    python3 -m toon.render episodes/pilot.md --frames   # keep PNG frames
"""
import argparse
import html
import math
import random
import shutil
import subprocess
from multiprocessing import Pool
from pathlib import Path

import cairosvg

from . import audio, puppet, scenes
from .script import parse

FPS = 12          # stop-motion feel: everything moves on 12 fps, jitter on twos
WALK_SPEED = 420  # px per second
LINE_GAP = 0.35   # seconds of silence after each line
ROOT = Path(__file__).resolve().parent.parent


# Elisa's looping Looney Tunes floor routine: (seconds, move).
ROUTINE = [(1.0, "cartwheel_left"), (0.25, "land"), (0.15, "crouch"), (1.0, "backflip"),
           (0.3, "land"), (1.3, "handstand"), (0.35, "flip_down"), (1.5, "split_jumps"),
           (1.0, "cartwheel_right"), (0.25, "land"), (0.5, "ta_da")]
ROUTINE_LEN = sum(d for d, _ in ROUTINE)
ROUTINE_SPAN = 110   # px either side of the home spot


def gymnastics(tt, x0):
    """Pose for the floor routine at tt seconds in: x, height, spin, squash and effects."""
    tt %= ROUTINE_LEN
    for i, (dur, move) in enumerate(ROUTINE):
        if tt < dur:
            u = tt / dur
            break
        tt -= dur
    A = ROUTINE_SPAN
    # Where each move happens: tumble left, flips on the left, bounce back to
    # the middle, cartwheel to the right, finish on the right.
    left_half = 1 <= i <= 6
    p = dict(x=x0 - A if left_half else x0 + A, lift=0.0, rot=0.0, squash=(1.0, 1.0),
             arms="up", legs="stand", mouth=None, fx=[])
    if move == "cartwheel_left":
        p.update(x=x0 + A - 2 * A * u, rot=-360 * u, arms="star", legs="spread",
                 lift=abs(math.sin(math.pi * u * 2)) * 18)
        p["fx"].append(("speed", 70, 1))
    elif move == "cartwheel_right":
        p.update(x=x0 + A * u, rot=360 * u, arms="star", legs="spread",
                 lift=abs(math.sin(math.pi * u * 2)) * 18)
        p["fx"].append(("speed", -70, -1))
    elif move == "land":
        p.update(squash=(1 + 0.22 * (1 - u), 1 - 0.25 * (1 - u)), arms="star")
        p["fx"].append(("dust", u))
    elif move == "crouch":
        p.update(squash=(1 + 0.12 * u, 1 - 0.15 * u))
    elif move == "backflip":
        p.update(lift=280 * 4 * u * (1 - u), rot=-360 * u, mouth="o" if 0.3 < u < 0.7 else None,
                 squash=(0.88, 1.18) if u < 0.15 else (1.0, 1.0))
    elif move == "handstand":
        p.update(rot=180 + 8 * math.sin(tt * 9), lift=-55, mouth="small")
    elif move == "flip_down":
        p.update(rot=180 + 180 * u, lift=-55 * (1 - u) + 70 * math.sin(math.pi * u))
    elif move == "split_jumps":
        v = (u * 3) % 1
        apex = 0.25 < v < 0.75
        p.update(x=x0 - A + A * u, lift=180 * 4 * v * (1 - v), arms="star" if apex else "up",
                 legs="spread" if apex else "stand",
                 squash=(1.15, 0.85) if v < 0.08 or v > 0.92 else (1.0, 1.0))
    elif move == "ta_da":
        p.update(mouth="small")
    return p


class Actor:
    def __init__(self, cid, spec):
        self.id, self.spec = cid, spec
        self.x, self.on = -200.0, False
        self.expression, self.arms = "neutral", "down"
        self.walking = self.sitting = False
        self.activity, self.act_start, self.home_x = "", 0, 0.0
        self.rng = random.Random(cid)
        self.blink_left = 0

    @property
    def ignores_others(self):
        return self.activity in ("ipad", "bored")

    def snapshot(self, frame, mouth="closed", look=(0, 2), head_tilt=0.0, speaking=False):
        if self.blink_left:
            self.blink_left -= 1
        elif self.rng.random() < (1 / 70 if self.activity == "bored" else 1 / 40):
            self.blink_left = 3 if self.activity == "bored" else 2
        expression = self.expression
        # Re-seat the cutout every other frame, like a hand nudging paper.
        # Yelling and frantic gaming shake every frame instead.
        amp, step = 1.0, 2
        if expression == "yelling" and speaking:
            amp, step = 4.5, 1
        elif self.activity == "ipad":
            amp, step = 1.8, 1
        j = random.Random(f"{self.id}:{frame // step}")
        jitter = (j.uniform(-1.2, 1.2) * amp, j.uniform(-1, 1) * amp, j.uniform(-0.6, 0.6) * amp)
        hop = -abs(math.sin(frame * math.pi / 3)) * 10 if self.walking else 0
        st = dict(id=self.id, x=self.x, y=scenes.GROUND_Y + hop, expression=expression,
                  arms=self.arms, mouth=mouth, look=look, blink=self.blink_left > 0,
                  head_tilt=head_tilt, jitter=jitter, t=frame / FPS, scale=1.2, z=0, fx=[])
        if self.sitting:
            st.update(y=scenes.SEAT_Y, legs="sit", sit_drop=scenes.GROUND_Y - scenes.SEAT_Y)
        tt = (frame - self.act_start) / FPS
        if self.activity == "ipad":
            st.update(arms="ipad", prop="ipad",
                      glow=("#5ec8ff", "#ff5ec4", "#ffe75e", "#6bff8a")[int(tt * 6) % 4],
                      head_tilt=head_tilt + (2 if frame % 2 else -2))
            if self.expression in ("neutral", ""):
                st["expression"] = "manic"
            st["y"] -= abs(math.sin(frame * 1.7)) * 4
        elif self.activity == "bored":
            st.update(arms="mug", prop="mug")
            if self.expression in ("neutral", ""):
                st["expression"] = "bored"
        elif self.activity == "gymnastics":
            g = gymnastics(tt, self.home_x)
            self.x = g["x"]
            st.update(x=g["x"], y=scenes.GROUND_Y - g["lift"], body_rot=g["rot"], squash=g["squash"],
                      arms=g["arms"], legs=g["legs"], z=1, blink=False,
                      fx=[(f[0], g["x"] + f[1], f[2]) if f[0] == "speed" else (f[0], f[1], g["x"])
                          for f in g["fx"]])
            if self.expression in ("neutral", ""):
                st["expression"] = "happy"
            if not speaking and g["mouth"]:
                st["mouth"] = g["mouth"]
        return st


class Timeline:
    def __init__(self, cast):
        self.cast = cast
        self.frames, self.clips = [], []
        self.bg, self.subtitle = "outside", ""

    def emit(self, n, per_frame=None):
        for i in range(n):
            idx = len(self.frames)
            mouths, looks, tilts = per_frame(i) if per_frame else ({}, {}, {})
            speaker = next(iter(mouths), None)
            states = []
            for a in self.cast.values():
                if not a.on:
                    continue
                look = looks.get(a.id)
                if (look is None and speaker and speaker != a.id and self.cast[speaker].on
                        and not a.ignores_others):
                    look = (5 if self.cast[speaker].x > a.x else -5, 1)
                states.append(a.snapshot(idx, mouths.get(a.id, "closed"), look or (0, 2),
                                         tilts.get(a.id, 0.0), speaking=a.id == speaker))
            self.frames.append(dict(bg=self.bg, actors=states, subtitle=self.subtitle))

    def walk(self, actor, target):
        dist = abs(target - actor.x)
        n = max(1, round(dist / WALK_SPEED * FPS))
        start = actor.x
        actor.walking = True

        def step(i):
            actor.x = start + (target - start) * (i + 1) / n
            return {}, {actor.id: (6 if target > start else -6, 1)}, {}
        self.emit(n, step)
        actor.walking = False


def build(meta, episode_scenes, cast, workdir):
    tl = Timeline(cast)
    title = meta.get("title", "")
    if title:
        tl.bg = "__title__"
        tl.emit(int(2.0 * FPS))
    for scene in episode_scenes:
        if scene.background not in scenes.BACKGROUNDS:
            raise SystemExit(f"unknown background {scene.background!r}, "
                             f"have {sorted(scenes.BACKGROUNDS)}")
        tl.bg = scene.background
        for a in cast.values():
            a.on = False
        for ln in scene.lines:
            if ln.who and ln.who not in cast:
                raise SystemExit(f"no character file characters/{ln.who}.yaml")
            a = cast.get(ln.who)
            if ln.kind == "pause":
                tl.emit(round(ln.seconds * FPS))
            elif ln.kind == "place":
                a.x, a.on, a.sitting = ln.x, True, ln.sit
            elif ln.kind == "activity":
                a.on = True
                a.activity, a.act_start = ln.activity, len(tl.frames)
                if ln.x:
                    a.x = ln.x
                a.home_x = a.x
            elif ln.kind == "enter":
                a.x, a.on = (-120 if ln.side == "left" else scenes.W + 120), True
                tl.walk(a, ln.x)
            elif ln.kind == "move":
                tl.walk(a, ln.x)
            elif ln.kind == "exit":
                tl.walk(a, -140 if ln.side == "left" else scenes.W + 140)
                a.on = False
            elif ln.kind == "say":
                if not a.on:
                    a.x, a.on = 640, True
                clip = workdir / f"line{len(tl.clips):03d}.wav"
                voice = dict(a.spec["voice"])
                # Big emotions get a more intense delivery from the voice model.
                if ln.expression == "yelling":
                    voice.update(exaggeration=max(float(voice.get("exaggeration", 0.5)), 0.9), cfg_weight=0.3)
                elif ln.expression == "manic":
                    voice.update(exaggeration=max(float(voice.get("exaggeration", 0.5)), 0.8), cfg_weight=0.4)
                if ln.audio:
                    samples = audio.load_recording(ROOT / ln.audio, clip)
                else:
                    samples = audio.synth(ln.text, voice, clip)
                shapes = audio.mouth_shapes(samples, FPS)
                start = len(tl.frames)
                tl.clips.append((start * audio.RATE // FPS, samples))
                saved = a.expression, a.arms
                a.expression = ln.expression or a.expression
                a.arms = ln.arms or a.arms
                tl.subtitle = f"{a.spec['name']}: {ln.text}"

                def talk(i, a=a, shapes=shapes):
                    m = shapes[i] if i < len(shapes) else "closed"
                    tilt = (2.5 if (i // 3) % 2 else -2.5) if m != "closed" else 0.0
                    return {a.id: m}, {}, {a.id: tilt}
                tl.emit(len(shapes) + round(LINE_GAP * FPS), talk)
                tl.subtitle = ""
                a.expression, a.arms = saved
                if ln.expression == "yelling":
                    a.expression = "angry"     # still fuming between lines
    return tl


def frame_svg(frame, cast, idx, title, show_subtitles):
    if frame["bg"] == "__title__":
        body = scenes.title_card(idx, html.escape(title))
    else:
        body = scenes.BACKGROUNDS[frame["bg"]](idx)
    for st in sorted(frame["actors"], key=lambda s: (s["z"], s["x"])):
        st = dict(st)
        spec = cast[st.pop("id")].spec
        st.pop("z")
        body += "".join(_fx(f) for f in st.pop("fx"))
        body += puppet.draw(spec, **st)
    if show_subtitles and frame["subtitle"]:
        text = html.escape(frame["subtitle"])
        body += (f'<rect x="0" y="664" width="{scenes.W}" height="56" fill="#000" fill-opacity="0.55"/>'
                 f'<text x="640" y="701" font-family="DejaVu Sans" font-size="26" fill="#fff" '
                 f'text-anchor="middle">{text}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{scenes.W}" height="{scenes.H}" '
            f'viewBox="0 0 {scenes.W} {scenes.H}">{body}</svg>')


def _fx(f):
    """Cartoon effects: speed lines behind fast moves, dust puffs on landings."""
    if f[0] == "speed":
        _, x, d = f
        y = scenes.GROUND_Y - 200
        return "".join(f'<path d="M {x:.0f},{y + k * 34} l {d * (90 - k * 12):.0f},0" stroke="#141414" '
                       f'stroke-width="4" stroke-linecap="round" opacity="0.55"/>' for k in range(4))
    if f[0] == "dust":
        _, u, x = f
        r, o = 14 + 30 * u, 0.7 * (1 - u)
        return "".join(f'<circle cx="{x + dx * (1 + 2 * u):.0f}" cy="{scenes.GROUND_Y - 8}" r="{r:.0f}" '
                       f'fill="#d9c7a8" opacity="{o:.2f}" stroke="#141414" stroke-width="2"/>' for dx in (-55, 0, 55))
    return ""


_job = {}


def _init(cast, title, subs, frames_dir):
    _job.update(cast=cast, title=title, subs=subs, dir=frames_dir)


def _render_one(args):
    idx, frame = args
    svg = frame_svg(frame, _job["cast"], idx, _job["title"], _job["subs"])
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(_job["dir"] / f"{idx:05d}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("-o", "--out")
    ap.add_argument("--frames", action="store_true", help="keep the PNG frames")
    args = ap.parse_args()

    ep = Path(args.episode)
    meta, episode_scenes = parse(ep)
    names = {ln.who for s in episode_scenes for ln in s.lines if ln.who}
    costumes = meta.get("costumes", {})
    cast = {n: Actor(n, puppet.load_character(ROOT / "characters" / f"{n}.yaml", costumes.get(n)))
            for n in sorted(names)}

    work = ROOT / "out" / ep.stem
    shutil.rmtree(work, ignore_errors=True)
    frames_dir = work / "frames"
    frames_dir.mkdir(parents=True)

    tl = build(meta, episode_scenes, cast, work)
    audio.write_mix(tl.clips, len(tl.frames) * audio.RATE // FPS, work / "audio.wav")

    with Pool(initializer=_init, initargs=(cast, meta.get("title", ""),
                                           meta.get("subtitles", True), frames_dir)) as pool:
        pool.map(_render_one, enumerate(tl.frames), chunksize=8)

    out = Path(args.out) if args.out else ROOT / "out" / f"{ep.stem}.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS),
                    "-i", str(frames_dir / "%05d.png"), "-i", str(work / "audio.wav"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
                    "-c:a", "aac", "-shortest", str(out)], check=True)
    if not args.frames:
        shutil.rmtree(frames_dir)
    print(f"{out}  ({len(tl.frames) / FPS:.1f}s, {len(tl.frames)} frames)")


if __name__ == "__main__":
    main()
