import os
from dataclasses import dataclass, field
from pathlib import Path

PROMPTS = Path(__file__).parent / "prompts"


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "Sapo"


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
        return s
