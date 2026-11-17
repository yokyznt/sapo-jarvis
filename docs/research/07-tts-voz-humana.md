# 07 — TTS en español con voz humana, sin límites y de baja latencia

> Objetivo: reemplazar Kokoro `ef_dora` más el g2p propio, que el usuario siente robótico. Se busca una voz que suene humana, sin cuotas, con el primer audio en menos de 400 ms después de tener el texto, que se pueda redistribuir y que no pida admin.
> Fecha de la investigación: 2026-10-31. Las licencias y fechas salen de `huggingface.co/api/models/<id>` (`cardData.license`) y `api.github.com/repos/<repo>` consultadas ese día.
> Hardware: RTX 5060 Ti 8 GB (Blackwell sm_120, CUDA 12.8+), i7-12700, 32 GB RAM. Ollama ya ocupa parte de la VRAM con qwen3.5:4b.
> Leyenda: **[doc]** viene de la fuente oficial, **[medido]** lo medimos en esta máquina y **[estimado]** es una inferencia nuestra (por ejemplo, la VRAM calculada a partir del tamaño de los pesos) que hay que medir.

---

## 1. Tabla comparativa

| Modelo | Español / acento latino | Naturalidad | Latencia al primer audio / streaming | VRAM y descarga | Licencia del código / de los pesos | Windows | Clonación |
|---|---|---|---|---|---|---|---|
| **Chatterbox Multilingual V3 + pack `es-mx-latam`** (Resemble, 10-jun-2026) | **Sí, es-419/es-MX dedicado** [doc]. CER 0.28 % en LATAM contra 2.89 % del modelo base de español [doc] | Muy alta. Resemble dice que en v3 ya no se distingue de forma confiable al oído [doc] | **No hace streaming oficial.** No publica la latencia del modelo multilingüe. Hay que trocear por frases o usar el fork `chatterbox-streaming` (MIT, sin mantenimiento desde 2025-06) | Pesos de 3.2 GB (T3 2.14 GB + S3Gen 1.06 GB) [doc]. VRAM de unos 2–4 GB [estimado] | MIT / MIT [doc]. Mete una marca de agua PerTh inaudible en todo el audio [doc] | `pip install chatterbox-tts`, PyTorch. ⚠ Fija `torch==2.6.0` en Python < 3.14, una versión que no soporta Blackwell. Hay que usar Python 3.14 (torch ≥ 2.9) o forzar torch cu128 | Sí, zero-shot con un clip de unos 10 s |
| **Qwen3-TTS 12Hz 0.6B / 1.7B** (Qwen, ene-2026) | Sí, es uno de sus 10 idiomas [doc]. **Ninguna voz preset es hispana** (las 9 son zh/en/ja/ko) [doc]. Para tener acento mexicano hay que clonar una referencia mexicana | Alta | **Hace streaming nativo** y anuncia un primer paquete en **97 ms** [doc] (en su hardware) | 0.6B ≈ 2.5 GB de pesos [doc]. VRAM de unos 2–3 GB [estimado] | Apache-2.0 / Apache-2.0 [doc] | Paquete `qwen-tts` con PyTorch. FlashAttention 2 es opcional y difícil de usar en Windows. vLLM-Omni solo funciona en Linux | Sí, desde 3 s de audio. El modelo 1.7B-VoiceDesign crea una voz a partir de una descripción |
| **Kyutai Pocket TTS `spanish` / `spanish_24l`** (abr-2026) | Sí. Trae la voz `lola` (Common Voice es) [doc]. El acento depende de la voz que se clone | Buena para su tamaño (100M) | **Streaming en CPU, unos 200 ms al primer chunk** [doc]. Unas 6× tiempo real en un M4 [doc] | 219 MB (12 capas) o 672 MB (24 capas) [doc]. **Corre en CPU, 0 VRAM** | MIT / **CC-BY-4.0** (hay que dar crédito; se puede redistribuir) [doc] | **Binario Rust para Windows x86 que no necesita Python ni torch** [doc]. También `pip install pocket-tts` | Sí, con un wav o un embedding `.safetensors` |
| Fun-CosyVoice 3 0.5B (Alibaba, dic-2025) | Sí, es uno de sus 9 idiomas [doc]. No tiene voz mexicana | Alta | Streaming bidireccional (texto y audio) con **unos 150 ms** [doc] | Repo de 9.7 GB (con variantes) [doc]. VRAM de unos 3–4 GB [estimado] | Apache-2.0 / Apache-2.0 [doc] | Difícil: el repo apunta a Linux y conda | Sí |
| VibeVoice-Realtime 0.5B (Microsoft) | **Solo inglés oficialmente.** El español es "experimental, úsese con cautela" [doc] | Alta en inglés | Unos 200–300 ms al primer audio y acepta texto en streaming [doc] | 2.0 GB [doc] | MIT / MIT. Microsoft "no lo recomienda para uso comercial" [doc] | PyTorch | No. Las voces vienen embebidas por política anti-deepfake [doc] |
| NeuTTS-Nano-Spanish (Neuphonic, 2026) | Sí, es un modelo dedicado al español [doc] | Buena para su tamaño | Streaming solo con GGUF (llama.cpp) [doc] | Unos 230M parámetros. Corre en CPU o GPU | Código "NeuTTS Open License 1.0": gratis por debajo de 5 M USD/año de ingresos y **no es OSI**. El repo HF está gated | Necesita `llama-cpp-python`, que hay que compilar | Sí |
| Kokoro-82M `ef_dora`/`em_alex`/`em_santa` (lo que usamos hoy) | Español genérico. Las voces es **no tienen grado de calidad** en VOICES.md, señal de pocos datos [doc] | Media: la prosodia es plana y de ahí viene lo "robótico" | Muy rápido (CPU/GPU, sherpa-onnx) | 0.36 GB | Apache-2.0. **misaki usa espeak-ng (GPL-3) para es** [doc] | Excelente (sherpa-onnx v2.0.1, 2026-10-26) | No |
| Piper `es_MX-claude-high` / `es_MX-ald-medium` | **Sí, es-MX nativo** [doc] | Media (VITS, 22 kHz). Se oye "de GPS" | Muy rápido en CPU | Unos 60–110 MB por voz | Voces MIT (datasets apache-2.0 / Unlicense) [doc]. **El motor activo `piper1-gpl` es GPL-3**; el `rhasspy/piper` MIT está archivado. Alternativa: sherpa-onnx (Apache), aunque la fonemización sigue siendo espeak-ng (GPL) | Fácil con sherpa-onnx | No |
| Orpheus `3b-es_it-ft-research_release` | Español e italiano, "research preview" de abr-2025 [doc] | Alta en inglés; en español es irregular | Unos 200 ms en streaming en su servidor [doc] | 3B: unos 6–7 GB en fp16, unos 2–3 GB en Q4 [estimado]. **Compite con Ollama** | Apache-2.0 / Apache-2.0 | Con llama.cpp/LM Studio | No (voces fijas) |
| IndexTTS-2.5 (bilibili, ago-2026) | Sí, añadió es [doc] | Muy alta y con control de emoción | Autorregresivo, sin streaming de baja latencia documentado | Varios GB | Licencia propia "bilibili-model-license": prohíbe usar las salidas para entrenar otros modelos y pide permiso por encima de 100 M MAU [doc] | Difícil | Sí |
| F5-TTS + `jpgallegoar/F5-Spanish` | Sí, varios acentos latinos (AR, CL, CO, PE, PR…) [doc] | Alta | Flow-matching, sin streaming real | Unos 1.3 GB | Código MIT. **Pesos CC-BY-NC-4.0** (la tarjeta se contradice y dice CC0; manda la etiqueta NC) | Python | Sí |
| XTTS-v2 (Coqui) | Sí (17 idiomas) | Alta | Unos 200 ms en streaming | Unos 2 GB | Código del fork idiap MPL-2.0. **Pesos CPML: no comerciales**, y Coqui ya cerró, así que no hay a quién comprar licencia | Python | Sí |
| Fish Audio S1-mini / S2 / Drama 3 | Sí (13+ idiomas) | Muy alta | Streaming | Varios GB | **S1-mini CC-BY-NC-SA**. S2/Drama 3 usan la "Fish Audio Community License": comercial solo por debajo de 500 k USD/año | SGLang (Linux) | Sí |
| Higgs Audio v3 4B (Boson) | Más de 100 idiomas | Muy alta | Streaming | 4B: no cabe junto con Ollama | **Licencia de investigación y no comercial** [doc] | SGLang | Sí |
| Supertonic 3 (Supertone) | 31 idiomas, incluido es | Buena | Muy rápido (ONNX, CPU) | Pequeño | Código MIT / modelo OpenRAIL-M. **El repo está archivado y sin soporte** desde 2026 | ONNX, fácil | Con su Voice Builder (servicio) |
| MeloTTS-Spanish | Español de España | Media | CPU en tiempo real | Pequeño | MIT | Python | No |
| Kyutai TTS 1.6B, Sesame CSM-1B, Spark-TTS, Chatterbox Turbo/Nano/Flash | **No tienen español** (en/fr, en, zh/en y en respectivamente) [doc] | — | — | — | Spark es CC-BY-NC-SA | — | — |

### Servicios en línea

| Servicio | Estado en oct-2026 | Latencia | Límites | Riesgos |
|---|---|---|---|---|
| **edge-tts** (Edge Read Aloud) con `es-MX-DaliaNeural` / `es-MX-JorgeNeural` | **Funciona.** Estuvo caído del 10 al 13 de octubre de 2026 (HTTP 403) porque Microsoft empezó a exigir el token **Sec-MS-GEC v2**. Se arregló en edge-tts 7.3.0 (2026-10-13) [issue #490](https://github.com/rany2/edge-tts/issues/490) | **[medido hoy en esta PC]** primer audio en 491–681 ms y frase completa en 0.7–1.6 s. **No llega a los 400 ms** | Sin cuota publicada | API no oficial: se puede romper sin aviso, como ya pasó. Usarla fuera de Edge probablemente choca con los ToS de Microsoft. El texto sale de la PC, lo que contradice "sin telemetría". La librería es **LGPL-3** |
| **Gemini Live API** (`gemini-3.8-live`) / Gemini 3.8 Flash TTS | Capa gratis disponible ("Free of charge") [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Baja (audio a audio) | Los RPM/RPD van **por proyecto** y solo se ven en AI Studio. Los modelos preview tienen límites más estrictos. Las sesiones de solo audio duran 15 min y las conexiones unos 10 min [doc](https://ai.google.dev/gemini-api/docs/live-api/session-management) | **En la capa gratis Google usa los datos "to improve our products"** [pricing], lo que choca con "sin telemetría". No es ilimitado. Exige que el usuario tenga su propia API key. Además Live es voz a voz, así que reemplazaría a Ollama, no solo al TTS |

---

## 2. Recomendación

### Principal: **Chatterbox Multilingual V3, pack `es-mx-latam`** (MIT), en la GPU
- **Por qué:** es el único modelo abierto y permisivo **afinado específicamente para español de México/LATAM**, con el CER más bajo publicado (0.28 %) y una naturalidad que Resemble presenta como indistinguible al oído. Además clona voz, así que el sapo puede tener una voz propia y consistente si grabamos 10 s con permiso o usamos una referencia CC0.
- **Cómo llegar a menos de 400 ms:** no tiene streaming oficial. Hay que mandar al TTS la **primera frase corta** en cuanto el LLM la termine (por ejemplo, partir en `,.;!?` con un máximo de unas 8 palabras para el primer chunk) y encadenar el resto mientras suena. Para más, hacer streaming por bloques de tokens T3 hacia S3Gen, como `chatterbox-streaming`. **Hay que medirlo en la 5060 Ti:** nadie publica la latencia del modelo multilingüe.
- **Riesgos:**
  1. Fija `torch==2.6.0`, que no corre en Blackwell. Hay que instalar con Python 3.14 (el pyproject pide torch ≥ 2.9) o instalar torch cu128 aparte con `--no-deps`.
  2. La VRAM es justa junto a qwen3.5:4b: conviene cargar el TTS en fp16 o bf16 y medirlo.
  3. La descarga en el primer arranque es de unos 3.3 GB desde HF (no necesita admin).
  4. La marca de agua PerTh va siempre activa. Es inaudible, así que la vemos como un punto a favor.

### Respaldo: **Kyutai Pocket TTS `spanish_24l`** (código MIT, pesos CC-BY-4.0), en la CPU
- **Por qué:** es el único que **garantiza** menos de 400 ms (unos 200 ms al primer chunk [doc]) con streaming real, **sin usar VRAM** (Ollama queda libre). Trae un **binario de Windows sin Python** (sin admin), la descarga es chica (219–672 MB) y clona voz. Si clonamos la misma referencia que en Chatterbox, la voz cambia poco al pasar de uno a otro.
- **Riesgos:** como modelo de 100M, la prosodia es menos rica que la de Chatterbox. La voz `lola` no es necesariamente mexicana, así que conviene clonar una referencia mx. CC-BY obliga a dar crédito en CREDITOS.md.

### Alternativa a probar en A/B: **Qwen3-TTS 0.6B-Base** (Apache-2.0)
Tiene streaming nativo y anuncia 97 ms, así que podría ganarle a Chatterbox en latencia. Pero no trae voz hispana preset: el acento mexicano depende por completo de la referencia que se clone. En Windows no hay vLLM-Omni.

### Descartados y por qué
- Por la licencia, al no ser comerciales o redistribuibles: F5-Spanish, XTTS-v2, Fish, Higgs v3, Spark e IndexTTS (salvo que el proyecto acepte una licencia propia).
- Por no tener español: Kyutai 1.6B, CSM, Chatterbox Turbo/Nano/Flash. VibeVoice solo lo tiene experimental.
- Por GPL o por sonar robótico: Piper.
- Por mantenimiento: Supertonic, que está archivado.
- **edge-tts:** solo como opción *opt-in* "voz en la nube" desactivada por defecto. No es local, se rompió en octubre de 2026, mide unos 500–700 ms y es LGPL.
- **Gemini Live:** no es ilimitado, entrena con los datos en la capa gratis y pide API key.

### Nota sobre Kokoro
Que el g2p sea propio no es el problema principal: las voces es de Kokoro tienen pocos datos (no tienen grado en VOICES.md) y la prosodia es plana. Pasarse a misaki/espeak mete GPL-3 y no arregla la entonación.

---

## 3. Próximo paso sugerido (medir, no suponer)
1. Escuchar el demo `es-mx-latam`: https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-es-mx-latam
2. Hacer un benchmark local de unos 20 minutos con las mismas 10 frases del sapo: TTFA (tiempo al primer audio), RTF y VRAM pico en tres configuraciones: (a) Chatterbox es-mx en fp16 por frases, (b) Pocket `spanish_24l` en CPU, (c) Qwen3-TTS 0.6B en streaming. Hacerlo con qwen3.5:4b cargado en Ollama.

---

## Fuentes
- Chatterbox README y pyproject: https://github.com/resemble-ai/chatterbox · https://raw.githubusercontent.com/resemble-ai/chatterbox/master/pyproject.toml
- Anuncio de Chatterbox Multilingual v3 (CER, idiomas, PerTh): https://www.resemble.ai/resources/chatterbox-multilingual-v3-tts-with-embedded-watermarking-for-25-languages
- Pack es-MX/LATAM: https://huggingface.co/ResembleAI/Chatterbox-Multilingual-es-mx-latam
- Chatterbox Flash (solo inglés): https://huggingface.co/ResembleAI/chatterbox-flash
- Qwen3-TTS: https://github.com/QwenLM/Qwen3-TTS · https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base
- Pocket TTS: https://github.com/kyutai-labs/pocket-tts · https://huggingface.co/kyutai/pocket-tts · https://kyutai.org/tts/
- Kyutai DSM (TTS 1.6B en/fr): https://github.com/kyutai-labs/delayed-streams-modeling
- CosyVoice 3: https://github.com/FunAudioLLM/CosyVoice · https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512
- VibeVoice Realtime: https://github.com/microsoft/VibeVoice/blob/main/docs/vibevoice-realtime-0.5b.md
- NeuTTS y su licencia: https://github.com/neuphonic/neutts · https://raw.githubusercontent.com/neuphonic/neutts/main/LICENSE
- Voces de Kokoro: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- Voces Piper es_MX: https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_MX · motor GPL: https://github.com/OHF-Voice/piper1-gpl
- Orpheus: https://github.com/canopyai/Orpheus-TTS · https://huggingface.co/canopylabs/3b-es_it-ft-research_release
- IndexTTS-2.5: https://github.com/index-tts/index-tts · https://huggingface.co/IndexTeam/IndexTTS-2.5
- F5-Spanish: https://huggingface.co/jpgallegoar/F5-Spanish
- XTTS-v2 (CPML): https://huggingface.co/coqui/XTTS-v2 · fork: https://github.com/idiap/coqui-ai-TTS
- Fish (licencia de oct-2026): https://github.com/fishaudio/fish-speech/blob/main/LICENSE · S1-mini: https://huggingface.co/fishaudio/s1-mini
- Higgs Audio v3: https://github.com/boson-ai/higgs-audio · https://huggingface.co/bosonai/higgs-audio-v3-tts-4b
- Supertonic (archivado): https://github.com/supertone-inc/supertonic
- Sesame CSM: https://github.com/SesameAILabs/csm · Spark-TTS: https://huggingface.co/SparkAudio/Spark-TTS-0.5B · MeloTTS: https://github.com/myshell-ai/MeloTTS
- sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx
- edge-tts (licencia LGPL, 7.3.0, issue 403): https://github.com/rany2/edge-tts · https://github.com/rany2/edge-tts/issues/490
- Gemini: https://ai.google.dev/gemini-api/docs/pricing · https://ai.google.dev/gemini-api/docs/rate-limits · https://ai.google.dev/gemini-api/docs/live-api/session-management
