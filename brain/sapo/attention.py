import io
import logging
import os
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .phrases import normalize

log = logging.getLogger("sapo.attention")

BROWSERS = {"chrome", "msedge", "firefox", "brave", "opera", "opera_gx", "vivaldi", "arc", "zen", "librewolf", "thorium"}
BROWSER_SUFFIX = re.compile(
    r"\s*[-—–|]\s*(google chrome|microsoft\s*edge|mozilla firefox|firefox|brave|opera|vivaldi|arc|zen browser|librewolf|thorium)\s*$",
    re.I,
)
SEPARATORS = re.compile(r"\s+[-—–|·]\s+")
IGNORED = {"sapo", "godot", "seelen-ui", "sapopreferencias", "lockapp", "searchhost", "startmenuexperiencehost", "shellexperiencehost", "textinputhost", "applicationframehost"}
SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
GENERIC = {"nueva pestana", "new tab", "inicio", "home", "untitled", "sin titulo", "documento", "document"}
MEET_CODE = re.compile(r"\b[a-z]{3}-[a-z]{4}-[a-z]{3}\b")
CALL_RULES = (
    (("ms-teams", "teams", "msteams"), ("reunion", "meeting", "llamada", "call", "en curso", "compartiendo", "sharing")),
    (("zoom", "zoomworkplace"), ("meeting", "reunion", "webinar", "compartiendo", "sharing")),
    (("discord",), ("voz", "voice", "llamada", "call", "stage", "escenario", "en directo")),
    (("slack",), ("huddle", "llamada", "call")),
    (("webex", "ciscocollabhost", "webexmta"), ("meeting", "reunion", "call", "llamada")),
    (("skype",), ("call", "llamada")),
)
SHARING = ("esta compartiendo tu pantalla", "is sharing your screen", "estas compartiendo", "you are sharing", "presentando ahora", "presenting now")


@dataclass(frozen=True)
class Foreground:
    process: str
    title: str
    fullscreen: bool = False
    pid: int = 0
    rect: tuple[int, int, int, int] | None = None


def stem(process: str) -> str:
    return Path(process).stem.lower()


def clean_title(fg: Foreground) -> str:
    title = fg.title.strip()
    if stem(fg.process) in BROWSERS:
        title = BROWSER_SUFFIX.sub("", title)
    return title.strip()


def app_name(fg: Foreground) -> str:
    base = stem(fg.process)
    if base in BROWSERS:
        parts = [p for p in SEPARATORS.split(clean_title(fg)) if p.strip()]
        if len(parts) >= 2:
            return parts[-1].strip()[:40]
        return {"msedge": "Edge", "chrome": "Chrome"}.get(base, base.capitalize())
    parts = [p for p in SEPARATORS.split(fg.title.strip()) if p.strip()]
    if parts and 2 <= len(parts[-1]) <= 30:
        last = normalize(parts[-1]).replace(" ", "")
        flat = normalize(base).replace(" ", "")
        if last and flat and (flat in last or last in flat):
            return parts[-1].strip()
    if len(parts) == 1 and 2 <= len(parts[0]) <= 30:
        only = normalize(parts[0]).replace(" ", "")
        if only and only in normalize(base).replace(" ", ""):
            return parts[0].strip()
    return base.capitalize() if base else "?"


def activity_key(fg: Foreground) -> str:
    return f"{stem(fg.process)}|{normalize(app_name(fg))}"


def blocked(fg: Foreground, words: Iterable[str]) -> bool:
    hay = f"{fg.process} {fg.title}".lower()
    flat = normalize(hay)
    for w in words:
        w = w.strip().lower()
        if w and (w in hay or normalize(w) in flat):
            return True
    return False


def in_call(fg: Foreground) -> bool:
    base = stem(fg.process)
    title = normalize(fg.title)
    if any(s in title for s in SHARING):
        return True
    for names, hints in CALL_RULES:
        if any(base == n or base.startswith(n) for n in names) and any(h in title for h in hints):
            return True
    if base in BROWSERS:
        raw = fg.title.lower()
        if raw.startswith("meet ") or raw.startswith("meet:") or "meet.google.com" in raw or MEET_CODE.search(raw):
            return True
        if "zoom" in title and ("meeting" in title or "reunion" in title):
            return True
        if "teams" in title and any(h in title for h in ("reunion", "meeting", "llamada", "call")):
            return True
    return False


def title_is_enough(fg: Foreground) -> bool:
    core = clean_title(fg)
    words = normalize(core).split()
    app = normalize(app_name(fg)).split()
    rest = [w for w in words if w not in app and w != stem(fg.process)]
    return len(rest) >= 2 and normalize(core) not in GENERIC


def fmt_minutes(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h} h" if m == 0 else f"{h} h {m} min"


class Attention:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        today: Callable[[], date] = date.today,
        settle: float = 120.0,
        vision_every: float = 600.0,
        max_step: float = 15.0,
        idle_limit: float = 300.0,
    ):
        self.clock = clock
        self.today = today
        self.settle = settle
        self.vision_every = vision_every
        self.max_step = max_step
        self.idle_limit = idle_limit
        self.current: Foreground | None = None
        self.key: str | None = None
        self.since = 0.0
        self.app_since = 0.0
        self.commented = True
        self.private = False
        self.call = False
        self.fullscreen = False
        self.last_seen: float | None = None
        self.last_capture = float("-inf")
        self.day: dict[str, float] = {}
        self.day_date = today()
        self.first = True

    @property
    def quiet(self) -> bool:
        return self.call or self.fullscreen

    def observe(self, fg: Foreground | None, blacklist: Iterable[str] = (), idle: float = 0.0) -> bool:
        now = self.clock()
        if self.today() != self.day_date:
            self.day, self.day_date = {}, self.today()
        if self.current is not None and self.last_seen is not None and not self.private and idle < self.idle_limit:
            app = app_name(self.current)
            self.day[app] = self.day.get(app, 0.0) + min(max(0.0, now - self.last_seen), self.max_step)
        self.last_seen = now
        if fg is None or stem(fg.process) in IGNORED or fg.pid == os.getpid():
            return False
        self.private = blocked(fg, blacklist)
        self.call = in_call(fg)
        self.fullscreen = fg.fullscreen
        key = "privado" if self.private else activity_key(fg)
        changed = key != self.key
        if changed:
            same_app = self.current is not None and not self.private and app_name(self.current) == app_name(fg)
            self.key = key
            self.since = now
            if not same_app:
                self.app_since = now
            self.commented = self.first or self.private
            self.first = False
        self.current = fg
        return changed

    def pending(self) -> Foreground | None:
        if self.current is None or self.commented or self.private or self.quiet:
            return None
        if self.clock() - self.since < self.settle:
            return None
        return self.current

    def mark_commented(self) -> None:
        self.commented = True

    def wants_vision(self, enabled: bool) -> bool:
        if not enabled or self.current is None or self.private or self.quiet:
            return False
        if self.clock() - self.last_capture < self.vision_every:
            return False
        return not title_is_enough(self.current)

    def captured(self) -> None:
        self.last_capture = self.clock()

    def minutes_here(self) -> float:
        return max(0.0, self.clock() - self.app_since)

    def summary(self, top: int = 4) -> str:
        items = sorted(((a, s) for a, s in self.day.items() if s >= 60), key=lambda x: -x[1])[:top]
        return ", ".join(f"{a} {fmt_minutes(s)}" for a, s in items)

    def describe(self) -> dict[str, str]:
        if self.current is None:
            return {"app": "", "title": "", "here": "", "day": self.summary()}
        if self.private:
            return {"app": "algo privado", "title": "", "here": "", "day": self.summary()}
        return {
            "app": app_name(self.current),
            "title": clean_title(self.current)[:120],
            "here": fmt_minutes(self.minutes_here()),
            "day": self.summary(),
        }


def read_foreground() -> Foreground | None:
    import ctypes
    from ctypes import wintypes

    import psutil

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    if cls.value in SHELL_CLASSES:
        return None
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        name = psutil.Process(pid.value).name()
    except psutil.Error:
        name = ""
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    full = False
    monitor = user32.MonitorFromWindow(hwnd, 2)
    if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        m = info.rcMonitor
        covers = rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom
        exact = max(m.left - rect.left, m.top - rect.top, rect.right - m.right, rect.bottom - m.bottom) <= 2
        full = covers and exact and not user32.IsZoomed(hwnd)
    full = full or notification_busy()
    return Foreground(name, buf.value, full, pid.value, (rect.left, rect.top, rect.right, rect.bottom))


def notification_busy() -> bool:
    import ctypes

    state = ctypes.c_int(0)
    try:
        if ctypes.WinDLL("shell32").SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return False
    except OSError:
        return False
    return state.value in (2, 3, 4)


def idle_seconds() -> float:
    import ctypes
    from ctypes import wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.WinDLL("user32").GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return max(0.0, (ctypes.WinDLL("kernel32").GetTickCount() - info.dwTime) / 1000.0)


def capture(fg: Foreground, size: int = 768, quality: int = 70) -> bytes:
    from PIL import ImageGrab

    box = fg.rect if fg.rect and fg.rect[2] - fg.rect[0] > 50 and fg.rect[3] - fg.rect[1] > 50 else None
    img = ImageGrab.grab(bbox=box, all_screens=True).convert("RGB")
    img.thumbnail((size, size))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()
