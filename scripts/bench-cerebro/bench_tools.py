"""Tasa de llamadas a herramientas correctas (10 órdenes x modelo), think=false."""
import json, sys, time, urllib.request
_src = open("bench_local.py", encoding="utf-8").read().split("def chat")[0]
exec(_src)

TOOLS = TOOLS + [{"type": "function", "function": {
    "name": "buscar_web", "description": "Busca algo en internet (noticias, clima, precios de hoy)",
    "parameters": {"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]}}}]
CASES = [("Abre Spotify", "abrir_app"), ("Pon el volumen al 30", "subir_volumen"),
         ("ábreme el bloc de notas", "abrir_app"), ("bájale al volumen a 10 porfa", "subir_volumen"),
         ("¿cómo va a estar el clima mañana en Monterrey?", "buscar_web"), ("abre discord", "abrir_app"),
         ("sube todo el volumen", "subir_volumen"), ("¿a cuánto está el dólar hoy?", "buscar_web"),
         ("¿cuánto es 12 al cuadrado?", None), ("cuéntame un chiste", None)]
for model in sys.argv[1:]:
    ok = 0; times = []
    for prompt, want in CASES:
        body = {"model": model, "stream": False, "think": False, "keep_alive": "10m", "tools": TOOLS,
                "options": {"num_ctx": 4096, "num_predict": 120, "temperature": 0.2},
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
        t0 = time.perf_counter()
        d = json.load(urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}), timeout=120))
        times.append(time.perf_counter() - t0)
        calls = d["message"].get("tool_calls") or []
        got = calls[0]["function"]["name"] if calls else None
        good = got == want
        ok += good
        print(f"  {'OK ' if good else 'MAL'} {prompt!r}: quería {want}, dio {got} {json.dumps(calls[0]['function']['arguments'], ensure_ascii=False) if calls else d['message']['content'][:60]!r}")
    print(f"{model}: {ok}/{len(CASES)} correctas, latencia media {sum(times)/len(times):.2f}s")
