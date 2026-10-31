# 07 · Voz Gemini

Etiqueta: `s07-voz` · Archivos: brain/sapo/voice/

## Tareas
- [x] Palabra clave local sin cambios
- [ ] Sesión Gemini Live tras 'oye sapo', cierre a 20 s de silencio
- [x] Gemini TTS Flash-Lite para espontáneos, voz y estilo elegibles
- [x] Caché en disco de frases repetidas
- [x] Respaldo NeMo + Kokoro
- [x] Mandar amplitud al sapo para mover la boca

## Criterios de aceptación
- [ ] Prueba real 2 s TTS y 1 turno Live
- [x] Respaldo funciona sin red
- [x] Boca sincronizada en captura

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|
| 2026-10-30 | La boca casi no se abría al hablar (nivel máx. 0.57 con Kokoro) | Arreglado: nivel relativo al percentil 90 de la frase y boca ovalada al hablar; verificado en capturas | etapa-3 |
| 2026-10-30 | Gemini Live sin probar | Pendiente: requiere key; hoy oye sapo usa STT local + cerebro Gemini + voz Gemini | etapa-3 |
| 2026-10-30 | Interferencia al terminar de hablar | Salida de audio persistente (no abre/cierra por frase), rampas de 12 ms y 250 ms de silencio al final; falta confirmación del usuario (no se pudo medir: había otro audio sonando) | etapa-6 |
