import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np
import pytest

from sapo.clips import (
    GAMEBAR,
    AudioRing,
    ClipResult,
    Clipper,
    EncoderPicker,
    Output,
    Recorder,
    assemble,
    find_ffmpeg,
    parse_hotkey,
    pick_output,
    select,
    timeline,
    trim,
    video_command,
    wrap_for,
    write_wav,
)
from sapo.config import ClipsConfig, LiveConfig, static_config

FFMPEG = find_ffmpeg()
FFPROBE = find_ffmpeg("ffprobe")
needs_ffmpeg = pytest.mark.skipif(not (FFMPEG and FFPROBE), reason="sin ffmpeg/ffprobe")


def probe(path: Path) -> tuple[float, set[str]]:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)],
        capture_output=True,
        check=True,
    ).stdout
    data = json.loads(out)
    return float(data["format"]["duration"]), {s["codec_type"] for s in data["streams"]}


def make_segments(folder: Path, seconds: int, start: float) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30",
            "-t", str(seconds),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-g", "60", "-force_key_frames", "expr:gte(t,n_forced*2)",
            "-f", "segment", "-segment_time", "2", "-segment_format", "mpegts", "-reset_timestamps", "1",
            str(folder / "seg%03d.ts"),
        ],
        check=True,
        capture_output=True,
    )
    files = sorted(folder.glob("seg*.ts"))
    for i, p in enumerate(files):
        t = start + 2 * (i + 1)
        os.utime(p, (t, t))
    return files


def sine(seconds: float, rate: int = 48000) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate
    tone = (np.sin(2 * np.pi * 440 * t) * 0.3 * 32767).astype(np.int16)
    return np.stack([tone, tone], axis=1)


class AliveProc:
    def __init__(self, alive=True, code=1):
        self.alive = alive
        self.code = code
        self.stdin = None
        self.stderr = None

    def poll(self):
        return None if self.alive else self.code

    def wait(self, timeout=None):
        if self.alive:
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        return self.code

    def kill(self):
        self.alive = False


@needs_ffmpeg
def test_assemble_segments_with_audio(tmp_path):
    files = make_segments(tmp_path / "buf", 12, time.time() - 20)
    assert len(files) == 6
    wav = tmp_path / "a.wav"
    write_wav(wav, sine(6.0))
    out = assemble(FFMPEG, files[-3:], tmp_path / "clips" / "Sapo_test.mp4", wav)
    duration, kinds = probe(out)
    assert kinds == {"video", "audio"}
    assert 5.5 <= duration <= 6.5
    assert not list((tmp_path / "clips").glob("*.tmp.mp4"))
    assert not list((tmp_path / "clips").glob("*.txt"))


@needs_ffmpeg
def test_recorder_clip_takes_last_seconds(tmp_path):
    now = time.time()
    folder = tmp_path / "clipbuf"
    make_segments(folder, 20, now - 20)
    rec = Recorder(FFMPEG, folder, audio_factory=None)
    rec.proc = AliveProc()
    rec.conf = ClipsConfig(enabled=True, buffer=120)
    ring = AudioRing(30)
    ring.push(sine(20.0), now)
    rec.audio = ring
    out, length = rec.clip(10, tmp_path / "out" / "Sapo_x.mp4")
    duration, kinds = probe(out)
    assert kinds == {"video", "audio"}
    assert 10 <= length < 12.5
    assert 9.5 <= duration <= 12.5
    assert not (folder / "work").exists()
    assert len(list(folder.glob("seg*.ts"))) == 10


def test_select_covers_requested_seconds(tmp_path):
    folder = tmp_path / "b"
    folder.mkdir()
    base = 1000.0
    for i in range(8):
        p = folder / f"seg{i:03d}.ts"
        p.write_bytes(b"x")
        os.utime(p, (base + 2 * (i + 1), base + 2 * (i + 1)))
    segs = timeline(folder, base + 16.5, live=True)
    assert len(segs) == 8
    assert segs[-1].end == base + 16.5
    chosen = select(segs, 5)
    assert [s.path.name for s in chosen] == ["seg005.ts", "seg006.ts", "seg007.ts"]
    assert sum(s.duration for s in chosen) >= 5


def test_buffer_never_grows(tmp_path):
    assert wrap_for(120) == 62
    cmd = video_command("ffmpeg", "h264_nvenc", 30, 1, tmp_path, 120)
    assert cmd[cmd.index("-segment_wrap") + 1] == "62"
    assert cmd[cmd.index("-segment_time") + 1] == "2"
    assert "ddagrab=output_idx=1:framerate=30:draw_mouse=1" in cmd
    for i in range(80):
        p = tmp_path / f"seg{i:03d}.ts"
        p.write_bytes(b"x")
        os.utime(p, (1000 + i, 1000 + i))
    assert trim(tmp_path, 62) == 18
    left = sorted(tmp_path.glob("seg*.ts"))
    assert len(left) == 62 and left[0].name == "seg018.ts"
    ring = AudioRing(10, rate=1000)
    size = ring.data.nbytes
    t = 0.0
    for _ in range(400):
        t += 0.1
        ring.push(np.full((100, 2), 0.5, np.float32), t)
    assert ring.data.nbytes == size
    assert ring.total == 40000
    tail = ring.window(t - 2, t)
    assert tail.shape == (2000, 2) and int(tail.min()) > 16000
    old = ring.window(t - 100, t - 90)
    assert not old.any()


def test_audio_window_alignment():
    ring = AudioRing(10, rate=100, channels=1)
    ring.push(np.arange(500, dtype=np.int16)[:, None], 105.0)
    got = ring.window(102.0, 104.0)[:, 0]
    assert list(got[:3]) == [200, 201, 202]
    assert len(got) == 200
    future = ring.window(104.5, 105.5)[:, 0]
    assert future[49] == 499 and not future[50:].any()


def test_encoder_fallback():
    tried = []

    def works(ffmpeg, enc):
        tried.append(enc)
        return enc == "h264_qsv"

    picker = EncoderPicker(works)
    assert picker.pick("ffmpeg") == "h264_qsv"
    assert picker.candidates("ffmpeg") == ["h264_qsv", "libx264"]
    assert tried.count("h264_nvenc") == 1
    assert EncoderPicker(lambda f, e: False).pick("ffmpeg") == "libx264"
    assert EncoderPicker(lambda f, e: True).pick("ffmpeg", "h264_amf") == "h264_amf"
    assert EncoderPicker(lambda f, e: True).pick("ffmpeg") == "h264_nvenc"


def test_recorder_start_falls_back_when_encoder_dies(tmp_path):
    calls = []

    def popen(cmd, **kw):
        calls.append((cmd, kw))
        return AliveProc(alive=len(calls) > 1)

    rec = Recorder("ffmpeg", tmp_path, popen=popen, outputs=lambda: [Output(0, "a", 0, 0, 1920, 1080), Output(1, "b", 0, -1080, 1920, 0)], picker=EncoderPicker(lambda f, e: True), audio_factory=None, settle=0.01)
    assert rec.start(ClipsConfig(enabled=True, monitor="1")) == "h264_amf"
    assert rec.running
    first, kw = calls[0]
    assert "h264_nvenc" in first and "ddagrab=output_idx=1:framerate=30:draw_mouse=1" in first
    if os.name == "nt":
        assert kw["creationflags"] & subprocess.BELOW_NORMAL_PRIORITY_CLASS
    rec.stop()
    assert not rec.running


def test_pick_output():
    outs = [Output(0, "abajo", 0, 0, 1920, 1080), Output(1, "arriba", 0, -1080, 1920, 0)]
    assert pick_output("primary", outs) == 0
    assert pick_output("1", outs) == 1
    assert pick_output("primary", [Output(0, "x", -1920, 0, 0, 1080), Output(1, "y", 0, 0, 1920, 1080)]) == 1
    assert pick_output("primary", []) == 0


def test_clips_config_parse():
    c = ClipsConfig.parse({"enabled": True, "method": "Medal", "seconds": 45, "buffer": 30, "fps": 99, "monitor": 1, "folder": " D:/Clips "})
    assert c.enabled and c.method == "medal" and c.buffer == 30 and c.seconds == 30 and c.fps == 30 and c.monitor == "1" and c.folder == "D:/Clips"
    assert ClipsConfig.parse("x") == ClipsConfig()
    assert ClipsConfig.parse({"method": "obs", "monitor": "arriba"}).method == "native"


def test_live_config_reads_clips(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"clips": {"enabled": True, "seconds": 10}}), encoding="utf-8")
    conf = LiveConfig(path)
    assert conf.clips.enabled and conf.clips.seconds == 10


def clipper_with(method, keys, recorder=None, enabled=True, folder=""):
    conf = static_config()
    conf.clips = ClipsConfig(enabled=enabled, method=method, medal_hotkey="Ctrl+Alt+F10" if method == "medal" else "F8", folder=folder)
    return Clipper(conf, recorder, videos=lambda: Path("C:/Videos"), keys=keys)


async def test_medal_and_gamebar_send_hotkeys_mocked():
    sent = []
    r = await clipper_with("medal", sent.append).save(20)
    assert r.state == "saved" and r.via == "medal"
    assert sent == [[0x11, 0x12, 0x79]]
    r = await clipper_with("gamebar", sent.append).save()
    assert r.state == "saved" and sent[-1] == GAMEBAR
    assert parse_hotkey("F8") == [0x77]
    assert parse_hotkey("Ctrl++") is None


async def test_native_never_sends_keys(tmp_path):
    sent = []

    class FakeRecorder:
        running = True

        def clip(self, seconds, out):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"mp4")
            return out, seconds

    c = clipper_with("native", sent.append, FakeRecorder(), folder=str(tmp_path / "Mis clips"))
    r = await c.save(12)
    assert r.state == "saved" and r.path.parent == tmp_path / "Mis clips"
    assert r.path.name.startswith("Sapo_") and r.path.suffix == ".mp4"
    assert r.seconds == 12
    assert sent == []
    off = await clipper_with("medal", sent.append, enabled=False).save()
    assert off.state == "error" and off.reason == "off" and sent == []
    missing = await clipper_with("native", sent.append, None).save()
    assert missing.reason == "no_ffmpeg"


def test_clipper_apply_follows_config():
    events = []

    class FakeRecorder:
        def __init__(self):
            self.running = False

        def start(self, conf):
            events.append(("start", conf.fps))
            self.running = True

        def stop(self, clean=True):
            events.append(("stop", clean))
            self.running = False

    conf = static_config()
    c = Clipper(conf, FakeRecorder(), videos=lambda: Path("."), keys=lambda k: None)
    assert c.apply() is None
    conf.clips = ClipsConfig(enabled=True)
    assert c.apply() == "started"
    assert c.apply() is None
    conf.clips = ClipsConfig(enabled=True, fps=60)
    assert c.apply() == "started"
    conf.clips = ClipsConfig(enabled=True, method="medal")
    assert c.apply() == "stopped"
    assert events == [("start", 30), ("start", 60), ("stop", True)]


def test_clip_result_message():
    assert ClipResult("saved", Path("C:/v/a.mp4"), 10.04).message() == {"type": "clip", "state": "saved", "path": str(Path("C:/v/a.mp4")), "seconds": 10.0}
    assert ClipResult("error").message() == {"type": "clip", "state": "error"}
