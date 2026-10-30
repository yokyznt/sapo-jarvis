import io
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .pc import norm

MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 12000
TEXT_EXT = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv", ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml",
    ".html", ".htm", ".css", ".scss", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte", ".py", ".pyw", ".gd", ".cs",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".java", ".kt", ".swift", ".rs", ".go", ".rb", ".php", ".lua", ".sh", ".bat", ".cmd", ".ps1",
    ".sql", ".r", ".m", ".dart", ".zig", ".srt", ".vtt", ".tex",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
SECRET_EXT = {".pem", ".key", ".pfx", ".p12", ".kdbx", ".kdb", ".keychain", ".ppk", ".gpg", ".pgp", ".asc", ".jks", ".keystore", ".ovpn", ".rdp", ".cer", ".crt", ".der", ".sqlite", ".db"}
SECRET_DIRS = {".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".password-store", "keys", "llaves", "secrets", "credentials", "microsoft\\credentials", "protect"}
SECRET_PREFIXES = ("password", "passwd", "contrasena", "credential", "credencial", "secret", "apikey", "keystore", "wallet", "htpasswd", "pgpass", "netrc")
SECRET_WORDS = (
    "token", "tokens", "seed", "otp", "2fa", "private", "privada", "privado", "recovery", "recuperacion", "id rsa", "id ed25519",
    "id ecdsa", "id dsa", "login data", "web data", "local state", "cookies", "api key", "claves", "llaves",
)
PRIVATE_KEY = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----|-----BEGIN OPENSSH PRIVATE KEY-----|-----BEGIN PGP PRIVATE KEY BLOCK-----")


@dataclass
class Drop:
    name: str
    kind: str
    text: str = ""
    image: bytes = b""
    reason: str = ""


def sensitive(path: Path, blacklist: tuple[str, ...] | list[str] = ()) -> bool:
    name = path.name.lower()
    if name.startswith(".env") or name in ("secrets.json", "credentials.json", "credentials", "known_hosts", "authorized_keys", ".npmrc", ".pypirc", ".netrc", ".git-credentials"):
        return True
    if path.suffix.lower() in SECRET_EXT:
        return True
    parts = [p.lower() for p in path.parts[:-1]]
    if any(p in SECRET_DIRS for p in parts):
        return True
    words = " " + norm(str(path)) + " "
    if any(f" {w}" in words for w in SECRET_PREFIXES) or any(f" {w} " in words for w in SECRET_WORDS):
        return True
    for word in blacklist:
        w = norm(word)
        if w and w in words:
            return True
    return False


def looks_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError as e:
        return e.start >= len(head) - 4


def decode_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16"):
        try:
            if enc == "utf-16" and not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                continue
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1252", "replace")


def pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return ""
    out: list[str] = []
    size = 0
    for page in reader.pages[:30]:
        chunk = page.extract_text() or ""
        out.append(chunk)
        size += len(chunk)
        if size >= MAX_TEXT:
            break
    return "\n".join(out)


def to_jpeg(raw: bytes) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(raw))
    img.seek(0)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def read_drop(raw_path: str, blacklist: tuple[str, ...] | list[str] = (), max_bytes: int = MAX_BYTES) -> Drop:
    path = Path(os.path.expandvars(raw_path.strip().strip('"'))).expanduser()
    name = path.name or raw_path
    if sensitive(path, blacklist):
        return Drop(name, "refused", reason="sensitive")
    if not path.exists():
        return Drop(name, "refused", reason="missing")
    if path.is_dir():
        return Drop(name, "refused", reason="folder")
    try:
        size = path.stat().st_size
    except OSError:
        return Drop(name, "refused", reason="missing")
    if size > max_bytes:
        return Drop(name, "refused", reason="big")
    try:
        raw = path.read_bytes()
    except OSError:
        return Drop(name, "refused", reason="unreadable")
    if PRIVATE_KEY.search(raw[:200000]):
        return Drop(name, "refused", reason="sensitive")
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        try:
            return Drop(name, "image", image=to_jpeg(raw))
        except Exception:
            return Drop(name, "refused", reason="unreadable")
    if ext == ".pdf":
        try:
            text = pdf_text(raw)
        except Exception:
            return Drop(name, "refused", reason="unreadable")
        if not text.strip():
            return Drop(name, "refused", reason="empty")
        return Drop(name, "pdf", text=text[:MAX_TEXT])
    if ext in TEXT_EXT or looks_text(raw[:4096]):
        text = decode_text(raw)
        if not text.strip():
            return Drop(name, "refused", reason="empty")
        return Drop(name, "code" if ext not in (".txt", ".md", ".markdown", ".rst", ".log", ".srt", ".vtt") else "text", text=text[:MAX_TEXT])
    return Drop(name, "refused", reason="unknown")
