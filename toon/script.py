"""Parses an episode markdown file.

    ---
    title: Pilot
    ---
    ## Scene 1: server room
    > JEFF enters from left to center
    JEFF (surprised, wave): The router logs are in Loki now!
    > pause 1
    > JEFF exits right

Dialogue: `NAME (modifiers): line`, optionally ending in `[audio: path.wav]`
to use a real recording instead of the placeholder voice. Modifiers are any
of the expressions or arm poses below, comma separated.
"""
import re
from dataclasses import dataclass, field

import yaml

EXPRESSIONS = {"neutral", "happy", "surprised", "angry", "sad"}
ARMS = {"down", "wave", "up", "point", "shrug"}
POSITIONS = {"far left": 200, "left": 330, "center": 640, "middle": 640,
             "right": 950, "far right": 1080}


@dataclass
class Line:
    kind: str                 # say | enter | move | exit | place | pause
    who: str = ""
    text: str = ""
    expression: str = ""
    arms: str = ""
    audio: str = ""
    side: str = ""            # entrance/exit side: left | right
    x: float = 0.0
    seconds: float = 0.0


@dataclass
class Scene:
    background: str
    lines: list = field(default_factory=list)


def _pos(word):
    word = word.strip().lower()
    if word not in POSITIONS:
        raise ValueError(f"unknown position {word!r}, use one of {sorted(POSITIONS)}")
    return POSITIONS[word]


def _direction(text, n):
    t = text.strip()
    if m := re.fullmatch(r"pause\s+([\d.]+)s?", t, re.I):
        return Line("pause", seconds=float(m.group(1)))
    if m := re.fullmatch(r"(\w+)\s+enters(?:\s+from\s+(left|right))?(?:\s+to\s+(.+))?", t, re.I):
        side = (m.group(2) or "left").lower()
        return Line("enter", who=m.group(1).lower(), side=side,
                    x=_pos(m.group(3) or "center"))
    if m := re.fullmatch(r"(\w+)\s+(?:walks|moves)\s+to\s+(.+)", t, re.I):
        return Line("move", who=m.group(1).lower(), x=_pos(m.group(2)))
    if m := re.fullmatch(r"(\w+)\s+exits(?:\s+(left|right))?", t, re.I):
        return Line("exit", who=m.group(1).lower(), side=(m.group(2) or "right").lower())
    if m := re.fullmatch(r"(\w+)\s+(?:stands|is)\s+(?:at\s+)?(.+)", t, re.I):
        return Line("place", who=m.group(1).lower(), x=_pos(m.group(2)))
    raise ValueError(f"line {n}: don't understand stage direction {text!r}")


def parse(path):
    with open(path) as f:
        src = f.read()
    meta = {}
    if src.startswith("---"):
        _, front, src = src.split("---", 2)
        meta = yaml.safe_load(front) or {}
    scenes = []
    for n, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("<!--"):
            continue
        if m := re.match(r"##\s*Scene[^:]*:\s*(.+)", line, re.I):
            scenes.append(Scene(m.group(1).strip().lower()))
            continue
        if line.startswith("#"):
            continue
        if not scenes:
            raise ValueError(f"line {n}: content before the first '## Scene N: <background>' heading")
        if line.startswith(">"):
            scenes[-1].lines.append(_direction(line[1:], n))
            continue
        m = re.match(r"([A-Za-z]+)\s*(?:\(([^)]*)\))?\s*:\s*(.+)", line)
        if not m:
            raise ValueError(f"line {n}: expected 'NAME: line' or '> direction', got {line!r}")
        who, mods, text = m.group(1).lower(), m.group(2) or "", m.group(3).strip()
        audio = ""
        if am := re.search(r"\[audio:\s*([^\]]+)\]\s*$", text):
            audio, text = am.group(1).strip(), text[:am.start()].strip()
        expr = arms = ""
        for mod in (x.strip().lower() for x in mods.split(",") if x.strip()):
            if mod in EXPRESSIONS:
                expr = mod
            elif mod in ARMS:
                arms = mod
            else:
                raise ValueError(f"line {n}: unknown modifier {mod!r}, "
                                 f"use {sorted(EXPRESSIONS | ARMS)}")
        scenes[-1].lines.append(Line("say", who=who, text=text, expression=expr,
                                     arms=arms, audio=audio))
    return meta, scenes
