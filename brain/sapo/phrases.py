import re
import unicodedata
from collections import deque
from collections.abc import Iterable
from difflib import SequenceMatcher

STOP = {
    "a", "al", "de", "del", "el", "la", "las", "lo", "los", "un", "una", "y", "o", "que", "en", "te", "me", "se",
    "es", "ya", "no", "si", "tu", "mi", "con", "por", "pa", "para", "eh", "ay", "oye", "pues",
}


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9ñ]+", t))


def content_words(text: str) -> set[str]:
    return {w for w in normalize(text).split() if w not in STOP and len(w) > 2}


def similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    wa, wb = content_words(a), content_words(b)
    jaccard = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    return max(ratio, jaccard)


class RecentPhrases:
    def __init__(self, size: int = 50, threshold: float = 0.72, seed: Iterable[str] = ()):
        self.items: deque[str] = deque(maxlen=size)
        self.threshold = threshold
        for text in seed:
            self.add(text)

    def add(self, text: str) -> None:
        if normalize(text):
            self.items.append(text)

    def match(self, text: str) -> str | None:
        best, score = None, 0.0
        for old in self.items:
            s = similarity(text, old)
            if s > score:
                best, score = old, s
        return best if score >= self.threshold else None

    def repeats(self, text: str) -> bool:
        return self.match(text) is not None


def word_count(text: str) -> int:
    return len(normalize(text).split())
