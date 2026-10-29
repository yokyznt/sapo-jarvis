import json
import pathlib

root = pathlib.Path(__file__).resolve().parent.parent
skins = json.loads((root / "pc" / "skins.json").read_text(encoding="utf-8"))
out = root / "assets" / "skins"
out.mkdir(parents=True, exist_ok=True)

ACC = {
    "leaf": '<path d="M122 26 L124 8" stroke="{o}" stroke-width="4"/><path d="M124 10 Q146 -6 166 6 Q146 22 124 10Z" fill="{a}" stroke="{o}" stroke-width="4"/>',
    "drop": '<path d="M120 2 Q108 22 108 30 A12 12 0 0 0 132 30 Q132 22 120 2Z" fill="{a}" stroke="{o}" stroke-width="4"/>',
    "moon": '<path d="M196 18 A16 16 0 1 0 214 40 A12 12 0 1 1 196 18Z" fill="{a}" stroke="{o}" stroke-width="3"/>',
    "sparkle": '<path d="M200 12 L205 26 L219 31 L205 36 L200 50 L195 36 L181 31 L195 26Z" fill="{a}" stroke="{o}" stroke-width="2.5"/>',
    "gills": "".join(
        f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y2}" stroke="{{o}}" stroke-width="20" stroke-linecap="round"/><line x1="{x0}" y1="{y}" x2="{x1}" y2="{y2}" stroke="{{a}}" stroke-width="12" stroke-linecap="round"/>'
        for x0, x1, y, y2 in [(24, 4, 96, 80), (22, 0, 108, 108), (24, 6, 120, 136), (216, 236, 96, 80), (218, 240, 108, 108), (216, 234, 120, 136)]
    ),
}

for s in skins:
    o, b, c, a = "#" + s["outline"], "#" + s["body"], "#" + s["cheek"], "#" + s["accent"]
    acc = ACC.get(s["accessory"], "").format(o=o, a=a)
    behind = acc if s["accessory"] == "gills" else ""
    front = "" if s["accessory"] == "gills" else acc
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="-6 -6 252 192" width="252" height="192">
  {behind}
  <g fill="{b}" stroke="{o}" stroke-width="8">
    <circle cx="74" cy="62" r="34"/>
    <circle cx="166" cy="62" r="34"/>
    <ellipse cx="120" cy="110" rx="106" ry="62"/>
  </g>
  <circle cx="74" cy="62" r="30" fill="{b}"/>
  <circle cx="166" cy="62" r="30" fill="{b}"/>
  <ellipse cx="120" cy="110" rx="102" ry="58" fill="{b}"/>
  {front}
  <circle cx="74" cy="65" r="20" fill="{o}"/>
  <circle cx="166" cy="65" r="20" fill="{o}"/>
  <circle cx="80" cy="59" r="6" fill="#fff"/>
  <circle cx="172" cy="59" r="6" fill="#fff"/>
  <ellipse cx="54" cy="116" rx="17" ry="14" fill="{c}"/>
  <ellipse cx="186" cy="116" rx="17" ry="14" fill="{c}"/>
  <path d="M104 104 Q120 120 136 104" fill="none" stroke="{o}" stroke-width="6" stroke-linecap="round"/>
</svg>
'''
    (out / f"{s['id']}.svg").write_text(svg, encoding="utf-8")
    print(s["id"])
