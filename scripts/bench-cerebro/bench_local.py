"""Mide TTFT y tok/s de modelos Ollama locales (streaming, think=false). Uso: python bench_local.py qwen3.5:4b"""
import json, sys, time, urllib.request

URL = "http://127.0.0.1:11434/api/chat"
SYSTEM = ("Eres Sapo, asistente de escritorio con personalidad de sapito sarcástico mexicano. "
          "REGLA 1: primero da la respuesta CORRECTA y exacta (datos, cuentas, consejos útiles). REGLA 2: luego, si quieres, una burla corta y amable. Nunca inventes ni te niegues. Si piden una acción en la PC, usa la herramienta. Máximo 2 frases, español de México.")
PROMPTS = [
    "¿Cuál es la capital de Australia?",
    "¿Cuánto es 17 por 23?",
    "Dame un consejo rápido para dormir mejor.",
    "¿Quién pintó La noche estrellada?",
]
TOOLS = [{"type": "function", "function": {
    "name": "abrir_app", "description": "Abre una aplicación en la PC",
    "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {
    "name": "subir_volumen", "description": "Cambia el volumen del sistema (0-100)",
    "parameters": {"type": "object", "properties": {"nivel": {"type": "integer"}}, "required": ["nivel"]}}}]


def chat(model, prompt, tools=None, stream=True):
    body = {"model": model, "stream": stream, "think": False, "keep_alive": "10m",
            "options": {"num_ctx": 4096, "num_predict": 120, "temperature": 0.6},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter(); ttft = None; text = ""; calls = None; last = {}
    with urllib.request.urlopen(req, timeout=300) as r:
        for line in r:
            if not line.strip():
                continue
            d = json.loads(line)
            msg = d.get("message", {})
            if ttft is None and (msg.get("content") or msg.get("tool_calls")):
                ttft = time.perf_counter() - t0
            text += msg.get("content", "")
            if msg.get("tool_calls"):
                calls = msg["tool_calls"]
            if d.get("done"):
                last = d
    total = time.perf_counter() - t0
    tps = last.get("eval_count", 0) / (last.get("eval_duration", 1) / 1e9) if last.get("eval_duration") else 0
    return ttft, total, tps, text.strip(), calls, last.get("load_duration", 0) / 1e9


for model in sys.argv[1:]:
    print(f"\n=== {model} ===")
    ttft, total, tps, text, _, load = chat(model, "Hola")  # carga en frío
    print(f"carga en frío: total {total:.2f}s (load {load:.2f}s)")
    for p in PROMPTS:
        ttft, total, tps, text, _, load = chat(model, p)
        print(f"TTFT {ttft*1000:.0f} ms | total {total:.2f}s | {tps:.0f} tok/s | {p} -> {text[:140]!r}")
    for p in ["Abre Spotify", "Pon el volumen al 30"]:
        ttft, total, tps, text, calls, _ = chat(model, p, tools=TOOLS, stream=False)
        print(f"TOOLS total {total:.2f}s | {p} -> {json.dumps(calls, ensure_ascii=False) if calls else text[:100]}")
