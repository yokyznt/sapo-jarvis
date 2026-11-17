import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

from .config import home_dir

log = logging.getLogger("sapo.vault")


def blob_api():
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    signature = [ctypes.POINTER(BLOB), wintypes.LPCWSTR, ctypes.POINTER(BLOB), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(BLOB)]
    crypt32.CryptProtectData.argtypes = signature
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(BLOB), ctypes.c_void_p] + signature[2:]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return ctypes, BLOB, crypt32, kernel32


def run_blob(data: bytes, protect: bool) -> bytes:
    if sys.platform != "win32":
        raise OSError("DPAPI solo existe en Windows")
    ctypes, BLOB, crypt32, kernel32 = blob_api()
    buf = ctypes.create_string_buffer(data, len(data))
    src = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = BLOB()
    flags = 0x1
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(src), "sapo", None, None, None, flags, ctypes.byref(out))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(src), None, None, None, None, flags, ctypes.byref(out))
    if not ok:
        raise OSError(f"DPAPI falló ({ctypes.get_last_error()})")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def protect(text: str) -> str:
    return base64.b64encode(run_blob(text.encode("utf-8"), True)).decode("ascii")


def unprotect(blob: str) -> str:
    return run_blob(base64.b64decode(blob), False).decode("utf-8")


def secrets_path() -> Path:
    return home_dir() / "secrets.json"


def load_json(path: Path, strict: bool = False) -> dict:
    for attempt in range(20):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except PermissionError:
            if attempt == 19:
                if strict:
                    raise
                return {}
            time.sleep(0.05)
        except (OSError, ValueError):
            if strict:
                raise
            return {}
    return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 19:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05)


class KeyStore:
    def __init__(self, name: str = "gemini_api_key", env: str = "GEMINI_API_KEY", path: Path | None = None):
        self.name = name
        self.env = env
        self.path = path or secrets_path()
        self.stamp: tuple[int, int] | None = None
        self.cached: str | None = None

    def __repr__(self) -> str:
        return f"KeyStore({self.name})"

    def get(self) -> str | None:
        from_env = os.environ.get(self.env, "").strip()
        if from_env:
            return from_env
        try:
            st = self.path.stat()
        except OSError:
            self.stamp, self.cached = None, None
            return None
        stamp = (st.st_mtime_ns, st.st_size)
        if stamp != self.stamp:
            self.stamp = stamp
            self.cached = self.read()
        return self.cached

    def read(self) -> str | None:
        try:
            blob = json.loads(self.path.read_text(encoding="utf-8-sig")).get(self.name)
            if not isinstance(blob, str) or not blob:
                return None
            return unprotect(blob).strip() or None
        except (OSError, ValueError, AttributeError) as e:
            log.warning("no pude descifrar %s en %s (%s)", self.name, self.path, type(e).__name__)
            return None
