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
