# 03 · Cerebro de IA para Sapo-Jarvis (100 % gratis)

> Investigación: 25-oct-2026. Hardware objetivo: Windows 11, **RTX 5060 Ti 8 GB**, 32 GB RAM, i7-12700, + celular Android.
> Regla de citas: **[P]** = fuente primaria (doc oficial, repo, model card). **[S]** = fuente secundaria (blog/benchmark de terceros); tratar como orientativa y verificar.
> Los límites de APIs gratis cambian seguido: revisa siempre la página de límites de tu cuenta antes de depender de ellos.

---

## 0. Resumen ejecutivo

| Pieza | Elección recomendada | Plan B |
|---|---|---|
| Runtime LLM | **Ollama** (API local + tool-calling) | llama.cpp (`llama-server`) para exprimir VRAM; LM Studio si quieres GUI |
| LLM principal (8 GB) | **`qwen3.5:4b`** (texto+imagen, tools, ~3.3–4 GB) | `qwen3.5:9b` (6.6–7.6 GB, solo si no corre nada más) / `gemma4:e4b` |
| Visión de pantalla | El mismo `qwen3.5:4b` (es multimodal) | `qwen3-vl:4b` (3.3 GB) |
| Fallback en la nube | **Groq** (no entrena con tus datos) | Gemini free (sí entrena), OpenRouter `:free`, Mistral Experiment |
| Control de PC | **Windows-MCP** (MIT) | pywinauto/pyautogui como tools propias |
| Control de Android | MCP sobre ADB (p.ej. `mobile-next/mobile-mcp`) | App MCP en el teléfono (`android-remote-control-mcp`) |
| Memoria | **sqlite-vec** (un solo archivo .db) | LanceDB / Chroma `PersistentClient` |
| STT | **faster-whisper** `large-v3-turbo` int8 (GPU) | **Moonshine** español (CPU, MIT) |
| TTS | **Kokoro-82M** `ef_dora` en CPU (Apache-2.0) + pitch-shift "kawaii" | Piper `es_MX` (CPU) / Chatterbox Multilingual (MIT, clonación) |
| Wake word | **openWakeWord** entrenando tu propio "Oye Sapo" | — |

---

## 1. LLM local

### 1.1 Runtimes (todos gratis)

| Runtime | Qué es | Notas para este proyecto |
|---|---|---|
| **Ollama** | Servidor local con API REST/OpenAI-compatible, soporte nativo de *tool calling*. | Docs de tools: https://docs.ollama.com/capabilities/tool-calling [P]. Mantiene el modelo cargado 5 min por defecto; se puede descargar al instante con `keep_alive: 0` u `OLLAMA_KEEP_ALIVE` (FAQ: https://docs.ollama.com/faq [P]). `ollama ps` muestra `100% GPU` / `x% CPU/GPU` [P, FAQ]. **Es la mejor base**: simple, y su control de carga/descarga es clave para cuando juegas (§7). |
| **llama.cpp** | Motor C/C++ (el que usa Ollama por debajo). `llama-server` da API OpenAI-compatible. | Más control fino (capas en GPU, `--n-cpu-moe` para MoE, cuantizaciones de KV cache). Hay builds para Blackwell/sm_120 (RTX 50) [S: https://github.com/Andgihat/llama-cpp-mtp-turboquant-sm120-blackwell-windows]. Úsalo si Ollama se queda corto. |
| **LM Studio** | App de escritorio con GUI + servidor local. | Gratis también para uso laboral desde jul-2025: https://lmstudio.ai/blog/free-for-work [P]. Cerrado (no open-source); bueno para probar modelos, menos para un servicio que corre 24/7. |

### 1.2 Modelos que caben en 8 GB (oct-2026)

Tamaños según la librería oficial de Ollama (el rango incluye la variación por contexto/cuantización):

| Modelo | Tamaño en Ollama | Capacidades | Fuente |
|---|---|---|---|
| **Qwen3.5 4B** (`qwen3.5:4b`) | 3.3–4.0 GB, 256K ctx | Texto + **imagen**, tools, thinking | https://ollama.com/library/qwen3.5 [P] |
| Qwen3.5 9B (`qwen3.5:9b`, es el `latest`) | 6.6–7.6 GB | Texto + imagen, tools | ídem [P] |
| Qwen3.5 2B / 0.8B | 2.7–3.1 GB / 1.2–1.3 GB | Texto + imagen | ídem [P] — útil como "cerebro mínimo" mientras juegas |
| **Gemma 4 E4B** (`gemma4:e4b`) | 6.6–9.5 GB, 128K | Texto + imagen, *function calling* nativo | https://ollama.com/library/gemma4 [P]; lanzamiento 31-mar-2026: https://ai.google.dev/gemma/docs/releases [P] |
| Gemma 4 E2B | 4.6–7.5 GB | Texto + imagen | ídem [P] |
| Gemma 4 12B | 7.7–8.0 GB | — | ídem [P]; **no cabe** con nada más al lado |
| Qwen3 8B (`qwen3:8b`) | ~5 GB Q4_K_M | tools, thinking (generación anterior) | https://ollama.com/library/qwen3:8b-q4_K_M [P] |
| Qwen3-VL 4B / 2B | 3.3 GB / 1.9 GB | Visión, agente GUI | https://ollama.com/library/qwen3-vl [P] |

Lo que **no** cabe en 8 GB: Qwen3.6 (27B = 18–19 GB, 35B MoE = 23–24 GB) https://ollama.com/library/qwen3.6 [P]; Qwen3.8 27B (18 GB) https://ollama.com/library/qwen3.8 [P]. El 35B-A3B *MoE* podría correr repartido GPU+RAM (32 GB) con llama.cpp `--n-cpu-moe`, pero sería lento y consume casi toda la RAM: no recomendado para un asistente siempre activo.

**Español:** Qwen3.5 y Gemma 4 son multilingües y manejan bien español; no encontré un benchmark oficial de español para tamaños 4B, así que **pruébalo tú** con 20 frases típicas del sapito (órdenes, charla, "abre Roblox") antes de decidir. Para tool-calling fiable en modelos pequeños: pocos tools a la vez (≤10), descripciones cortas, `temperature` baja (0.2–0.4) y validación del JSON antes de ejecutar.

### 1.3 Velocidad esperada en RTX 5060 Ti 8 GB (448 GB/s)

| Modelo | tok/s | Fuente |
|---|---|---|
| Llama 3.1 8B Q4_K_M (Ollama) | ~75 | [S] https://specpicks.com/benchmarks/nvidia-geforce-rtx-5060-ti-8gb |
| Qwen3 8B (4.7 GB) | ~55 (ctx máx. ~8K) | [S] https://vramguide.com/gpu/rtx-5060-ti-8/ |
| Techo teórico 8B Q4 | ~97 | [S] https://quantized.uk/gpu/rtx-5060-ti-8g/ (cálculo, no benchmark) |
| Modelos 4B Q4 | **estimado ~90–120** | Extrapolación propia por ancho de banda (no medido) |

Una respuesta hablada típica (40–80 tokens) sale en < 1 s con 4B. Si el modelo se "desborda" de VRAM, cae a ~5 tok/s [S: https://techfuelhq.com/tutorials/self-host-local-llm-rtx-5060-2026/].

---

## 2. APIs con tier gratis permanente

| Proveedor | Gratis permanente | Límites (oct-2026) | ¿Entrena con tus datos? |
|---|---|---|---|
| **Groq** | Sí, sin tarjeta | Por modelo, a nivel organización. Ej.: `openai/gpt-oss-120b`, `gpt-oss-20b`, `qwen/qwen3.8-27b`: **30 RPM, 1 000 RPD, 8K TPM, 200K TPD**; `whisper-large-v3(-turbo)`: 20 RPM, 2 000 RPD, 7 200 s audio/hora, 28 800 s/día. Fuente: https://console.groq.com/docs/rate-limits [P] (la página dice que los exactos están en tu panel de límites). | **No por defecto.** Inferencia no se retiene salvo troubleshooting/abuso (hasta 30 días), desactivable en Data Controls: https://console.groq.com/docs/your-data [P]; el Services Agreement prohíbe usar inputs/outputs para entrenar: https://console.groq.com/docs/legal/services-agreement [P]. |
| **Google Gemini API** | Sí (Free Tier) | Gratis en modelos Flash/Flash-Lite (p.ej. Gemini 3.8 Flash, 3.6 Flash, 3.5/3.1 Flash-Lite, Gemma 4); **Pro y Gemini 4 Argon no tienen free tier**: https://ai.google.dev/gemini-api/docs/pricing [P]. Google **ya no publica** RPM/RPD exactos; se ven por proyecto en AI Studio; RPD se reinicia a medianoche del Pacífico: https://ai.google.dev/gemini-api/docs/rate-limits [P]. Reportes de terceros: ~5 RPM / **20 RPD** en 3.8/3.6 Flash y ~**500 RPD** en Flash-Lite [S: https://www.scriptbyai.com/gemini-api-free-tier-limits/]. | **Sí.** En el tier gratis Google usa prompts y respuestas para mejorar productos y **revisores humanos pueden leerlos**; "no envíes info sensible": https://ai.google.dev/gemini-api/terms [P]. ⚠️ Los términos exigen **18+ años** y no usarlo en apps dirigidas a menores [P, misma URL]. |
| **OpenRouter** (`:free`) | Sí | **50 req/día** y 20 req/min sin créditos; **1 000 req/día** si alguna vez compraste ≥10 créditos (eso ya no es "gratis"): https://openrouter.ai/docs/faq y https://openrouter.ai/pricing [P]. ~25 modelos gratis, 4 proveedores gratis [P, pricing]. | **Depende del proveedor.** OpenRouter no enruta a proveedores que entrenan salvo que actives el toggle en Privacy: https://openrouter.ai/docs/guides/privacy/provider-logging [P]. Muchos `:free` sí pueden entrenar [S: https://www.truefoundry.com/blog/openrouter-free-models-whats-actually-free-and-what-it-costs-you]. |
| **Cerebras** | **No** (ya no es permanente) | Free Trial: **$5 de créditos que vencen a los 30 días, requiere tarjeta verificada**; en trial `gpt-oss-120b` y `qwen-3.8-27b`: 5 RPM, 30K TPM sin caché, 1M tokens/día: https://inference-docs.cerebras.ai/support/rate-limits [P]. | No aplica al presupuesto 100 % gratis → **descartado**. |
| **Mistral (AI Studio, plan "Experiment"/Free)** | Sí, verificación por teléfono | Límites "muy restrictivos", visibles en admin.mistral.ai → Limits; se miden en req/segundo y tokens/min por organización: https://docs.mistral.ai/resources/known-limitations [P]. Terceros reportan ~1 req/s [S: https://cabina.ai/blog/mistral-api-pricing/]. | **Sí por defecto** en Free mode ("we may use your data"), con opt-out: https://help.mistral.ai/en/articles/347617 [P]. |

**Orden de fallback recomendado:** Groq (privado, rápido, 1 000 RPD) → Gemini Flash-Lite (solo charla no sensible, y solo si el usuario es mayor de edad) → OpenRouter `:free` con toggle de entrenamiento **apagado**. Nunca mandes capturas de pantalla, contraseñas ni datos del teléfono a tiers que entrenan.

---

## 3. Agente con herramientas (PC + teléfono)

### 3.1 Arquitectura

```
[Micrófono PC / app Android] → wake word → STT → ┐
                                                 ▼
                         ORQUESTADOR (Python, asyncio)
             ┌──────────── router de modelo ────────────┐
             │ local Ollama (qwen3.5:4b)  │  Groq/Gemini │  ← según GPU libre / modo juego
             └───────────────┬────────────┴──────────────┘
                             │ tool calls (JSON / MCP)
     ┌───────────────┬───────┴────────┬─────────────────┬──────────────┐
  Windows-MCP     Android MCP       Memoria          Visión          Utilidades
 (apps, mouse,   (ADB por Wi-Fi /  (sqlite-vec)   (screenshot →     (clima, timers,
  teclado, UI)    Tailscale)                         VLM)            notas)
                             │
                      TTS → altavoz PC / app Android + animación del sapito
```

- **Cliente MCP propio:** el SDK oficial `mcp` de Python permite que tu orquestador hable con cualquier servidor MCP y traduzca sus tools al formato `tools=[...]` de Ollama (que es el mismo esquema JSON de OpenAI) [P: https://docs.ollama.com/capabilities/tool-calling].
- **Confirmación obligatoria** para acciones destructivas (cerrar apps, borrar, enviar mensajes): el modelo pequeño se equivoca.

### 3.2 Control de Windows

| Herramienta | Estado / licencia | Uso |
|---|---|---|
| **Windows-MCP** (CursorTouch) | MIT, ~10.2K ⭐, activo. Funciona con cualquier LLM, visión opcional, latencia 0.2–0.5 s entre acciones: https://github.com/CursorTouch/Windows-MCP [P] | Abrir apps, clicks, teclado, leer árbol de UI. Leer su política de seguridad: https://github.com/CursorTouch/Windows-MCP/security/policy [P]. |
| Open Interpreter | Relanzado en jul-2026 como **agente de programación en Rust** (Apache-2.0), ya no es el "controla tu PC" de 2024: https://www.openinterpreter.com/blog [P] | No es la pieza adecuada para el sapito. |
| Tools propias | `pyautogui`, `pywinauto`, `psutil`, `subprocess` | Para acciones fijas y seguras (volumen, abrir Roblox, timer) es mejor un tool propio que un agente genérico. |

### 3.3 Control del teléfono Android

| Opción | Cómo | Fuente |
|---|---|---|
| **mobile-mcp** (mobile-next) | Servidor MCP que maneja el teléfono vía ADB (USB o Wi-Fi) | [S] https://github.com/mouse9527/mobile-mcp-image (empaqueta mobile-next/mobile-mcp) |
| adb-mcp | MCP estructurado sobre ADB: lanzar apps, input, capturas | [P] https://github.com/FlashZ/adb-mcp |
| android-remote-control-mcp | App que corre **en el teléfono** como servidor MCP (accesibilidad + capturas), con túnel | [P] https://github.com/danielealbano/android-remote-control-mcp |

Conectividad gratis PC↔teléfono fuera de casa: **Tailscale Personal** (gratis "indefinidamente", 6 usuarios): https://tailscale.com/pricing y https://tailscale.com/docs/account/manage-plans/free-plans-discounts [P]. La app del sapito en Android puede ser un cliente ligero (audio/WebSocket) y el cerebro vive en la PC; si la PC está apagada, el teléfono llama directo a Groq. Correr un LLM en el propio teléfono (Ollama en Termux) es posible pero solo CPU y ≤3B [S: https://github.com/LvL23HT/-Complete-Tutorial-Install-Ollama-on-Termux-Android-].

Frameworks de pipeline de voz open-source si no quieres hacerlo a mano: **Pipecat** (tiene servicio Moonshine incluido: https://github.com/pipecat-ai/pipecat [P]) o LiveKit Agents (https://livekit.com/voice-agents [P]).

---

## 4. "Conciencia" / personalidad

### 4.1 Aclaración honesta
Nada de esto crea **consciencia real**. Un LLM predice texto; la "personalidad" es un prompt + memoria recuperada + variables de estado que tú programas. El sapito puede *parecer* que recuerda, se alegra o "piensa solo", pero no siente ni tiene experiencia subjetiva. Conviene que el propio sapito lo diga si le preguntan ("soy un programa, pero me acuerdo de ti"). Esto también evita apego dañino, especialmente si lo usan niños.

### 4.2 Memoria a largo plazo (vector DB local, gratis)

| Opción | Pros | Fuente |
|---|---|---|
| **sqlite-vec** | Extensión de SQLite en C sin dependencias, MIT/Apache-2.0; última estable **0.1.9 (31-mar-2026)**; todo en un `.db` junto con tus tablas normales | https://pypi.org/project/sqlite-vec/ , https://github.com/asg017/sqlite-vec/releases [P] |
| LanceDB OSS | Embebida, sin servidor, guarda en un directorio | https://docs.lancedb.com/ [P] |
| Chroma | `PersistentClient` local | https://docs.trychroma.com/docs/run-chroma/clients [P] |
| Mem0 OSS / Letta (ex-MemGPT) | Capas de memoria ya hechas, funcionan con Ollama | https://docs.mem0.ai/cookbooks/operations/email-automation [P], Letta Apache-2.0 https://docs.letta.com/llms.txt [P] |

Embeddings locales: **EmbeddingGemma 2** (740M, publicado 6-oct-2026: https://ai.google.dev/gemma/docs/releases [P]) o el EmbeddingGemma 300M original si quieres menos VRAM/CPU.

### 4.3 Diseño estilo *Generative Agents* (Park et al., 2023)
Paper: https://arxiv.org/abs/2304.03442 [P]. Tres ideas que se adaptan bien:
1. **Memory stream:** cada evento ("el usuario ganó en Fortnite", "le gusta el verde") se guarda con `timestamp`, `importancia (1–10)` puntuada por el LLM y embedding.
2. **Recuperación** por puntaje = recencia (decaimiento exponencial) + importancia + similitud semántica.
3. **Reflexión:** cuando la suma de importancia reciente pasa un umbral, el LLM resume en "insights" ("al usuario le estresan las tareas de mates") que se guardan como memorias nuevas.

### 4.4 Estado emocional y loop autónomo
- Estado como variables numéricas persistidas (`ánimo`, `energía`, `cariño`, `aburrimiento`) que cambian con eventos y decaen con el tiempo; se inyectan en el system prompt ("Te sientes un poco aburrido") y controlan la animación/voz del sapito.
- **Loop de pensamientos**: un *tick* cada 5–15 min **solo si la GPU está libre y el usuario no está jugando**: el modelo lee memorias recientes + hora + estado y decide `{pensar_en_silencio | sugerir_algo | no_hacer_nada}`. Con tope de mensajes no solicitados por hora para que no sea molesto. Usa el modelo más chico (`qwen3.5:2b` o 0.8b) para estos ticks.

---

## 5. Voz

### 5.1 STT (voz → texto)

| Motor | Español | Recursos | Licencia | Fuente |
|---|---|---|---|---|
| **faster-whisper** `large-v3-turbo` int8 | Muy bueno | ~1.6 GB VRAM int8, ~30× tiempo real en GPU [S] | MIT | [S] https://www.spheron.network/blog/faster-whisper-gpu-cloud-production-deployment-guide/ ; [S] https://nexgpu.net/en/models/whisper/ (whisper oficial: turbo ~6 GB en PyTorch) |
| **whisper.cpp** | Igual modelo Whisper | CPU, CUDA, **Vulkan**; v1.9.5 (6-oct-2026) | MIT | [S] https://freedom.tech/posts/2026-10-06-whisper-cpp-1-9-5/ |
| **Moonshine** (Small/Tiny Streaming ES) | **WER 4.9 %** (Small, 123M) / 6.2 % (Tiny, 34M) | CPU, streaming, minúsculo | **MIT** | [P] https://github.com/moonshine-ai/moonshine/blob/main/docs/models/available-models.md |
| Groq Whisper (nube) | Muy bueno | 2 000 req/día gratis | — | [P] https://console.groq.com/docs/rate-limits |

VAD (detectar cuándo hablas): **Silero VAD**, MIT: https://github.com/snakers4/silero-vad [P].
Recomendación: **Moonshine Small ES en CPU** como base (no gasta VRAM, sirve también en modo juego) y faster-whisper turbo en GPU solo si notas errores.

### 5.2 TTS (texto → voz) "kawaii" en español

| Motor | Español | Licencia (¡pesos!) | VRAM / CPU | Fuente |
|---|---|---|---|---|
| **Kokoro-82M** | 1 voz femenina (`ef_dora`) + 2 masculinas (`em_alex`, `em_santa`); el propio autor avisa que el soporte no-inglés puede ser "delgado" | **Apache-2.0** (código y pesos) | 82M params → corre bien en CPU; en GPU con PyTorch 2.4–4 GB medidos [S] | [P] https://huggingface.co/hexgrad/Kokoro-82M/raw/main/VOICES.md , [P] https://huggingface.co/hexgrad/Kokoro-82M ; [S] https://nexgpu.net/en/models/kokoro/ |
| **Piper** (OHF-Voice/piper1-gpl) | Voces `es_MX`, `es_ES`, `es_AR` | Motor **GPL-3.0**; cada voz tiene la licencia de su dataset (revisar MODEL_CARD) | CPU, muy rápido (ONNX) | [P] https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md |
| **Chatterbox Multilingual** (Resemble) | Sí (23 idiomas) + fine-tune dedicado `es-es`; control de "exageración emocional"; **clonación** con audio de referencia | **MIT** | ~3.5 GB VRAM solo TTS (multilingual) | [P] https://huggingface.co/ResembleAI/chatterbox , [P] https://huggingface.co/ResembleAI/Chatterbox-Multilingual-es-es , [P] https://docs.nvidia.com/ace-for-games/chatterbox-tts/samples.html |
| F5-TTS | Clonación | Código MIT, **pesos CC-BY-NC-4.0** (no comercial) | GPU | [S] https://www.openspeech.dev/models/f5-tts |
| XTTS-v2 (Coqui) | Clonación, español | **Coqui Public Model License: solo uso no comercial** (modelo y salidas); Coqui cerró | GPU | [P] https://huggingface.co/coqui/XTTS-v2/raw/main/LICENSE.txt |

**Cómo lograr la voz kawaii sin pagar:**
1. Kokoro `ef_dora` en CPU + **subir el pitch 3–5 semitonos** y velocidad 1.1× con un efecto (p.ej. `librosa`/`pyrubberband` o SoX). Barato y 100 % Apache.
2. Si quieres una voz "personaje" más expresiva: Chatterbox con un **audio de referencia propio** (tu voz o una voz con permiso, actuada aguda) y `exaggeration` alto. Solo en GPU libre.
3. **Clonación y ética/licencia:** clona solo voces propias o con permiso explícito; **no** clones voces de VTubers/actores/personajes. Si algún día el proyecto se vuelve comercial, evita F5-TTS y XTTS-v2 (no comerciales).

### 5.3 Wake word
**openWakeWord**: código Apache-2.0; entrena una palabra propia ("Oye Sapo") en < 1 h con el notebook de Colab: https://github.com/dscripka/openWakeWord [P]. Ojo licencias: los **modelos pre-entrenados oficiales** son **CC BY-NC-SA 4.0** (https://huggingface.co/davidscripka/openwakeword [P]) y los generados en el servicio web openwakeword.com son **solo uso personal/no comercial** (https://openwakeword.com/terms [P]). Para uso personal, todo OK. Corre en CPU con costo mínimo.

---

## 6. Visión de pantalla

- **Modelo:** `qwen3.5:4b` ya acepta imágenes (Ollama lo lista como "Text, Image") [P: https://ollama.com/library/qwen3.5] → **un solo modelo para chat + visión**, sin cargar un segundo VLM. Alternativa dedicada: `qwen3-vl:4b` (3.3 GB), que Qwen describe con capacidades de agente GUI (reconocer elementos, operar interfaces) [P: https://ollama.com/library/qwen3-vl].
- **Flujo:** `mss` (captura rápida) → reducir a ~1280 px de ancho → mandar como imagen al endpoint `/api/chat` con la pregunta ("¿qué hay en pantalla?", "¿dónde está el botón Jugar?").
- **Para actuar** (clicks) es más fiable usar el árbol de UI de **Windows-MCP** que coordenadas adivinadas por el VLM; la visión sirve para *entender* (comentar el juego, leer un error).
- **Privacidad:** capturas de pantalla **solo al modelo local** o a Groq; nunca a tiers que entrenan.
- **Nunca** hagas capturas continuas durante el juego (gasta GPU y puede verse como software de terceros por anti-cheats); pide la captura bajo demanda.

---

## 7. Presupuesto de VRAM y modo juego

### 7.1 Todo local a la vez (escritorio, sin juego)
Cifras de las fuentes citadas arriba; overhead de Windows/escritorio es estimación propia.

| Componente | Opción "ligera" (recomendada) | Opción "pesada" |
|---|---|---|
| Windows + navegador (DWM, etc.) | ~0.5–1 GB (estimado) | ~0.5–1 GB |
| LLM + visión | `qwen3.5:4b` **3.3–4.0 GB** | `qwen3.5:9b` 6.6–7.6 GB |
| STT | Moonshine en **CPU → 0 GB** | faster-whisper turbo int8 ~1.6 GB |
| TTS | Kokoro en **CPU → 0 GB** | Chatterbox ~3.5 GB |
| Wake word + VAD | CPU → 0 GB | CPU |
| **Total GPU** | **≈ 4–5 GB ✅ (sobran ~3 GB)** | **≈ 12–14 GB ❌ no cabe** |

Con la opción ligera el i7-12700 (12 núcleos) absorbe STT+TTS sin problema. Si hace falta precisión, sube solo el STT a GPU (≈ 6–6.5 GB total, todavía cabe).

### 7.2 Qué pasa al jugar Fortnite / Roblox
- **Fortnite**: Epic pide **8 GB de VRAM o más** para los presets "Epic" (2 GB para el recomendado básico): https://www.epicgames.com/help/en-US/c-202300000001636/c-202300000001719/what-are-the-system-requirements-for-fortnite-on-pc-a202300000012731 [P]. Es decir, Fortnite en alto ya usa *toda* tu tarjeta.
- **Roblox**: requisitos bajos (DirectX 10+, GPU dedicada recomendada): https://en.help.roblox.com/hc/en-us/articles/203312800 [P]; aun así, experiencias pesadas llegan a 3–5 GB (estimado, varía mucho).
- **Riesgo:** desde el driver 536.40, cuando CUDA se queda sin VRAM, NVIDIA usa RAM del sistema ("Sysmem Fallback") en vez de fallar → no crashea pero **todo se vuelve lento** (juego con tirones, LLM a pocos tok/s): https://nvidia.custhelp.com/app/answers/detail/a_id/5490 [P].

### 7.3 Estrategia "Modo Juego" automática
1. Un vigilante (`psutil`, cada 5 s) detecta el proceso del juego (p.ej. `FortniteClient-Win64-Shipping.exe`, `RobloxPlayerBeta.exe` — verifica los nombres exactos en el Administrador de tareas) y/o lee VRAM libre con `nvidia-smi --query-gpu=memory.used,memory.total --format=csv`.
2. Al entrar en modo juego: llamar a Ollama con `keep_alive: 0` para **descargar el modelo de la GPU** [P: https://docs.ollama.com/faq]; poner `OLLAMA_MAX_LOADED_MODELS=1`.
3. El cerebro pasa a **Groq** (o Gemini Flash-Lite para charla no sensible). STT (Moonshine) y TTS (Kokoro/Piper) **siguen en CPU** → el sapito sigue hablando sin tocar la GPU.
4. Desactivar el loop autónomo, la visión de pantalla y las capturas.
5. Si no hay internet: caer a `qwen3.5:0.8b`/`2b` **forzado a CPU** (`num_gpu: 0` en Ollama) — lento pero funcional para órdenes simples.
6. Al cerrar el juego: volver a precargar `qwen3.5:4b` en GPU.

---

## Fuentes primarias principales
- Ollama: https://ollama.com/library/qwen3.5 · https://ollama.com/library/gemma4 · https://ollama.com/library/qwen3-vl · https://docs.ollama.com/faq · https://docs.ollama.com/capabilities/tool-calling
- Gemma releases: https://ai.google.dev/gemma/docs/releases
- Groq: https://console.groq.com/docs/rate-limits · https://console.groq.com/docs/your-data
- Gemini: https://ai.google.dev/gemini-api/docs/pricing · https://ai.google.dev/gemini-api/docs/rate-limits · https://ai.google.dev/gemini-api/terms
- OpenRouter: https://openrouter.ai/docs/faq · https://openrouter.ai/pricing
- Cerebras: https://inference-docs.cerebras.ai/support/rate-limits
- Mistral: https://help.mistral.ai/en/articles/347617 · https://docs.mistral.ai/resources/known-limitations
- Windows-MCP: https://github.com/CursorTouch/Windows-MCP
- Moonshine: https://github.com/moonshine-ai/moonshine/blob/main/docs/models/available-models.md
- Kokoro: https://huggingface.co/hexgrad/Kokoro-82M · Chatterbox: https://huggingface.co/ResembleAI/chatterbox · Piper: https://github.com/OHF-Voice/piper1-gpl · XTTS-v2: https://huggingface.co/coqui/XTTS-v2
- openWakeWord: https://github.com/dscripka/openWakeWord · sqlite-vec: https://pypi.org/project/sqlite-vec/
- Generative Agents: https://arxiv.org/abs/2304.03442
- Epic (Fortnite): enlace en §7.2 · NVIDIA Sysmem Fallback: https://nvidia.custhelp.com/app/answers/detail/a_id/5490

## Pendiente de verificar en la práctica
- Calidad real del español y del tool-calling de `qwen3.5:4b` vs `gemma4:e4b` (hacer una prueba A/B con 20 órdenes).
- tok/s reales de modelos 4B en tu 5060 Ti (la cifra de 90–120 es extrapolación).
- Límites exactos de Gemini/Mistral en tu cuenta (no se publican oficialmente).
- Edad del usuario final: si es menor de 18, **no usar Gemini API** (términos de Google).

## Recomendación (5 líneas)
1. Base local: **Ollama + `qwen3.5:4b`** (chat + visión + tools en ~4 GB), con `qwen3.5:2b` para pensamientos autónomos.
2. Voz en CPU: **openWakeWord ("Oye Sapo") → Silero VAD → Moonshine ES → Kokoro `ef_dora` con pitch +4** = voz kawaii sin gastar VRAM.
3. Manos: **Windows-MCP** para la PC y **mobile-mcp/ADB vía Tailscale** para Android, con confirmación en acciones peligrosas.
4. Alma: **sqlite-vec** + memory stream/reflexión estilo Generative Agents + variables de ánimo; el sapito admite que no es consciente.
5. Modo juego: detectar Fortnite/Roblox → descargar el LLM (`keep_alive:0`) y pasar a **Groq** (no entrena con tus datos); Gemini solo como respaldo no sensible y si el usuario es adulto.
