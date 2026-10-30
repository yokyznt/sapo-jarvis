import asyncio
import collections
import logging
import math
import os
import shutil
import subprocess
import threading
import time
import wave
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .config import ClipsConfig, LiveConfig
from .protocol import clip as clip_msg

log = logging.getLogger("sapo.clips")

SEGMENT = 2
ENCODERS = ("h264_nvenc", "h264_amf", "h264_qsv", "libx264")
FLAGS = (getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)) if os.name == "nt" else 0
GAMEBAR = [0x5B, 0x12, 0x47]
VK_NAMES = {
    "ctrl": 0x11,
    "control": 0x11,
    "ctl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "windows": 0x5B,
    "super": 0x5B,
    "meta": 0x5B,
    "space": 0x20,
    "espacio": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "esc": 0x1B,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "pause": 0x13,
    "printscreen": 0x2C,
    "scrolllock": 0x91,
}
EXTENDED = {0x5B, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x2C}
RATE = 48000
CHANNELS = 2


class ClipError(Exception):
    pass


@dataclass(frozen=True)
class Output:
    idx: int
    name: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def primary(self) -> bool:
        return self.left == 0 and self.top == 0


@dataclass(frozen=True)
class Segment:
    path: Path
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class ClipResult:
    state: str
    path: Path | None = None
    seconds: float | None = None
    reason: str = ""
    via: str = "native"

    def message(self) -> dict[str, Any]:
        return clip_msg(self.state, str(self.path) if self.path else None, self.seconds)


def find_ffmpeg(name: str = "ffmpeg") -> str | None:
    override = os.environ.get("SAPO_FFMPEG")
    if override and name == "ffmpeg" and Path(override).is_file():
        return override
    if override and name != "ffmpeg":
        sibling = Path(override).with_name(f"{name}.exe")
        if sibling.is_file():
            return str(sibling)
    hit = shutil.which(name)
    if hit:
        return hit
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    link = local / "Microsoft/WinGet/Links" / f"{name}.exe"
    if link.is_file():
        return str(link)
    packages = local / "Microsoft/WinGet/Packages"
    if packages.is_dir():
        for folder in sorted(packages.glob("*FFmpeg*"), reverse=True):
            for exe in sorted(folder.glob(f"*/bin/{name}.exe"), reverse=True):
                return str(exe)
    return None


def buffer_dir() -> Path:
    home = os.environ.get("SAPO_HOME")
    if home:
        return Path(home) / "clipbuf"
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache") / "Sapo" / "clipbuf"


def encoder_works(ffmpeg: str, encoder: str) -> bool:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30", "-frames:v", "10", "-pix_fmt", "yuv420p" if encoder == "libx264" else "nv12", "-c:v", encoder, "-f", "null", "-"]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=20, creationflags=FLAGS).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class EncoderPicker:
    def __init__(self, works: Callable[[str, str], bool] = encoder_works):
        self.works = works
        self.cache: dict[tuple[str, str], bool] = {}

    def ok(self, ffmpeg: str, encoder: str) -> bool:
        key = (ffmpeg, encoder)
        if key not in self.cache:
            self.cache[key] = bool(self.works(ffmpeg, encoder))
            log.info("encoder %s: %s", encoder, "sí" if self.cache[key] else "no")
        return self.cache[key]

    def candidates(self, ffmpeg: str, prefer: str = "auto") -> list[str]:
        order = list(ENCODERS)
        if prefer in order:
            order.remove(prefer)
            order.insert(0, prefer)
        return [e for e in order if e == "libx264" or self.ok(ffmpeg, e)]

    def pick(self, ffmpeg: str, prefer: str = "auto") -> str:
        found = self.candidates(ffmpeg, prefer)
        return found[0] if found else "libx264"


def encoder_args(encoder: str, fps: int) -> list[str]:
    gop = str(fps * SEGMENT)
    keys = ["-g", gop, "-keyint_min", gop, "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT})"]
    if encoder == "h264_nvenc":
        return ["-c:v", encoder, "-preset", "p3", "-rc", "vbr", "-cq", "26", "-b:v", "0", "-maxrate", "16M", "-bufsize", "32M", "-bf", "0", *keys]
    if encoder == "h264_amf":
        return ["-c:v", encoder, "-quality", "speed", "-rc", "cqp", "-qp_i", "24", "-qp_p", "26", "-bf", "0", *keys]
    if encoder == "h264_qsv":
        return ["-c:v", encoder, "-preset", "veryfast", "-global_quality", "26", *keys]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-crf", "26", "-pix_fmt", "yuv420p", *keys]


def video_filter(encoder: str, fps: int, output_idx: int) -> str:
    grab = f"ddagrab=output_idx={output_idx}:framerate={fps}:draw_mouse=1"
    if encoder in ("h264_nvenc", "h264_amf"):
        return grab
    if encoder == "h264_qsv":
        return grab + ",hwdownload,format=bgra,format=nv12"
    return grab + ",hwdownload,format=bgra,format=yuv420p"


def wrap_for(buffer: int) -> int:
    return math.ceil(buffer / SEGMENT) + 2


def video_command(ffmpeg: str, encoder: str, fps: int, output_idx: int, folder: Path, buffer: int) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "error",
        "-y",
        "-filter_complex",
        video_filter(encoder, fps, output_idx),
        *encoder_args(encoder, fps),
        "-an",
        "-f",
        "segment",
        "-segment_time",
        str(SEGMENT),
        "-segment_wrap",
        str(wrap_for(buffer)),
        "-segment_format",
        "mpegts",
        "-reset_timestamps",
        "1",
        str(folder / "seg%03d.ts"),
    ]


def dxgi_outputs() -> list[Output]:
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]

    class DESC(ctypes.Structure):
        _fields_ = [("name", wintypes.WCHAR * 32), ("rect", wintypes.RECT), ("attached", wintypes.BOOL), ("rotation", ctypes.c_int), ("monitor", wintypes.HMONITOR)]

    def method(obj, index, *argtypes):
        vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vtbl[index])

    def release(obj):
        method(obj, 2)(obj)

    iid = GUID(0x7B7166EC, 0x21C7, 0x44AE, (ctypes.c_ubyte * 8)(0xB2, 0x1A, 0xC9, 0xAE, 0x32, 0x1A, 0xE3, 0x69))
    factory = ctypes.c_void_p()
    try:
        dxgi = ctypes.WinDLL("dxgi")
        if dxgi.CreateDXGIFactory(ctypes.byref(iid), ctypes.byref(factory)) != 0 or not factory:
            return []
    except OSError:
        return []
    found: list[Output] = []
    adapter = ctypes.c_void_p()
    try:
        if method(factory, 7, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(factory, 0, ctypes.byref(adapter)) != 0 or not adapter:
            return []
        i = 0
        while i < 16:
            output = ctypes.c_void_p()
            if method(adapter, 7, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(adapter, i, ctypes.byref(output)) != 0 or not output:
                break
            desc = DESC()
            if method(output, 7, ctypes.POINTER(DESC))(output, ctypes.byref(desc)) == 0:
                r = desc.rect
                found.append(Output(i, desc.name, r.left, r.top, r.right, r.bottom))
            release(output)
            i += 1
        release(adapter)
    finally:
        release(factory)
    return found


def pick_output(monitor: str, outputs: list[Output]) -> int:
    if monitor.isdigit():
        return int(monitor)
    for out in outputs:
        if out.primary:
            return out.idx
    return 0


def timeline(folder: Path, now: float, live: bool = True) -> list[Segment]:
    files = []
    for p in folder.glob("seg*.ts"):
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_size > 0:
            files.append((st.st_mtime, p))
    files.sort()
    out: list[Segment] = []
    prev: float | None = None
    for i, (mtime, p) in enumerate(files):
        last = i == len(files) - 1
        end = max(mtime, now) if last and live else mtime
        start = prev if prev is not None else mtime - SEGMENT
        start = max(start, end - 3 * SEGMENT) if not last else start
        out.append(Segment(p, start, end))
        prev = mtime
    return out


def select(segments: list[Segment], seconds: float) -> list[Segment]:
    chosen: list[Segment] = []
    total = 0.0
    for seg in reversed(segments):
        chosen.append(seg)
        total += seg.duration
        if total >= seconds:
            break
    chosen.reverse()
    return chosen


def trim(folder: Path, keep: int) -> int:
    files = sorted(folder.glob("seg*.ts"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    removed = 0
    for p in files[: max(0, len(files) - keep)]:
        try:
            p.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def clear(folder: Path) -> None:
    if not folder.is_dir():
        return
    for p in list(folder.glob("seg*.ts")):
        try:
            p.unlink()
        except OSError:
            pass
    shutil.rmtree(folder / "work", ignore_errors=True)


def write_wav(path: Path, samples: np.ndarray, rate: int = RATE) -> None:
    data = np.ascontiguousarray(samples, dtype=np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(data.shape[1] if data.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())


def concat_line(path: Path) -> str:
    return "file '" + path.resolve().as_posix().replace("'", "'\\''") + "'"


def assemble(ffmpeg: str, parts: list[Path], out: Path, wav: Path | None = None, timeout: float = 180) -> Path:
    if not parts:
        raise ClipError("no hay segmentos")
    out.parent.mkdir(parents=True, exist_ok=True)
    listing = out.with_name(out.stem + ".txt")
    listing.write_text("\n".join(concat_line(p) for p in parts) + "\n", encoding="utf-8")
    tmp = out.with_name(out.stem + ".tmp.mp4")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing)]
    if wav is not None:
        cmd += ["-i", str(wav), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest"]
    else:
        cmd += ["-map", "0:v:0", "-c:v", "copy"]
    cmd += ["-movflags", "+faststart", str(tmp)]
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=FLAGS)
    except subprocess.TimeoutExpired as e:
        raise ClipError("ffmpeg tardó demasiado uniendo el clip") from e
    finally:
        listing.unlink(missing_ok=True)
    if done.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise ClipError("ffmpeg no pudo unir el clip: " + done.stderr.decode("utf-8", "replace").strip()[-300:])
    os.replace(tmp, out)
    return out


class AudioRing:
    def __init__(self, seconds: float, rate: int = RATE, channels: int = CHANNELS):
        self.rate = rate
        self.channels = channels
        self.capacity = int((seconds + 6) * rate)
        self.data = np.zeros((self.capacity, channels), np.int16)
        self.total = 0
        self.end: float | None = None
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.thread: threading.Thread | None = None
        self.error = ""

    def push(self, chunk: np.ndarray, t: float) -> None:
        if chunk.ndim == 1:
            chunk = chunk[:, None]
        if chunk.shape[1] != self.channels:
            chunk = np.repeat(chunk[:, :1], self.channels, axis=1) if chunk.shape[1] < self.channels else chunk[:, : self.channels]
        if chunk.dtype != np.int16:
            chunk = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16)
        n = len(chunk)
        if n > self.capacity:
            chunk = chunk[-self.capacity :]
            n = self.capacity
        with self.lock:
            pos = self.total % self.capacity
            first = min(n, self.capacity - pos)
            self.data[pos : pos + first] = chunk[:first]
            if first < n:
                self.data[: n - first] = chunk[first:]
            self.total += n
            self.end = t

    def window(self, t0: float, t1: float) -> np.ndarray:
        n = max(0, int(round((t1 - t0) * self.rate)))
        out = np.zeros((n, self.channels), np.int16)
        with self.lock:
            if self.end is None or n == 0:
                return out
            first = self.total - int(round((self.end - t0) * self.rate))
            lo = max(first, self.total - self.capacity, 0)
            hi = min(first + n, self.total)
            i = lo
            while i < hi:
                pos = i % self.capacity
                take = min(hi - i, self.capacity - pos)
                out[i - first : i - first + take] = self.data[pos : pos + take]
                i += take
        return out

    def start(self) -> None:
        self.stopping.clear()
        self.thread = threading.Thread(target=self.run, name="sapo-audio-loopback", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(timeout=3)
            self.thread = None

    def run(self) -> None:
        import warnings

        try:
            import soundcard
        except Exception as e:
            self.error = f"sin soundcard: {e!r}"
            log.warning("no hay audio del sistema: %s", self.error)
            return
        if os.name == "nt":
            import ctypes

            ctypes.windll.ole32.CoInitializeEx(None, 0)
        warnings.filterwarnings("ignore", module="soundcard")
        block = self.rate // 10
        while not self.stopping.is_set():
            try:
                speaker = soundcard.default_speaker()
                mic = soundcard.get_microphone(id=str(speaker.name), include_loopback=True)
                checked = time.monotonic()
                with mic.recorder(samplerate=self.rate, channels=self.channels) as rec:
                    while not self.stopping.is_set():
                        chunk = rec.record(numframes=block)
                        self.push(chunk, time.time())
                        if time.monotonic() - checked > 5:
                            checked = time.monotonic()
                            if soundcard.default_speaker().name != speaker.name:
                                log.info("cambió la bocina, reabro el loopback")
                                break
                self.error = ""
            except Exception as e:
                self.error = repr(e)
                log.warning("loopback de audio falló: %r", e)
                self.stopping.wait(2)


class Recorder:
    def __init__(
        self,
        ffmpeg: str,
        folder: Path | None = None,
        popen: Callable[..., Any] = subprocess.Popen,
        outputs: Callable[[], list[Output]] = dxgi_outputs,
        picker: EncoderPicker | None = None,
        audio_factory: Callable[[float], Any] | None = AudioRing,
        settle: float = 2.5,
    ):
        self.ffmpeg = ffmpeg
        self.folder = folder or buffer_dir()
        self.popen = popen
        self.outputs = outputs
        self.picker = picker or EncoderPicker()
        self.audio_factory = audio_factory
        self.settle = settle
        self.proc: Any = None
        self.audio: Any = None
        self.encoder = ""
        self.conf: ClipsConfig | None = None
        self.errors: collections.deque[str] = collections.deque(maxlen=20)
        self.lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def drain(self, proc: Any) -> None:
        def pump() -> None:
            try:
                for line in proc.stderr:
                    text = line.decode("utf-8", "replace").strip()
                    if text:
                        self.errors.append(text)
            except (OSError, ValueError):
                pass

        if getattr(proc, "stderr", None) is not None:
            threading.Thread(target=pump, name="sapo-ffmpeg-log", daemon=True).start()

    def start(self, conf: ClipsConfig) -> str:
        with self.lock:
            self.halt(clean=True)
            self.folder.mkdir(parents=True, exist_ok=True)
            idx = pick_output(conf.monitor, self.outputs())
            for encoder in self.picker.candidates(self.ffmpeg, conf.encoder):
                cmd = video_command(self.ffmpeg, encoder, conf.fps, idx, self.folder, conf.buffer)
                self.errors.clear()
                proc = self.popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=FLAGS)
                self.drain(proc)
                try:
                    proc.wait(timeout=self.settle)
                except subprocess.TimeoutExpired:
                    self.proc = proc
                    self.encoder = encoder
                    break
                log.warning("ffmpeg con %s no arrancó: %s", encoder, " | ".join(self.errors)[-300:])
            else:
                raise ClipError("ffmpeg no pudo grabar la pantalla: " + " | ".join(self.errors)[-300:])
            self.conf = conf
            if conf.audio and self.audio_factory is not None:
                self.audio = self.audio_factory(conf.buffer)
                self.audio.start()
            log.info("grabando búfer de clips: %s, monitor %s, %s fps, %s s", self.encoder, idx, conf.fps, conf.buffer)
            return self.encoder

    def halt(self, clean: bool = False) -> None:
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            try:
                proc.stdin.write(b"q")
                proc.stdin.flush()
                proc.stdin.close()
            except (OSError, ValueError, AttributeError):
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        if self.audio is not None:
            self.audio.stop()
            self.audio = None
        if clean:
            clear(self.folder)

    def stop(self, clean: bool = True) -> None:
        with self.lock:
            self.halt(clean=clean)
            self.conf = None

    def keep(self) -> int:
        return wrap_for(self.conf.buffer if self.conf else 120)

    def clip(self, seconds: float, out: Path) -> tuple[Path, float]:
        now = time.time()
        segments = timeline(self.folder, now, live=self.running)
        chosen = select(segments, seconds)
        if not chosen:
            raise ClipError("todavía no hay video en el búfer")
        t0, t1 = chosen[0].start, chosen[-1].end
        work = self.folder / "work"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True, exist_ok=True)
        try:
            parts = []
            for i, seg in enumerate(chosen):
                dst = work / f"{i:03d}.ts"
                shutil.copyfile(seg.path, dst)
                parts.append(dst)
            wav = None
            if self.audio is not None:
                wav = work / "audio.wav"
                write_wav(wav, self.audio.window(t0, t1), self.audio.rate)
            assemble(self.ffmpeg, parts, out, wav)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        trim(self.folder, self.keep())
        return out, t1 - t0


def parse_hotkey(text: str) -> list[int] | None:
    keys: list[int] = []
    for raw in text.lower().replace(" ", "").split("+"):
        if not raw:
            return None
        if raw in VK_NAMES:
            keys.append(VK_NAMES[raw])
        elif raw.startswith("f") and raw[1:].isdigit() and 1 <= int(raw[1:]) <= 24:
            keys.append(0x6F + int(raw[1:]))
        elif len(raw) == 1 and (raw.isascii() and raw.isalnum()):
            keys.append(ord(raw.upper()))
        else:
            return None
    return keys or None


def send_combo(vks: list[int]) -> None:
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

    def key(vk: int, up: bool) -> INPUT:
        flags = (2 if up else 0) | (1 if vk in EXTENDED else 0)
        return INPUT(type=1, u=UNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)))

    events = [key(vk, False) for vk in vks] + [key(vk, True) for vk in reversed(vks)]
    array = (INPUT * len(events))(*events)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput(len(events), array, ctypes.sizeof(INPUT))


def default_videos() -> Path:
    from .pc import WindowsPC

    return WindowsPC().folder("videos")


class Clipper:
    def __init__(
        self,
        config: LiveConfig,
        recorder: Recorder | None,
        videos: Callable[[], Path] = default_videos,
        keys: Callable[[list[int]], None] = send_combo,
        now: Callable[[], datetime] = datetime.now,
        retry: float = 15.0,
    ):
        self.config = config
        self.recorder = recorder
        self.videos = videos
        self.keys = keys
        self.now = now
        self.retry = retry
        self.active: tuple | None = None
        self.failed_at = float("-inf")

    def folder(self) -> Path:
        custom = self.config.clips.folder
        if custom:
            return Path(os.path.expandvars(custom)).expanduser()
        return self.videos() / "Sapo Clips"

    def target(self) -> Path:
        folder = self.folder()
        stamp = self.now()
        path = folder / f"Sapo_{stamp:%Y-%m-%d_%H-%M-%S}.mp4"
        i = 2
        while path.exists():
            path = folder / f"Sapo_{stamp:%Y-%m-%d_%H-%M-%S}_{i}.mp4"
            i += 1
        return path

    async def save(self, seconds: float | None = None) -> ClipResult:
        conf = self.config.clips
        method = conf.method
        if not conf.enabled:
            return ClipResult("error", reason="off", via=method)
        if method in ("medal", "gamebar"):
            combo = parse_hotkey(conf.medal_hotkey) if method == "medal" else GAMEBAR
            if not combo:
                return ClipResult("error", reason="hotkey", via=method)
            try:
                await asyncio.to_thread(self.keys, combo)
            except Exception as e:
                log.warning("no pude mandar el atajo de %s: %r", method, e)
                return ClipResult("error", reason="failed", via=method)
            return ClipResult("saved", via=method)
        if self.recorder is None:
            return ClipResult("error", reason="no_ffmpeg")
        if not self.recorder.running:
            return ClipResult("error", reason="not_ready")
        wanted = float(seconds) if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and seconds > 0 else float(conf.seconds)
        wanted = max(5.0, min(wanted, float(conf.buffer)))
        try:
            path, length = await asyncio.to_thread(self.recorder.clip, wanted, self.target())
        except ClipError as e:
            log.warning("clip falló: %s", e)
            return ClipResult("error", reason="not_ready" if "búfer" in str(e) else "failed")
        except Exception as e:
            log.warning("clip falló: %r", e)
            return ClipResult("error", reason="failed")
        log.info("clip guardado: %s (%.1f s)", path, length)
        return ClipResult("saved", path, length)

    def wanted(self) -> tuple | None:
        c = self.config.clips
        if not c.enabled or c.method != "native" or self.recorder is None:
            return None
        return (c.fps, c.buffer, c.monitor, c.encoder, c.audio)

    def apply(self) -> str | None:
        key = self.wanted()
        rec = self.recorder
        if rec is None:
            return None
        if key is None:
            if self.active is not None or rec.running:
                rec.stop(clean=True)
                self.active = None
                return "stopped"
            return None
        if key == self.active and rec.running:
            return None
        if key == self.active and time.monotonic() - self.failed_at < self.retry:
            return None
        try:
            rec.start(self.config.clips)
        except Exception as e:
            log.warning("no pude arrancar el grabador de clips: %s", e)
            self.active = key
            self.failed_at = time.monotonic()
            return "failed"
        self.active = key
        return "started"

    async def watch(self, emit: Callable[[dict[str, Any]], Awaitable[None]] | None = None, every: float = 1.0) -> None:
        if self.recorder is None and self.config.clips.enabled and self.config.clips.method == "native":
            log.warning("clips activados pero no encontré FFmpeg (instala con: winget install Gyan.FFmpeg)")
        try:
            while True:
                try:
                    change = await asyncio.to_thread(self.apply)
                    if change == "started" and emit is not None:
                        await emit(clip_msg("recording"))
                except Exception as e:
                    log.warning("vigilancia de clips falló: %r", e)
                await asyncio.sleep(every)
        finally:
            self.close()

    def close(self) -> None:
        if self.recorder is not None:
            self.recorder.stop(clean=False)
        self.active = None


def make_clipper(config: LiveConfig) -> Clipper:
    ffmpeg = find_ffmpeg()
    return Clipper(config, Recorder(ffmpeg) if ffmpeg else None)
