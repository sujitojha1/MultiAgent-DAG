"""Generate the PulseDAG extension icons (16 / 48 / 128 px).

Theme: a neon "pulse" heartbeat line threading through three DAG nodes,
on a deep indigo→violet gradient rounded square. Run:

    uv run python make_icons.py

Produces icon16.png, icon48.png, icon128.png in this directory.
"""
from __future__ import annotations

import math
from PIL import Image, ImageDraw

# Render at 4x then downsample for crisp anti-aliased edges.
SS = 4
SIZE = 128
S = SIZE * SS

BG_TOP = (79, 70, 229)      # indigo-600
BG_BOT = (168, 85, 247)     # violet-500
PULSE = (52, 245, 168)      # neon green
NODE = (255, 255, 255)
NODE_GLOW = (190, 255, 225)


def _rounded_gradient(size: int, radius: int) -> Image.Image:
    """Vertical gradient clipped to a rounded square."""
    grad = Image.new("RGB", (size, size))
    px = grad.load()
    for y in range(size):
        t = y / (size - 1)
        r = round(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)

    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def make(size_out: int) -> Image.Image:
    img = _rounded_gradient(S, radius=int(S * 0.22))
    d = ImageDraw.Draw(img)

    # Pulse / ECG polyline across the middle.
    cx = S * 0.5
    base = S * 0.56
    amp = S * 0.16
    pts = [
        (S * 0.10, base),
        (S * 0.30, base),
        (S * 0.40, base - amp * 0.4),
        (S * 0.47, base + amp),
        (S * 0.55, base - amp * 1.5),
        (S * 0.63, base + amp * 0.5),
        (S * 0.72, base),
        (S * 0.90, base),
    ]
    lw = max(2, int(S * 0.045))
    # soft glow underlay
    d.line(pts, fill=(*PULSE, 90), width=lw * 3, joint="curve")
    d.line(pts, fill=PULSE, width=lw, joint="curve")

    # Three DAG nodes connected top-left → mid → top-right.
    nodes = [(S * 0.26, S * 0.30), (S * 0.50, S * 0.22), (S * 0.74, S * 0.34)]
    edge_w = max(2, int(S * 0.022))
    for a, b in [(nodes[0], nodes[1]), (nodes[1], nodes[2])]:
        d.line([a, b], fill=(255, 255, 255, 200), width=edge_w)
    r = S * 0.055
    for (nx, ny) in nodes:
        d.ellipse([nx - r * 1.7, ny - r * 1.7, nx + r * 1.7, ny + r * 1.7],
                  fill=(*NODE_GLOW, 70))
        d.ellipse([nx - r, ny - r, nx + r, ny + r], fill=NODE)

    return img.resize((size_out, size_out), Image.LANCZOS)


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for s in (16, 48, 128):
        make(s).save(os.path.join(here, f"icon{s}.png"))
        print(f"wrote icon{s}.png")
