import base64
import ctypes
from ctypes import wintypes

from . import store

KEY = "gemini_api_key"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_crypt32.CryptProtectData.argtypes = [ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
_crypt32.CryptProtectData.restype = wintypes.BOOL
_crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
_crypt32.CryptUnprotectData.restype = wintypes.BOOL
_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_kernel32.LocalFree.restype = ctypes.c_void_p
_UI_FORBIDDEN = 0x1


def _call(fn, data: bytes) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    inp = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    if not fn(ctypes.byref(inp), None, None, None, None, _UI_FORBIDDEN, ctypes.byref(out)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def protect(data: bytes) -> bytes:
    return _call(_crypt32.CryptProtectData, data)


def unprotect(data: bytes) -> bytes:
    return _call(_crypt32.CryptUnprotectData, data)


def path():
    return store.home() / "secrets.json"


def save_key(key: str) -> None:
    key = key.strip()
    if not key or len(key) > 300 or any(ord(c) <= 32 for c in key):
        raise ValueError("key inválida")
    data = store.read_json(path())
    data[KEY] = base64.b64encode(protect(key.encode("utf-8"))).decode("ascii")
    store.write_json(path(), data)


def load_key() -> str | None:
    raw = store.read_json(path()).get(KEY)
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return unprotect(base64.b64decode(raw)).decode("utf-8")
    except (OSError, ValueError):
        return None


def has_key() -> bool:
    return load_key() is not None


def delete_key() -> None:
    data = store.read_json(path())
    if KEY in data:
        del data[KEY]
        store.write_json(path(), data)
