import base64
import collections
import hashlib
import json
import logging
import os
import secrets
import shutil
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("sapo.obs")

SCENE = "Sapo Clips"
GAME = "Sapo Juego"
SCREEN = "Sapo Pantalla"
OUTPUTS_EVENTS = 1 << 6
DEFAULT_PORT = 4455


class ObsError(Exception):
    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code


class ObsAuthError(ObsError):
    pass


def find_obs() -> Path | None:
    override = os.environ.get("SAPO_OBS")
    if override is not None:
        return Path(override) if override and Path(override).is_file() else None
    roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), "C:/Program Files", os.environ.get("ProgramFiles(x86)")]
    for root in roots:
        if root:
            exe = Path(root) / "obs-studio" / "bin" / "64bit" / "obs64.exe"
            if exe.is_file():
                return exe
    return None


def config_dir() -> Path:
    override = os.environ.get("SAPO_OBS_CONFIG")
    if override:
        return Path(override)
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming") / "obs-studio"


def ws_config_path(base: Path | None = None) -> Path:
    return (base or config_dir()) / "plugin_config" / "obs-websocket" / "config.json"


def read_ws_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def ws_settings(data: dict[str, Any]) -> tuple[bool, int, str | None]:
    port = data.get("server_port")
    port = port if isinstance(port, int) and not isinstance(port, bool) and 0 < port < 65536 else DEFAULT_PORT
    password = data.get("server_password") if data.get("auth_required", True) else None
    return bool(data.get("server_enabled")), port, password if isinstance(password, str) and password else None


def ensure_ws_server(path: Path) -> tuple[int, str | None]:
    data = read_ws_config(path)
    enabled, port, password = ws_settings(data)
    needs_password = data.get("auth_required", True) is not False and not password
    if enabled and not needs_password:
        return port, password
    if path.is_file():
        backup = path.with_name("config.json.sapo-backup")
        if not backup.exists():
            shutil.copy2(path, backup)
    data["server_enabled"] = True
    data.setdefault("server_port", port)
    if needs_password:
        data["auth_required"] = True
        data["server_password"] = secrets.token_urlsafe(18)
    data.setdefault("first_load", False)
    data.setdefault("alerts_enabled", False)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    log.info("activé el servidor WebSocket de OBS en el puerto %s", port)
    _, port, password = ws_settings(data)
    return port, password


def auth_string(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(hashlib.sha256((password + salt).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()


def read_ini(path: Path) -> tuple[list[str], bool]:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig", "replace").splitlines(), bom


def write_ini(path: Path, lines: list[str], bom: bool) -> None:
    tmp = path.with_name(path.name + ".sapo.tmp")
    tmp.write_bytes((b"\xef\xbb\xbf" if bom else b"") + ("\n".join(lines) + "\n").encode("utf-8"))
    os.replace(tmp, path)


def ini_get(lines: list[str], section: str, key: str) -> str | None:
    current = None
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            current = s[1:-1]
        elif current == section and "=" in s and s.split("=", 1)[0].strip() == key:
            return s.split("=", 1)[1]
    return None


def ini_set(lines: list[str], section: str, key: str, value: str | None) -> list[str]:
    out = list(lines)
    start = None
    end = len(out)
    for i, line in enumerate(out):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if start is not None:
                end = i
                break
            if s[1:-1] == section:
                start = i
    if start is None:
        if value is None:
            return out
        while out and not out[-1].strip():
            out.pop()
        if out:
            out.append("")
        return out + [f"[{section}]", f"{key}={value}"]
    for i in range(start + 1, end):
        s = out[i].strip()
        if "=" in s and s.split("=", 1)[0].strip() == key:
            if value is None:
                del out[i]
                if not any(line.strip() for line in out[start + 1 : end - 1]):
                    lo = start - 1 if start > 0 and not out[start - 1].strip() else start
                    del out[lo : end - 1]
            else:
                out[i] = f"{key}={value}"
            return out
    if value is None:
        return out
    insert = end
    while insert > start + 1 and not out[insert - 1].strip():
        insert -= 1
    out.insert(insert, f"{key}={value}")
    return out


def profile_ini(base: Path | None = None) -> Path | None:
    base = base or config_dir()
    profile = None
    for name in ("user.ini", "global.ini"):
        path = base / name
        if path.is_file():
            lines, _ = read_ini(path)
            profile = ini_get(lines, "Basic", "ProfileDir")
            if profile:
                break
    root = base / "basic" / "profiles"
    if profile and (root / profile / "basic.ini").is_file():
        return root / profile / "basic.ini"
    found = sorted(root.glob("*/basic.ini")) if root.is_dir() else []
    return found[0] if found else None


def patch_ini(path: Path, values: dict[tuple[str, str], str | None]) -> dict[tuple[str, str], str | None]:
    lines, bom = read_ini(path)
    old = {k: ini_get(lines, *k) for k in values}
    for (section, key), value in values.items():
        lines = ini_set(lines, section, key, value)
    write_ini(path, lines, bom)
    return old


def replay_values(seconds: int) -> dict[tuple[str, str], str | None]:
    return {
        ("SimpleOutput", "RecRB"): "true",
        ("SimpleOutput", "RecRBTime"): str(int(seconds)),
        ("AdvOut", "RecRB"): "true",
        ("AdvOut", "RecRBTime"): str(int(seconds)),
    }


def clear_sentinels(base: Path, since: float = 0.0) -> int:
    folder = base / ".sentinel"
    removed = 0
    for p in folder.glob("run_*") if folder.is_dir() else []:
        try:
            if p.stat().st_mtime >= since:
                p.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def obs_pids(exe_name: str = "obs64.exe") -> list[int]:
    try:
        import psutil
    except ImportError:
        return []
    found = []
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info.get("name") or "").lower() == exe_name.lower():
                found.append(p.pid)
        except Exception:
            continue
    return found


def close_windows(pid: int) -> int:
    if os.name != "nt":
        return 0
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [proc, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    hits: list[int] = []

    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            name = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, name, 128)
            if name.value.startswith("Qt") and "QWindowIcon" in name.value:
                hits.append(hwnd)
        return True

    user32.EnumWindows(proc(visit), 0)
    for hwnd in hits:
        user32.PostMessageW(hwnd, 0x0010, 0, 0)
    return len(hits)


class ObsClient:
    def __init__(self, port: int = DEFAULT_PORT, password: str | None = None, host: str = "127.0.0.1", timeout: float = 5.0):
        self.url = f"ws://{host}:{port}"
        self.password = password
        self.timeout = timeout
        self.ws: Any = None
        self.reader: threading.Thread | None = None
        self.pending: dict[str, dict[str, Any]] = {}
        self.cond = threading.Condition()
        self.events: collections.deque[tuple[int, str, dict[str, Any]]] = collections.deque(maxlen=200)
        self.seq = 0
        self.counter = 0
        self.closed = True
        self.version = ""

    @property
    def alive(self) -> bool:
        return not self.closed

    def connect(self) -> "ObsClient":
        from websockets.exceptions import ConnectionClosed
        from websockets.sync.client import connect

        try:
            ws = connect(self.url, open_timeout=self.timeout, close_timeout=2, max_size=None, legacy=True)
        except (OSError, TimeoutError) as e:
            raise ObsError(f"no pude conectar a OBS en {self.url}: {e!r}") from e
        except Exception as e:
            raise ObsError(f"no pude conectar a OBS en {self.url}: {e!r}") from e
        try:
            hello = json.loads(ws.recv(timeout=self.timeout))
            if hello.get("op") != 0:
                raise ObsError("OBS no mandó Hello")
            data = hello.get("d") or {}
            self.version = str(data.get("obsWebSocketVersion") or "")
            identify: dict[str, Any] = {"rpcVersion": 1, "eventSubscriptions": OUTPUTS_EVENTS}
            challenge = data.get("authentication")
            if challenge:
                if not self.password:
                    raise ObsAuthError("OBS pide contraseña y no tengo")
                identify["authentication"] = auth_string(self.password, challenge["salt"], challenge["challenge"])
            ws.send(json.dumps({"op": 1, "d": identify}))
            try:
                reply = json.loads(ws.recv(timeout=self.timeout))
            except ConnectionClosed as e:
                code = e.rcvd.code if e.rcvd else 0
                if code == 4009:
                    raise ObsAuthError("contraseña de OBS incorrecta", code) from e
                raise ObsError(f"OBS cerró la conexión ({code})", code) from e
            if reply.get("op") != 2:
                raise ObsError("OBS no confirmó la identificación")
        except BaseException:
            ws.close()
            raise
        self.ws = ws
        self.closed = False
        self.reader = threading.Thread(target=self.read, name="sapo-obs-ws", daemon=True)
        self.reader.start()
        return self

    def read(self) -> None:
        try:
            for raw in self.ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                op, d = msg.get("op"), msg.get("d") or {}
                with self.cond:
                    if op == 7:
                        rid = d.get("requestId")
                        if rid in self.pending:
                            self.pending[rid] = d
                    elif op == 5:
                        self.seq += 1
                        self.events.append((self.seq, str(d.get("eventType")), d.get("eventData") or {}))
                    self.cond.notify_all()
        except Exception:
            pass
        finally:
            with self.cond:
                self.closed = True
                self.cond.notify_all()

    def request(self, kind: str, data: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
        if self.closed:
            raise ObsError("sin conexión con OBS")
        with self.cond:
            self.counter += 1
            rid = f"sapo-{self.counter}"
            self.pending[rid] = {}
        payload: dict[str, Any] = {"requestType": kind, "requestId": rid}
        if data is not None:
            payload["requestData"] = data
        try:
            self.ws.send(json.dumps({"op": 6, "d": payload}))
        except Exception as e:
            with self.cond:
                self.pending.pop(rid, None)
            raise ObsError(f"no pude mandar {kind} a OBS: {e!r}") from e
        deadline = time.monotonic() + timeout
        with self.cond:
            while not self.pending.get(rid) and not self.closed:
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                self.cond.wait(left)
            reply = self.pending.pop(rid, {})
        if not reply:
            raise ObsError(f"OBS no respondió a {kind}")
        status = reply.get("requestStatus") or {}
        if not status.get("result"):
            raise ObsError(f"{kind}: {status.get('comment') or 'falló'}", int(status.get("code") or 0))
        return reply.get("responseData") or {}

    def mark(self) -> int:
        with self.cond:
            return self.seq

    def wait_event(self, kind: str, after: int, timeout: float) -> dict[str, Any] | None:
        deadline = time.monotonic() + timeout
        with self.cond:
            while True:
                for seq, name, data in self.events:
                    if seq > after and name == kind:
                        return data
                left = deadline - time.monotonic()
                if left <= 0 or self.closed:
                    return None
                self.cond.wait(left)

    def close(self) -> None:
        ws, self.ws = self.ws, None
        self.closed = True
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass


def ensure_scene(client: ObsClient, primary_hint: str = "0,0") -> bool:
    created = False
    scenes = {s.get("sceneName") for s in client.request("GetSceneList").get("scenes", [])}
    if SCENE not in scenes:
        client.request("CreateScene", {"sceneName": SCENE})
        created = True
    inputs = {i.get("inputName") for i in client.request("GetInputList").get("inputs", [])}
    video = client.request("GetVideoSettings")
    width, height = video.get("baseWidth") or 1920, video.get("baseHeight") or 1080
    wanted = ((SCREEN, "monitor_capture", {}), (GAME, "game_capture", {"capture_mode": "any_fullscreen", "capture_cursor": True}))
    for name, kind, settings in wanted:
        items = {i.get("sourceName"): i for i in client.request("GetSceneItemList", {"sceneName": SCENE}).get("sceneItems", [])}
        if name in items:
            continue
        if name in inputs:
            item = client.request("CreateSceneItem", {"sceneName": SCENE, "sourceName": name}).get("sceneItemId")
        else:
            item = client.request("CreateInput", {"sceneName": SCENE, "inputName": name, "inputKind": kind, "inputSettings": settings, "sceneItemEnabled": True}).get("sceneItemId")
            if kind == "monitor_capture":
                pick_primary(client, name, primary_hint)
        created = True
        if item is not None:
            try:
                client.request("SetSceneItemTransform", {"sceneName": SCENE, "sceneItemId": item, "sceneItemTransform": {"boundsType": "OBS_BOUNDS_SCALE_INNER", "boundsWidth": float(width), "boundsHeight": float(height), "positionX": 0.0, "positionY": 0.0, "alignment": 5, "boundsAlignment": 0}})
            except ObsError as e:
                log.info("no pude ajustar %s al lienzo: %s", name, e)
    items = client.request("GetSceneItemList", {"sceneName": SCENE}).get("sceneItems", [])
    index = {i.get("sourceName"): i for i in items}
    if GAME in index and SCREEN in index and index[GAME].get("sceneItemIndex", 0) < index[SCREEN].get("sceneItemIndex", 0):
        client.request("SetSceneItemIndex", {"sceneName": SCENE, "sceneItemId": index[GAME]["sceneItemId"], "sceneItemIndex": len(items) - 1})
    return created


def pick_primary(client: ObsClient, name: str, hint: str) -> None:
    for prop in ("monitor_id", "monitor"):
        try:
            items = client.request("GetInputPropertiesListPropertyItems", {"inputName": name, "propertyName": prop}).get("propertyItems", [])
        except ObsError:
            continue
        chosen = None
        for item in items:
            label = str(item.get("itemName") or "")
            if f"@ {hint}" in label or "primar" in label.lower() or "principal" in label.lower():
                chosen = item
                break
        if chosen is not None:
            client.request("SetInputSettings", {"inputName": name, "inputSettings": {prop: chosen.get("itemValue")}})
            return
