import re

from .pc import norm

PLAY = re.compile(r"\b(pon|ponme|ponle|pone|pones|pongas|reproduce|reproduceme|reproducir|toca|tocame|quiero escuchar|escuchar|play)\b")
STRONG = re.compile(r"\b(reproduce|reproduceme|reproducir|tocame|quiero escuchar|play)\b")
MUSICAL = re.compile(r"\b(cancion|canciones|rola|rolas|musica|tema|album|disco|playlist|spotify|youtube|de|del)\b")
NOT_MUSIC = re.compile(r"\b(temporizador|alarma|recordatorio|timer|volumen|siguiente|anterior|pausa|pausala|sigue|continua|video de|captura|nota|clima)\b")
NOISE = [
    r"\b(oye sapo|oye|sapo|sapito|porfa|por favor|bueno|eh|este|ahorita|ahora|rapido)\b",
    r"\babre (spotify|youtube)( y)?\b",
    r"\b(en|desde|por|con) (el )?(spotify|youtube)\b",
    r"\b(spotify|youtube)\b",
    r"\b(pon|ponme|ponle|pone|pones|pongas|reproduce|reproduceme|reproducir|toca|tocame|quiero escuchar|escuchar|play|quiero|puedes|podrias)\b",
    r"\b(una|la|el|alguna|algo|unas|un|otra|las|los|mi)? ?(cancion|canciones|rola|rolas|musica|tema|temas)( de| del)?\b",
    r"\balgo (de|del)\b",
]


def platform(text: str) -> str:
    s = norm(text)
    if "youtube" in s:
        return "youtube"
    if "spotify" in s:
        return "spotify"
    return ""


def music(text: str) -> dict | None:
    s = norm(text)
    if not PLAY.search(s) or NOT_MUSIC.search(s) or not (MUSICAL.search(s) or STRONG.search(s)):
        return None
    q = s
    for pattern in NOISE:
        q = re.sub(pattern, " ", q)
    q = re.sub(r"^\s*(y|de|del|a)\s+", " ", " ".join(q.split()))
    q = re.sub(r"\s+(y|de|del|en|a)\s*$", " ", q)
    q = " ".join(q.split())
    if len(q) < 2:
        return None
    return {"query": q, "where": platform(text)}


CONTROLS = (
    ("next", re.compile(r"\b(siguiente|la que sigue|otra cancion|otra rola|cambiale|salta(la)?|skip)\b")),
    ("previous", re.compile(r"\b(anterior|la de antes|regresa la (cancion|rola))\b")),
    ("stop", re.compile(r"\b(pausa(la)?|pausar|pausale|para la (musica|cancion|rola)|deten(la)?|quita la (musica|cancion|rola)|apaga la (musica|cancion|rola)|silencio)\b")),
    ("resume", re.compile(r"\b(sigue|continua|reanuda|quitale la pausa|quita la pausa|dale play|ponle play|play)\b")),
)
SHORT = re.compile(r"\b(musica|cancion|rola|spotify|pausa|siguiente|anterior|play)\b")


def control(text: str) -> str | None:
    s = norm(text)
    if len(s.split()) > 8 or music(text) is not None:
        return None
    for action, pattern in CONTROLS:
        if pattern.search(s) and (SHORT.search(s) or len(s.split()) <= 3):
            return action
    return None
