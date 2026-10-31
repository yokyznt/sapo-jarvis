# Etapa 3 · contrato voz ↔ sapo

Mensajes nuevos del cerebro/voz al sapo (WebSocket `ws://127.0.0.1:8765`, JSON):

| type | campos | uso |
|---|---|---|
| `speaking` | `on: bool` | empieza/termina de hablar en voz alta |
| `mouth` | `level: 0..1` | amplitud RMS suavizada, ~30 Hz mientras habla; el sapo abre la boca proporcional |
| `quiet` | `on: bool`, `reason: "game" \| "call" \| "fullscreen"` | silencio: sin croacs ni voz espontánea mientras `on` |
| `croak` | `kind` | pide un croac puntual (`corto`, `doble`, `grunon`, `feliz`, `sueno`, `sorpresa`, `aterrizaje`, `plop`) |

El sapo ignora tipos desconocidos. El cerebro reenvía a todos los clientes (`pc` y `voice`) los mensajes `speaking`, `mouth`, `quiet` y `croak`.

## Config nueva

```json
"pc": { "sounds": true, "volume": 0.6, "croak_min": 3, "croak_max": 10 },
"voice": { "engine": "gemini | local", "gemini_voice": "Puck", "voice": "ef_dora", "live": true, "live_timeout": 20 }
```
