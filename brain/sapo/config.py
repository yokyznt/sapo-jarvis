import asyncio
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

PROMPTS = Path(__file__).parent / "prompts"
PERSONALITIES = ("sarcastico", "tierno", "tranquilo")
DEFAULT_BLACKLIST = (
    "keepass",
    "1password",
    "bitwarden",
    "bbva",
    "banamex",
    "santander",
    "banorte",
    "whatsapp",
    "outlook",
    "gmail",
    "inprivate",
    "incógnito",
    "hermes",
)

log = logging.getLogger("sapo.config")


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "Sapo"


def home_dir() -> Path:
    home = os.environ.get("SAPO_HOME")
    return Path(home) if home else data_dir()


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    lang: str = "es"
    ollama_url: str = "http://127.0.0.1:11434"
    big_model: str = "qwen3.5:4b"
    small_model: str = "qwen3.5:2b"
    groq_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    db_path: Path = field(default_factory=lambda: data_dir() / "memoria.db")
    history: int = 12
    num_predict: int = 160
    min_vram_mb: int = 6000
    tools: bool = True
    confirm_timeout: float = 30.0
    search_url: str = "https://duckduckgo.com/?q={q}"
    notes_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ.get
        s = cls()
        s.host = env("SAPO_HOST", s.host)
        s.port = int(env("SAPO_PORT", s.port))
        s.lang = env("SAPO_LANG", s.lang)
        s.ollama_url = env("OLLAMA_URL", s.ollama_url)
        s.big_model = env("SAPO_MODEL_BIG", s.big_model)
        s.small_model = env("SAPO_MODEL_SMALL", s.small_model)
        s.groq_key = env("GROQ_API_KEY") or None
        s.groq_model = env("GROQ_MODEL", s.groq_model)
        db = env("SAPO_DB")
        if db:
            s.db_path = Path(db)
        s.history = int(env("SAPO_HISTORY", s.history))
        s.num_predict = int(env("SAPO_NUM_PREDICT", s.num_predict))
        s.tools = env("SAPO_TOOLS", "1") not in ("0", "no", "false")
        s.confirm_timeout = float(env("SAPO_CONFIRM_TIMEOUT", s.confirm_timeout))
        s.search_url = env("SAPO_SEARCH_URL", s.search_url)
        notes = env("SAPO_NOTES")
        if notes:
            s.notes_dir = Path(notes)
        return s


@dataclass(frozen=True)
class BrainConfig:
    provider: str = "gemini"
    gemini_model: str = "gemini-flash-latest"
    gemini_lite_model: str = "gemini-flash-lite-latest"
    ollama_model: str = ""
    ollama_game_model: str = ""
    personality: str = "sarcastico"
    comment_minutes: float = 10.0
    attention: bool = True
    vision: bool = True
    blacklist: tuple[str, ...] = DEFAULT_BLACKLIST

    @classmethod
    def parse(cls, raw: Any) -> "BrainConfig":
        d = cls()
        if not isinstance(raw, dict):
            return d
        values: dict[str, Any] = {}
        for key in ("gemini_model", "gemini_lite_model", "ollama_model", "ollama_game_model"):
            v = raw.get(key)
            if isinstance(v, str) and v.strip():
                values[key] = v.strip()
        for key, allowed in (("provider", ("gemini", "ollama")), ("personality", PERSONALITIES)):
            v = raw.get(key)
            if isinstance(v, str) and v.strip().lower() in allowed:
                values[key] = v.strip().lower()
        minutes = raw.get("comment_minutes")
        if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and 1 <= minutes <= 240:
            values["comment_minutes"] = float(minutes)
        for key in ("attention", "vision"):
            if isinstance(raw.get(key), bool):
                values[key] = raw[key]
        black = raw.get("blacklist")
        if isinstance(black, list):
            values["blacklist"] = tuple(w.strip().lower() for w in black if isinstance(w, str) and w.strip())
        return cls(**{f.name: values.get(f.name, getattr(d, f.name)) for f in fields(cls)})


def config_path() -> Path:
    return home_dir() / "config.json"


class LiveConfig:
    def __init__(self, path: Path | None = None):
        self.path = path or config_path()
        self.stamp: tuple[int, int] | None = None
        self.brain = BrainConfig()
        self.listeners: list[Callable[[BrainConfig], None]] = []
        self.poll()

    def current(self) -> tuple[int, int] | None:
        try:
            st = self.path.stat()
        except OSError:
            return None
        return st.st_mtime_ns, st.st_size

    def poll(self) -> bool:
        stamp = self.current()
        if stamp == self.stamp:
            return False
        self.stamp = stamp
        raw: Any = {}
        if stamp is not None:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as e:
                log.warning("config.json ilegible (%s), sigo con la anterior", e)
                return False
        new = BrainConfig.parse(raw.get("brain") if isinstance(raw, dict) else None)
        if new == self.brain:
            return False
        self.brain = new
        log.info("config recargada: proveedor %s, personalidad %s, comentarios cada %s min", new.provider, new.personality, new.comment_minutes)
        for listener in self.listeners:
            listener(new)
        return True

    async def watch(self, every: float = 1.0) -> None:
        while True:
            await asyncio.sleep(every)
            try:
                self.poll()
            except Exception as e:
                log.warning("no pude releer la config: %r", e)


def static_config(**kw: Any) -> LiveConfig:
    conf = LiveConfig(Path(os.devnull) / "sapo-sin-config.json")
    conf.brain = BrainConfig(**kw)
    return conf
