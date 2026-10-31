import difflib
import io
import json
import os
import re
import subprocess
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class Window:
    hwnd: int
    title: str
    process: str


class PC(Protocol):
    def open_app(self, name: str) -> str: ...

    def open_url(self, url: str) -> None: ...

    def open_path(self, path: Path) -> None: ...

    def folder(self, key: str) -> Path: ...

    def volume(self) -> tuple[int, bool]: ...

    def set_volume(self, percent: int) -> None: ...

    def set_mute(self, on: bool) -> None: ...

    def media_key(self, action: str) -> None: ...

    def clipboard(self) -> str: ...

    def set_clipboard(self, text: str) -> None: ...

    def windows(self) -> list[Window]: ...

    def window_do(self, hwnd: int, action: str) -> None: ...

    def screenshot(self) -> bytes: ...

    def lock(self) -> None: ...

    def power(self, action: str) -> None: ...

    def trash(self, path: Path) -> None: ...


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def best_match(query: str, names: list[str]) -> str | None:
    q = norm(query)
    if not q:
        return None
    normed = [(norm(n), n) for n in names if norm(n)]
    for n, original in normed:
        if n == q:
            return original
    for test in (
        lambda n: f" {q}" in f" {n}",
        lambda n: q in n,
        lambda n: all(w in n.split() for w in q.split()),
    ):
        hits = sorted((len(n), original) for n, original in normed if test(n))
        if hits:
            return hits[0][1]
    close = difflib.get_close_matches(q, [n for n, _ in normed], n=1, cutoff=0.75)
    if close:
        return next(original for n, original in normed if n == close[0])
    return None


ALIASES = {
    "bloc de notas": "notepad.exe",
    "notepad": "notepad.exe",
    "notas": "notepad.exe",
    "calculadora": "calc.exe",
    "calc": "calc.exe",
    "explorador": "explorer.exe",
    "explorador de archivos": "explorer.exe",
    "archivos": "explorer.exe",
    "paint": "mspaint.exe",
    "cmd": "cmd.exe",
    "simbolo del sistema": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "administrador de tareas": "taskmgr.exe",
    "configuracion": "ms-settings:",
    "ajustes": "ms-settings:",
    "panel de control": "control.exe",
}

SHELL_FOLDERS = {
    "documents": ("Personal", "Documents"),
    "desktop": ("Desktop", "Desktop"),
    "downloads": ("{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
    "pictures": ("My Pictures", "Pictures"),
    "music": ("My Music", "Music"),
    "videos": ("My Video", "Videos"),
}

MEDIA_KEYS = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2}
WINDOW_SHOW = {"minimize": 6, "maximize": 3, "restore": 9}


class WindowsPC:
    def __init__(self) -> None:
        self.start_apps: list[dict] | None = None

    def start_menu(self) -> dict[str, Path]:
        roots = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
            self.folder("desktop"),
            Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop",
        ]
        found: dict[str, Path] = {}
        for root in roots:
            if not root.is_dir():
                continue
            for ext in ("*.lnk", "*.url"):
                for p in root.rglob(ext):
                    stem = p.stem
                    if re.search(r"uninstall|desinstal", stem, re.I):
                        continue
                    found.setdefault(stem, p)
        return found

    def store_apps(self) -> list[dict]:
        if self.start_apps is None:
            try:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-StartApps | ConvertTo-Json -Compress"],
                    capture_output=True,
                    timeout=15,
                    creationflags=NO_WINDOW,
                ).stdout.decode("utf-8", "replace")
                data = json.loads(out or "[]")
                self.start_apps = data if isinstance(data, list) else [data]
            except (OSError, subprocess.SubprocessError, ValueError):
                self.start_apps = []
        return self.start_apps

    def open_app(self, name: str) -> str:
        key = best_match(name, list(ALIASES))
        if key and norm(key) == norm(name):
            os.startfile(ALIASES[key])
            return key
        entries = self.start_menu()
        hit = best_match(name, list(entries))
        if hit:
            os.startfile(str(entries[hit]))
            return hit
        apps = {a.get("Name", ""): a.get("AppID", "") for a in self.store_apps() if a.get("AppID")}
        hit = best_match(name, list(apps))
        if hit:
            os.startfile(f"shell:AppsFolder\\{apps[hit]}")
            return hit
        if key:
            os.startfile(ALIASES[key])
            return key
        raise LookupError(name)

    def open_url(self, url: str) -> None:
        os.startfile(url)

    def open_path(self, path: Path) -> None:
        os.startfile(str(path))

    def folder(self, key: str) -> Path:
        if key == "home":
            return Path.home()
        reg, default = SHELL_FOLDERS[key]
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                value, _ = winreg.QueryValueEx(k, reg)
            return Path(os.path.expandvars(value))
        except OSError:
            return Path.home() / default

    def endpoint(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities

        comtypes.CoInitialize()
        return AudioUtilities.GetSpeakers().EndpointVolume

    def volume(self) -> tuple[int, bool]:
        ep = self.endpoint()
        return round(ep.GetMasterVolumeLevelScalar() * 100), bool(ep.GetMute())

    def set_volume(self, percent: int) -> None:
        ep = self.endpoint()
        ep.SetMasterVolumeLevelScalar(max(0, min(100, percent)) / 100, None)
        if percent > 0 and ep.GetMute():
            ep.SetMute(0, None)

    def set_mute(self, on: bool) -> None:
        self.endpoint().SetMute(1 if on else 0, None)

    def send_keys(self, vks: list[int]) -> None:
        import ctypes
        from ctypes import wintypes

        ulong_ptr = ctypes.c_size_t

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

        class UNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", UNION)]

        events = []
        for vk in vks:
            for flags in (1, 3):
                events.append(INPUT(type=1, u=UNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0))))
        array = (INPUT * len(events))(*events)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        user32.SendInput(len(events), array, ctypes.sizeof(INPUT))

    def media_key(self, action: str) -> None:
        self.send_keys([MEDIA_KEYS[action]])

    def clipboard_api(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        for _ in range(10):
            if user32.OpenClipboard(None):
                return ctypes, user32, kernel32
            time.sleep(0.05)
        raise OSError("el portapapeles está ocupado")

    def clipboard(self) -> str:
        ctypes, user32, kernel32 = self.clipboard_api()
        try:
            handle = user32.GetClipboardData(13)
            if not handle:
                return ""
            ptr = kernel32.GlobalLock(handle)
            try:
                return ctypes.wstring_at(ptr) if ptr else ""
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def set_clipboard(self, text: str) -> None:
        ctypes, user32, kernel32 = self.clipboard_api()
        try:
            user32.EmptyClipboard()
            data = text.encode("utf-16-le") + b"\0\0"
            handle = kernel32.GlobalAlloc(2, len(data))
            ptr = kernel32.GlobalLock(handle)
            ctypes.memmove(ptr, data, len(data))
            kernel32.GlobalUnlock(handle)
            user32.SetClipboardData(13, handle)
        finally:
            user32.CloseClipboard()

    def windows(self) -> list[Window]:
        import ctypes
        from ctypes import wintypes

        import psutil

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        dwm = ctypes.WinDLL("dwmapi")
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindow.restype = wintypes.HWND
        user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        found: list[Window] = []
        names: dict[int, str] = {}

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def visit(hwnd, _):
            if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):
                return True
            if user32.GetWindowLongPtrW(hwnd, -20) & 0x08000080:
                return True
            cloaked = ctypes.c_int(0)
            dwm.DwmGetWindowAttribute(wintypes.HWND(hwnd), 14, ctypes.byref(cloaked), 4)
            if cloaked.value:
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if not length:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value not in names:
                try:
                    names[pid.value] = psutil.Process(pid.value).name()
                except psutil.Error:
                    names[pid.value] = ""
            if buf.value in ("Program Manager", "Windows Input Experience"):
                return True
            found.append(Window(int(hwnd), buf.value, names[pid.value]))
            return True

        user32.EnumWindows(visit, 0)
        return found

    def window_do(self, hwnd: int, action: str) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.IsIconic.argtypes = [wintypes.HWND]
        if action == "close":
            user32.PostMessageW(hwnd, 0x10, 0, 0)
        elif action == "focus":
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)
            self.send_keys([0x12])
            user32.SetForegroundWindow(hwnd)
        else:
            user32.ShowWindow(hwnd, WINDOW_SHOW[action])

    def screenshot(self) -> bytes:
        from PIL import ImageGrab

        img = ImageGrab.grab(all_screens=True).convert("RGB")
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue()

    def lock(self) -> None:
        import ctypes

        ctypes.WinDLL("user32").LockWorkStation()

    def power(self, action: str) -> None:
        commands = {
            "shutdown": ["shutdown", "/s", "/t", "0"],
            "restart": ["shutdown", "/r", "/t", "0"],
            "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        }
        subprocess.Popen(commands[action], creationflags=NO_WINDOW)

    def trash(self, path: Path) -> None:
        from send2trash import send2trash

        send2trash(str(path))
