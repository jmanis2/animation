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


class Actor:
    def __init__(self, cid, spec):
        self.id, self.spec = cid, spec
        self.x, self.on = -200.0, False
        self.expression, self.arms = "neutral", "down"
        self.walking = False
        self.rng = random.Random(cid)
        self.blink_left = 0

    def snapshot(self, frame, mouth="closed", look=(0, 2), head_tilt=0.0):
        if self.blink_left:
            self.blink_left -= 1
        elif self.rng.random() < 1 / 40:
            self.blink_left = 2
        # Re-seat the cutout every other frame, like a hand nudging paper.
        j = random.Random(f"{self.id}:{frame // 2}")
        jitter = (j.uniform(-1.2, 1.2), j.uniform(-1, 1), j.uniform(-0.6, 0.6))
        hop = -abs(math.sin(frame * math.pi / 3)) * 10 if self.walking else 0
        return dict(id=self.id, x=self.x, y=scenes.GROUND_Y + hop,
                    expression=self.expression, arms=self.arms, mouth=mouth,
                    look=look, blink=self.blink_left > 0, head_tilt=head_tilt,
                    jitter=jitter, t=frame / FPS, scale=1.2)


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
                if look is None and speaker and speaker != a.id and self.cast[speaker].on:
                    look = (5 if self.cast[speaker].x > a.x else -5, 1)
                states.append(a.snapshot(idx, mouths.get(a.id, "closed"),
                                         look or (0, 2), tilts.get(a.id, 0.0)))
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
                a.x, a.on = ln.x, True
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
                if ln.audio:
                    samples = audio.load_recording(ROOT / ln.audio, clip)
                else:
                    samples = audio.synth(ln.text, a.spec["voice"], clip)
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
    return tl


def frame_svg(frame, cast, idx, title, show_subtitles):
    if frame["bg"] == "__title__":
        body = scenes.title_card(idx, html.escape(title))
    else:
        body = scenes.BACKGROUNDS[frame["bg"]](idx)
    for st in sorted(frame["actors"], key=lambda s: s["x"]):
        st = dict(st)
        spec = cast[st.pop("id")].spec
        body += puppet.draw(spec, **st)
    if show_subtitles and frame["subtitle"]:
        text = html.escape(frame["subtitle"])
        body += (f'<rect x="0" y="664" width="{scenes.W}" height="56" fill="#000" fill-opacity="0.55"/>'
                 f'<text x="640" y="701" font-family="DejaVu Sans" font-size="26" fill="#fff" '
                 f'text-anchor="middle">{text}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{scenes.W}" height="{scenes.H}" '
            f'viewBox="0 0 {scenes.W} {scenes.H}">{body}</svg>')


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
    cast = {n: Actor(n, puppet.load_character(ROOT / "characters" / f"{n}.yaml"))
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
