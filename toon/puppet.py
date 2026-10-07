"""Cutout puppets: turns a character YAML spec plus a per-frame pose into SVG.

Coordinates are local to the character: origin at the feet, y going up is
negative. A standing character is about 330px tall.
"""
import yaml

OUTLINE = "#141414"
SW = 3
MOUTH_DARK = "#3a0d0d"

HEAD_CY = -228
HEAD_R = 80
EYE_Y = -238
MOUTH_Y = -176
NECK = (0, -150)


def load_character(path):
    with open(path) as f:
        spec = yaml.safe_load(f)
    spec.setdefault("eyes", {})
    spec.setdefault("hair", {"style": "bald"})
    spec.setdefault("facial_hair", {"style": "none"})
    spec.setdefault("voice", {})
    return spec


def _ell(cx, cy, rx, ry, fill, stroke=OUTLINE, sw=SW):
    return (f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def _path(d, fill="none", stroke=OUTLINE, sw=SW, cap="round"):
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linejoin="round" stroke-linecap="{cap}"/>')


# Arm poses for the viewer-right arm as (elbow, hand); mirrored for the left.
ARM_POSES = {
    "down":  ((58, -108), (64, -74)),
    "wave":  ((84, -150), (112, -200)),
    "point": ((82, -136), (122, -140)),
    "shrug": ((76, -112), (100, -146)),
}


def _arm_points(side, arms, t):
    """Which pose each arm takes for a given `arms` keyword."""
    if arms == "up":
        pose = "wave"
    elif arms == "shrug":
        pose = "shrug"
    elif arms in ("wave", "point") and side == 1:
        pose = arms
    else:
        pose = "down"
    (ex, ey), (hx, hy) = ARM_POSES[pose]
    if pose == "wave":
        # Waving hand swings on twos, like a moved cutout.
        hx += 12 if (int(t * 6) % 2) else -6
    return (side * 46, -140), (side * ex, ey), (side * hx, hy)


def _arm(spec, side, arms, t):
    top = spec["outfit"]["top"]
    (sx, sy), (ex, ey), (hx, hy) = _arm_points(side, arms, t)
    d = f"M {sx},{sy} L {ex},{ey} L {hx},{hy}"
    out = [_path(d, stroke=OUTLINE, sw=27), _path(d, stroke=top["color"], sw=21)]
    if top.get("trim"):
        # Short trim band at the cuff.
        fx, fy = hx + (ex - hx) * 0.28, hy + (ey - hy) * 0.28
        out.append(_path(f"M {fx:.1f},{fy:.1f} L {hx + (ex - hx) * 0.18:.1f},{hy + (ey - hy) * 0.18:.1f}",
                         stroke=top["trim"], sw=21, cap="butt"))
    out.append(_ell(hx, hy, 12, 12, spec["skin"]))
    return "".join(out)


def _legs(spec):
    o = spec["outfit"]
    return "".join([
        _path("M -44,-46 L 44,-46 L 44,-10 L -44,-10 Z", fill=o["pants"]),
        _path("M 0,-34 L 0,-10", sw=2.5),
        _ell(-24, -7, 26, 9, o["shoes"]),
        _ell(24, -7, 26, 9, o["shoes"]),
    ])


def _torso(spec):
    top = spec["outfit"]["top"]
    out = [_path("M -46,-152 L 46,-152 L 58,-42 L -58,-42 Z", fill=top["color"])]
    if top.get("collar"):
        out.append(_path("M -26,-152 L 0,-120 L 26,-152 Z", fill=top["collar"]))
        out.append(_path("M -26,-150 L -12,-132 L -4,-146", fill=top["collar"], sw=2.5))
        out.append(_path("M 26,-150 L 12,-132 L 4,-146", fill=top["collar"], sw=2.5))
    if top.get("style") == "track_jacket":
        out.append(_path("M 0,-120 L 0,-44", sw=2.5))
        if top.get("trim"):
            out.append(_path("M -30,-152 L -2,-118", stroke=top["trim"], sw=5))
            out.append(_path("M 30,-152 L 2,-118", stroke=top["trim"], sw=5))
            out.append(_path("M -57,-50 L 57,-50", stroke=top["trim"], sw=5, cap="butt"))
    return "".join(out)


def _hair_back(spec):
    h = spec["hair"]
    if h["style"] == "long":
        return _path("M -84,-236 C -96,-170 -92,-130 -70,-112 L 70,-112 "
                     "C 92,-130 96,-170 84,-236 Z", fill=h["color"])
    return ""


def _hair_front(spec):
    h, c = spec["hair"], spec["hair"].get("color", "#000")
    style = h["style"]
    if style == "pompadour":
        return "".join([
            _path("M -82,-226 C -96,-302 -54,-348 4,-344 C 66,-348 98,-302 82,-226 "
                  "L 76,-250 C 70,-284 42,-300 14,-298 C -22,-302 -58,-290 -74,-252 Z",
                  fill=c),
            # Side part and the comb lines that give it the swept-back look.
            _path("M -34,-298 C -40,-316 -30,-332 -10,-338", stroke="#5a4335", sw=2.5),
            _path("M 10,-300 C 30,-318 52,-322 70,-308", stroke="#5a4335", sw=2),
            # Sideburns
            _path("M -80,-232 L -76,-206 L -70,-226 Z", fill=c, sw=2),
            _path("M 80,-232 L 76,-206 L 70,-226 Z", fill=c, sw=2),
        ])
    if style == "short":
        return _path("M -80,-234 C -86,-290 -46,-314 0,-312 C 46,-314 86,-290 80,-234 "
                     "C 60,-262 30,-272 0,-272 C -30,-272 -60,-262 -80,-234 Z", fill=c)
    if style == "long":
        return _path("M -84,-232 C -90,-296 -46,-316 0,-314 C 46,-316 90,-296 84,-232 "
                     "C 66,-262 36,-276 4,-270 C -30,-278 -62,-262 -84,-232 Z", fill=c)
    return ""


def _brows(spec, expression):
    c = spec["hair"].get("color", "#222")
    lift = -8 if spec["eyes"].get("brows") == "raised" else 0
    if expression == "surprised":
        lift -= 6
    y = EYE_Y - 32 + lift
    if expression == "angry":
        left, right = f"M -44,{y - 6} L -8,{y + 10}", f"M 44,{y - 6} L 8,{y + 10}"
    elif expression == "sad":
        left, right = f"M -44,{y + 8} L -8,{y - 6}", f"M 44,{y + 8} L 8,{y - 6}"
    else:
        left = f"M -44,{y + 4} Q -26,{y - 10} -8,{y + 2}"
        right = f"M 44,{y + 4} Q 26,{y - 10} 8,{y + 2}"
    return _path(left, stroke=c, sw=7) + _path(right, stroke=c, sw=7)


def _eyes(spec, expression, look, blink):
    if blink:
        return "".join(_path(f"M {x - 18},{EYE_Y} Q {x},{EYE_Y + 8} {x + 18},{EYE_Y}", sw=3.5)
                       for x in (-21, 21))
    rx, ry, pr = 22, 26, 3.8
    if expression == "surprised":
        rx, ry, pr = 23, 30, 3.2
    elif expression == "happy":
        ry = 21
    lx, ly = look
    out = []
    for x in (-21, 21):
        out.append(_ell(x, EYE_Y, rx, ry, "#ffffff"))
        out.append(f'<circle cx="{x + lx:.1f}" cy="{EYE_Y + ly:.1f}" r="{pr}" '
                   f'fill="{spec["eyes"].get("pupil", "#000")}"/>')
    if expression == "angry":
        for x in (-21, 21):
            # Lid cut across the top of each eye, lower on the inner side.
            top = EYE_Y - 28
            inner_r, inner_l = (18, 4) if x < 0 else (4, 18)
            out.append(_path(f"M {x - 25},{top} L {x + 25},{top} L {x + 25},{top + inner_r} "
                             f"L {x - 25},{top + inner_l} Z", fill=spec["skin"], stroke="none"))
            out.append(_path(f"M {x - 23},{top + inner_l} L {x + 23},{top + inner_r}", sw=3))
    return "".join(out)


def _mouth(expression, mouth):
    y = MOUTH_Y
    if mouth in (None, "closed"):
        if expression == "happy":
            return _path(f"M -22,{y - 6} Q 0,{y + 14} 22,{y - 6}", sw=3.5)
        if expression in ("sad", "angry"):
            return _path(f"M -18,{y + 6} Q 0,{y - 6} 18,{y + 6}", sw=3.5)
        if expression == "surprised":
            return _ell(0, y, 6, 7, MOUTH_DARK)
        return _path(f"M -16,{y} Q 0,{y + 4} 16,{y}", sw=3.5)
    if mouth == "small":
        return _ell(0, y, 12, 8, MOUTH_DARK)
    if mouth == "o":
        return _ell(0, y + 2, 10, 12, MOUTH_DARK)
    # wide
    return "".join([
        _ell(0, y + 3, 18, 15, MOUTH_DARK),
        _ell(0, y + 12, 10, 5, "#d4545b", stroke="none"),
        _path(f"M -14,{y - 6} L 14,{y - 6}", stroke="#ffffff", sw=5, cap="butt"),
    ])


def _facial_hair(spec):
    f = spec["facial_hair"]
    if f["style"] == "chevron_mustache":
        c = f["color"]
        return _path("M -46,-184 C -44,-206 -22,-214 0,-206 C 22,-214 44,-206 46,-184 "
                     "C 34,-192 16,-194 0,-190 C -16,-194 -34,-192 -46,-184 Z", fill=c, sw=2.5)
    return ""


def _head(spec, expression, mouth, look, blink):
    out = []
    if spec.get("ears"):
        out.append(_ell(-80, -226, 11, 17, spec["skin"]))
        out.append(_ell(80, -226, 11, 17, spec["skin"]))
    out.append(_ell(0, HEAD_CY, HEAD_R, HEAD_R + 2, spec["skin"]))
    out.append(_eyes(spec, expression, look, blink))
    out.append(_brows(spec, expression))
    out.append(_mouth(expression, mouth))
    out.append(_facial_hair(spec))
    out.append(_hair_front(spec))
    return "".join(out)


def draw(spec, x, y, expression="neutral", mouth="closed", arms="down",
         look=(0, 2), blink=False, head_tilt=0.0, jitter=(0, 0, 0), t=0.0, scale=1.0):
    """SVG group for one character standing with feet at (x, y)."""
    jx, jy, jr = jitter
    head = _head(spec, expression, mouth, look, blink)
    return (
        f'<g transform="translate({x + jx:.1f},{y + jy:.1f}) rotate({jr:.2f}) scale({scale})">'
        + _hair_back(spec)
        + _legs(spec)
        + _torso(spec)
        + _arm(spec, -1, arms, t)
        + _arm(spec, 1, arms, t)
        + f'<g transform="rotate({head_tilt:.2f} {NECK[0]} {NECK[1]})">{head}</g>'
        + "</g>"
    )
