import json
import os
from pathlib import Path

import webview

from .api import Api
from .system import dark_mode

UI = Path(__file__).resolve().parent / "ui"


def page() -> str:
    html = (UI / "index.html").read_text("utf-8")
    css = (UI / "style.css").read_text("utf-8")
    js = (UI / "app.js").read_text("utf-8")
    tab = json.dumps(os.environ.get("SAPO_PREFS_TAB", ""))
    return html.replace("{{CSS}}", css).replace("{{JS}}", f"const START_TAB = {tab};\n" + js)


def main() -> None:
    api = Api()
    extra = {}
    pos = os.environ.get("SAPO_PREFS_POS")
    if pos:
        try:
            x, y = (int(v) for v in pos.split(","))
            extra = {"x": x, "y": y, "focus": False}
        except ValueError:
            pass
    webview.create_window(
        "Preferencias del Sapo",
        html=page(),
        js_api=api,
        width=940,
        height=700,
        min_size=(760, 540),
        background_color="#161b15" if dark_mode() else "#f3f7ee",
        **extra,
    )
    webview.start(gui="edgechromium", private_mode=True)


if __name__ == "__main__":
    main()
