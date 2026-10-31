import base64
import hashlib
import json
import socket
import subprocess
import threading
from pathlib import Path

import pytest
from websockets.sync.server import serve

from sapo.clips import Clipper, ObsRecorder, Output, Recorder, EncoderPicker, find_ffmpeg, trim_last
from sapo.config import ClipsConfig, static_config
from sapo.obs import GAME, SCENE, SCREEN, ObsAuthError, ObsClient, auth_string, ensure_scene, ensure_ws_server, ini_get, patch_ini, profile_ini, read_ini

FFMPEG = find_ffmpeg()
FFPROBE = find_ffmpeg("ffprobe")
needs_ffmpeg = pytest.mark.skipif(not (FFMPEG and FFPROBE), reason="sin ffmpeg/ffprobe")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def probe(path: Path) -> tuple[float, set[str]]:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)], capture_output=True, check=True).stdout
    data = json.loads(out)
    return float(data["format"]["duration"]), {s["codec_type"] for s in data["streams"]}


def make_replay(path: Path, seconds: int = 20) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-g", "30",
            "-c:a", "aac", "-shortest", str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


class FakeObs:
    def __init__(self, password: str | None, port: int | None = None, replay: Path | None = None, out_dir: Path | None = None):
        self.password = password
        self.replay = replay
        self.out_dir = out_dir
        self.scenes = ["Escena"]
        self.program = "Escena"
        self.inputs: dict[str, str] = {"Audio del escritorio": "wasapi_output_capture"}
        self.items: dict[str, list[dict]] = {"Escena": []}
        self.next_id = 1
        self.buffer = False
        self.params: dict[tuple[str, str], str] = {}
        self.log: list[str] = []
        self.saved = 0
        self.last = ""
        self.not_ready = 0
        self.available = True
        self.server = serve(self.handle, "127.0.0.1", port or 0)
        self.port = self.server.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def shutdown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)

    def handle(self, conn):
        hello = {"obsWebSocketVersion": "5.7.0", "rpcVersion": 1}
        if self.password:
            hello["authentication"] = {"challenge": "reto123", "salt": "sal456"}
        conn.send(json.dumps({"op": 0, "d": hello}))
        ident = json.loads(conn.recv())
        if ident.get("op") != 1:
            conn.close(4007, "no")
            return
        if self.password:
            secret = base64.b64encode(hashlib.sha256((self.password + "sal456").encode()).digest()).decode()
            good = base64.b64encode(hashlib.sha256((secret + "reto123").encode()).digest()).decode()
            if ident["d"].get("authentication") != good:
                conn.close(4009, "Authentication failed.")
                return
        conn.send(json.dumps({"op": 2, "d": {"negotiatedRpcVersion": 1}}))
        for raw in conn:
            msg = json.loads(raw)
            if msg.get("op") != 6:
                continue
            d = msg["d"]
            kind = d["requestType"]
            self.log.append(kind)
            ok, data, events = True, {}, []
            try:
                data, events = self.answer(kind, d.get("requestData") or {})
            except KeyError as e:
                ok, data = False, {"code": 600, "comment": f"no existe {e}"}
            except ValueError as e:
                ok, data = False, {"code": int(str(e)), "comment": "estado"}
            if ok:
                reply = {"requestType": kind, "requestId": d["requestId"], "requestStatus": {"result": True, "code": 100}, "responseData": data}
            else:
                reply = {"requestType": kind, "requestId": d["requestId"], "requestStatus": {"result": False, **data}}
            conn.send(json.dumps({"op": 7, "d": reply}))
            for name, payload in events:
                conn.send(json.dumps({"op": 5, "d": {"eventType": name, "eventIntent": 64, "eventData": payload}}))

    def item(self, scene, name):
        item = {"sourceName": name, "sceneItemId": self.next_id, "sceneItemIndex": len(self.items[scene])}
        self.next_id += 1
        self.items[scene].append(item)
        return item

    def answer(self, kind, req):
        if self.not_ready > 0 and kind != "GetVersion":
            self.not_ready -= 1
            raise ValueError("207")
        if not self.available and "ReplayBuffer" in kind:
            raise ValueError("604")
        if kind == "GetVersion":
            return {"obsVersion": "32.1.2"}, []
        if kind == "GetSceneList":
            return {"currentProgramSceneName": self.program, "scenes": [{"sceneName": s} for s in self.scenes]}, []
        if kind == "CreateScene":
            if req["sceneName"] in self.scenes:
                raise ValueError("601")
            self.scenes.append(req["sceneName"])
            self.items[req["sceneName"]] = []
            return {}, []
        if kind == "GetInputList":
            return {"inputs": [{"inputName": n, "inputKind": k} for n, k in self.inputs.items()]}, []
        if kind == "GetVideoSettings":
            return {"baseWidth": 1920, "baseHeight": 1080}, []
        if kind == "GetSceneItemList":
            return {"sceneItems": [dict(i) for i in self.items[req["sceneName"]]]}, []
        if kind == "CreateInput":
            if req["inputName"] in self.inputs:
                raise ValueError("601")
            self.inputs[req["inputName"]] = req["inputKind"]
            return {"sceneItemId": self.item(req["sceneName"], req["inputName"])["sceneItemId"]}, []
        if kind == "CreateSceneItem":
            if req["sourceName"] not in self.inputs:
                raise KeyError(req["sourceName"])
            return {"sceneItemId": self.item(req["sceneName"], req["sourceName"])["sceneItemId"]}, []
        if kind == "SetSceneItemIndex":
            items = self.items[req["sceneName"]]
            it = next(i for i in items if i["sceneItemId"] == req["sceneItemId"])
            items.remove(it)
            items.insert(req["sceneItemIndex"], it)
            for n, i in enumerate(items):
                i["sceneItemIndex"] = n
            return {}, []
        if kind in ("SetSceneItemTransform", "SetInputSettings"):
            return {}, []
        if kind == "GetInputPropertiesListPropertyItems":
            return {"propertyItems": [{"itemName": "B: 1920x1080 @ 0,-1080", "itemValue": "b"}, {"itemName": "A: 1920x1080 @ 0,0", "itemValue": "a"}]}, []
        if kind == "SetCurrentProgramScene":
            if req["sceneName"] not in self.scenes:
                raise KeyError(req["sceneName"])
            self.program = req["sceneName"]
            return {}, []
        if kind == "SetProfileParameter":
            self.params[(req["parameterCategory"], req["parameterName"])] = req["parameterValue"]
            return {}, []
        if kind == "GetReplayBufferStatus":
            return {"outputActive": self.buffer}, []
        if kind == "StartReplayBuffer":
            if self.buffer:
                raise ValueError("500")
            self.buffer = True
            return {}, [("ReplayBufferStateChanged", {"outputActive": True, "outputState": "OBS_WEBSOCKET_OUTPUT_STARTED"})]
        if kind == "StopReplayBuffer":
            if not self.buffer:
                raise ValueError("501")
            self.buffer = False
            return {}, [("ReplayBufferStateChanged", {"outputActive": False, "outputState": "OBS_WEBSOCKET_OUTPUT_STOPPED"})]
        if kind == "SaveReplayBuffer":
            if not self.buffer:
                raise ValueError("501")
            self.saved += 1
            dst = self.out_dir / f"Replay {self.saved}{self.replay.suffix}"
            dst.write_bytes(self.replay.read_bytes())
            self.last = str(dst)
            return {}, [("ReplayBufferSaved", {"savedReplayPath": self.last})]
        if kind == "GetLastReplayBufferReplay":
            return {"savedReplayPath": self.last}, []
        raise ValueError("204")


def test_auth_string_matches_spec():
    secret = base64.b64encode(hashlib.sha256(b"supersecretpasswordsalt").digest()).decode()
    expected = base64.b64encode(hashlib.sha256((secret + "challenge").encode()).digest()).decode()
    assert auth_string("supersecretpassword", "salt", "challenge") == expected


def test_client_auth_good_and_bad():
    obs = FakeObs("secreto")
    try:
        c = ObsClient(obs.port, "secreto").connect()
        assert c.alive and c.version == "5.7.0"
        assert c.request("GetVersion")["obsVersion"] == "32.1.2"
        c.close()
        with pytest.raises(ObsAuthError):
            ObsClient(obs.port, "mala").connect()
        with pytest.raises(ObsAuthError):
            ObsClient(obs.port, None).connect()
    finally:
        obs.shutdown()


def test_scene_creation_is_idempotent():
    obs = FakeObs(None)
    try:
        c = ObsClient(obs.port).connect()
        assert ensure_scene(c) is True
        assert ensure_scene(c) is False
        c.close()
        assert obs.scenes == ["Escena", SCENE]
        assert obs.program == "Escena"
        assert obs.items["Escena"] == []
        assert [i["sourceName"] for i in obs.items[SCENE]] == [SCREEN, GAME]
        assert obs.inputs[GAME] == "game_capture" and obs.inputs[SCREEN] == "monitor_capture"
        assert obs.log.count("CreateInput") == 2 and obs.log.count("CreateScene") == 1
        del obs.items[SCENE][1]
        c = ObsClient(obs.port).connect()
        assert ensure_scene(c) is True
        c.close()
        assert [i["sourceName"] for i in obs.items[SCENE]] == [SCREEN, GAME]
        assert obs.log.count("CreateSceneItem") == 1 and obs.log.count("CreateInput") == 2
    finally:
        obs.shutdown()


def test_ensure_ws_server_keeps_keys_and_backs_up(tmp_path):
    path = tmp_path / "plugin_config" / "obs-websocket" / "config.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"alerts_enabled": False, "auth_required": True, "first_load": False, "server_enabled": False, "server_password": "", "server_port": 4460, "futuro": 7}), encoding="utf-8")
    port, password = ensure_ws_server(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert port == 4460 and password and len(password) >= 16
    assert data["server_enabled"] is True and data["server_password"] == password and data["futuro"] == 7 and data["auth_required"] is True
    assert json.loads((path.parent / "config.json.sapo-backup").read_text(encoding="utf-8"))["server_enabled"] is False
    stamp = path.stat().st_mtime_ns
    assert ensure_ws_server(path) == (4460, password)
    assert path.stat().st_mtime_ns == stamp
    fresh = tmp_path / "otro" / "config.json"
    port, password = ensure_ws_server(fresh)
    assert port == 4455 and password and json.loads(fresh.read_text(encoding="utf-8"))["server_enabled"] is True


def write_profile(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    (base / "user.ini").write_bytes(b"\xef\xbb\xbf[General]\nFirstRun=true\n\n[Basic]\nProfile=kick\nProfileDir=kick\n")
    ini = base / "basic" / "profiles" / "kick" / "basic.ini"
    ini.parent.mkdir(parents=True)
    ini.write_bytes(b"\xef\xbb\xbf[General]\nName=kick\n\n[SimpleOutput]\nFilePath=C:\\\\Users\\\\x\\\\Videos\nRecRB=false\nRecRBTime=20\n\n[AdvOut]\nRecRB=false\n\n[Video]\nBaseCX=1920\n")
    return ini


def test_profile_patch_and_restore(tmp_path):
    ini = write_profile(tmp_path)
    assert profile_ini(tmp_path) == ini
    before = ini.read_bytes()
    old = patch_ini(ini, {("SimpleOutput", "RecRB"): "true", ("SimpleOutput", "RecRBTime"): "30", ("AdvOut", "RecRBTime"): "30", ("Nueva", "X"): "1"})
    lines, bom = read_ini(ini)
    assert bom and ini_get(lines, "SimpleOutput", "RecRB") == "true" and ini_get(lines, "AdvOut", "RecRBTime") == "30" and ini_get(lines, "Video", "BaseCX") == "1920"
    assert ini_get(lines, "SimpleOutput", "FilePath") == "C:\\\\Users\\\\x\\\\Videos"
    patch_ini(ini, old)
    assert ini.read_bytes().rstrip(b"\n") == before.rstrip(b"\n")


class FakeProc:
    def __init__(self, on_exit=None):
        self.pid = 4242
        self.code = None
        self.on_exit = on_exit

    def poll(self):
        return self.code

    def exit(self):
        if self.code is None:
            self.code = 0
            if self.on_exit:
                self.on_exit()

    def wait(self, timeout=None):
        if self.code is None:
            raise subprocess.TimeoutExpired("obs", timeout)
        return self.code

    def kill(self):
        self.exit()


def obs_base(tmp_path: Path, port: int, enabled: bool = False, password: str = "") -> Path:
    base = tmp_path / "obs-studio"
    ini = write_profile(base)
    cfg = base / "plugin_config" / "obs-websocket" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"alerts_enabled": False, "auth_required": True, "first_load": False, "server_enabled": enabled, "server_password": password, "server_port": port}), encoding="utf-8")
    return base


@needs_ffmpeg
def test_obs_recorder_launch_save_and_close(tmp_path):
    port = free_port()
    base = obs_base(tmp_path, port)
    replay = make_replay(tmp_path / "src" / "replay.mp4")
    out_dir = tmp_path / "Videos"
    out_dir.mkdir()
    exe = tmp_path / "bin" / "64bit" / "obs64.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    state = {}

    def popen(cmd, **kw):
        cfg = json.loads((base / "plugin_config" / "obs-websocket" / "config.json").read_text(encoding="utf-8"))
        assert cfg["server_enabled"] is True and cfg["server_password"]
        lines, _ = read_ini(base / "basic" / "profiles" / "kick" / "basic.ini")
        assert ini_get(lines, "SimpleOutput", "RecRB") == "true" and ini_get(lines, "SimpleOutput", "RecRBTime") == "30"
        obs = FakeObs(cfg["server_password"], port, replay, out_dir)
        obs.buffer = "--startreplaybuffer" in cmd
        state.update(obs=obs, cmd=cmd, kw=kw)
        proc = FakeProc(obs.shutdown)
        state["proc"] = proc
        return proc

    closed = []
    rec = ObsRecorder(FFMPEG, exe, base=base, popen=popen, pids=lambda: [], closer=lambda pid: closed.append(pid) or state["proc"].exit(), pause=0.05)
    conf = ClipsConfig(enabled=True, method="obs", seconds=10, buffer=30)
    assert rec.start(conf) == "obs"
    obs = state["obs"]
    assert state["kw"]["cwd"] == str(exe.parent)
    assert "--minimize-to-tray" in state["cmd"] and "--disable-shutdown-check" in state["cmd"]
    assert obs.program == SCENE and obs.buffer
    assert obs.params[("SimpleOutput", "RecRBTime")] == "30" and obs.params[("AdvOut", "RecRBTime")] == "30"
    assert "StartReplayBuffer" not in obs.log
    assert rec.running
    out, length = rec.clip(10, tmp_path / "clips" / "Sapo_2026-10-30_12-00-00.mp4")
    duration, kinds = probe(out)
    assert out.name == "Sapo_2026-10-30_12-00-00.mp4"
    assert kinds == {"video", "audio"} and 9.5 <= duration <= 11.5 and abs(length - duration) < 0.2
    assert not list(out_dir.iterdir())
    rec.start(ClipsConfig(enabled=True, method="obs", seconds=10, buffer=60))
    assert obs.log.count("StopReplayBuffer") == 1 and obs.log.count("StartReplayBuffer") == 1 and obs.buffer
    assert obs.params[("SimpleOutput", "RecRBTime")] == "60"
    rec.stop()
    assert obs.program == "Escena"
    assert closed == [4242] and state["proc"].poll() == 0
    assert obs.log.count("StopReplayBuffer") == 2
    lines, _ = read_ini(base / "basic" / "profiles" / "kick" / "basic.ini")
    assert ini_get(lines, "SimpleOutput", "RecRB") == "false" and ini_get(lines, "SimpleOutput", "RecRBTime") == "20" and ini_get(lines, "AdvOut", "RecRBTime") is None
    assert not rec.running


@needs_ffmpeg
def test_obs_already_running_is_left_open(tmp_path):
    replay = make_replay(tmp_path / "src" / "replay.mkv", 15)
    out_dir = tmp_path / "Videos"
    out_dir.mkdir()
    obs = FakeObs("clave", None, replay, out_dir)
    try:
        base = obs_base(tmp_path, obs.port, enabled=True, password="clave")
        launched, closed = [], []
        rec = ObsRecorder(FFMPEG, tmp_path / "obs64.exe", base=base, popen=lambda *a, **k: launched.append(a), pids=lambda: [999], closer=closed.append, pause=0.05)
        rec.start(ClipsConfig(enabled=True, method="obs", seconds=8, buffer=30))
        assert launched == [] and obs.program == "Escena" and SCENE in obs.scenes and obs.buffer
        out, _ = rec.clip(8, tmp_path / "clips" / "Sapo_x.mp4")
        duration, kinds = probe(out)
        assert out.suffix == ".mp4" and kinds == {"video", "audio"} and 7.5 <= duration <= 9.5
        rec.stop()
        assert closed == [] and not obs.buffer and "StopReplayBuffer" in obs.log
        lines, _ = read_ini(base / "basic" / "profiles" / "kick" / "basic.ini")
        assert ini_get(lines, "SimpleOutput", "RecRB") == "false"
    finally:
        obs.shutdown()


def test_obs_running_with_server_off_is_reported(tmp_path):
    base = obs_base(tmp_path, free_port(), enabled=False)
    rec = ObsRecorder(None, tmp_path / "obs64.exe", base=base, popen=lambda *a, **k: pytest.fail("no debe abrir OBS"), pids=lambda: [5], pause=0.01)
    with pytest.raises(Exception, match="WebSocket"):
        rec.start(ClipsConfig(enabled=True, method="obs"))
    assert json.loads((base / "plugin_config" / "obs-websocket" / "config.json").read_text(encoding="utf-8"))["server_enabled"] is False


@needs_ffmpeg
def test_trim_falls_back_to_whole_copy(tmp_path):
    src = make_replay(tmp_path / "r.mkv", 6)
    out = trim_last(str(tmp_path / "no-hay-ffmpeg.exe"), src, tmp_path / "c" / "Sapo_a.mp4", 3)
    assert out.suffix == ".mkv" and out.read_bytes() == src.read_bytes()
    out = trim_last(FFMPEG, src, tmp_path / "c" / "Sapo_b.mp4", 3)
    duration, kinds = probe(out)
    assert out.suffix == ".mp4" and 2.5 <= duration <= 4.5 and kinds == {"video", "audio"}


class FakeBackend:
    def __init__(self, name, events):
        self.name = name
        self.events = events
        self.running = False
        self.fail = False

    def start(self, conf, clean=True):
        self.events.append((self.name, "start", clean))
        if self.fail:
            raise RuntimeError("no")
        self.running = True

    def stop(self, clean=True):
        self.events.append((self.name, "stop"))
        self.running = False


def test_clipper_switches_between_native_and_obs():
    events = []
    conf = static_config()
    native, obs = FakeBackend("native", events), FakeBackend("obs", events)
    c = Clipper(conf, native, videos=lambda: Path("."), keys=lambda k: None, obs=obs)
    conf.clips = ClipsConfig(enabled=True, method="native")
    assert c.apply() == "started"
    conf.clips = ClipsConfig(enabled=True, method="obs")
    assert c.apply() == "started"
    assert c.apply() is None
    conf.clips = ClipsConfig(enabled=False, method="obs")
    assert c.apply() == "stopped"
    assert events == [("native", "start", True), ("native", "stop"), ("obs", "start", True), ("obs", "stop")]
    assert ClipsConfig().method == "native"


def test_native_restart_with_backoff_keeps_buffer():
    events = []
    conf = static_config()
    conf.clips = ClipsConfig(enabled=True, method="native")
    now = [100.0]
    rec = FakeBackend("native", events)
    c = Clipper(conf, rec, videos=lambda: Path("."), keys=lambda k: None, clock=lambda: now[0])
    assert c.apply() == "started"
    rec.running = False
    now[0] += 0.5
    assert c.apply() is None
    now[0] += 1.0
    assert c.apply() == "restarted"
    assert events[-1] == ("native", "start", False)
    rec.running = False
    rec.fail = True
    now[0] += 1.0
    assert c.apply() is None
    now[0] += 1.5
    assert c.apply() == "failed"
    now[0] += 2.0
    assert c.apply() is None
    rec.fail = False
    now[0] += 3.0
    assert c.apply() == "restarted"
    assert [e for e in events if e[1] == "start"] == [("native", "start", True), ("native", "start", False), ("native", "start", False), ("native", "start", False)]


class AliveProc:
    def __init__(self):
        self.alive = True
        self.stdin = None
        self.stderr = None

    def poll(self):
        return None if self.alive else 1

    def wait(self, timeout=None):
        if self.alive:
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        return 1

    def kill(self):
        self.alive = False


def test_recorder_restart_does_not_clear_segments(tmp_path):
    cmds = []

    def popen(cmd, **kw):
        cmds.append(cmd)
        return AliveProc()

    rec = Recorder("ffmpeg", tmp_path, popen=popen, outputs=lambda: [Output(0, "a", 0, 0, 1920, 1080)], picker=EncoderPicker(lambda f, e: True), audio_factory=None, settle=0.01)
    conf = ClipsConfig(enabled=True, method="native", buffer=10)
    rec.start(conf)
    for i in range(3):
        (tmp_path / f"seg{i:03d}.ts").write_bytes(b"x")
    rec.proc.alive = False
    rec.start(conf, clean=False)
    assert len(list(tmp_path.glob("seg*.ts"))) == 3
    assert cmds[-1][-1].endswith("seg01_%03d.ts") and cmds[0][-1].endswith("seg%03d.ts")
    rec.start(conf)
    assert not list(tmp_path.glob("seg*.ts"))
    rec.stop()


def test_obs_waits_until_ready_and_reports_missing_replay_buffer(tmp_path):
    obs = FakeObs(None)
    obs.not_ready = 3
    obs.available = False
    try:
        base = obs_base(tmp_path, obs.port, enabled=True)
        cfg = base / "plugin_config" / "obs-websocket" / "config.json"
        cfg.write_text(json.dumps({"server_enabled": True, "auth_required": False, "server_port": obs.port}), encoding="utf-8")
        rec = ObsRecorder(None, tmp_path / "obs64.exe", base=base, pids=lambda: [1], closer=lambda pid: pytest.fail("no debe cerrar"), pause=0.01)
        with pytest.raises(Exception, match="Búfer de repetición"):
            rec.start(ClipsConfig(enabled=True, method="obs"))
        assert obs.log[:3] == ["GetSceneList"] * 3 and SCENE in obs.scenes
        assert obs.params[("SimpleOutput", "RecRB")] == "true"
        obs.available = True
        rec.start(ClipsConfig(enabled=True, method="obs"))
        assert obs.buffer and rec.running
        rec.stop()
        assert not obs.buffer
    finally:
        obs.shutdown()
