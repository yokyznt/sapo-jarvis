import ctypes
import json
import sys
import winreg
from ctypes import wintypes
from pathlib import Path

LOCAL_VOICES = ["ef_dora", "em_alex", "em_santa"]
GEMINI_VOICES = ["Kore", "Leda", "Aoede", "Zephyr", "Callirrhoe", "Autonoe", "Puck", "Charon", "Fenrir", "Orus"]


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "data"
    return Path(__file__).resolve().parents[2]


def skins() -> list[dict]:
    root = resource_root()
    try:
        items = json.loads((root / "pc" / "skins.json").read_text("utf-8-sig"))
    except (OSError, ValueError):
        items = []
    out = []
    for s in items:
        if not isinstance(s, dict) or "id" not in s:
            continue
        svg = root / "assets" / "skins" / f"{s['id']}.svg"
        try:
            art = svg.read_text("utf-8")
        except OSError:
            art = ""
        out.append({"id": s["id"], "name": s.get("name", s["id"]), "body": "#" + s.get("body", "b6dc9b"), "cheek": "#" + s.get("cheek", "f7a3a0"), "svg": art})
    return out


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def monitors() -> list[dict]:
    user32 = ctypes.windll.user32
    found = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(hmon, hdc, rect, data):
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            found.append({"x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top, "primary": bool(info.dwFlags & 1)})
        return True

    try:
        user32.EnumDisplayMonitors(None, None, proc(cb), 0)
    except OSError:
        return []
    primary = next((m for m in found if m["primary"]), None)
    for i, m in enumerate(found):
        m["index"] = i
        where = ""
        if primary and not m["primary"]:
            dx, dy = m["x"] - primary["x"], m["y"] - primary["y"]
            if abs(dy) >= abs(dx):
                where = "arriba" if dy < 0 else "abajo"
            else:
                where = "a la izquierda" if dx < 0 else "a la derecha"
        m["label"] = f"Pantalla {i + 1} · {m['w']}×{m['h']}" + (" · principal" if m["primary"] else f" · {where}" if where else "")
    return found


def audio_devices() -> dict:
    try:
        import sounddevice as sd
        api = sd.default.hostapi
        devs = sd.query_devices()
    except Exception:
        return {"inputs": [], "outputs": []}
    inputs, outputs = [], []
    for d in devs:
        if d.get("hostapi") != api:
            continue
        name = str(d.get("name", ""))
        low = name.lower()
        if not name.strip() or "asignador" in low or "mapper" in low or "controlador primario" in low or "primary sound" in low:
            continue
        if d.get("max_input_channels", 0) > 0 and name not in inputs:
            inputs.append(name)
        if d.get("max_output_channels", 0) > 0 and name not in outputs:
            outputs.append(name)
    return {"inputs": inputs, "outputs": outputs}


def dark_mode() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False
