import shutil
import subprocess
from dataclasses import dataclass

from .config import Settings


@dataclass(frozen=True)
class Profile:
    name: str
    model: str
    num_gpu: int | None
    game_model: str
    game_num_gpu: int | None
    unload_on_game: bool


def vram_mb() -> int:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return 0
    try:
        out = subprocess.run(
            [exe, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    values = [int(line.strip()) for line in out.splitlines() if line.strip().isdigit()]
    return max(values, default=0)


def pick_profile(settings: Settings, vram: int | None = None) -> Profile:
    mb = vram_mb() if vram is None else vram
    if mb >= settings.min_vram_mb:
        return Profile("gpu", settings.big_model, None, settings.small_model, 0, True)
    return Profile("cpu", settings.small_model, 0, settings.small_model, 0, False)
