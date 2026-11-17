import math
import re
import unicodedata

OPS = [
    ("dividido entre", "/"),
    ("dividido por", "/"),
    ("multiplicado por", "*"),
    ("elevado a la", "^"),
    ("elevado a", "^"),
    ("entre", "/"),
    ("sobre", "/"),
    ("por", "*"),
    ("mas", "+"),
    ("menos", "-"),
]
SYMBOLS = {"×": "*", "x": "*", "÷": "/", ":": "/", "*": "*", "/": "/", "+": "+", "-": "-", "^": "^"}
NUM = r"\d+(?:[.,]\d+)?"
PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 3}
SHOW = {"+": "+", "-": "−", "*": "×", "/": "÷", "^": "^"}


def plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def number(raw: str) -> float:
    return float(raw.replace(",", "."))


def fmt(value: float) -> str:
    if math.isfinite(value) and abs(value - round(value)) < 1e-9 and abs(value) < 1e15:
        return f"{int(round(value)):,}".replace(",", " ")
    return f"{value:.6g}".replace(".", ",") if abs(value) < 1e15 else f"{value:.4g}"


def tokens(expr: str) -> list[str] | None:
    s = expr
    for word, sym in OPS:
        s = re.sub(rf"\b{word}\b", f" {sym} ", s)
    s = re.sub(rf"(?<=\d)\s*x\s*(?=\d)", " * ", s)
    out: list[str] = []
    for m in re.finditer(rf"{NUM}|[()+\-*/^×÷:]|\S+", s):
        t = m.group(0)
        if re.fullmatch(NUM, t) or t in "()":
            out.append(t)
        elif t in SYMBOLS:
            out.append(SYMBOLS[t])
        else:
            return None
    return out


def evaluate(toks: list[str]) -> float | None:
    output: list[float] = []
    stack: list[str] = []

    def apply() -> bool:
        op = stack.pop()
        if op == "(" or len(output) < 2:
            return False
        b, a = output.pop(), output.pop()
        if op == "/" and b == 0:
            return False
        if op == "^" and (abs(b) > 64 or abs(a) > 1e6):
            return False
        output.append({"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else 0.0, "^": a ** b if op == "^" else 0.0}[op])
        return True

    prev = None
    for t in toks:
        if re.fullmatch(NUM, t):
            if prev is not None and (re.fullmatch(NUM, prev) or prev == ")"):
                return None
            output.append(number(t))
        elif t == "(":
            stack.append(t)
        elif t == ")":
            while stack and stack[-1] != "(":
                if not apply():
                    return None
            if not stack:
                return None
            stack.pop()
        else:
            if t == "-" and (prev is None or prev in PREC or prev == "("):
                output.append(0.0)
            while stack and stack[-1] != "(" and (PREC[stack[-1]] > PREC[t] or (PREC[stack[-1]] == PREC[t] and t != "^")):
                if not apply():
                    return None
            stack.append(t)
        prev = t
    while stack:
        if stack[-1] == "(" or not apply():
            return None
    if len(output) != 1:
        return None
    return output[0]


def arithmetic(text: str) -> str | None:
    s = plain(text)
    m = re.search(rf"({NUM})\s*(?:%|por ciento)\s+de\s+({NUM})", s)
    if m:
        a, b = number(m.group(1)), number(m.group(2))
        return f"{fmt(a)} % de {fmt(b)} = {fmt(a * b / 100)}"
    m = re.search(rf"raiz(?: cuadrada)? de\s+({NUM})", s)
    if m:
        a = number(m.group(1))
        return f"√{fmt(a)} = {fmt(math.sqrt(a))}"
    m = re.search(rf"({NUM})\s+al cuadrado", s)
    if m:
        a = number(m.group(1))
        return f"{fmt(a)}² = {fmt(a * a)}"
    m = re.search(rf"({NUM})\s+al cubo", s)
    if m:
        a = number(m.group(1))
        return f"{fmt(a)}³ = {fmt(a ** 3)}"
    words = "|".join(re.escape(w) for w, _ in OPS)
    pattern = rf"[(\s]*-?\s*{NUM}(?:\s*(?:{words}|[+\-*/^×÷:]|(?<=\d)\s*x(?=\s*\d))\s*[(\s]*-?\s*{NUM}[)\s]*)+"
    best = None
    for m in re.finditer(pattern, s):
        chunk = m.group(0).strip()
        if best is None or len(chunk) > len(best):
            best = chunk
    if best is None:
        return None
    if re.fullmatch(r"\d{1,2}\s*[:/-]\s*\d{1,2}(\s*[/-]\s*\d{2,4})?", best):
        return None
    toks = tokens(best)
    if not toks or sum(1 for t in toks if t in PREC) == 0:
        return None
    value = evaluate(toks)
    if value is None:
        return None
    shown = " ".join(SHOW.get(t, t.replace(".", ",")) for t in toks).replace("( ", "(").replace(" )", ")")
    return f"{shown} = {fmt(value)}"


def verified(text: str) -> str | None:
    calc = arithmetic(text)
    if calc is None:
        return None
    return f"Dato verificado (úsalo tal cual, no lo recalcules): {calc}"


ASK = re.compile(
    r"^\s*(?:oye\s+|sapo\s+|oye sapo\s+)?(?:que|quien|quienes|cual|cuales|cuanto|cuanta|cuantos|cuantas|como|donde|cuando|por que|porque|para que|de que|en que|dime|explica|explicame|recomienda|recomiendame|sabes|define|traduce|calcula|cuentame|me puedes decir|me dices)\b"
)


def asks_fact(text: str) -> bool:
    s = plain(text).strip()
    if not s:
        return False
    if "?" in text or "¿" in text:
        return True
    return bool(ASK.match(s))
