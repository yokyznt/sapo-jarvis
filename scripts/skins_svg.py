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
RX, RY = R * 1.04, R * 0.96


def outline(n=160):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        s = math.sin(a)
        x = RX * math.cos(a)
        if s > 0:
            x *= 1 + 0.04 * s
        pts.append((x, RY * s))
    return pts


def hsv(hexc, sm, vm):
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    r, g, b = colorsys.hsv_to_rgb(h, min(1, s * sm), min(1, v * vm))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


ACC = {
    "leaf": '<path d="M2 -66 L3 -84" stroke="{d}" stroke-width="4"/><path d="M3 -84 Q26 -104 50 -92 Q28 -72 3 -84Z" fill="{a}" stroke="{d}" stroke-width="2.5"/>',
    "drop": '<path d="M2 -110 Q-10 -90 -10 -82 A12 12 0 0 0 14 -82 Q14 -90 2 -110Z" fill="{a}" stroke="{d}" stroke-width="2.5"/>',
    "moon": '<path d="M78 -118 A16 16 0 1 0 96 -96 A13 13 0 1 1 78 -118Z" fill="{a}" stroke="{d}" stroke-width="2"/>',
    "sparkle": '<path d="M88 -104 L93 -90 L107 -85 L93 -80 L88 -66 L83 -80 L69 -85 L83 -90Z" fill="{a}" stroke="{d}" stroke-width="2"/>',
}
FRECKLES = ((-0.1, -0.03), (0.04, -0.07), (0.08, 0.05))

path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in outline()) + "Z"
for s in skins:
    b, ink, cheek, acc = s["body"], "#" + s["outline"], "#" + s["cheek"], "#" + s["accent"]
    mouth_col, tongue = "#" + s["mouth"], "#" + s["tongue"]
    top, bottom, edge, freckle = hsv(b, 0.82, 1.06), hsv(b, 1.12, 0.9), hsv(b, 1.2, 0.72), hsv(b, 1.3, 0.62)
    eyes = "".join(f'<ellipse cx="{side * R * 0.36:.1f}" cy="{-R * 0.18:.1f}" rx="{R * 0.11:.1f}" ry="{R * 0.16:.1f}" fill="{ink}"/>' for side in (-1, 1))
    cheeks = ""
    for side in (-1, 1):
        cx, cy = side * R * 0.62, R * 0.14
        cheeks += f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{R * 0.18:.1f}" ry="{R * 0.11:.1f}" fill="{cheek}" opacity=".85"/>'
        cheeks += "".join(f'<circle cx="{cx + fx * side * R:.1f}" cy="{cy + fy * R:.1f}" r="{R * 0.038:.1f}" fill="{freckle}" opacity=".75"/>' for fx, fy in FRECKLES)
    r = R * 0.26
    w, depth, my = r * 0.62, r * 0.55, R * 0.22
    mouth = (
        f'<clipPath id="m"><path d="M{-w:.1f} {my:.1f} A{w:.1f} {depth:.1f} 0 0 0 {w:.1f} {my:.1f}Z"/></clipPath>'
        f'<path d="M{-w:.1f} {my:.1f} A{w:.1f} {depth:.1f} 0 0 0 {w:.1f} {my:.1f}Z" fill="{mouth_col}" stroke="{mouth_col}" stroke-width="2.4" stroke-linejoin="round"/>'
        f'<ellipse clip-path="url(#m)" cx="0" cy="{my + depth * 1.02:.1f}" rx="{w * 0.58:.1f}" ry="{w * 0.52:.1f}" fill="{tongue}"/>'
    )
    extra = ACC.get(s["accessory"], "").format(a=acc, d=hsv(s["accent"], 1.1, 0.7))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="-120 -125 240 230" width="240" height="230">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>
    <radialGradient id="h" gradientUnits="userSpaceOnUse" cx="{-RX * 0.36:.1f}" cy="{-RY * 0.5:.1f}" r="{R * 0.38:.1f}"><stop offset="0" stop-color="#fff" stop-opacity=".5"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
  </defs>
  <ellipse cx="0" cy="{RY + 6:.1f}" rx="{R:.1f}" ry="{R * 0.16:.1f}" fill="#000" opacity=".12"/>
  <path d="{path}" fill="url(#g)" stroke="{edge}" stroke-width="3"/>
  <path d="{path}" fill="url(#h)"/>
  <g transform="translate(0 22)">{extra}</g>
  {cheeks}
  {eyes}
  {mouth}
</svg>
'''
    (out / f"{s['id']}.svg").write_text(svg, encoding="utf-8")
    print(s["id"])
