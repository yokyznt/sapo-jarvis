# 06 · Cerebro Gemini y frases

Etiqueta: `s06-cerebro` · Archivos: brain/sapo/llm.py, brain/sapo/providers/, brain/sapo/prompts/

## Tareas
- [x] Proveedor intercambiable: Gemini (default) → Ollama de respaldo
- [x] Flash para chat, herramientas y visión; Flash-Lite para espontáneos; IDs con models.list
- [x] Key cifrada con DPAPI en %APPDATA%\Sapo
- [x] Prompt nuevo: personaje fijo, ejemplos buenos y prohibidos, 4–18 palabras
- [x] Anti-repetición contra las últimas 50 frases
- [ ] Resumen diario de memoria

## Criterios de aceptación
- [x] Sin key o sin cupo cae a Ollama sin error visible
- [x] pytest con proveedor falso
- [ ] Prueba real: chat, herramienta, visión

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|

Pendiente: prueba real con Gemini (falta key), resumen diario de memoria.
| 2026-10-30 | Una página web podía conectarse a ws://127.0.0.1:8765 y mandar órdenes | Arreglado: se rechaza cualquier Origin de navegador (403); prueba test_origin y sapo real conectado | etapa-6 |
| 2026-10-30 | Un mensaje WebSocket con type/name/what como lista u objeto, o un número gigante en boredom/level, tiraba la conexión con TypeError/OverflowError | Arreglado: protocol.py y server.relay validan que sean texto y acotan antes de convertir a float; prueba test_hardening | etapa-6 |
| 2026-10-30 | file_drop leía archivos sensibles a través de un junction/symlink (p. ej. docs -> .ssh) y abría rutas UNC `\\servidor` (fuga de hash NTLM) | Arreglado: files.read_drop rechaza rutas que empiezan con `\\` o `//` y revisa sensible también la ruta resuelta; prueba test_hardening | etapa-6 |
| 2026-10-30 | Si Gemini respondía 200 sin JSON a models.list (portal cautivo), el arranque del cerebro se caía con ValueError | Arreglado: gemini.models convierte el error en GeminiError; prueba test_hardening | etapa-6 |
