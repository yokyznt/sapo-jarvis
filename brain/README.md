# Cerebro del Sapo

Servidor local (Python + Ollama) que le da personalidad, memoria y ganas de molestar al sapo de Godot. Todo corre en tu PC, sin telemetría.

## Requisitos

- [uv](https://docs.astral.sh/uv/) y [Ollama](https://ollama.com)
- Modelos: `ollama pull qwen3.5:4b` y `ollama pull qwen3.5:2b`

## Uso

```bash
cd brain
uv run sapo-brain          # servidor en ws://127.0.0.1:8765 (-v para logs, --sin-autonomo)
uv run sapo-chat           # chatea por texto; /e petted 0.5 manda un evento; /salir
uv run pytest              # pruebas con un LLM falso, sin red
```

## Perfiles

| Hardware | Normal | Modo juego (`game_on`) |
|---|---|---|
| NVIDIA con 6 GB o más | `qwen3.5:4b` en GPU | descarga el 4b (`keep_alive: 0`) y usa `qwen3.5:2b` en CPU (`num_gpu: 0`) |
| Sin GPU | `qwen3.5:2b` en CPU | igual |

Si existe `GROQ_API_KEY` se usa Groq solo como respaldo cuando Ollama falla (`GROQ_MODEL`, por defecto `openai/gpt-oss-20b`).

## Variables

`SAPO_HOST`, `SAPO_PORT`, `SAPO_LANG` (`es`), `OLLAMA_URL`, `SAPO_MODEL_BIG`, `SAPO_MODEL_SMALL`, `SAPO_DB` (por defecto `%APPDATA%\Sapo\memoria.db`), `SAPO_HISTORY`, `SAPO_NUM_PREDICT`.

## Protocolo (un JSON por mensaje WebSocket)

Sapo → cerebro: `{"type":"hello","version":1}`, `{"type":"chat","text":"..."}`, `{"type":"event","name":"petted|thrown|ignored|woke|game_on|game_off|dancing|stole_cursor|moved_window","boredom":0.0-1.0}`

Cerebro → sapo: `{"type":"say","text":"≤90 caracteres","mood":"sarcastic|happy|annoyed|sleepy|curious"}`, `{"type":"action","name":"dance|jump|sleep|look_around|steal_cursor|none"}`, `{"type":"thinking","on":true}`

Los mensajes salen a todos los clientes conectados (sapo y `sapo-chat` ven lo mismo).

## Cómo piensa

- Personalidad e idioma en `sapo/prompts/<idioma>.md` y frases/eventos en `sapo/prompts/<idioma>.json`.
- Memoria SQLite: conversaciones, eventos y hechos del usuario (el LLM decide qué hecho guardar). `Retriever` en `sapo/memory.py` es el punto para enchufar sqlite-vec.
- Eventos: reacción del LLM con límite (25 s por evento, 4 por minuto); si está ocupado, frase rápida predefinida.
- Loop autónomo: cada 2–6 min (más seguido con aburrimiento alto, máx. 12/hora) decide si comenta o hace una acción. Callado en modo juego.
