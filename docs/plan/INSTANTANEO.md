# Plan: sapo instantáneo, ilimitado y coherente

Metas (medidas en la PC del usuario, RTX 5060 Ti 8 GB):

| Métrica | Hoy | Meta |
|---|---|---|
| Texto empieza a aparecer | 1–15 s (Gemini primero, espera 14 s si está saturado) | < 0.3 s |
| Primer sonido de voz | 3–8 s (espera el audio completo) | < 0.7 s |
| Límite diario | Gemini TTS 10 frases/modelo, Gemini Flash ~20 peticiones | Sin límite (todo local) |
| Coherencia (quiz 15 preguntas) | variable | ≥ 14/15, cuentas 100 % |
| Herramientas (10 órdenes) | 5/10 con personalidad | 10/10 |
| Sin internet | se calla | habla igual |

Fuentes: `docs/research/07-tts-voz-humana.md`, `docs/research/08-cerebro-instantaneo.md` y la medición de latencias del 31-oct (Gemini Live ~1 s a primer audio, flash-lite ~0.8 s a primer token, qwen3.5:4b local 68–133 ms a primer token y ~92 tok/s).

## Arquitectura

```
voz (VAD+STT local) ─┐
chat / evento ───────┼─► router ─┬─ acción  → pasada de herramientas (prompt neutral, qwen3.5:4b) → ejecuta → frase
                     │           ├─ cuenta  → calcular (Python, exacto)
                     │           └─ charla  → chat con personalidad (qwen3.5:4b, streaming)
                     │                         └─ si no sabe / actualidad / jugando → nube (Gemma 4 26B → Groq → flash-lite)
                     └─► reacción inmediata (< 100 ms): animación + "mmm" pregrabado + burbuja "..."
tokens ──► cortador de frases ──► TTS local por frase (cola) ──► bocina + boca, mientras se genera la siguiente
```

- Todo lo normal corre local: ilimitado, sin cuotas, funciona sin internet.
- La nube es respaldo, nunca camino obligatorio, con tiempo máximo de 2 s antes de volver a local.
- El texto se muestra en la burbuja palabra por palabra mientras se genera.

## Etapas

### Etapa 11 · Cerebro instantáneo (local primero)
1. `Router` en `llm.py`: Ollama local primero; Gemini/Groq solo como respaldo o cuando `game` está activo. Sin espera de 14 s.
2. Streaming de tokens de Ollama hasta Godot (`say_part` en el protocolo, burbuja que crece).
3. Modelo siempre cargado: `keep_alive:-1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_FLASH_ATTENTION=1`, `num_ctx 4096`; arranque y vigilancia de Ollama desde el cerebro (hoy se apaga y nadie lo levanta).
4. Prompt de charla < 800 tokens; historial resumido; JSON quitado del chat (texto plano + etiquetas cortas para ánimo/acción).
5. Router de intención: herramientas con prompt neutral (10/10), `calcular` para cuentas, charla con personalidad.
6. Respaldo nube en orden: `gemma-4-26b-a4b-it` (Gemini API) → Groq `gpt-oss-20b` → `gemini-3.5-flash-lite`; key de Groq opcional en Preferencias.
7. Banco de pruebas `scripts/bench-cerebro/` en CI local: latencia, quiz 15 preguntas, 10 órdenes.

### Etapa 12 · Voz humana local ilimitada
1. Spike medido (Fase 0, abajo) entre Chatterbox Multilingual V3 `es-mx-latam` (GPU, MIT) y Kyutai Pocket TTS `spanish_24l` (CPU, streaming, CC-BY-4.0), opcional Qwen3-TTS 0.6B.
2. Servicio `sapo-tts` local con cola por frases, primer audio < 400 ms tras la primera frase.
3. Voz del sapo única: un clip de referencia (licencia libre o generado una vez) para que primaria y respaldo suenen igual.
4. Gemini TTS/Live quedan como opción "voz de nube" en Preferencias, apagada por defecto.
5. Frases fijas (saludos, reacciones, "mmm", errores) prerenderizadas al instalar → 0 ms.

### Etapa 13 · Tubería en streaming de punta a punta
1. Cortador de frases (puntuación, máx. ~12 palabras para la primera) y cola LLM → TTS → bocina, con la boca sincronizada por bloque.
2. Reacción inmediata al escuchar o recibir chat (< 100 ms).
3. Interrupción: si el usuario habla o hace clic, se corta la voz.
4. STT: medir y bajar el silencio de fin de frase (VAD) a ~0.5 s; reconocimiento parcial mientras hablas.

### Etapa 14 · Modo juego, calidad y memoria
1. Al detectar juego: sacar modelos de la GPU, chat por nube corto, voz Pocket TTS en CPU; al salir, recargar en segundo plano.
2. Coherencia: memoria de hechos del usuario recuperada por similitud (sin pasar el historial entero), detector de "no sé" → nube.
3. Presupuesto de VRAM vigilado (qwen 4b + TTS ≤ 7 GB); si no cabe, TTS a CPU.
4. Pruebas de regresión de latencia en cada PR (falla si el primer audio > 0.8 s en el banco).

## Fase 0 · Spike (antes de programar)
- Medir en la PC: Chatterbox es-mx fp16 por frases, Pocket TTS CPU y Qwen3-TTS con qwen3.5:4b cargado: primer audio, RTF, VRAM pico y calidad (10 frases del sapo, escucha del usuario).
- Medir STT actual (NeMo CTC int8): tiempo desde fin de voz a texto.
- Resultado: tabla en `docs/research/09-spike-voz.md` y decisión de motor.

## Riesgos
- torch para Blackwell (RTX 50) necesita CUDA 12.8+: Chatterbox fija `torch==2.6.0`; forzar torch ≥ 2.8 cu128.
- VRAM justa con juego + modelos: de ahí el modo juego.
- qwen3.5:4b inventa en cosas de actualidad: router a nube o "no sé".
- Instalador más pesado (+0.7–3.5 GB de modelos): descarga en el primer arranque, sin admin.
