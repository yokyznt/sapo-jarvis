# Etapas 11–13 · contrato del sapo instantáneo

## Protocolo nuevo (cerebro → Godot y voz)

| Mensaje | Uso |
|---|---|
| `{"type":"say_start","id":"<n>","mood":"happy"}` | Empieza una respuesta en streaming. Godot abre la burbuja vacía y quita los puntitos de "pensando". |
| `{"type":"say_part","id":"<n>","text":"Es Canberra."}` | Una frase completa (termina en `.`, `?`, `!`, `…`, `:` o salto, o un trozo de ≤ 14 palabras cortado en coma/espacio). Godot la agrega a la burbuja; la voz la pone en su cola. |
| `{"type":"say_end","id":"<n>","action":"none"}` | Fin. Godot calcula la vida de la burbuja con el texto total; la voz deja de esperar partes. |
| `{"type":"say","text":...,"mood":...}` | Se mantiene para respuestas de una pieza (frases fijas, eventos). |
| `{"type":"hush"}` | Godot o la voz piden callar: el cerebro cancela el streaming en curso y la voz vacía su cola y corta el audio. |

`MAX_SAY` aplica al total (280). `id` es un contador por proceso.

## Cerebro (`brain/`)
- `Router.stream(messages) -> AsyncIterator[str]`: Ollama local primero (`/api/chat` con `stream:true`, `think:false`, sin `format`, `keep_alive:-1`); si Ollama no da el primer token en 1.5 s o falla, cae a Gemini `streamGenerateContent` (`gemma-4-26b-a4b-it`, luego `gemini-3.5-flash-lite`). Si `game` está activo, nube primero.
- Chat con personalidad en texto plano: la primera línea puede llevar `[ánimo]` (p. ej. `[happy]`); sin JSON.
- `Sentences`: corta tokens en frases según la tabla de arriba; la primera frase sale en cuanto hay ≥ 3 palabras y un signo de corte.
- `Brain.respond_stream(text)`: misma memoria, `facts.verified`, herramientas (si `wants_tools`, la pasada de herramientas sigue siendo de una pieza y se manda con `say`).
- Prompt de charla < 800 tokens.
- Ollama: `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_FLASH_ATTENTION=1` al lanzarlo; precarga del modelo al arrancar y cada 5 min si se descargó; vigilancia cada 10 s.

## Voz (`brain/sapo/voice/`)
- `LiveSession`: conexión `gemini-3.8-live` siempre abierta con el lector; se reabre a los 8 min, al cambiar voz/modelo o si falla; `speak(text) -> Iterator[np.ndarray]` entrega bloques PCM 24 kHz conforme llegan.
- `Speaker.stream_say(blocks)`: toca cada bloque en cuanto llega (OutputStream persistente), manda `speaking`/`mouth` igual que hoy.
- Cola por `id`: `say_part` se encola; mientras suena una frase se pide la siguiente a Live (máx. 1 adelantada). `hush` corta.
- Caché: frases completas se guardan como hoy; si la frase está en caché se toca sin red.
- Respaldo: si Live falla → Gemini TTS rotando modelos → silencio. Nunca voz local.

## Godot (`pc/`)
- `say_start/say_part/say_end` en `FrogBrain.cs`: burbuja que crece; el ánimo se aplica en `say_start`.
- Reacción inmediata (< 100 ms) al mandar chat o al terminar de oír la palabra clave: ojitos atentos + "mmm" (croac corto suave) + puntitos.
- Clic sobre el sapo mientras habla → manda `hush`.

## Metas medibles
- Ollama caliente: primer `say_part` < 600 ms tras el chat.
- Primer audio < 1.2 s tras el chat (cerebro + Live caliente).
- Quiz de 15 preguntas ≥ 14/15; 10 órdenes 10/10.
