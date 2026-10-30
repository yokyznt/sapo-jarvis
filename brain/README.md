# Cerebro del Sapo

Servidor local (Python + Ollama) que le da personalidad, memoria y ganas de molestar al sapo de Godot. Todo corre en tu PC, sin telemetría.

## Requisitos

- [uv](https://docs.astral.sh/uv/) y [Ollama](https://ollama.com)
- Modelos: `ollama pull qwen3.5:4b` y `ollama pull qwen3.5:2b`

## Uso

```bash
cd brain
uv run sapo-brain          # servidor en ws://127.0.0.1:8765 (-v para logs, --sin-autonomo)
uv run sapo-chat           # chatea por texto; /e petted 0.5 manda un evento; /si y /no confirman; /salir
uv run pytest              # pruebas con un LLM y un sistema operativo falsos, sin red
```

## Perfiles

| Hardware | Normal | Modo juego (`game_on`) |
|---|---|---|
| NVIDIA con 6 GB o más | `qwen3.5:4b` en GPU | descarga el 4b (`keep_alive: 0`) y usa `qwen3.5:2b` en CPU (`num_gpu: 0`) |
| Sin GPU | `qwen3.5:2b` en CPU | igual |

Si existe `GROQ_API_KEY` se usa Groq solo como respaldo cuando Ollama falla (`GROQ_MODEL`, por defecto `openai/gpt-oss-20b`).

## Variables

`SAPO_HOST`, `SAPO_PORT`, `SAPO_LANG` (`es`), `OLLAMA_URL`, `SAPO_MODEL_BIG`, `SAPO_MODEL_SMALL`, `SAPO_DB` (por defecto `%APPDATA%\Sapo\memoria.db`), `SAPO_HISTORY`, `SAPO_NUM_PREDICT`, `SAPO_TOOLS` (`0` apaga las herramientas), `SAPO_CONFIRM_TIMEOUT` (30 s), `SAPO_SEARCH_URL` (por defecto DuckDuckGo, `{q}` es la búsqueda), `SAPO_NOTES` (por defecto `Documentos\Sapo`).

## Protocolo (un JSON por mensaje WebSocket)

Sapo → cerebro: `{"type":"hello","version":1}`, `{"type":"chat","text":"..."}`, `{"type":"event","name":"petted|thrown|ignored|woke|game_on|game_off|dancing|stole_cursor|moved_window","boredom":0.0-1.0}`, `{"type":"confirm_reply","id":"...","ok":true}`

Cerebro → sapo: `{"type":"say","text":"≤90 caracteres","mood":"sarcastic|happy|annoyed|sleepy|curious"}`, `{"type":"action","name":"dance|jump|sleep|look_around|steal_cursor|none"}`, `{"type":"thinking","on":true}`, `{"type":"confirm","id":"...","text":"¿Apago la compu?"}`

Los mensajes salen a todos los clientes conectados (sapo y `sapo-chat` ven lo mismo).

## Cómo piensa

- Personalidad e idioma en `sapo/prompts/<idioma>.md` y frases/eventos en `sapo/prompts/<idioma>.json`.
- Memoria SQLite: conversaciones, eventos y hechos del usuario (el LLM decide qué hecho guardar). `Retriever` en `sapo/memory.py` es el punto para enchufar sqlite-vec.
- Eventos: reacción del LLM con límite (25 s por evento, 4 por minuto); si está ocupado, frase rápida predefinida.
- Loop autónomo: cada 2–6 min (más seguido con aburrimiento alto, máx. 12/hora) decide si comenta o hace una acción. Callado en modo juego.

## Herramientas (control de la PC)

Si pides algo por chat o voz, el cerebro usa tool calling nativo de Ollama (`/api/chat` con `tools`): el modelo elige la herramienta, el cerebro la ejecuta y una segunda llamada (con el JSON de siempre) contesta con el resultado. Solo se ofrecen herramientas si el mensaje trae alguna palabra de acción (`tool_words` en `prompts/es.json`); la plática normal va directo sin ellas.

| Herramienta | Qué hace | Ejemplo |
|---|---|---|
| `open_app` | abre una app por nombre (alias, accesos `.lnk` del menú Inicio y escritorio, apps de la Tienda vía `Get-StartApps`) | "abre Spotify" |
| `open_url` / `web_search` | abre una página o busca en el navegador | "busca recetas de chilaquiles" |
| `volume` | subir, bajar, fijar %, silenciar, consultar (pycaw) | "ponle el volumen al 30" |
| `media` | play/pausa, siguiente, anterior, detener (teclas multimedia con `SendInput`) | "siguiente canción" |
| `get_time` | fecha y hora | "qué hora es" |
| `set_timer` | temporizador o recordatorio en minutos o a una hora `HH:MM`; al vencer el sapo lo dice | "recuérdame la junta a las 17:30" |
| `open_folder` | documentos, descargas, escritorio, imágenes, música, videos o una ruta | "abre mis descargas" |
| `create_note` | guarda una nota `.txt` en `Documentos\Sapo` | "anota que compre tortillas" |
| `clipboard_read` / `clipboard_write` | lee o copia texto del portapapeles | "qué tengo copiado" |
| `list_windows` | lista las ventanas abiertas | "qué ventanas tengo abiertas" |
| `window` | minimiza, maximiza, restaura o enfoca una ventana | "minimiza Discord" |
| `screen` | captura la pantalla y la describe con la visión de qwen3.5 | "qué hay en mi pantalla" |
| `lock_pc` | bloquea la PC | "bloquea la compu" |
| `power` ⚠ | apagar, reiniciar, suspender | "apaga la compu" |
| `close_window` ⚠ | cierra una ventana o app (`WM_CLOSE`, la app puede pedir guardar) | "cierra el bloc de notas" |
| `delete_file` ⚠ | manda un archivo o carpeta a la papelera (send2trash); nunca toca `C:\Windows`, `Archivos de programa`, raíces de disco ni tus carpetas principales | "borra viejo.zip de descargas" |

⚠ **Confirmación**: antes de algo irreversible el cerebro manda `{"type":"confirm","id","text"}` a todos los clientes y espera hasta 30 s un `confirm_reply` con ese `id`, o un chat (texto o voz) que empiece con "sí / dale / va / ok" o "no / nel / cancela". Cualquier otro mensaje, o el silencio, cancela.

**Modo juego**: con `game_on` no se ejecuta nada que toque ventanas, mouse, teclado o capturas (`open_*`, `web_search`, `media`, `window`, `close_window`, `screen`, `lock_pc`); el sapo contesta que ahorita no. Hora, volumen, recordatorios, notas, portapapeles, lista de ventanas y energía (con confirmación) sí funcionan.

Las herramientas viven en `sapo/tools.py` (`Toolbox`, lógica pura) sobre la interfaz `PC` de `sapo/pc.py` (`WindowsPC` con ctypes, pycaw, Pillow y send2trash). Las pruebas usan un `FakePC` y nunca ejecutan acciones reales. Los temporizadores viven en memoria: se pierden si reinicias el cerebro.

## Voz

```
uv run sapo-voice            # escucha el micrófono; di "oye sapo, ¿qué hora es?"
uv run sapo-voice --decir "Croac"
uv run sapo-voice --dispositivos
```

- Palabra clave: VAD + voz a texto y búsqueda aproximada de "oye sapo" (`--palabra` / `SAPO_WAKE`). sherpa-onnx no tiene palabra clave en español.
- Todo en CPU. Modelos en `%APPDATA%\Sapo\models` (se bajan solos la primera vez, ~40 s). RAM ~620 MB. Voz a texto ~0.3 s; primer audio hablado ~1.3 s.
- Voz `ef_dora` con tono +2.5 (`--tono`, `--velocidad`, `--voz`). El micrófono se silencia mientras habla.
- Conversor de texto a fonemas propio para español: no usa espeak-ng (sin dependencias GPL).

### Créditos de modelos

| Uso | Modelo | Licencia |
|---|---|---|
| Detección de voz | Silero VAD | MIT |
| Voz a texto | NVIDIA NeMo FastConformer CTC es (sherpa-onnx int8) | CC-BY-4.0 |
| Texto a voz | Kokoro-82M v1.0 multi-lang (hexgrad) | Apache-2.0 |

## Gemini

- Proveedor por defecto si hay key (`GEMINI_API_KEY` o la guardada en Preferencias, cifrada con DPAPI en `%APPDATA%\Sapo\secrets.json`). Sin key, sin red o sin cupo usa Ollama y reintenta Gemini después.
- `brain.gemini_model` (chat, herramientas, visión) y `brain.gemini_lite_model` (comentarios espontáneos) en `config.json`.
- Plan gratis: Google puede usar los datos para mejorar sus productos.

## Atención y calma

- Lee la ventana activa cada 3 s; comenta una vez tras 2 min en una actividad nueva; captura con visión máx. 1 cada 10 min si el título no basta.
- Lista negra (`brain.blacklist`): nunca comenta ni captura.
- Máx. 1 espontáneo cada `brain.comment_minutes`; nunca dos seguidos sin que respondas; silencio en juego, llamadas y pantalla completa.

## Voz Gemini y boca

- `voice.engine`: `gemini` (voz `voice.gemini_voice`, modelo `voice.tts_model`) o `local` (Kokoro). Sin key, sin red o con error usa Kokoro sin avisar y reintenta Gemini después.
- Caché de frases en `%APPDATA%\Sapo\cache\tts` (máx. 200 MB).
- Mientras habla manda `speaking` y `mouth` (~30 por segundo) para mover la boca del sapo.
- Con `quiet` (juego, llamada, pantalla completa) solo habla si le preguntaste en el último minuto.

## Clips

- Activa `clips.enabled` en Preferencias. FFmpeg (`winget install Gyan.FFmpeg`) graba la pantalla en segmentos de 2 s (búfer de `clips.buffer` s en `%LOCALAPPDATA%\Sapo\clipbuf`) con NVENC/AMF/QSV o x264, y el audio del sistema por WASAPI loopback (soundcard).
- "Sapo clipea eso" guarda los últimos `clips.seconds` s en `Videos\Sapo Clips`. Funciona aunque estés jugando.
- `medal` y `gamebar` simulan su atajo de teclado: algunos anti-cheat (EAC, Vanguard) pueden marcar teclas simuladas; el modo `native` no toca el juego.
- No captura juegos en pantalla completa exclusiva; usa ventana sin bordes.

## Archivos y Windows

- Suelta un archivo sobre el sapo: lo resume en 1–2 frases (texto, código, PDF; imágenes con Gemini). Nunca lee `.env`, llaves, `.ssh` ni nombres con password/token.
- Reacciona a maximizar, minimizar, mover ventanas, notificaciones, batería baja, sin internet, silencio, capturas y portapapeles, con enfriamiento y en silencio en juego o llamadas.
- Doble clic al sapo: escribe en su burbuja.
