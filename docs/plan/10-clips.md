# 10 · Clips

Etiqueta: `s10-clips` · Archivos: brain/sapo/clips/

## Tareas
- [x] Búfer FFmpeg ddagrab + h264_nvenc, segmentos de 2 s, últimos 2 min
- [x] Audio del sistema por WASAPI loopback
- [x] 'Clipea eso' une últimos 30 s → Videos\Sapo Clips
- [x] Métodos opcionales: Medal (atajo) y Game Bar
- [x] Funciona por voz en modo juego

## Criterios de aceptación
- [x] Clip real de 10 s con audio
- [x] Búfer no crece sin límite
- [x] Sin teclas simuladas en modo nativo

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|
| 2026-10-30 | Audio del clip en silencio (-91 dB) por CoInitializeEx antes de soundcard | Arreglado: importar soundcard primero; clip real con audio -14.8 dB | etapa-4 |
