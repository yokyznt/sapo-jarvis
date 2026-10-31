import os
import shutil
import sys
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..config import data_dir

BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"


@dataclass(frozen=True)
class Model:
    name: str
    url: str
    marker: str
    license: str


MODELS = {
    "vad": Model("silero_vad", f"{BASE}/asr-models/silero_vad.onnx", "silero_vad.onnx", "MIT"),
    "stt": Model(
        "sherpa-onnx-nemo-fast-conformer-ctc-es-1424-int8",
        f"{BASE}/asr-models/sherpa-onnx-nemo-fast-conformer-ctc-es-1424-int8.tar.bz2",
        "model.int8.onnx",
        "CC-BY-4.0",
    ),
    "tts": Model(
        "kokoro-multi-lang-v1_0",
        f"{BASE}/tts-models/kokoro-multi-lang-v1_0.tar.bz2",
        "model.onnx",
        "Apache-2.0",
    ),
}


def models_dir() -> Path:
    env = os.environ.get("SAPO_MODELS")
    return Path(env) if env else data_dir() / "models"


def model_path(key: str, root: Path | None = None) -> Path:
    return (root or models_dir()) / MODELS[key].name


def _progress(label: str):
    def hook(blocks: int, size: int, total: int) -> None:
        done = blocks * size
        if total > 0:
            pct = min(100, done * 100 // total)
            sys.stderr.write(f"\r{label}: {pct:3d}% ({done >> 20}/{total >> 20} MB)")
        else:
            sys.stderr.write(f"\r{label}: {done >> 20} MB")
        sys.stderr.flush()

    return hook


def ensure(key: str, root: Path | None = None) -> Path:
    model = MODELS[key]
    target = model_path(key, root)
    if (target / model.marker).exists():
        return target
    root = target.parent
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / (Path(model.url).name + ".part")
    urllib.request.urlretrieve(model.url, tmp, _progress(model.name))
    sys.stderr.write("\n")
    if model.url.endswith(".tar.bz2"):
        staging = root / (model.name + ".tmp")
        shutil.rmtree(staging, ignore_errors=True)
        with tarfile.open(tmp, "r:bz2") as tar:
            tar.extractall(staging, filter="data")
        inner = staging / model.name
        shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(inner if inner.exists() else staging), target)
        shutil.rmtree(staging, ignore_errors=True)
        tmp.unlink()
    else:
        target.mkdir(parents=True, exist_ok=True)
        tmp.replace(target / model.marker)
    return target


def ensure_all(root: Path | None = None) -> dict[str, Path]:
    return {key: ensure(key, root) for key in MODELS}


def main() -> None:
    for key, path in ensure_all().items():
        print(f"{key}: {path} ({MODELS[key].license})")
