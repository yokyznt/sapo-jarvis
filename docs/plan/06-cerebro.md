# 06 · Cerebro Gemini y frases

Etiqueta: `s06-cerebro` · Archivos: brain/sapo/llm.py, brain/sapo/providers/, brain/sapo/prompts/

## Tareas
- [ ] Proveedor intercambiable: Gemini (default) → Ollama de respaldo
- [ ] Flash para chat, herramientas y visión; Flash-Lite para espontáneos; IDs con models.list
- [ ] Key cifrada con DPAPI en %APPDATA%\Sapo
- [ ] Prompt nuevo: personaje fijo, ejemplos buenos y prohibidos, 4–18 palabras
- [ ] Anti-repetición contra las últimas 50 frases
- [ ] Resumen diario de memoria

## Criterios de aceptación
- [ ] Sin key o sin cupo cae a Ollama sin error visible
- [ ] pytest con proveedor falso
- [ ] Prueba real: chat, herramienta, visión

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|
