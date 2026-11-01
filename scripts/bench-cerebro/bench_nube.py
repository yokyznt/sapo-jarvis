"""Mide TTFT (primer token) y tiempo total de APIs gratis con streaming.

Uso (las llaves se leen de variables de entorno; si falta una, ese proveedor se salta):
    GEMINI_API_KEY=... GROQ_API_KEY=... python bench_nube.py
No imprime llaves. Cada corrida gasta ~4 peticiones por modelo de tu cuota diaria.
"""
import json, os, time, urllib.request, urllib.error

SYSTEM = ("Eres Sapo, sapito sarcástico mexicano de escritorio. Primero da la respuesta correcta; "
          "luego, si quieres, una burla corta. Máximo 2 frases.")
PROMPTS = ["¿Cuál es la capital de Australia?", "¿Cuánto es el 15% de 840?",
           "Dame un consejo rápido para dormir mejor.", "¿Quién escribió Cien años de soledad?"]


def stream(req):
    t0 = time.perf_counter(); ttft = None; text = ""
    with urllib.request.urlopen(req, timeout=30) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:") or line.endswith("[DONE]"):
                continue
            chunk = extract(json.loads(line[5:]))
            if chunk and ttft is None:
                ttft = time.perf_counter() - t0
            text += chunk
    return ttft or 0.0, time.perf_counter() - t0, text.strip()


def extract(d):
    if "choices" in d:  # OpenAI-compatible (Groq, Cerebras, OpenRouter, NVIDIA, Mistral)
        return (d["choices"][0].get("delta") or {}).get("content") or "" if d["choices"] else ""
    parts = ((d.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def gemini(model, prompt, key):
    gen = {"maxOutputTokens": 150, "temperature": 0.6}
    gen["thinkingConfig"] = {"thinkingLevel": "minimal"}
    body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
    return urllib.request.Request(url, data=json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json", "x-goog-api-key": key})


def openai_like(base, model, prompt, key, extra=None):
    body = {"model": model, "stream": True, "max_tokens": 200, "temperature": 0.6,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
    body.update(extra or {})
    return urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})


CASES = [
    ("GEMINI_API_KEY", "gemini-3.5-flash-lite", lambda m, p, k: gemini(m, p, k)),
    ("GEMINI_API_KEY", "gemma-4-26b-a4b-it", lambda m, p, k: gemini(m, p, k)),
    ("GROQ_API_KEY", "openai/gpt-oss-20b",
     lambda m, p, k: openai_like("https://api.groq.com/openai/v1", m, p, k, {"reasoning_effort": "low"})),
    ("GROQ_API_KEY", "qwen/qwen3.8-27b",
     lambda m, p, k: openai_like("https://api.groq.com/openai/v1", m, p, k, {"reasoning_effort": "none"})),
]

for env, model, build in CASES:
    key = os.environ.get(env)
    if not key:
        print(f"-- {model}: sin {env}, me lo salto")
        continue
    print(f"=== {model} ===")
    for p in PROMPTS:
        try:
            ttft, total, text = stream(build(model, p, key))
            print(f"TTFT {ttft*1000:.0f} ms | total {total:.2f}s | {p} -> {text[:100]!r}")
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code} en {p!r}: {e.read()[:160]!r}")
        except Exception as e:  # timeouts, red
            print(f"error en {p!r}: {e}")
