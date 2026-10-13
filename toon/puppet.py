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
    if top.get("style") in ("sweatshirt", "tee"):
        # Ribbed crew neck, cuff band at the hem.
        out.append(_path("M -30,-152 Q 0,-126 30,-152", fill=top.get("rib", top["color"]), sw=2.5))
        out.append(_path("M -24,-150 Q 0,-132 24,-150", stroke="#141414", sw=1.5))
        if top["style"] == "sweatshirt":
            out.append(_path("M -57,-52 L 57,-52", stroke="#141414", sw=1.5, cap="butt"))
        if top.get("graphic") == "soccer_ball":
            out.append(_soccer_graphic(top))
    if top.get("style") == "polo":
        # Collar flaps in the shirt color, short button placket.
        c = top["color"]
        out.append(_path("M -28,-154 L -10,-126 L 0,-140 Z", fill=c, sw=2.5))
        out.append(_path("M 28,-154 L 10,-126 L 0,-140 Z", fill=c, sw=2.5))
        out.append(_path("M -6,-138 L -6,-96 L 6,-96 L 6,-138", sw=2))
        out.append(_ell(0, -122, 3, 3, "#f2f2f2", sw=1))
        out.append(_ell(0, -106, 3, 3, "#f2f2f2", sw=1))
    if top.get("style") == "quarter_zip":
        # Fleece stand collar with a contrasting zipper running to mid chest.
        z = top.get("zip", "#d9b8b0")
        out.append(_path("M -32,-156 L -26,-138 L 0,-128 L 26,-138 L 32,-156 Q 0,-146 -32,-156 Z",
                         fill=top["color"], sw=2.5))
        out.append(_path("M -26,-140 L 0,-130 L 26,-140", stroke=z, sw=3))
        out.append(_path("M 0,-130 L 0,-84", stroke=z, sw=4))
        out.append(_ell(0, -84, 3, 5, z, sw=1.5))
        if top.get("logo"):
            out.append(_path("M 18,-122 L 22,-112 L 26,-120 L 30,-112 L 34,-122", stroke=z, sw=2))
    if top.get("style") == "track_jacket":
        out.append(_path("M 0,-120 L 0,-44", sw=2.5))
        if top.get("trim"):
            out.append(_path("M -30,-152 L -2,-118", stroke=top["trim"], sw=5))
            out.append(_path("M 30,-152 L 2,-118", stroke=top["trim"], sw=5))
            out.append(_path("M -57,-50 L 57,-50", stroke=top["trim"], sw=5, cap="butt"))
    return "".join(out)


def _soccer_graphic(top):
    """Drippy soccer ball and sideways STRIKER lettering on the wearer's left chest."""
    cx, cy, r = 10, -108, 14
    ink, accent = top.get("print", "#f2f2f2"), top.get("accent", "#4fc3f7")
    out = [_ell(cx, cy, r, r, ink, stroke="#141414", sw=1.5)]
    out.append(f'<polygon points="{cx},{cy - 5} {cx + 5},{cy - 1} {cx + 3},{cy + 5} '
               f'{cx - 3},{cy + 5} {cx - 5},{cy - 1}" fill="#141414"/>')
    for dx, dy in ((0, -1), (0.95, -0.3), (0.6, 0.8), (-0.6, 0.8), (-0.95, -0.3)):
        out.append(_path(f"M {cx + dx * 6:.1f},{cy + dy * 6:.1f} L {cx + dx * r:.1f},{cy + dy * r:.1f}",
                         stroke="#141414", sw=1.2))
    for dx, ln in ((-8, 12), (-2, 18), (5, 9), (10, 14)):
        out.append(_path(f"M {cx + dx},{cy + r - 3} L {cx + dx},{cy + r + ln}", stroke=ink, sw=2))
    out.append(f'<text x="0" y="0" transform="translate({cx + 20},{cy - 20}) rotate(90)" '
               f'font-family="DejaVu Sans" font-weight="bold" font-size="12" fill="{accent}">STRIKER</text>')
    return "".join(out)


def _hair_back(spec):
    h = spec["hair"]
    if h["style"] == "long_wavy":
        return _path("M -86,-240 C -106,-196 -86,-166 -102,-128 C -96,-104 -84,-108 -76,-94 "
                     "C -60,-100 -50,-96 -40,-104 L 40,-104 C 50,-96 60,-100 76,-94 "
                     "C 84,-108 96,-104 102,-128 C 86,-166 106,-196 86,-240 Z", fill=h["color"])
    if h["style"] == "long_straight":
        return _path("M -84,-240 C -92,-200 -92,-150 -90,-100 L -60,-96 L -30,-100 L 30,-100 "
                     "L 60,-96 L 90,-100 C 92,-150 92,-200 84,-240 Z", fill=h["color"])
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
    if style == "long_wavy":
        # Swept back off the forehead, slightly off-center part, waves framing the face.
        hi = h.get("highlight", "#6b3a26")
        return "".join([
            _path("M -84,-226 C -92,-300 -48,-324 -6,-320 C 48,-324 92,-300 84,-226 "
                  "C 80,-252 66,-278 40,-292 C 20,-300 6,-302 -6,-298 C -22,-302 -48,-294 -66,-274 "
                  "C -76,-262 -82,-246 -84,-226 Z", fill=c),
            _path("M -84,-234 C -98,-204 -86,-180 -96,-150 C -90,-138 -82,-140 -76,-132 "
                  "C -80,-160 -72,-190 -74,-232 Z", fill=c, sw=2.5),
            _path("M 84,-234 C 98,-204 86,-180 96,-150 C 90,-138 82,-140 76,-132 "
                  "C 80,-160 72,-190 74,-232 Z", fill=c, sw=2.5),
            _path("M -6,-298 C -2,-308 2,-314 6,-320", stroke=hi, sw=2),
            _path("M -56,-290 C -70,-270 -80,-240 -88,-200", stroke=hi, sw=2.5),
        ])
    if style == "long_straight":
        # Side part on one side, the rest sweeping across the forehead.
        hi = h.get("highlight", "#e2b57a")
        return "".join([
            _path("M -82,-226 C -88,-296 -50,-322 -26,-320 C 30,-324 88,-298 82,-226 "
                  "C 76,-250 58,-264 34,-270 C 6,-280 -14,-292 -26,-302 C -46,-292 -68,-266 -82,-226 Z",
                  fill=c),
            _path("M -82,-230 L -90,-140 L -76,-144 L -72,-228 Z", fill=c, sw=2.5),
            _path("M 82,-230 L 90,-140 L 76,-144 L 72,-228 Z", fill=c, sw=2.5),
            _path("M -26,-302 L -24,-318", stroke=hi, sw=2),
            _path("M -10,-298 C 20,-288 50,-276 70,-256", stroke=hi, sw=2),
        ])
    if style == "quiff":
        # Faded short sides, longer top swept up and over to one side.
        hi = h.get("highlight", "#8a7462")
        return "".join([
            _path("M -81,-226 C -86,-262 -76,-282 -60,-290 C -50,-314 -10,-332 30,-326 "
                  "C 66,-320 88,-298 81,-226 L 76,-246 C 72,-270 56,-286 28,-290 "
                  "C 0,-296 -34,-292 -56,-280 C -68,-272 -74,-256 -77,-242 Z", fill=c),
            _path("M -54,-294 C -34,-316 0,-326 34,-320", stroke=hi, sw=2.5),
            _path("M -30,-294 C -10,-310 20,-316 54,-308", stroke=hi, sw=2),
            _path("M 10,-292 C 34,-306 58,-304 74,-288", stroke=hi, sw=2),
            # Shorter faded hair over the ears
            _path("M -81,-240 L -78,-212 L -72,-236 Z", fill=c, sw=2),
            _path("M 81,-240 L 78,-212 L 72,-236 Z", fill=c, sw=2),
        ])
    if style == "textured_short":
        # Short on the sides, longer messy top pushed up at the front.
        return "".join([
            _path("M -81,-226 C -88,-282 -60,-316 -10,-322 L -2,-334 L 10,-322 L 24,-332 "
                  "L 32,-318 C 66,-314 90,-282 81,-226 L 74,-244 C 66,-270 46,-282 24,-282 "
                  "L 14,-290 L 4,-280 C -14,-286 -40,-282 -54,-268 C -64,-262 -72,-252 -74,-244 Z",
                  fill=c),
            _path("M -40,-292 C -30,-306 -14,-312 2,-312", stroke="#6a4c36", sw=2),
            _path("M 30,-298 C 44,-302 58,-296 66,-286", stroke="#6a4c36", sw=2),
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
    if expression == "silly":
        lx, ly = -7, 0
    out = []
    for x in (-21, 21):
        out.append(_ell(x, EYE_Y, rx, ry, "#ffffff"))
        out.append(f'<circle cx="{x + lx:.1f}" cy="{EYE_Y + ly:.1f}" r="{pr}" '
                   f'fill="{spec["eyes"].get("pupil", "#000")}"/>')
    if spec["eyes"].get("lashes") and not blink:
        for x, s in ((-21, -1), (21, 1)):
            for k in (0, 1):
                bx, by = x + s * (14 + k * 6), EYE_Y - ry + 6 + k * 8
                out.append(_path(f"M {bx},{by} L {bx + s * 7},{by - 6}", sw=2.5))
    if expression == "angry":
        for x in (-21, 21):
            # Lid cut across the top of each eye, lower on the inner side.
            top = EYE_Y - 28
            inner_r, inner_l = (18, 4) if x < 0 else (4, 18)
            out.append(_path(f"M {x - 25},{top} L {x + 25},{top} L {x + 25},{top + inner_r} "
                             f"L {x - 25},{top + inner_l} Z", fill=spec["skin"], stroke="none"))
            out.append(_path(f"M {x - 23},{top + inner_l} L {x + 23},{top + inner_r}", sw=3))
    return "".join(out)


def _mouth(expression, mouth, smile=None):
    y = MOUTH_Y
    if mouth in (None, "closed"):
        if expression == "silly":
            return _ell(8, y, 9, 8, "#c4707f") + _path(f"M 2,{y} L 14,{y}", stroke="#7a3040", sw=2)
        if expression == "happy" and smile == "teeth":
            return "".join([
                _path(f"M -28,{y - 8} Q 0,{y + 24} 28,{y - 8} Q 0,{y - 2} -28,{y - 8} Z",
                      fill=MOUTH_DARK),
                _path(f"M -24,{y - 6} Q 0,{y + 2} 24,{y - 6} L 22,{y + 1} Q 0,{y + 8} -22,{y + 1} Z",
                      fill="#ffffff", sw=1.5),
            ])
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
    if f["style"] == "full_beard":
        # Short beard over the jaw joined to the mustache, with an opening for
        # the mouth (even-odd hole) and an optional gray patch on the chin.
        c, y = f["color"], MOUTH_Y
        beard = (f"M -78,-204 C -77,-164 -50,-136 0,-132 C 50,-136 77,-164 78,-204 "
                 f"C 70,-192 60,-188 46,-190 C 30,-196 12,-198 0,-194 C -12,-198 -30,-196 -46,-190 "
                 f"C -60,-188 -70,-192 -78,-204 Z "
                 f"M -20,{y + 2} A 20,12 0 1 0 20,{y + 2} A 20,12 0 1 0 -20,{y + 2} Z")
        out = [f'<path d="{beard}" fill="{c}" fill-rule="evenodd" stroke="{OUTLINE}" '
               f'stroke-width="{SW}" stroke-linejoin="round"/>']
        if f.get("gray"):
            out.append(_path("M -20,-140 Q 0,-131 20,-140 Q 0,-152 -20,-140 Z",
                             fill=f["gray"], stroke="none"))
        return "".join(out)
    return ""


def _glasses(spec):
    g = spec.get("glasses")
    if not g:
        return ""
    c, y0, y1 = g.get("color", "#55585e"), EYE_Y - 26, EYE_Y + 24
    out = []
    for x0 in (-50, 2):
        out.append(f'<rect x="{x0}" y="{y0}" width="48" height="{y1 - y0}" rx="7" '
                   f'fill="#dff3f5" fill-opacity="0.18" stroke="{c}" stroke-width="5"/>')
    out.append(_path(f"M -2,{y0 + 14} L 2,{y0 + 14}", stroke=c, sw=5, cap="butt"))
    out.append(_path(f"M -50,{y0 + 10} L -78,{y0 + 16}", stroke=c, sw=4))
    out.append(_path(f"M 50,{y0 + 10} L 78,{y0 + 16}", stroke=c, sw=4))
    return "".join(out)


def _head(spec, expression, mouth, look, blink):
    out = []
    if spec.get("ears"):
        out.append(_ell(-80, -226, 11, 17, spec["skin"]))
        out.append(_ell(80, -226, 11, 17, spec["skin"]))
    out.append(_ell(0, HEAD_CY, HEAD_R, HEAD_R + 2, spec["skin"]))
    out.append(_eyes(spec, expression, look, blink))
    out.append(_brows(spec, expression))
    if spec.get("freckles"):
        fc = spec.get("freckle_color", "#c98a62")
        for x, y in ((-50, -210), (-42, -204), (-56, -202), (-46, -214), (-36, -210),
                     (50, -210), (42, -204), (56, -202), (46, -214), (36, -210)):
            out.append(f'<circle cx="{x}" cy="{y}" r="1.8" fill="{fc}"/>')
    if spec["facial_hair"]["style"] == "full_beard":
        out.append(_facial_hair(spec))
        out.append(_mouth(expression, mouth, spec.get("smile")))
    else:
        out.append(_mouth(expression, mouth, spec.get("smile")))
        out.append(_facial_hair(spec))
    out.append(_glasses(spec))
    out.append(_hair_front(spec))
    return "".join(out)


def draw(spec, x, y, expression="neutral", mouth="closed", arms="down",
         look=(0, 2), blink=False, head_tilt=0.0, jitter=(0, 0, 0), t=0.0, scale=1.0):
    """SVG group for one character standing with feet at (x, y)."""
    jx, jy, jr = jitter
    head = _head(spec, expression, mouth, look, blink)
    # Kids get a shrunken body under a full-size head, like South Park kids.
    body_scale = 0.8 if spec.get("build") == "kid" else 1.0
    neck_drop = -NECK[1] * (1 - body_scale)
    scale *= spec.get("size", 1.0)
    body = (_legs(spec) + _torso(spec) + _arm(spec, -1, arms, t) + _arm(spec, 1, arms, t))
    return (
        f'<g transform="translate({x + jx:.1f},{y + jy:.1f}) rotate({jr:.2f}) scale({scale})">'
        f'<g transform="translate(0,{neck_drop:.1f})">{_hair_back(spec)}</g>'
        f'<g transform="scale({body_scale})">{body}</g>'
        f'<g transform="translate(0,{neck_drop:.1f}) rotate({head_tilt:.2f} {NECK[0]} {NECK[1]})">{head}</g>'
        + "</g>"
    )
