import asyncio
import ctypes
import json
import logging
import os
import subprocess
import time
import urllib.request
from ctypes import wintypes
from typing import Any

log = logging.getLogger("sapo.spotify")

PORT = 9229
FLAGS = [
    f"--remote-debugging-port={PORT}",
    "--remote-debugging-address=127.0.0.1",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--minimized",
]
NO_WINDOW = 0x08000000

FIND_ROWS = """(() => {
  const words = WORDS;
  const fold = s => s.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
  const seen = new Set();
  const out = [];
  const add = (row, target) => {
    if (!row || seen.has(row)) return;
    seen.add(row);
    const b = row.getBoundingClientRect();
    if (b.width <= 0 || b.top < 0 || b.top > innerHeight) return;
    const spot = [0.62, 0.55, 0.7].map(f => ({x: b.left + b.width * f, y: b.top + b.height / 2})).find(p => { const e = document.elementFromPoint(p.x, p.y); return e && !e.closest('a, button'); }) || {x: b.left + b.width * 0.62, y: b.top + b.height / 2};
    const t = fold(row.innerText.replace(/\\n/g, ' '));
    out.push({t: t.slice(0, 120), s: words.filter(w => t.includes(w)).length, song: /cancion|song/.test(t) ? 1 : 0, x: spot.x, y: spot.y});
  };
  for (const r of document.querySelectorAll('[data-testid="tracklist-row"]')) add(r, r);
  for (const t of document.querySelectorAll('[data-testid="title"]')) {
    let row = t;
    for (let i = 0; i < 6 && row && !row.querySelector('[data-testid="subtitle"]'); i++) row = row.parentElement;
    add(row, t);
  }
  out.sort((a, b) => (b.s - a.s) || (b.song - a.song) || (a.y - b.y));
  return JSON.stringify({rows: out.slice(0, 3), path: location.pathname, w: innerWidth});
})()"""

NOW = """(() => { const w = document.querySelector('[data-testid="now-playing-widget-v2"]') || document.querySelector('[data-testid="now-playing-widget"]');
  const p = document.querySelector('[data-testid="control-button-playpause"]');
  return JSON.stringify({title: document.title, now: w ? w.innerText.replace(/\\n/g, ' - ') : '', label: p ? (p.getAttribute('aria-label') || '') : ''}); })()"""

SEARCH = """(() => { const i = document.querySelector('[data-testid="search-input"]'); if (!i) return 'sin input';
  i.focus(); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(i, '');
  i.dispatchEvent(new Event('input', {bubbles: true})); return 'ok'; })()"""

PLAY_AT = """(() => {
  let row = document.elementFromPoint(X, Y);
  for (let i = 0; i < 8 && row && !row.querySelector('[data-testid="subtitle"], [data-testid="tracklist-row"]') && row.dataset.testid !== 'tracklist-row'; i++) row = row.parentElement;
  if (!row) return 'sin fila';
  const b = [...row.querySelectorAll('button')].find(b => /^(reproducir|play)\\b/i.test(b.getAttribute('aria-label') || '') || b.dataset.testid === 'play-button');
  if (!b) return 'sin boton';
  b.click();
  return 'ok ' + (b.getAttribute('aria-label') || '');
})()"""

PAGE_PLAY = """(() => {
  if (/^(buscar|search)\\b/i.test(document.title)) return 'sigue en la búsqueda';
  const scope = document.querySelector('[data-testid="action-bar-row"]') || document.querySelector('main') || document;
  const b = scope.querySelector('[data-testid="play-button"]');
  if (!b) return 'sin boton';
  if (/paus/i.test(b.getAttribute('aria-label') || '')) return 'ya';
  b.click();
  return 'ok ' + location.pathname;
})()"""

BUTTON = """(() => { const b = document.querySelector('[data-testid="ID"]'); if (!b) return 'no'; b.click(); return 'ok'; })()"""


FILLER = {"del", "los", "las", "una", "uno", "con", "por", "que", "feat", "the", "cancion", "rola", "spotify", "pon", "ponme"}


def fold(text: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def find_exe() -> str:
    candidates = [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Spotify", "Spotify.exe"),
    ]
    try:
        import psutil

        for p in psutil.process_iter(["name", "exe"]):
            if (p.info["name"] or "").lower() == "spotify.exe" and p.info["exe"] and "windowsapps" not in p.info["exe"].lower():
                candidates.insert(0, p.info["exe"])
    except Exception:
        pass
    return next((c for c in candidates if os.path.exists(c)), candidates[0])


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


class Hidden:
    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.saved: WINDOWPLACEMENT | None = None

    def placement(self) -> WINDOWPLACEMENT:
        wp = WINDOWPLACEMENT()
        wp.length = ctypes.sizeof(WINDOWPLACEMENT)
        self.user32.GetWindowPlacement(wintypes.HWND(self.hwnd), ctypes.byref(wp))
        return wp

    def rescue(self) -> bool:
        ex = self.user32.GetWindowLongW(wintypes.HWND(self.hwnd), -20)
        if not ex & 0x80000:
            return False
        self.user32.SetWindowLongW(wintypes.HWND(self.hwnd), -20, ex & ~0x80000)
        self.user32.ShowWindow(wintypes.HWND(self.hwnd), 7)
        return True

    def __enter__(self) -> "Hidden":
        self.rescue()
        h = wintypes.HWND(self.hwnd)
        self.untouched = bool(self.user32.IsWindowVisible(h)) and not self.user32.IsIconic(h)
        if self.untouched:
            return self
        self.saved = self.placement()
        ex = self.user32.GetWindowLongW(h, -20)
        self.user32.SetWindowLongW(h, -20, ex | 0x80000)
        self.user32.SetLayeredWindowAttributes(h, 0, 0, 2)
        self.user32.ShowWindow(h, 4)
        self.user32.SetWindowPos(h, wintypes.HWND(1), 0, 0, 0, 0, 0x0010 | 0x0002 | 0x0001)
        return self

    def __exit__(self, *exc: Any) -> None:
        if getattr(self, "untouched", False):
            return
        h = wintypes.HWND(self.hwnd)
        self.user32.ShowWindow(h, 7)
        ex = self.user32.GetWindowLongW(h, -20)
        self.user32.SetWindowLongW(h, -20, ex & ~0x80000)
        if self.saved is not None:
            wp = self.saved
            wp.showCmd = 7
            self.user32.SetWindowPlacement(h, ctypes.byref(wp))


class Spotify:
    def __init__(self, exe: str | None = None, port: int = PORT):
        self.exe = exe or find_exe()
        self.port = port
        self.n = 0

    def installed(self) -> bool:
        if not os.path.exists(self.exe):
            self.exe = find_exe()
        return os.path.exists(self.exe)

    def pages(self) -> list[dict]:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json", timeout=2) as r:
                return [p for p in json.load(r) if p.get("type") == "page" and "xpui" in p.get("url", "")]
        except Exception:
            return []

    def processes(self) -> list[Any]:
        import psutil

        return [p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "spotify.exe"]

    def window(self) -> int:
        import psutil

        pids = {p.pid for p in self.processes()}
        found = []
        user32 = ctypes.WinDLL("user32")

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def visit(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and user32.GetWindowTextLengthW(hwnd) and not user32.GetWindow(hwnd, 4):
                cls = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(hwnd, cls, 64)
                if cls.value == "Chrome_WidgetWin_1":
                    found.append(int(hwnd))
            return True

        user32.EnumWindows(visit, 0)
        return found[0] if found else 0

    def rescue(self) -> bool:
        hwnd = self.window()
        return bool(hwnd) and Hidden(hwnd).rescue()

    async def ready(self, sleep=asyncio.sleep) -> bool:
        if self.pages():
            return True
        if not self.installed():
            return False
        for p in self.processes():
            try:
                p.kill()
            except Exception:
                pass
        await sleep(1.5)
        subprocess.Popen([self.exe, *FLAGS], creationflags=NO_WINDOW, close_fds=True)
        for _ in range(40):
            await sleep(0.5)
            if self.pages() and self.window():
                await sleep(2.5)
                return True
        return False

    async def call(self, ws, method: str, params: dict | None = None) -> dict:
        self.n += 1
        await ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), 10))
            if m.get("id") == self.n:
                return m.get("result", {})

    async def js(self, ws, expr: str) -> Any:
        r = await self.call(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    def connect(self):
        import websockets

        page = self.pages()[0]
        return websockets.connect(page["webSocketDebuggerUrl"], max_size=2**24, origin=f"http://127.0.0.1:{self.port}")

    async def double(self, ws, row: dict) -> None:
        await self.call(ws, "Input.dispatchMouseEvent", {"type": "mouseMoved", "x": row["x"], "y": row["y"]})
        for count in (1, 2):
            for kind in ("mousePressed", "mouseReleased"):
                await self.call(ws, "Input.dispatchMouseEvent", {"type": kind, "x": row["x"], "y": row["y"], "button": "left", "clickCount": count})

    async def enter(self, ws) -> None:
        base = {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13}
        await self.call(ws, "Input.dispatchKeyEvent", {"type": "rawKeyDown", **base})
        await self.call(ws, "Input.dispatchKeyEvent", {"type": "char", "text": "\r", **base})
        await self.call(ws, "Input.dispatchKeyEvent", {"type": "keyUp", **base})

    async def now(self) -> dict:
        async with self.connect() as ws:
            return json.loads(await self.js(ws, NOW) or "{}")

    async def press(self, testid: str) -> bool:
        if not self.pages():
            return False
        with Hidden(self.window()):
            await asyncio.sleep(0.6)
            async with self.connect() as ws:
                return await self.js(ws, BUTTON.replace("ID", testid)) == "ok"

    async def resume(self) -> bool:
        state = await self.now()
        if "paus" in fold(state.get("label", "")):
            return True
        await self.press("control-button-playpause")
        for _ in range(6):
            await asyncio.sleep(0.5)
            if "paus" in fold((await self.now()).get("label", "")):
                return True
        return False

    async def pause(self) -> bool:
        for _ in range(2):
            state = await self.now()
            if "paus" not in fold(state.get("label", "")):
                return True
            await self.press("control-button-playpause")
            for _ in range(6):
                await asyncio.sleep(0.5)
                if "paus" not in fold((await self.now()).get("label", "")):
                    return True
        return False

    async def play(self, query: str, sleep=asyncio.sleep) -> tuple[bool, str]:
        if not await self.ready(sleep):
            return False, "no pude abrir Spotify"
        hwnd = self.window()
        words = [w for w in fold(query).split() if len(w) > 2 and w not in FILLER] or fold(query).split()
        with Hidden(hwnd):
            await sleep(1.0)
            async with self.connect() as ws:
                await self.js(ws, "(() => { const b = document.querySelector('[data-testid=\"search-icon\"]'); b && b.click(); return 1; })()")
                await sleep(0.4)
                await self.call(ws, "Emulation.setFocusEmulationEnabled", {"enabled": True})
                if await self.js(ws, SEARCH) != "ok":
                    return False, "no encontré la búsqueda de Spotify"
                await self.call(ws, "Input.insertText", {"text": query})
                await sleep(0.3)
                await self.enter(ws)
                best = None
                for tick in range(20):
                    await sleep(0.5)
                    data = json.loads(await self.js(ws, FIND_ROWS.replace("WORDS", json.dumps(words))) or "{}")
                    rows = data.get("rows") or []
                    if rows and rows[0]["s"] > 0 and (best is None or rows[0]["s"] > best["s"]):
                        best = rows[0]
                    if best is not None and (best["s"] >= len(words) or tick >= 8):
                        break
                if best is None:
                    return False, f"Spotify no me dio resultados de {query}"
                await self.call(ws, "Input.dispatchMouseEvent", {"type": "mouseMoved", "x": best["x"], "y": best["y"]})
                await sleep(0.4)
                clicked = await self.js(ws, PLAY_AT.replace("X", str(best["x"])).replace("Y", str(best["y"])))
                log.info("spotify: fila %r -> %s", best.get("t"), clicked)
                if not str(clicked).startswith("ok"):
                    await self.double(ws, best)
                ad = False
                for tick in range(16):
                    await sleep(0.5)
                    if tick == 4 and not str(await self.js(ws, "document.title")).lower().startswith(("buscar", "search")):
                        data = json.loads(await self.js(ws, FIND_ROWS.replace("WORDS", json.dumps(words))) or "{}")
                        rows = [r for r in data.get("rows") or [] if r["s"] > 0]
                        if rows:
                            log.info("spotify: en la página, doble clic a %r", rows[0].get("t"))
                            await self.double(ws, rows[0])
                        else:
                            log.info("spotify: botón de la página -> %s", await self.js(ws, PAGE_PLAY))
                    state = json.loads(await self.js(ws, NOW) or "{}")
                    text = fold(state.get("now", ""))
                    if any(k in text for k in ("publicidad", "advertisement", "anuncio")):
                        ad = True
                        continue
                    if all(w in text for w in words) and "paus" in fold(state.get("label", "")):
                        return True, state.get("now") or state.get("title") or query
                if ad:
                    return True, f"{query} (primero pasa un anuncio de Spotify)"
                return False, "le di play pero no veo que suene"
