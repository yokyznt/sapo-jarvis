# 09 — Spike de voz local (Fase 0)

> Medido el 2026-10-31 en la PC del usuario: RTX 5060 Ti 8 GB (driver 616.64), i7-12700, 32 GB, Windows 11, plan de energía "Alto rendimiento".
> Condición real: `qwen3.5:4b` cargado en la GPU con Ollama (`keep_alive 30m`, 3.1 GB de VRAM) durante todas las mediciones.
> Entorno aislado: `%LOCALAPPDATA%/hermes/cache/scratch/spike-voz` (un venv uv con Python 3.12 por motor: `cb`, `pk`, `qw`). No se tocó `brain/.venv`, solo se usó para correr el STT del proyecto.
> Frases: las 10 del sapo de `INSTANTANEO.md`. Cada motor hace un calentamiento antes de medir.

## Tabla

| Motor | Dispositivo | Primer audio | RTF (gen/dur) | VRAM pico (qwen cargado) | WER (STT NeMo) | Notas de instalación en Windows |
|---|---|---|---|---|---|---|
| **Pocket TTS `spanish` (12 capas), Python, 1 hilo** | CPU | **197 ms** media, 228 ms máx. (streaming) | **0.61** | 0 | 0.175 | `uv pip install pocket-tts` + torch 2.15 CPU, sin problemas. Carga 1–13 s |
| Pocket TTS `spanish`, Python, 4 hilos | CPU | **174 ms** media, 210 ms máx. | 0.70 | 0 | 0.151 | Igual. Más hilos no mejora el RTF |
| Pocket TTS `spanish`, binario Rust v4.0.1 (`serve`, HTTP streaming) | CPU | 276 ms media, 378 ms máx. (incluye HTTP) | 0.70 | 0 | 0.194 | Zip de GitHub, sin Python ni torch. `pocket-tts.exe serve --language spanish` → `POST /tts` (form `text`) devuelve WAV en streaming |
| Pocket TTS `spanish_24l`, Python, 1 hilo | CPU | 640 ms media, 851 ms máx. | **1.80** (más lento que tiempo real) | 0 | — | El propio binario avisa: los `24l` son "preview, no destilados" |
| Pocket TTS `spanish_24l`, Python, 4 hilos | CPU | 347 ms media, 402 ms máx. | **1.39** | 0 | 0.196 | |
| Pocket TTS `spanish_24l`, binario Rust | CPU | 885 ms media, 1025 ms máx. | **1.95** | 0 | 0.142 | |
| **Chatterbox Multilingual V3 `es-mx-latam`, fp32** | GPU | sin streaming: **4.75 s** para "Ya llevas dos horas en Roblox," (cláusula de 6 palabras) y 5.6 s la frase 1 completa | **1.60** | torch 3.56 GB; GPU total **7.99 / 8.15 GB** (al límite) | 0.182 | Ver "Problemas". Voz clonada de la referencia oficial `es_mx_f1.wav` |
| Chatterbox `es-mx-latam`, T3 en fp16 + autocast | GPU | 5.2 s cláusula, 6.3 s frase 1 | **1.80** | torch 2.61 GB; GPU total 7.5 GB | 0.186 | fp16 ahorra 1 GB pero no acelera |
| **Qwen3-TTS 12Hz 0.6B-Base**, bf16, sdpa | GPU | sin streaming: **12.2 s** cláusula, 25.8 s frase 1 | **4.80** | torch 2.55 GB; GPU total 7.0 GB | 0.158 | `qwen-tts` 0.1.1 + torch 2.8 cu128. Sin flash-attn. Clonación ICL con la misma referencia mx |

- **Primer audio**: en Pocket es el primer bloque del stream; en Chatterbox y Qwen3-TTS es el audio completo de la primera frase corta, porque su paquete no hace streaming.
- **RTF** > 1 significa que genera más lento de lo que dura el audio: la cola de frases se vacía y el sapo se queda callado entre frases.
- **WER**: transcribiendo cada WAV con el `Stt` del proyecto (`brain/sapo/voice`, NeMo fast-conformer CTC es int8). Todos los motores quedan entre 0.14 y 0.20, y casi todo el error es del STT con palabras coloquiales o nombres: "Órale" → "rale/Orale", "grandote" → "gran dote", "ahí mero" → "aimero/hay mero", "Excel a" → "excela", "chido" → "chiido". **No distingue naturalidad entre motores**: hay que escucharlos.
- **Silencios**: Pocket arranca con 0.3–0.5 s de silencio al inicio (media), así que el primer sonido audible llega en unos 0.5–0.6 s si no se recorta. También mete pausas de 0.4–0.67 s en las comas. Chatterbox (0.10 s al inicio) y Qwen3-TTS (0.14 s) casi no tienen silencio inicial. Ningún motor tuvo cortes raros a media palabra ni audio vacío.

## STT actual (NeMo CTC int8, sherpa-onnx, CPU)
- Transcribir un WAV de 2.5–4 s tarda **240–400 ms de mediana** (máx. 836 ms con la máquina ocupada), medido con `Stt.transcribe` del proyecto.
- A eso se suma la espera del VAD (`silence=0.8` s en `engine.py`), así que hoy pasan unos **1.1–1.2 s** desde que el usuario deja de hablar hasta tener el texto. Bajar el VAD a 0.5 s (Etapa 13) lo deja en unos 0.8 s.

## Recomendación
1. **Voz principal para la Etapa 12: Pocket TTS `spanish` (12 capas) en CPU.** Es el único motor que cumple las dos metas en esta PC: primer bloque en menos de 230 ms y tiempo real (RTF de 0.6–0.7) sin usar VRAM, así que qwen3.5:4b queda solo en la GPU. Usar 1–2 hilos (4 no mejora), recortar el silencio inicial del stream y meter el binario Rust como servicio `sapo-tts` (no hace falta Python ni torch en el instalador). Hay que dar crédito CC-BY-4.0 en CREDITOS.md.
2. **`spanish_24l` todavía no**: con RTF de 1.4–1.95 no llega a tiempo real en el i7-12700. Volver a medir cuando Kyutai publique la versión destilada.
3. **Chatterbox `es-mx-latam` no sirve para tiempo real tal cual.** Tarda unos 5 s por frase corta y es más lento que tiempo real, y fp16 no cambia la velocidad: hace 18–20 pasos/s del bucle T3 tanto en fp32 como en fp16, señal de que el límite es el bucle de Python/HF por token y no el cálculo. Además deja la GPU al límite junto a qwen. Usos posibles:
   - Prerenderizar en la instalación las frases fijas (saludos, "mmm", errores) con la voz mexicana, si al usuario le gusta más.
   - Hacer un spike aparte de optimización (CUDA graphs o `torch.compile` del T3, como los forks "fast"/`chatterbox-streaming`), con meta de RTF < 0.5, antes de pensarlo como voz principal.
4. **Qwen3-TTS 0.6B se descarta en Windows**: el paquete `qwen-tts` no hace streaming de generación (`non_streaming_mode` solo simula la entrada de texto) y da un RTF de 4.8. Su latencia anunciada de 97 ms depende de vLLM-Omni, que solo corre en Linux.
5. **Voz propia del sapo**: Pocket solo clona con los pesos "with voice cloning" del repo gated `kyutai/pocket-tts`, que piden aceptar los términos en HF y un `HF_TOKEN`. Sin eso solo hay voces del catálogo (`lola` para es). Decisión del usuario: aceptar los términos para clonar una referencia mx, o quedarse con `lola`.

## Audios para escuchar
`C:\Users\yokis\AppData\Local\hermes\cache\scratch\spike-voz\out\<motor>\01.wav … 10.wav`
- `pocket_spanish_lola_t1` (recomendado), `pocket_spanish_lola_t4`, `pocketrs_spanish_lola`
- `pocket_spanish_24l_lola_t4`, `pocketrs_spanish_24l_lola`
- `chatterbox_fp32`, `chatterbox_fp16` (voz `es_mx_f1`)
- `qwen3tts_0.6b` (voz `es_mx_f1` clonada)

⚠ La carpeta `scratch` se limpia sola tras 24 h sin uso: escúchalos o cópialos antes. Los números crudos están en `out/*.json` y `out/stt_eval.json`, y los scripts (`cb_bench.py`, `pk_bench.py`, `rust_bench.py`, `qw_bench.py`, `stt_eval.py`) en la misma carpeta.

## Problemas encontrados
- `pip install chatterbox-tts` (0.1.7) fija `torch==2.6.0` en Python < 3.14, una versión que no soporta Blackwell, y su `transformers==5.2.0` no coincide con el código del pack es-mx. Se usó el código que trae el Space oficial `ResembleAI/Chatterbox-Multilingual-TTS-es-mx-latam` (`chatterbox/src`, carga `t3_es_mx_latam.safetensors` + `s3gen_v3.pt`) con sus requisitos: `torch==2.8.0+cu128`, `transformers==4.46.3`, `numpy 1.26`, `librosa 0.10`.
- `librosa 0.10` importa `pkg_resources`, así que hubo que instalar `setuptools<81`.
- Las descargas de HF van por HTTP normal (sin `hf_xet`): unos 3.3 GB para Chatterbox y unos 2.5 GB para Qwen3-TTS. La primera carga de Chatterbox tardó 111 s y con caché 16 s.
- En Windows no hay symlinks en la caché de HF sin modo desarrollador (solo es un aviso, copia los archivos).
- La clonación de voz en Pocket (Python y Rust) falla sin acceso al repo gated: Python da `VOICE_CLONING_UNSUPPORTED` y Rust da HTTP 500.
- La VRAM "base" que reporta `nvidia-smi` varió entre 3.9 y 5.3 GB por otras apps abiertas (navegador, Discord, Spotify). Por eso la columna da el pico total medido y el pico de torch.
