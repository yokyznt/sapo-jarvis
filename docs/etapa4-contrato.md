# Etapa 4 · contrato sapo ↔ cerebro

Sapo → cerebro (nuevos, JSON por el WebSocket existente):

| type | campos | uso |
|---|---|---|
| `event` | `name: "file_drop"`, `path: str` | soltaron un archivo sobre el sapo; el cerebro lo resume (texto, PDF, imagen, código; máx. 2 MB) y responde con `say` |
| `event` | `name: "win"`, `what: "maximized" \| "minimized" \| "moved" \| "notification" \| "battery_low" \| "offline" \| "online" \| "muted" \| "screenshot" \| "clipboard" \| "hour"` | reacciones; el cerebro puede comentar (respeta calma y quiet) |
| `chat` | `text`, `source: "bubble"` | texto escrito en la burbuja tras doble clic |

Cerebro → sapo:

| type | campos | uso |
|---|---|---|
| `clip` | `state: "saved" \| "error" \| "recording"`, `path?`, `seconds?` | el sapo hace animación de cámara/flash y croac feliz al guardar |

Herramienta nueva del cerebro: `clip(seconds=30)` → guarda los últimos N s en `Videos\Sapo Clips`. Palabras de acción en `es.json`: clipea, clip, graba eso, guarda eso.

Config nueva:

```json
"clips": { "enabled": false, "method": "native | medal | gamebar", "seconds": 30, "buffer": 120, "fps": 30, "folder": "" }
```
`enabled` en false por defecto (consume GPU); se activa en Preferencias.
