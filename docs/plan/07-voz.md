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
| 2026-10-30 | Gemini leía en voz alta la instrucción de estilo ('dilo en español mexicano…') | Arreglado: solo se manda el texto; caché de voz borrada y versionada | etapa-6 |
| 2026-10-30 | Ruido fuerte al final de cada frase con Gemini: la respuesta es WAV con encabezado y metadatos C2PA al final y se reproducían como audio | Arreglado: se lee solo el bloque data del WAV; verificado con tu key (cola en silencio, sin clic al inicio) | etapa-6 |
| 2026-10-31 | A veces hablaba con voz robótica (Kokoro) | Causa: la capa gratis de Gemini TTS da solo 10 frases al día por modelo; al acabarse caía a la voz local. Arreglado: rota 4 modelos TTS con descanso por modelo, luego usa Gemini Live (gemini-3.8-live) como lector de voz humana sin tope diario (revisa que lea el texto exacto), guarda cada frase en caché, y si todo falla se queda callado con la burbuja en vez de usar la voz robótica. Probado con la key real: 30/30 frases con voz humana en 2 corridas, 0 robóticas; 260 pruebas ×3 | etapa-10 |
