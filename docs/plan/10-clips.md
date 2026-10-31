# 10 · Clips

Etiqueta: `s10-clips` · Archivos: brain/sapo/clips/

## Tareas
- [x] Búfer FFmpeg ddagrab + h264_nvenc, segmentos de 2 s, últimos 2 min
- [x] Audio del sistema por WASAPI loopback
- [x] 'Clipea eso' une últimos 30 s → Videos\Sapo Clips
- [x] Métodos opcionales: Medal (atajo) y Game Bar
- [x] Funciona por voz en modo juego

- [x] Pantalla completa exclusiva vía OBS (obs-websocket, replay buffer + Game Capture)

## Criterios de aceptación
- [x] Clip real de 10 s con audio
- [x] Búfer no crece sin límite
- [x] Sin teclas simuladas en modo nativo

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|
| 2026-10-30 | Audio del clip en silencio (-91 dB) por CoInitializeEx antes de soundcard | Arreglado: importar soundcard primero; clip real con audio -14.8 dB | etapa-4 |
| 2026-10-30 | OBS respondía 'not ready' al conectar | Arreglado: reintenta mientras OBS arranca | etapa-4 |
| 2026-10-30 | OBS quedaba escondido en el diálogo de modo seguro tras un cierre forzado | Arreglado: limpia .sentinel antes de lanzar | etapa-4 |
| 2026-10-30 | La escena 'Sapo Clips' quedaba como escena del usuario | Arreglado: restaura la escena anterior al cerrar | etapa-4 |
| 2026-10-30 | Con OBS ya abierto, el primer intento fallaba y reintentaba a los 15 s | Arreglado: reintento a 5 s; 3/3 clips reales con OBS del usuario | etapa-4 |
| 2026-10-30 | Audio de clips con OBS sin verificar | Verificado: tono de prueba en el clip a -17 dB | etapa-6 |
