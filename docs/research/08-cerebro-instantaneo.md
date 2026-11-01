# 08 · Cerebro instantáneo, ilimitado y coherente

> Investigación: 31-oct-2026. Hardware: RTX 5060 Ti **8 GB**, i7-12700, 32 GB RAM, Ollama 0.40.11.
> Continúa [03-cerebro-ia.md](03-cerebro-ia.md). Meta: **primer token < 500 ms**, respuesta corta **< 1.5 s**, **200–500 mensajes/día sin tope**, español mexicano coherente y *function calling*.
> Etiquetas: **[P]** fuente primaria (doc oficial) · **[S]** secundaria (blog o medición de terceros; verifícala) · **[M]** medido en esta PC el 31-oct-2026 con los scripts de [`scripts/bench-cerebro/`](../../scripts/bench-cerebro/).

---

## 0. Veredicto corto

| Rol | Elección | Por qué |
|---|---|---|
| **Primario (siempre)** | **Local `qwen3.5:4b`** (Q4_K_M, la etiqueta por defecto) en Ollama, cargado todo el tiempo, `think:false`, **streaming** | **[M]** primer token en **68–133 ms**, ~92 tok/s, respuesta corta completa en **0.25–0.7 s**. 13–14 de 15 en el examen de cultura general. Sin cuota: ilimitado de verdad. |
| **Herramientas** | Mismo `qwen3.5:4b`, pero en una **pasada aparte con un prompt neutral** (sin personalidad) | **[M]** 10/10 llamadas correctas con prompt neutral contra **5/10** con el prompt sarcástico: con personaje, el modelo *finge* que ya lo hizo (“Ya abrí Spotify”) y no llama la herramienta. |
| **Respaldo nube 1** | **Gemma 4 26B-A4B** (`gemma-4-26b-a4b-it`) en la API de Gemini, `thinkingLevel: minimal` | Gratis [P]; soporta tools e imágenes [P]; ~**14 400 RPD / 30 RPM / 16K TPM** en la capa gratis [S]. Es la cuota alta de Google. |
| **Respaldo nube 2** | **Groq `openai/gpt-oss-20b`** (`reasoning_effort: low`) | 30 RPM, 1 000 RPD, 8K TPM y **200K tokens/día** [P]; ~1 000 tok/s [P]; tools sí [P]; sin tarjeta. |
| **Respaldo nube 3** | `gemini-3.5-flash-lite` | 15 RPM y **~500 RPD** [S]. Úsalo solo cuando falle lo demás. |
| **Quitar** | `gemini-flash-latest` / `gemini-3.x-flash` como principal | Capa gratis de **~5 RPM y 20 RPD** [S]: se acaba en minutos. Explica los 503/429 y timeouts. |
| **Mientras juegas** | Descargar el modelo de la GPU (`keep_alive:0`) y pasar a la nube (Gemma 4 → Groq) | Con el 4b cargado, la VRAM usada llega a ~4.7 GB (3.1 GB del modelo + 1.6 GB del escritorio) [M]. En CPU el 2b es lento y alucina (ver §2.4). |

**Idea central:** lo “instantáneo” e “ilimitado” solo lo da el modelo local. Ninguna API gratis garantiza 500 mensajes al día con primer token < 500 ms. La nube queda como respaldo y para escalar preguntas difíciles.

---

## 1. APIs gratis (estado al 31-oct-2026)

| Proveedor | Modelos útiles (chat ES + tools) | Límites capa gratis | ¿Ilimitado para 200–500 msgs/día? | Tools | ¿Tarjeta? | Notas |
|---|---|---|---|---|---|---|
| **Google Gemini API** | `gemma-4-26b-a4b-it`, `gemma-4-31b-it`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.8-flash`, `gemini-3.6-flash` | Google **ya no publica** las cifras por modelo: están en el panel de AI Studio de cada proyecto [P: [rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)]. Medición de terceros: Gemma 4 **30 RPM / 14 400 RPD / 16K TPM**; Flash-Lite 3.x **15 RPM / 500 RPD**; Flash 3.5–3.7 **5 RPM / 20 RPD** [S: [naveencreation/gemini-free-tier-limits](https://github.com/naveencreation/gemini-free-tier-limits)] | **Gemma 4 sí** (vigila los 16K TPM: unas 8 peticiones/min con prompts de 2K). Flash-Lite casi (500). Flash **no**. | Sí, incluido Gemma 4 [P: [Gemma en Gemini API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api)] | No [P: [pricing](https://ai.google.dev/gemini-api/docs/pricing)] | Límites **por proyecto**, no por llave; el RPD se reinicia a medianoche del Pacífico [P]. Capa gratis = **Google usa tus datos** para mejorar productos [P: pricing]. Gemini 4 Argon y 3.1 Pro no están en la capa gratis [P]. TTFT de 3.5 Flash-Lite: **6.59 s** según AA (con razonamiento y prompt largo) [S: [AA](https://artificialanalysis.ai/models/gemini-3-5-flash-lite)]; mídelo con `thinkingLevel: minimal`. |
| **Groq** | `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b` | **30 RPM, 1K RPD, 8K TPM, 200K TPD** por modelo [P: [rate-limits](https://console.groq.com/docs/rate-limits)]. Llama 3.1 8B y 3.3 70B ahora son solo Enterprise [P: [models](https://console.groq.com/docs/models)] | **Sí si sumas modelos**: son 200K tokens/día **por modelo**. Con prompts de ~1.5K tokens salen ~130 msgs/día por modelo, y los tokens en caché **no cuentan** [P]. Con 3 modelos y caché pasas los 400. | Sí, todos [P: [tool-use](https://console.groq.com/docs/tool-use/overview)] | No | gpt-oss-20b ~1 000 tok/s [P]. Caché de prompt solo en gpt-oss [P: [prompt-caching](https://console.groq.com/docs/prompt-caching)]: pon el system prompt y las tools primero y fijos. TTFT de gpt-oss-20b-low según AA: ~3 s (prompt de benchmark largo) [S: [AA](https://artificialanalysis.ai/models/gpt-oss-20b-low/providers)]. |
| **Cerebras** | `gpt-oss-120b`, `qwen-3.8-27b` | **Ya no hay capa gratis permanente**: prueba de **$5 que caduca en 30 días** (5 RPM, 1M TPD) [P: [rate-limits FAQ](https://inference-docs.cerebras.ai/support/rate-limits)] | No | Sí | No para la prueba | Descartado como respaldo permanente. |
| **SambaNova** | `DeepSeek-V3.1/V3.2`, `Llama-3.3-70B`, `gpt-oss-120b`, `gemma-4-31B-it` | **20 RPM, 20 RPD, 200K TPD** por modelo [P: [rate-limits](https://docs.sambanova.ai/docs/en/models/rate-limits)] | No (20 al día) | Sí | No | Sirve solo como último recurso. |
| **OpenRouter `:free`** | Más de 25 modelos gratis | **20 RPM, 50 RPD** (1 000 RPD si alguna vez compraste 10 créditos) [P: [pricing](https://openrouter.ai/pricing), [limits](https://openrouter.ai/docs/api/reference/limits)] | No | Depende del modelo | No (o $10 una vez) | |
| **Mistral La Plateforme** | Mistral Small/Medium, Ministral | Modo Free: RPS + tokens/min + **tope mensual**; las cifras solo aparecen en tu panel [P: [help](https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them)] | Incierto: cuando se acaba el tope mensual, se para hasta el mes siguiente [S: [agentdeals](https://agentdeals.dev/mistral-api-pricing-2026)] | Sí | No | Buen español. Opcional como respaldo 4. |
| **GitHub Models** | — | **Retirado el 30-jul-2026** [P: [docs](https://docs.github.com/en/github-models)] | — | — | — | Descartado. |
| **Cloudflare Workers AI** | `@cf/google/gemma-4-26b-a4b-it`, `@cf/zai-org/glm-4.7-flash`, `@cf/nvidia/nemotron-3-120b-a12b` siguen en el plan Free [P: [changelog](https://developers.cloudflare.com/changelog/post/2026-07-28-models-require-workers-paid/)] | **10 000 neuronas/día**, reinicio a las 00:00 UTC [P: [pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)] | Probablemente no para modelos de 26B o más. Solo te alcanza para los chicos (Llama 3.2 3B ≈ 30K neuronas por millón de tokens de salida [P]). | Algunos | No | Requiere cuenta de Cloudflare. |
| **NVIDIA NIM (build.nvidia.com)** | Catálogo grande | **Hasta 40 RPM** en la mayoría de modelos y sin cobro por token; “free to prototype” [P: FAQ en [build.nvidia.com](https://build.nvidia.com/nvidia/kumo-relational/deploy)] | Por minuto sí; no publican RPD | Depende del modelo | No (cuenta verificada) | NVIDIA registra entradas y salidas [P]. Es para prototipos, no para un producto. |
| **Hugging Face Inference Providers** | — | Cuentas gratis: **$0 de créditos**; PRO: $2/mes [P: [pricing](https://huggingface.co/docs/inference-providers/pricing)] | No | — | Sí para pagar | Descartado. |

**Cómo leer “ilimitado”:** en la nube gratis, el límite real casi siempre son los **tokens por día o por minuto**, no las peticiones. Cada mensaje del sapo manda system prompt, definiciones de tools e historial (fácil 1–2K tokens). Recorta el historial y manda las tools solo cuando hagan falta (§3).

---

## 2. Local en 8 GB

### 2.1 Mediciones en esta PC [M]

Ollama 0.40.11, `think:false`, `num_ctx 4096`, streaming, prompts cortos (~120 tokens). Scripts en `scripts/bench-cerebro/`.

| Modelo | VRAM (`ollama ps`) | Carga en frío | Primer token (caliente) | Velocidad | Respuesta corta completa | Cultura general (15 preguntas) | Tools, prompt neutral | Tools, prompt con personaje |
|---|---|---|---|---|---|---|---|---|
| **qwen3.5:4b** (GPU) | 3.1 GB, 100 % GPU | 6.5 s | **68–133 ms** | **~92 tok/s** | 0.25–0.70 s | **13/15**, 14/15 en otra corrida | **10/10** | 5/10 (finge acciones) |
| qwen3.5:2b (GPU) | 2.4 GB, 100 % GPU | 5.0 s | 47–90 ms | ~89 tok/s | 0.23–0.77 s | 11/15 (Sídney, Picasso, Madero) | **10/10** | **10/10** |
| qwen3.5:2b (**CPU**, `num_gpu:0`) | RAM | 6.5 s | **~950 ms** | ~13 tok/s | 3–5.5 s | inventa (Delacroix, Sídney) | — | — |

Fallos de `qwen3.5:4b` que vale la pena ver:
- **Aritmética con varios pasos**: “144 entre 12 más 7 por 3” → contestó 5 (lo correcto es 33). Solución: una **tool `calcular`** determinista. No dejes las cuentas al LLM.
- **Datos ambiguos**: “río más largo de México” → Balsas. El Bravo/Grande es el más largo si cuentas la frontera; el Lerma-Santiago, si cuentas solo el interior. Mejor escalar a la nube.
- **Prompt**: con “eres un sapito sarcástico” y nada más, el modelo se negó a dar la capital de Australia y a hacer cuentas. Con **“REGLA 1: primero da la respuesta CORRECTA… REGLA 2: luego una burla corta”** acertó. Esa regla debe ir en el system prompt.
- Con modelos híbridos (Gated DeltaNet), llama.cpp **reprocesa el prompt completo** en cada turno (“forcing full prompt re-processing… hybrid/recurrent memory”, log de Ollama [M]). El prefill medido fue de ~1 900 tok/s, así que **cada 1 000 tokens de prompt suman ~0.5 s al primer token**. Mantén el system prompt, las tools y el historial **cortos**: idealmente menos de 800 tokens en total.

### 2.2 Candidatos que caben (tamaños de la librería oficial de Ollama [P])

| Modelo | Tamaño Ollama | Caps | Comentario para el sapo |
|---|---|---|---|
| **qwen3.5:4b** ✅ (instalado) | 3.3–4.0 GB | vision, tools, thinking; 201 idiomas [P: [ollama](https://ollama.com/library/qwen3.5:4b)] | El mejor equilibrio que medimos. |
| qwen3.5:2b ✅ (instalado) | 2.7–3.1 GB | ídem | Úsalo solo como **enrutador de tools** o en modo juego. Para datos no sirve. |
| qwen3.5:4b-mtp-q4_K_M | 4.1 GB | + cabeza MTP (decodificación especulativa) [P: [tags](https://ollama.com/library/qwen3.5/tags)] | Opcional: podría subir los tok/s. A 92 tok/s una respuesta de 40 tokens ya tarda ~0.45 s, así que la ganancia práctica es poca. Pruébalo antes de cambiar. |
| qwen3.5:9b | 6.6–7.6 GB | ídem | Más listo, pero **no deja espacio para juegos** ni para la visión. Solo con la PC libre. |
| gemma4:e4b / e2b | 6.6–9.5 GB / 4.6–7.5 GB [P: [ollama](https://ollama.com/library/gemma4)] | vision, tools, thinking, audio | En Ollama pesan más de lo que sugiere el nombre. No caben cómodos con un juego abierto. |
| gemma4:12b | 7.7–8.0 GB | — | Llena los 8 GB. Descartado. |
| llama3.1:8b | 4.9 GB, solo texto, sin actualizar desde hace 1 año [P] | tools | Más viejo que Qwen 3.5. No aporta. |
| ministral-3:3b / 8b | 3.0 / 6.0 GB [P] | vision, tools | Buen español (Mistral). Alternativa a probar si Qwen se ve flojo. |
| phi4-mini | 2.5 GB [P] | tools | Español más débil. No recomendado. |
| granite4:3b | 2.1 GB [P] | tools | Orientado a empresa e inglés. No recomendado. |

### 2.3 Ajustes de Ollama recomendados

| Ajuste | Valor | Fuente | Por qué |
|---|---|---|---|
| `OLLAMA_KEEP_ALIVE` / `keep_alive` | `-1` (siempre cargado) cuando no juegas; `0` al detectar un juego | [P: [FAQ](https://docs.ollama.com/faq)] | Evita los 5–6.5 s de carga en frío [M]. |
| `OLLAMA_FLASH_ATTENTION` | `1` (Ollama ya lo activa solo si el backend lo soporta) | [P: FAQ] | Requisito para cuantizar la caché KV. |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | [P: FAQ: “~1/2 de memoria, pérdida muy pequeña”] | Ahorra VRAM. Ojo: el FAQ avisa que los modelos con mucho GQA (Qwen) sufren más; **no uses `q4_0`**. |
| `num_ctx` | 4096 (8192 máximo) | — | Más contexto = más VRAM y más prefill. |
| `OLLAMA_MAX_LOADED_MODELS` | 1 o 2 | [P: FAQ] | Si 4b y 2b quedan cargados a la vez, la VRAM usada sube a 7.75 GB [M]. Carga uno solo, o el 2b solo para el modo juego. |
| `think` | `false` | — | El modo pensamiento suma segundos. |
| `format` (JSON schema) | **Quitarlo en el chat** | — | Hoy `llm.py` manda `REPLY_SCHEMA` y `stream:false`. Forzar JSON impide mostrar el texto mientras se genera y gasta tokens. Pide texto plano y separa la emoción o acción con un marcador simple, o usa la pasada de tools. |
| Decodificación especulativa | Opcional: `qwen3.5:4b-mtp-*` o `draft_num_predict` [P: [Modelfile](https://docs.ollama.com/modelfile)] | — | Con 92 tok/s ya cumples la meta. Pruébala solo si notas lentitud. |

### 2.4 Impacto de jugar (Fortnite / Roblox) con el modelo cargado

- La VRAM base del escritorio fue de ~1.6 GB; con 4b + 2b cargados llegó a **7.75 GB de 8.15 GB** [M]. Con solo el 4b quedan ~3.4 GB libres para el juego: Fortnite en calidad media o alta probablemente se quedaría corto, y el driver empezaría a mover memoria a RAM (tirones y bajones de FPS en los dos).
- La inferencia en GPU compite con el juego por los núcleos: cada respuesta (~0.5 s al 100 % de GPU) puede causar un bajón de FPS. Es breve, pero se nota en partidas competitivas.
- **Política recomendada** (el proyecto ya tiene “ocupado cuando juegas” y `ollama_game_model`): al detectar el juego, `keep_alive:0` al modelo GPU y **todo a la nube** (Gemma 4 → Groq). Si no hay internet o se acabó la cuota, usa el `qwen3.5:2b` en **CPU** (~1 s de primer token y 13 tok/s [M]) solo para tools y frases cortas, con un aviso de “ando en modo ahorro”. Al cerrar el juego, precarga otra vez (`keep_alive:-1`).

---

## 3. Estrategia: router local primero

```
mensaje
  │
  ├─ 0) Caché exacta (texto normalizado) ─ acierto → responde (0 ms)
  │
  ├─ 1) ¿Es una acción? (regex o palabras clave: abre|pon|sube|baja|cierra|busca|clima|dólar|alarma|…)
  │      sí → PASADA DE TOOLS: qwen3.5:4b, prompt NEUTRAL, tools mínimas, temperature 0.2  [10/10 M]
  │            → ejecuta la tool → frase sarcástica corta (plantilla o 2.ª pasada de ~0.3 s)
  │
  ├─ 2) ¿Hay cuentas? → tool `calcular` (Python seguro) y el LLM solo comenta el resultado
  │
  ├─ 3) Chat normal → qwen3.5:4b local, STREAMING, persona con “REGLA 1: respuesta correcta”
  │
  └─ 4) Escala a la nube si:
         • juego activo / GPU ocupada / Ollama caído
         • el tema es de actualidad (noticias, precios, “hoy”) → nube con búsqueda o tool `buscar_web`
         • el usuario insiste (“¿seguro?”, “estás mal”) o pide algo largo (explicación o redacción > 3 frases)
       Orden: gemma-4-26b-a4b-it → groq gpt-oss-20b → groq qwen3.8-27b → gemini-3.5-flash-lite → local de todos modos
       Con streaming en todos. Cortocircuito (circuit breaker) de 60 s por modelo ante 429/503 (llm.py ya lo hace).
```

**¿Por qué local primero y no al revés?** El local respondió en **< 140 ms** al primer token, sin cuota y sin depender de la red. Las APIs gratis tienen primer token de 0.3 a varios segundos y cuotas diarias. Los 503/429 de Gemini Flash que ves hoy son justo eso. La nube solo aporta cuando el modelo de 4B no sabe (actualidad, razonamiento largo) o cuando la GPU está ocupada.

**Streaming:** hoy todo usa `stream:false` (Ollama) y `generateContent` (Gemini). Cambiar a `stream:true` / `streamGenerateContent?alt=sse` y mostrar la burbuja y el TTS por frase hace que la respuesta *se sienta* instantánea aunque la nube tarde 1 s.

**Caché semántica:** su beneficio es bajo porque el local ya es instantáneo. Si la agregas:
- Exacta + normalizada (minúsculas, sin acentos ni signos) para saludos y preguntas repetidas.
- Semántica con embeddings locales (p. ej. `qwen3-embedding` o `embeddinggemma` en Ollama, guardados en el sqlite-vec que ya propone 03), umbral de coseno ≥ 0.92 y TTL de días.
- **Nunca** caches acciones, preguntas con “hoy/ahora/clima/precio” ni respuestas de cuentas personales.

---

## 4. Cambios concretos sugeridos al código actual

1. `config.py`: `gemini_model` por defecto **`gemma-4-26b-a4b-it`** y `gemini_lite_model = "gemini-3.5-flash-lite"`. Quita `gemini-flash-latest` del camino caliente (20 RPD [S]).
2. `llm.py`: provider por defecto **`ollama`** con nube como respaldo (hoy `complete()` intenta Gemini primero con un timeout de 14 s).
3. Agregar un cliente Groq con streaming y `reasoning_effort:"low"` para gpt-oss, y una tool `calcular`.
4. Separar la pasada de tools (prompt neutral) del prompt con personalidad.
5. Quitar `format=REPLY_SCHEMA` en el chat y activar `stream:true`. Precargar con `keep_alive:-1` y descargar con `keep_alive:0` al jugar (ya existen `preload` y `unload`).
6. Recortar el prompt: menos de 800 tokens en total (system + tools + historial) para que el prefill no se coma la meta de 500 ms.

## 5. Pendiente o sin verificar

- Las cifras RPM/RPD de la capa gratis de Gemini vienen de un tercero [S]. **Revísalas en `https://aistudio.google.com/rate-limit`** con tu proyecto.
- No medí la latencia de la nube: no había llaves en variables de entorno y no descifré la bóveda. Corre `GEMINI_API_KEY=… GROQ_API_KEY=… python scripts/bench-cerebro/bench_nube.py`. El valor `reasoning_effort:"none"` para qwen3.8 en Groq no está probado.
- No probé `qwen3.5:9b`, `ministral-3` ni la variante MTP (no se descargaron modelos nuevos).
- Las mediciones son de una sola corrida con pocas preguntas: sirven como orientación, no son un benchmark formal.
