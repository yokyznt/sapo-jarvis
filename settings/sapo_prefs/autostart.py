import os
import shlex
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "Sapo"


def get(key: str = RUN_KEY, name: str = NAME) -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            value, _ = winreg.QueryValueEx(k, name)
            return str(value)
    except OSError:
        return None


def set(command: str, key: str = RUN_KEY, name: str = NAME) -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, command)


def remove(key: str = RUN_KEY, name: str = NAME) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
    except FileNotFoundError:
        pass


def program(command: str) -> Path | None:
    command = command.strip()
    if not command:
        return None
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        return None
    return Path(parts[0].strip('"')) if parts else None


def command_ok(command: str) -> bool:
    exe = program(command)
    return exe is not None and exe.is_file()


def find_sapo_exe() -> Path | None:
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
    candidates = []
    if base:
        candidates += [base / "Sapo.exe", base.parent / "Sapo.exe", base.parent / "Sapo" / "Sapo.exe"]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Sapo" / "Sapo.exe")
    return next((c for c in candidates if c.is_file()), None)


def default_command() -> str:
    exe = find_sapo_exe()
    return f'"{exe}"' if exe else ""
