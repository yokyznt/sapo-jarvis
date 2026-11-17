import asyncio
import io
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("sapo.desktop")

KEYS = {
    "enter": 0x0D, "esc": 0x1B, "tab": 0x09, "space": 0x20, "backspace": 0x08, "delete": 0x2E,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    "f5": 0x74, "f11": 0x7A,
}
DANGER = re.compile(r"\b(pag[ao]r?|compra[r]?|buy|pay|checkout|elimina[r]?|borra[r]? (?:la )?cuenta|delete account|cerrar sesi[oó]n|log ?out|sign ?out|transfer)", re.I)
ACTIONS = ("click", "doble_click", "escribir", "tecla", "scroll", "esperar", "listo", "no_puedo")

PROMPT = """Controlas la compu del usuario viendo la pantalla. Objetivo: {goal}
Ventana: {title}. Pasos que ya hiciste: {history}{changed}
Responde SOLO un JSON con: {{"accion": uno de {acciones}, "x": de 0 (borde izquierdo) a 1000 (borde derecho), "y": de 0 (arriba) a 1000 (abajo), "texto": "lo que se escribe", "tecla": "enter|esc|tab|ctrl+l|...", "cantidad": entero de -10 a 10 para scroll (negativo = abajo), "nota": "frase corta de qué ves y por qué"}}.
Reglas: una sola acción; x y y son el centro exacto del elemento en ESTA imagen. Usa listo en cuanto la imagen muestre cumplido el objetivo (por ejemplo, ya estás en la página que se pidió). Si un clic no cambió nada, no lo repitas igual: prueba otro elemento, otra forma o no_puedo. Usa no_puedo si hay que pagar, comprar, borrar o iniciar sesión. Nunca des clic en anuncios ni banners. Para escribir en un campo, primero dale click."""


VERIFY = """Mira la imagen con cuidado. ¿Ya se ve cumplido este objetivo: {goal}?
Fíjate en los nombres exactos (artista, canción, página) y no supongas. Responde SOLO JSON: {{"cumplido": true o false, "por_que": "frase corta de lo que realmente se ve"}}"""


def parse_verdict(raw: str) -> tuple[bool, str]:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return False, "no supe verificar"
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return False, "no supe verificar"
    return data.get("cumplido") is True, str(data.get("por_que") or "")[:160]


@dataclass
class Shot:
    image: bytes
    left: int
    top: int
    width: int
    height: int


@dataclass
class Step:
    action: str
    point: tuple[float, float] | None = None
    text: str = ""
    key: str = ""
    amount: int = 0
    note: str = ""


def parse_step(raw: str) -> Step:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return Step("no_puedo", note="respuesta sin JSON")
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return Step("no_puedo", note="JSON roto")
    action = str(data.get("accion") or "").strip().lower().replace(" ", "_")
    if action not in ACTIONS:
        return Step("no_puedo", note=f"acción rara {action!r}")
    point = None
    x, y = data.get("x"), data.get("y")
    p = data.get("punto")
    if not (isinstance(x, (int, float)) and isinstance(y, (int, float))) and isinstance(p, (list, tuple)) and len(p) == 2:
        y, x = p
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        point = (max(0.0, min(1000.0, float(y))), max(0.0, min(1000.0, float(x))))
    try:
        amount = int(data.get("cantidad") or 0)
    except (TypeError, ValueError):
        amount = 0
    return Step(action, point, str(data.get("texto") or "")[:300], str(data.get("tecla") or "").lower()[:30], max(-10, min(10, amount)), str(data.get("nota") or "")[:160])


def repeated(a: Step, b: Step) -> bool:
    if a.action != b.action:
        return False
    if a.point is None or b.point is None:
        return a.action in ("escribir", "tecla") and (a.text, a.key) == (b.text, b.key)
    return abs(a.point[0] - b.point[0]) < 20 and abs(a.point[1] - b.point[1]) < 20


def thumb(image: bytes) -> Any:
    try:
        from PIL import Image

        return Image.open(io.BytesIO(image)).convert("L").resize((64, 40))
    except Exception:
        return None


def same(a: Any, b: Any) -> bool:
    from PIL import ImageChops, ImageStat

    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0] < 1.5


def to_screen(shot: Shot, point: tuple[float, float]) -> tuple[int, int]:
    y, x = point
    return shot.left + round(x / 1000 * shot.width), shot.top + round(y / 1000 * shot.height)


class Hands:
    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.wt = wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    def alive(self, hwnd: int) -> bool:
        return bool(self.user32.IsWindow(hwnd))

    def foreground(self) -> int:
        return int(self.user32.GetForegroundWindow() or 0)

    def title(self, hwnd: int) -> str:
        buf = self.ctypes.create_unicode_buffer(300)
        self.user32.GetWindowTextW(hwnd, buf, 300)
        return buf.value

    def shot(self, hwnd: int) -> Shot:
        from PIL import ImageGrab

        r = self.wt.RECT()
        self.user32.GetWindowRect(hwnd, self.ctypes.byref(r))
        left, top, right, bottom = r.left + 7, r.top, r.right - 7, r.bottom - 7
        img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True).convert("RGB")
        img.thumbnail((1280, 1280))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        return Shot(buf.getvalue(), left, top, right - left, bottom - top)

    def cursor(self) -> tuple[int, int]:
        p = self.wt.POINT()
        self.user32.GetCursorPos(self.ctypes.byref(p))
        return p.x, p.y

    def click(self, x: int, y: int, double: bool = False) -> None:
        back = self.cursor()
        self.user32.SetCursorPos(x, y)
        time.sleep(0.05)
        for _ in range(2 if double else 1):
            self.user32.mouse_event(0x0002, 0, 0, 0, 0)
            self.user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.06)
        time.sleep(0.05)
        self.user32.SetCursorPos(*back)

    def scroll(self, x: int, y: int, amount: int) -> None:
        back = self.cursor()
        self.user32.SetCursorPos(x, y)
        time.sleep(0.05)
        self.user32.mouse_event(0x0800, 0, 0, amount * 120, 0)
        time.sleep(0.05)
        self.user32.SetCursorPos(*back)

    def key(self, combo: str) -> None:
        codes = []
        for part in combo.replace(" ", "").split("+"):
            if part in KEYS:
                codes.append(KEYS[part])
            elif len(part) == 1 and part.isalnum():
                codes.append(ord(part.upper()))
        for c in codes:
            self.user32.keybd_event(c, 0, 0, 0)
        for c in reversed(codes):
            self.user32.keybd_event(c, 0, 2, 0)

    def write(self, text: str) -> None:
        ctypes = self.ctypes

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("ki", KEYBDINPUT), ("pad", ctypes.c_ubyte * 8)]

        for ch in text:
            for flags in (0x0004, 0x0004 | 0x0002):
                inp = INPUT(1, KEYBDINPUT(0, ord(ch), flags, 0, 0))
                self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            time.sleep(0.01)


See = Callable[[bytes, str], Awaitable[str]]


@dataclass
class DesktopAgent:
    hands: Any
    see: See
    focus: Callable[[int], None]
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep
    max_steps: int = 10
    done_when: Callable[[str], bool] | None = None
    verify: See | None = None
    log: list[str] = field(default_factory=list)

    async def call(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    async def run(self, hwnd: int, goal: str) -> tuple[bool, str]:
        history: list[str] = []
        before = None
        last: Step | None = None
        repeats = 0
        await self.call(self.focus, hwnd)
        await self.sleep(0.4)
        for _ in range(self.max_steps):
            if not self.hands.alive(hwnd):
                return False, "se cerró la ventana"
            title = self.hands.title(hwnd)
            if self.done_when is not None and history and self.done_when(title):
                return True, title
            shot = await self.call(self.hands.shot, hwnd)
            now = thumb(shot.image)
            changed = "\nOJO: la pantalla NO cambió con tu último paso." if history and before is not None and now is not None and same(before, now) else ""
            before = now
            prompt = PROMPT.format(goal=goal, title=title, history="; ".join(history[-6:]) or "ninguno", acciones="|".join(ACTIONS), changed=changed)
            step = parse_step(await self.see(shot.image, prompt))
            log.info("paso %s %s %s", step.action, step.point, step.note)
            self.log.append(f"{step.action} {step.point} {step.note}")
            if step.action == "listo":
                ok, why = parse_verdict(await self.check(shot.image, VERIFY.format(goal=goal)))
                log.info("verificación %s: %s", ok, why)
                if ok:
                    return True, why or step.note or title
                history.append(f"dijiste listo pero NO se cumple: {why}")
                continue
            if step.action == "no_puedo":
                return False, step.note or "no pude"
            if last is not None and repeated(last, step):
                repeats += 1
                ok, why = parse_verdict(await self.check(shot.image, VERIFY.format(goal=goal)))
                log.info("paso repetido, verificación %s: %s", ok, why)
                if ok:
                    return True, why or title
                if repeats >= 2:
                    return False, f"me atoré repitiendo lo mismo ({why})"
                history.append(f"repetiste el mismo paso y NO se cumple ({why}); cambia de estrategia")
                last = None
                continue
            last = step
            if DANGER.search(f"{step.note} {step.text}"):
                return False, "eso parece pagar, comprar o borrar algo; te lo dejo a ti"
            await self.act(shot, step, hwnd)
            await self.sleep(0.6)
            front = getattr(self.hands, "foreground", None)
            if front is not None and front() not in (0, hwnd):
                await self.call(self.focus, hwnd)
                history.append("ese paso abrió otra ventana; regresé a la app, no lo repitas")
                continue
            where = f" en x={round(step.point[1])} y={round(step.point[0])}" if step.point else ""
            history.append(f"{step.action}{where} ({step.note})")
            await self.sleep(1.2)
        if self.done_when is not None and self.done_when(self.hands.title(hwnd)):
            return True, self.hands.title(hwnd)
        return False, f"le di {self.max_steps} pasos y no terminé"

    async def check(self, image: bytes, prompt: str) -> str:
        if self.verify is not None:
            try:
                return await asyncio.wait_for(self.verify(image, prompt), 15)
            except Exception as e:
                log.info("verificación fuerte falló: %r", e)
        return await self.see(image, prompt)

    async def act(self, shot: Shot, step: Step, hwnd: int = 0) -> None:
        front = getattr(self.hands, "foreground", None)
        if step.action in ("escribir", "tecla") and front is not None and hwnd and front() != hwnd:
            await self.call(self.focus, hwnd)
        if step.action in ("click", "doble_click", "scroll") and step.point is None:
            return
        if step.action in ("click", "doble_click"):
            x, y = to_screen(shot, step.point)
            await self.call(self.hands.click, x, y, step.action == "doble_click")
        elif step.action == "scroll":
            x, y = to_screen(shot, step.point)
            await self.call(self.hands.scroll, x, y, step.amount or -3)
        elif step.action == "escribir" and step.text:
            await self.call(self.hands.write, step.text)
        elif step.action == "tecla" and step.key:
            await self.call(self.hands.key, step.key)
        elif step.action == "esperar":
            await self.sleep(1.5)
