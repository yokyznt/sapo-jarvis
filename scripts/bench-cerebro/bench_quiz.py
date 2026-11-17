"""Mini-examen de cultura general/cuentas en español (auto-calificado por subcadena)."""
import json, sys, time, urllib.request, unicodedata
exec(open("bench_local.py", encoding="utf-8").read().split("def chat")[0])

Q = [("¿Cuál es la capital de Australia?", ["canberra"]),
     ("¿Cuánto es 17 por 23?", ["391"]),
     ("¿Quién pintó La noche estrellada?", ["van gogh"]),
     ("¿En qué año cayó el Muro de Berlín?", ["1989"]),
     ("¿Cuál es el planeta más grande del sistema solar?", ["jupiter"]),
     ("¿Cuánto es el 15% de 840?", ["126"]),
     ("¿Quién escribió Cien años de soledad?", ["garcia marquez"]),
     ("¿Cuál es el río más largo de México?", ["bravo", "grande"]),
     ("¿Cuántos huesos tiene un adulto humano?", ["206"]),
     ("Si salgo a las 3:45 pm y el viaje dura 2 horas 30 minutos, ¿a qué hora llego?", ["6:15", "18:15"]),
     ("¿Cuál es la fórmula química del agua?", ["h2o", "h₂o"]),
     ("¿Quién fue el primer presidente de México?", ["guadalupe victoria"]),
     ("¿Cuánto es 144 entre 12 más 7 por 3?", ["33"]),
     ("¿Qué gas absorben las plantas en la fotosíntesis?", ["co2", "dioxido de carbono", "co₂"]),
     ("¿En qué continente está Egipto?", ["africa"])]

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").replace("*", "")

for model in sys.argv[1:]:
    ok = 0; t = []
    for q, ans in Q:
        body = {"model": model, "stream": False, "think": False, "keep_alive": "10m",
                "options": {"num_ctx": 4096, "num_predict": 150, "temperature": 0.3},
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}]}
        t0 = time.perf_counter()
        d = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/chat",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=120))
        t.append(time.perf_counter() - t0)
        txt = d["message"]["content"]
        good = any(a in norm(txt) for a in ans)
        ok += good
        if not good:
            print(f"  MAL {q!r} -> {txt[:110]!r}")
    print(f"{model}: {ok}/{len(Q)} correctas, total medio {sum(t)/len(t):.2f}s")
