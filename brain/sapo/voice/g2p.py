import re
import unicodedata

VOWELS = "aeiouáéíóúü"
STRONG = "aeoáéóíú"
ACCENT = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"}
UNSTRESSED = frozenset(
    "el la los las lo le les de del a al en y e o u ni que se me te nos os mi mis tu tus su sus un con por sin si cuando como donde pero mas".split()
)
UNITS = "cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciseis diecisiete dieciocho diecinueve veinte veintiuno veintidos veintitres veinticuatro veinticinco veintiseis veintisiete veintiocho veintinueve".split()
TENS = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
HUNDREDS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}
PAUSES = ",.!?;:"
SOFT = {"b": "β", "d": "ð", "g": "ɣ"}


def number(n: int) -> str:
    if n < 30:
        return UNITS[n]
    if n < 100:
        tens, unit = divmod(n, 10)
        return TENS[tens] + (f" y {UNITS[unit]}" if unit else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        if n == 100:
            return "cien"
        return HUNDREDS[hundreds] + (f" {number(rest)}" if rest else "")
    if n < 1_000_000:
        thousands, rest = divmod(n, 1000)
        head = "mil" if thousands == 1 else f"{number(thousands)} mil"
        return head + (f" {number(rest)}" if rest else "")
    return " ".join(UNITS[int(d)] for d in str(n))


def clean(text: str) -> str:
    text = text.lower().replace("%", " por ciento")
    text = re.sub(r"(\d+):(\d{2})", lambda m: f"{m.group(1)} y {int(m.group(2))}" if int(m.group(2)) else m.group(1), text)
    text = re.sub(r"\d+", lambda m: f" {number(int(m.group()))} ", text)
    text = "".join(c for c in text if c.isalpha() or c.isspace() or c in PAUSES or unicodedata.category(c) == "Mn")
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s*([,.!?;:])\s*", r" \1 ", text)
    return " ".join(text.split())


def nuclei(word: str) -> list[tuple[int, int]]:
    spans = []
    i = 0
    while i < len(word):
        if word[i] in VOWELS and not (word[i] == "u" and i > 0 and word[i - 1] in "qg" and i + 1 < len(word) and word[i + 1] in "eiéí"):
            j = i + 1
            while j < len(word) and word[j] in VOWELS and not (word[j - 1] in STRONG and word[j] in STRONG) and word[j] not in "íú" and word[j - 1] not in "íú":
                j += 1
            spans.append((i, j))
            i = j
        else:
            i += 1
    return spans


def stressed(word: str, spans: list[tuple[int, int]]) -> int | None:
    if not spans or (len(spans) == 1 and word in UNSTRESSED):
        return None
    for k, (a, b) in enumerate(spans):
        if any(c in "áéíóú" for c in word[a:b]):
            return k
    if len(spans) == 1:
        return 0
    return len(spans) - 2 if word[-1] in "aeiouns" else len(spans) - 1


def word_phonemes(word: str) -> list[str]:
    spans = nuclei(word)
    stress = stressed(word, spans)
    marks = {}
    for k, (a, b) in enumerate(spans):
        if k == stress:
            pos = next((p for p in range(a, b) if word[p] in "áéíóú"), None)
            if pos is None:
                pos = next((p for p in range(a, b) if word[p] in STRONG), a)
            marks[pos] = True
    out: list[str] = []
    i = 0
    n = len(word)
    while i < n:
        c = word[i]
        nxt = word[i + 1] if i + 1 < n else ""
        if i in marks:
            out.append("ˈ")
        if c in VOWELS:
            v = ACCENT.get(c, c)
            if c in "iu" and i not in marks and (nxt in VOWELS and nxt not in "iu"):
                v = "j" if c == "i" else "w"
            if c == "u" and i > 0 and word[i - 1] in "qg" and nxt in "eiéí":
                i += 1
                continue
            out.append(v)
        elif c == "c":
            if nxt == "h":
                out.append("ʧ")
                i += 1
            elif nxt in "eiéí":
                out.append("s")
            else:
                out.append("k")
        elif c == "q":
            out.append("k")
        elif c == "g":
            out.append("x" if nxt in "eiéí" else "g")
        elif c == "j":
            out.append("x")
        elif c == "h":
            pass
        elif c == "l" and nxt == "l":
            out.append("ʝ")
            i += 1
        elif c == "y":
            out.append("i" if not nxt or nxt not in VOWELS else "ʝ")
        elif c == "ñ":
            out.append("ɲ")
        elif c in "zs":
            out.append("s")
        elif c == "v":
            out.append("b")
        elif c == "x":
            out.extend(["k", "s"])
        elif c == "w":
            out.append("w")
        elif c == "r":
            if nxt == "r":
                out.append("r")
                i += 1
            elif i == 0 or word[i - 1] in "lns":
                out.append("r")
            else:
                out.append("ɾ")
        elif c.isalpha():
            out.append(c)
        i += 1
    return out


def soften(tokens: list[str]) -> list[str]:
    out: list[str] = []
    prev = ""
    for t in tokens:
        if t in SOFT and prev and prev in "aeiouɾrsjw" and not (t == "d" and prev == "l"):
            out.append(SOFT[t])
        else:
            out.append(t)
        if t not in ("ˈ", " "):
            prev = t if t not in PAUSES else ""
    return out


def phonemize(text: str) -> list[list[str]]:
    sentences: list[list[str]] = []
    current: list[str] = []
    for word in clean(text).split():
        if word in PAUSES:
            if current and current[-1] == " ":
                current.pop()
            current.append(word)
            if word in ".!?":
                sentences.append(current)
                current = []
            else:
                current.append(" ")
            continue
        current.extend(word_phonemes(word))
        current.append(" ")
    while current and current[-1] == " ":
        current.pop()
    if current:
        sentences.append(current)
    return [soften(s) for s in sentences if any(t not in PAUSES and t != " " for t in s)]
