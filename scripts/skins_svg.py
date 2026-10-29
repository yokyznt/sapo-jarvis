import colorsys
import json
import math
import pathlib

root = pathlib.Path(__file__).resolve().parent.parent
skins = json.loads((root / "pc" / "skins.json").read_text(encoding="utf-8"))
out = root / "assets" / "skins"
out.mkdir(parents=True, exist_ok=True)
for old in out.glob("*.svg"):
    old.unlink()

R = 80.0
RX, RY, E = R * 1.16, R * 0.86, 2 / 2.7


def outline(n=160):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        x = RX * math.copysign(abs(c) ** E, c)
        y = RY * math.copysign(abs(s) ** E, s)
        if s < 0:
            for b in (-1, 1):
                d = (a - (-math.pi / 2 + b * 0.5) + math.pi) % (2 * math.pi) - math.pi
                y -= R * 0.15 * math.exp(-(d * d) / (0.32 * 0.32))
        pts.append((x, y))
    return pts


def hsv(hexc, sm, vm):
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    r, g, b = colorsys.hsv_to_rgb(h, min(1, s * sm), min(1, v * vm))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def pill(cx, cy, w, h, col):
    return f'<rect x="{cx - w / 2:.1f}" y="{cy - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{w / 2:.1f}" fill="{col}"/>'


ACC = {
    "leaf": '<path d="M2 -66 L3 -84" stroke="{d}" stroke-width="4"/><path d="M3 -84 Q26 -104 50 -92 Q28 -72 3 -84Z" fill="{a}" stroke="{d}" stroke-width="2.5"/>',
    "drop": '<path d="M2 -110 Q-10 -90 -10 -82 A12 12 0 0 0 14 -82 Q14 -90 2 -110Z" fill="{a}" stroke="{d}" stroke-width="2.5"/>',
    "moon": '<path d="M78 -118 A16 16 0 1 0 96 -96 A13 13 0 1 1 78 -118Z" fill="{a}" stroke="{d}" stroke-width="2"/>',
    "sparkle": '<path d="M88 -104 L93 -90 L107 -85 L93 -80 L88 -66 L83 -80 L69 -85 L83 -90Z" fill="{a}" stroke="{d}" stroke-width="2"/>',
}

path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in outline()) + "Z"
pitch = 0.3
for s in skins:
    b, ink, cheek, acc = s["body"], "#" + s["outline"], "#" + s["cheek"], "#" + s["accent"]
    top, bottom, rim = hsv(b, 0.95, 1.08), hsv(b, 1.25, 0.84), hsv(b, 1.4, 0.62)
    eyes = ""
    for side in (-1, 1):
        ya = side * 0.42
        ex, ey = math.sin(ya) * math.cos(pitch) * RX, -math.sin(pitch) * RY
        w, h = R * 0.25 * max(0.2, math.cos(ya)), R * 0.31 * math.cos(pitch)
        eyes += pill(ex, ey, w, h, ink) + f'<circle cx="{ex + w * 0.17:.1f}" cy="{ey - h * 0.22:.1f}" r="{w * 0.17:.1f}" fill="#fff" opacity=".9"/>'
    cheeks = "".join(f'<ellipse cx="{side * RX * 0.58:.1f}" cy="{RY * 0.18:.1f}" rx="{R * 0.19:.1f}" ry="{R * 0.114:.1f}" fill="{cheek}" opacity=".5"/>' for side in (-1, 1))
    mr = R * 0.11
    my = RY * 0.2 - mr * 0.7
    mouth = f'<path d="M{-mr * 0.81:.1f} {my + mr * 0.59:.1f} A{mr:.1f} {mr:.1f} 0 0 0 {mr * 0.81:.1f} {my + mr * 0.59:.1f}" fill="none" stroke="{ink}" stroke-width="3" stroke-linecap="round"/>'
    extra = ACC.get(s["accessory"], "").format(a=acc, d=hsv(s["accent"], 1.1, 0.7))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="-120 -125 240 230" width="240" height="230">
  <defs>
    <linearGradient id="g" gradientUnits="userSpaceOnUse" x1="{RX * 0.7:.1f}" y1="{-RY * 0.85:.1f}" x2="{-RX * 0.8:.1f}" y2="{RY * 0.9:.1f}"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>
    <radialGradient id="r" gradientUnits="userSpaceOnUse" cx="0" cy="4" r="{RX * 1.05:.1f}"><stop offset=".62" stop-color="{rim}" stop-opacity="0"/><stop offset="1" stop-color="{rim}" stop-opacity=".5"/></radialGradient>
    <radialGradient id="h" gradientUnits="userSpaceOnUse" cx="{RX * 0.34:.1f}" cy="{-RY * 0.46:.1f}" r="{R * 0.46:.1f}"><stop offset="0" stop-color="#fff" stop-opacity=".6"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
  </defs>
  <ellipse cx="0" cy="{RY + 6:.1f}" rx="{R * 1.05:.1f}" ry="{R * 0.17:.1f}" fill="#000" opacity=".12"/>
  <path d="{path}" fill="url(#g)"/>
  <path d="{path}" fill="url(#r)"/>
  <path d="{path}" fill="url(#h)"/>
  {extra}
  {cheeks}
  {eyes}
  {mouth}
</svg>
'''
    (out / f"{s['id']}.svg").write_text(svg, encoding="utf-8")
    print(s["id"])
