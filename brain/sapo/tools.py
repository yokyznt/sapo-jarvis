import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from .clips import ClipResult, Clipper
from .pc import PC, Window, best_match, norm

log = logging.getLogger("sapo.tools")

Ask = Callable[[str], Awaitable[bool]]
Notify = Callable[[str], Awaitable[None]]
Emit = Callable[[dict[str, Any]], Awaitable[None]]
See = Callable[[bytes, str], Awaitable[str]]
Handler = Callable[[dict[str, Any], Ask | None], Awaitable[str]]

YES = {"si", "sip", "simon", "dale", "va", "ok", "okay", "hazlo", "claro", "adelante", "confirmo", "yes", "orale", "sale"}
NO = {"no", "nel", "nop", "cancela", "cancelar", "cancelalo", "alto", "espera", "nada"}
FOLDERS = {
    "documentos": "documents",
    "documents": "documents",
    "mis documentos": "documents",
    "escritorio": "desktop",
    "desktop": "desktop",
    "descargas": "downloads",
    "downloads": "downloads",
    "imagenes": "pictures",
    "fotos": "pictures",
    "pictures": "pictures",
    "musica": "music",
    "music": "music",
    "videos": "videos",
    "inicio": "home",
    "usuario": "home",
    "home": "home",
}
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
POWER = {"shutdown": "¿Apago la compu?", "restart": "¿Reinicio la compu?", "sleep": "¿Suspendo la compu?"}
MAX_TIMER = 7 * 24 * 3600
CLIP_WORDS = re.compile(r"\b(clip\w*|clipazo|clipe\w*)\b|\b(graba|grabalo|guarda|guardalo)\s+(eso|esto|lo que paso|la jugada)\b")
NOT_CLIP = ("nota", "apunta", "anota", "portapapeles", "clipboard", "archivo", "documento")
NUMBERS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cinco": 5, "diez": 10, "quince": 15, "veinte": 20, "treinta": 30, "cuarenta": 40, "cuarenta y cinco": 45, "sesenta": 60, "noventa": 90, "medio": 0.5}


def parse_yes_no(text: str) -> bool | None:
    words = norm(text).split()
    if not words:
        return None
    if words[0] in YES:
        return True
    if words[0] in NO or words[:2] == ["mejor", "no"]:
        return False
    return None


def wants_tools(text: str, prefixes: list[str]) -> bool:
    words = norm(text).split()
    return any(w.startswith(p) for w in words for p in prefixes if len(p) >= 4 or w == p)


def wants_clip(text: str) -> bool:
    t = norm(text)
    if not CLIP_WORDS.search(t):
        return False
    return not any(w in t.split() for w in NOT_CLIP)


def clip_seconds(text: str) -> float | None:
    t = norm(text)
    m = re.search(r"(\d+(?:\s\d+)?|cuarenta y cinco|[a-z]+)\s+(segundos?|seg|s|minutos?|min)\b", t)
    if not m:
        return None
    raw = m.group(1).replace(" ", ".")
    try:
        value = float(raw)
    except ValueError:
        if raw.replace(".", " ") not in NUMBERS:
            return None
        value = float(NUMBERS[raw.replace(".", " ")])
    if m.group(2).startswith("min"):
        value *= 60
    return value if value > 0 else None


class ToolError(Exception):
    pass


@dataclass
class Result:
    text: str
    ok: bool = True
    blocked: bool = False


@dataclass
class Tool:
    name: str
    description: str
    params: dict[str, Any]
    required: tuple[str, ...]
    handler: Handler
    desktop: bool = False
    confirms: bool = False

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": self.params, "required": list(self.required)},
            },
        }


def enum(*values: str, desc: str = "") -> dict[str, Any]:
    d: dict[str, Any] = {"type": "string", "enum": list(values)}
    if desc:
        d["description"] = desc
    return d


def text(desc: str) -> dict[str, Any]:
    return {"type": "string", "description": desc}


def find_window(windows: list[Window], query: str) -> Window | None:
    q = norm(query)
    if not q:
        return None
    for w in windows:
        if norm(w.title) == q:
            return w
    for w in windows:
        if norm(Path(w.process).stem) == q:
            return w
    for w in windows:
        if q in norm(w.title) or q in norm(Path(w.process).stem):
            return w
    hit = best_match(query, [w.title for w in windows])
    return next((w for w in windows if w.title == hit), None)


class Toolbox:
    def __init__(
        self,
        pc: PC,
        see: See | None = None,
        notes_dir: Path | None = None,
        search_url: str = "https://duckduckgo.com/?q={q}",
        now: Callable[[], datetime] = datetime.now,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        clipper: Clipper | None = None,
    ):
        self.pc = pc
        self.clipper = clipper
        self.emit: Emit | None = None
        self.see = see
        self.notes_dir = notes_dir
        self.search_url = search_url
        self.now = now
        self.sleep = sleep
        self.notify: Notify | None = None
        self.timers: set[asyncio.Task] = set()
        self.tools = {t.name: t for t in self.build()}

    def build(self) -> list[Tool]:
        return [
            Tool("get_time", "Fecha y hora actual; solo si el usuario la pregunta.", {}, (), self.get_time),
            Tool(
                "set_timer",
                "Pone un temporizador o recordatorio; el sapo avisa al vencer. Usa minutes (en cuánto) o at (HH:MM, 24 h).",
                {"minutes": {"type": "number", "description": "minutos desde ahora"}, "at": text("hora HH:MM"), "text": text("qué recordar")},
                ("text",),
                self.set_timer,
            ),
            Tool(
                "volume",
                "Volumen de la PC: subir, bajar, fijar %, silenciar o consultar.",
                {"action": enum("up", "down", "set", "mute", "unmute", "get"), "percent": {"type": "integer", "description": "0-100; para set o cuánto subir/bajar"}},
                ("action",),
                self.volume,
            ),
            Tool("media", "Control de música/video: play/pausa, siguiente, anterior, detener.", {"action": enum("play_pause", "next", "previous", "stop")}, ("action",), self.media, desktop=True),
            Tool("open_app", "Abre una aplicación por nombre (Spotify, Chrome, bloc de notas...).", {"name": text("nombre de la app")}, ("name",), self.open_app, desktop=True),
            Tool("open_url", "Abre una página web en el navegador.", {"url": text("dirección web")}, ("url",), self.open_url, desktop=True),
            Tool("web_search", "Busca algo en internet en el navegador.", {"query": text("qué buscar")}, ("query",), self.web_search, desktop=True),
            Tool("open_folder", "Abre una carpeta (documentos, descargas, escritorio, imágenes, música, videos o una ruta).", {"name": text("carpeta o ruta")}, ("name",), self.open_folder, desktop=True),
            Tool("create_note", "Crea una nota de texto en Documentos/Sapo.", {"text": text("contenido"), "title": text("título corto")}, ("text",), self.create_note),
            Tool("clipboard_read", "Lee el texto del portapapeles.", {}, (), self.clipboard_read),
            Tool("clipboard_write", "Copia un texto al portapapeles.", {"text": text("texto a copiar")}, ("text",), self.clipboard_write),
            Tool("list_windows", "Lista las ventanas abiertas.", {}, (), self.list_windows),
            Tool(
                "window",
                "Minimiza, maximiza, restaura o enfoca una ventana por título o app.",
                {"action": enum("minimize", "maximize", "restore", "focus"), "title": text("título o app de la ventana")},
                ("action", "title"),
                self.window,
                desktop=True,
            ),
            Tool("close_window", "Cierra una ventana o app (pide confirmación).", {"title": text("título o app de la ventana")}, ("title",), self.close_window, desktop=True, confirms=True),
            Tool("screen", "Toma captura de pantalla y describe qué hay en la pantalla.", {"question": text("qué quiere saber de la pantalla")}, (), self.screen, desktop=True),
            Tool("lock_pc", "Bloquea la PC.", {}, (), self.lock_pc, desktop=True),
            Tool("power", "Apaga, reinicia o suspende la PC (pide confirmación).", {"action": enum("shutdown", "restart", "sleep")}, ("action",), self.power, confirms=True),
            Tool(
                "clip",
                "Guarda un clip de video de los últimos segundos de la pantalla con audio (clipea eso, graba eso, guarda eso).",
                {"seconds": {"type": "integer", "description": "cuántos segundos hacia atrás; por defecto el de la config (30)"}},
                (),
                self.clip,
            ),
            Tool("delete_file", "Manda un archivo o carpeta a la papelera (pide confirmación).", {"path": text("ruta o nombre del archivo")}, ("path",), self.delete_file, confirms=True),
        ]

    def specs(self) -> list[dict[str, Any]]:
        return [t.spec() for t in self.tools.values()]

    async def run(self, name: str, args: Any, game: bool = False, ask: Ask | None = None) -> Result:
        tool = self.tools.get(name)
        if tool is None:
            return Result(f"error: no existe la herramienta {name}", ok=False)
        if isinstance(args, str):
            try:
                args = json.loads(args or "{}")
            except ValueError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        if game and tool.desktop:
            return Result("bloqueado: el usuario está jugando", ok=False, blocked=True)
        try:
            return Result(await tool.handler(args, ask))
        except ToolError as e:
            return Result(f"error: {e}", ok=False)
        except Exception as e:
            log.warning("la herramienta %s falló: %r", name, e)
            return Result(f"error: {e!r}"[:300], ok=False)

    async def confirmed(self, ask: Ask | None, question: str) -> bool:
        return ask is not None and await ask(question)

    async def call(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    async def get_time(self, a, ask) -> str:
        n = self.now()
        return f"{DAYS[n.weekday()]} {n.day} de {MONTHS[n.month - 1]} de {n.year}, {n:%H:%M}"

    async def set_timer(self, a, ask) -> str:
        what = str(a.get("text") or "tu recordatorio").strip()[:120]
        now = self.now()
        if a.get("at"):
            m = re.fullmatch(r"\s*(\d{1,2})[:.h](\d{2})\s*", str(a["at"]))
            if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
                raise ToolError("hora inválida, usa HH:MM")
            due = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
            if due <= now:
                due += timedelta(days=1)
            seconds = (due - now).total_seconds()
        else:
            try:
                seconds = float(a.get("minutes")) * 60
            except (TypeError, ValueError):
                raise ToolError("falta minutes o at")
            due = now + timedelta(seconds=seconds)
        if not 0 < seconds <= MAX_TIMER:
            raise ToolError("el tiempo debe ser entre 1 segundo y 7 días")
        task = asyncio.create_task(self.fire(seconds, what))
        self.timers.add(task)
        task.add_done_callback(self.timers.discard)
        return f"listo: aviso a las {due:%H:%M} ({round(seconds / 60, 1)} min): {what}"

    async def fire(self, seconds: float, what: str) -> None:
        await self.sleep(seconds)
        if self.notify:
            await self.notify(what)

    async def volume(self, a, ask) -> str:
        action = a.get("action")
        pct = a.get("percent")
        if action in ("up", "down"):
            current, _ = await self.call(self.pc.volume)
            step = int(pct) if isinstance(pct, (int, float)) and pct else 10
            await self.call(self.pc.set_volume, max(0, min(100, current + (step if action == "up" else -step))))
        elif action == "set":
            if not isinstance(pct, (int, float)):
                raise ToolError("falta percent")
            await self.call(self.pc.set_volume, max(0, min(100, int(pct))))
        elif action in ("mute", "unmute"):
            await self.call(self.pc.set_mute, action == "mute")
        elif action != "get":
            raise ToolError("acción inválida")
        level, muted = await self.call(self.pc.volume)
        return f"volumen: {level}%" + (" (silenciado)" if muted else "")

    async def media(self, a, ask) -> str:
        action = a.get("action")
        if action not in ("play_pause", "next", "previous", "stop"):
            raise ToolError("acción inválida")
        await self.call(self.pc.media_key, action)
        return f"ok: tecla {action} enviada"

    async def open_app(self, a, ask) -> str:
        name = str(a.get("name") or "").strip()
        if not name:
            raise ToolError("falta name")
        try:
            opened = await self.call(self.pc.open_app, name)
        except LookupError:
            raise ToolError(f"no encontré la app {name}")
        return f"ok: abrí {opened}"

    async def open_url(self, a, ask) -> str:
        url = str(a.get("url") or "").strip()
        if not url or " " in url:
            raise ToolError("url inválida")
        if not re.match(r"https?://", url, re.I):
            url = "https://" + url.split("://")[-1]
        await self.call(self.pc.open_url, url)
        return f"ok: abrí {url}"

    async def web_search(self, a, ask) -> str:
        q = str(a.get("query") or "").strip()
        if not q:
            raise ToolError("falta query")
        await self.call(self.pc.open_url, self.search_url.replace("{q}", quote_plus(q)))
        return f"ok: busqué «{q}»"

    def resolve_folder(self, name: str) -> Path:
        key = FOLDERS.get(norm(name))
        if key:
            return self.pc.folder(key)
        p = Path(name).expanduser()
        if p.is_absolute():
            return p
        for base in ("desktop", "documents", "downloads", "home"):
            candidate = self.pc.folder(base) / name
            if candidate.exists():
                return candidate
        raise ToolError(f"no encontré {name}")

    async def open_folder(self, a, ask) -> str:
        path = self.resolve_folder(str(a.get("name") or "documentos"))
        if not path.is_dir():
            raise ToolError(f"no existe la carpeta {path}")
        await self.call(self.pc.open_path, path)
        return f"ok: abrí {path}"

    async def create_note(self, a, ask) -> str:
        body = str(a.get("text") or "").strip()
        if not body:
            raise ToolError("falta text")
        title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(a.get("title") or "")).strip()[:40] or "nota"
        folder = self.notes_dir or self.pc.folder("documents") / "Sapo"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self.now():%Y-%m-%d %H%M} {title}.txt"
        i = 2
        while path.exists():
            path = folder / f"{self.now():%Y-%m-%d %H%M} {title} {i}.txt"
            i += 1
        path.write_text(body + "\n", encoding="utf-8")
        return f"ok: nota guardada en {path}"

    async def clipboard_read(self, a, ask) -> str:
        content = await self.call(self.pc.clipboard)
        if not content:
            return "el portapapeles está vacío o no tiene texto"
        return "portapapeles: " + content[:1000]

    async def clipboard_write(self, a, ask) -> str:
        await self.call(self.pc.set_clipboard, str(a.get("text") or ""))
        return "ok: copiado al portapapeles"

    async def list_windows(self, a, ask) -> str:
        windows = await self.call(self.pc.windows)
        if not windows:
            return "no hay ventanas abiertas"
        return "ventanas: " + "; ".join(f"{w.title} ({w.process})" for w in windows[:20])

    async def target(self, a) -> Window:
        query = str(a.get("title") or "").strip()
        w = find_window(await self.call(self.pc.windows), query)
        if w is None:
            raise ToolError(f"no encontré una ventana «{query}»")
        return w

    async def window(self, a, ask) -> str:
        action = a.get("action")
        if action not in ("minimize", "maximize", "restore", "focus"):
            raise ToolError("acción inválida")
        w = await self.target(a)
        await self.call(self.pc.window_do, w.hwnd, action)
        return f"ok: {action} {w.title}"

    async def close_window(self, a, ask) -> str:
        w = await self.target(a)
        if not await self.confirmed(ask, f"¿Cierro «{w.title[:50]}»?"):
            return "cancelado: el usuario no confirmó"
        await self.call(self.pc.window_do, w.hwnd, "close")
        return f"ok: cerré {w.title}"

    async def screen(self, a, ask) -> str:
        if self.see is None:
            raise ToolError("no tengo visión")
        image = await self.call(self.pc.screenshot)
        question = str(a.get("question") or "").strip()
        prompt = "Describe en español, en 2 o 3 frases, qué se ve en esta captura de pantalla: apps, ventanas y contenido principal."
        if question:
            prompt += f" Responde además: {question}"
        description = (await self.see(image, prompt)).strip()
        return "pantalla: " + (description[:800] or "no pude distinguir nada")

    async def lock_pc(self, a, ask) -> str:
        await self.call(self.pc.lock)
        return "ok: PC bloqueada"

    async def power(self, a, ask) -> str:
        action = a.get("action")
        if action not in POWER:
            raise ToolError("acción inválida")
        if not await self.confirmed(ask, POWER[action]):
            return "cancelado: el usuario no confirmó"
        await self.call(self.pc.power, action)
        return f"ok: {action} en marcha"

    def protected(self, path: Path) -> bool:
        resolved = path.resolve()
        if resolved.parent == resolved:
            return True
        roots = [Path("C:/Windows"), Path("C:/Program Files"), Path("C:/Program Files (x86)"), Path("C:/ProgramData")]
        if any(resolved == r or r in resolved.parents for r in roots):
            return True
        keys = ("home", "desktop", "documents", "downloads", "pictures", "music", "videos")
        return any(resolved == self.pc.folder(k).resolve() for k in keys)

    async def delete_file(self, a, ask) -> str:
        name = str(a.get("path") or "").strip()
        if not name:
            raise ToolError("falta path")
        path = self.resolve_folder(name)
        if not path.exists():
            raise ToolError(f"no encontré {name}")
        if self.protected(path):
            raise ToolError("esa ruta no la toco")
        if not await self.confirmed(ask, f"¿Mando «{path.name[:50]}» a la papelera?"):
            return "cancelado: el usuario no confirmó"
        await self.call(self.pc.trash, path)
        return f"ok: {path} está en la papelera"

    async def take_clip(self, seconds: float | None = None) -> ClipResult:
        if self.clipper is None:
            result = ClipResult("error", reason="off")
        else:
            result = await self.clipper.save(seconds)
        if self.emit is not None:
            await self.emit(result.message())
        return result

    async def clip(self, a, ask) -> str:
        seconds = a.get("seconds")
        if isinstance(seconds, str):
            try:
                seconds = float(seconds)
            except ValueError:
                seconds = None
        result = await self.take_clip(seconds if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else None)
        if result.state != "saved":
            reasons = {
                "off": "los clips están apagados; se activan en Preferencias",
                "no_ffmpeg": "no encontré FFmpeg",
                "not_ready": "el grabador todavía no tiene video",
                "hotkey": "el atajo de Medal es inválido",
            }
            raise ToolError(reasons.get(result.reason, "no se pudo guardar el clip"))
        if result.via != "native":
            return f"ok: le pedí el clip a {'Medal' if result.via == 'medal' else 'la Xbox Game Bar'}"
        return f"ok: clip de {round(result.seconds or 0)} s guardado en {result.path}"
