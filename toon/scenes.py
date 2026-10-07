"""Flat construction-paper backgrounds, 1280x720. Each takes the frame index so
backgrounds can have small animated details (blinking rack LEDs)."""
import random

W, H = 1280, 720
GROUND_Y = 650  # where characters' feet stand


def _rect(x, y, w, h, fill, stroke="#141414", sw=3):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def _poly(points, fill, stroke="#141414", sw=3):
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>'


def outside(frame):
    out = [_rect(0, 0, W, H, "#8cc4ec", stroke="none")]
    out.append(_poly([(-40, 470), (200, 170), (430, 470)], "#7f8fa8"))
    out.append(_poly([(130, 257), (200, 170), (268, 257), (232, 240), (200, 262), (165, 240)], "#ffffff", sw=2))
    out.append(_poly([(300, 470), (620, 120), (930, 470)], "#7083a0"))
    out.append(_poly([(540, 208), (620, 120), (700, 208), (660, 192), (620, 216), (585, 192)], "#ffffff", sw=2))
    out.append(_poly([(820, 470), (1080, 200), (1340, 470)], "#8496b0"))
    out.append(_poly([(1018, 264), (1080, 200), (1142, 264), (1110, 250), (1080, 270), (1050, 250)], "#ffffff", sw=2))
    for x, s in ((90, 1.0), (1180, 1.2), (980, 0.8), (300, 0.7)):
        out.append(_rect(x - 8 * s, 470 - 30 * s, 16 * s, 30 * s, "#6b4a2b"))
        for i, (w, h) in enumerate(((70, 60), (56, 50), (40, 44))):
            y = 450 - i * 34 * s
            out.append(_poly([(x - w * s / 2, y), (x, y - h * s), (x + w * s / 2, y)], "#2f6b3a"))
    out.append(_rect(-10, 470, W + 20, H, "#f3f5f8"))
    out.append(_rect(-10, 560, W + 20, 40, "#d9dde4", stroke="none"))
    return "".join(out)


def living_room(frame):
    out = [_rect(0, 0, W, 560, "#e9d8a6", stroke="none")]
    for x in range(40, W, 80):
        out.append(f'<rect x="{x}" y="0" width="22" height="560" fill="#e1cd94"/>')
    out.append(_rect(-10, 560, W + 20, 200, "#8a5a3c"))
    out.append(_rect(140, 130, 260, 200, "#9fd3f5"))
    out.append(f'<path d="M 270,130 L 270,330 M 140,230 L 400,230" stroke="#141414" stroke-width="6"/>')
    out.append(_rect(820, 260, 300, 190, "#2a2a2e"))
    out.append(_rect(840, 278, 260, 150, "#4b6f96"))
    out.append(_rect(900, 450, 140, 110, "#6e4a2f"))
    out.append(_rect(-30, 430, 330, 130, "#b5463c"))
    out.append(_rect(-30, 380, 330, 70, "#c4554a"))
    return "".join(out)


def server_room(frame):
    out = [_rect(0, 0, W, 560, "#5d6470", stroke="none")]
    out.append(_rect(-10, 560, W + 20, 200, "#3b3f46"))
    rng = random.Random(frame // 3)
    for rx in (120, 330, 960):
        out.append(_rect(rx, 130, 180, 430, "#26282d"))
        for i in range(9):
            y = 150 + i * 44
            out.append(_rect(rx + 12, y, 156, 34, "#3a3d44", sw=2))
            for j in range(4):
                on = rng.random() < 0.6
                color = ("#3ce06a" if j < 3 else "#f0a020") if on else "#1d2a20"
                out.append(f'<circle cx="{rx + 30 + j * 16}" cy="{y + 17}" r="4" fill="{color}"/>')
    out.append(_rect(600, 200, 220, 140, "#f2f2f2"))
    out.append(f'<text x="710" y="260" font-family="DejaVu Sans" font-weight="bold" font-size="30" '
               f'text-anchor="middle" fill="#141414">LOGS</text>')
    out.append(f'<path d="M 620,320 L 660,295 L 700,305 L 740,270 L 800,280" fill="none" '
               f'stroke="#c8102e" stroke-width="5"/>')
    return "".join(out)


def title_card(frame, title=""):
    return (_rect(0, 0, W, H, "#e4b33a", stroke="none")
            + _rect(140, 220, 1000, 280, "#f6efe0", sw=6)
            + f'<text x="640" y="385" font-family="DejaVu Sans" font-weight="bold" font-size="64" '
              f'text-anchor="middle" fill="#141414">{title}</text>')


BACKGROUNDS = {
    "outside": outside,
    "living_room": living_room,
    "living room": living_room,
    "server_room": server_room,
    "server room": server_room,
}
