# 09 · Interacciones con Windows

Etiqueta: `s09-windows` · Archivos: pc/src/WinEvents.cs, pc/src/Frog.cs

## Tareas
- [x] Maximizar bajo él → cae; minimizar → susto; mover → tambaleo
- [ ] Sentarse en barra de tareas y reloj; croar cada hora
- [x] Voltear a notificaciones nuevas
- [x] Reaccionar a batería baja, sin internet, volumen 0, portapapeles, captura
- [x] Archivo arrastrado sobre el sapo → resumen con Gemini
- [x] Doble clic → chat de texto en burbuja

## Criterios de aceptación
- [x] Cada reacción probada con ventana de prueba en el monitor de arriba

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|
| 2026-10-30 | Al maximizar la ventana bajo el sapo quedaba flotando | Arreglado en ValidatePlatform; cae y avisa | etapa-4 |
| 2026-10-30 | Burbuja: 127 errores 'cannot be greater' en DrawBubble con burbuja angosta | Arreglado; 0 errores en la corrida siguiente | etapa-4 |
| 2026-10-30 | Batería baja nunca avisaba (se marcaba antes de conectar) | Arreglado: espera a estar conectado; evento recibido | etapa-4 |
| 2026-10-30 | Barra de tareas del monitor de arriba oculta automáticamente; notificaciones de prueba no generaron ventana | Pendiente de probar con toast real | etapa-4 |
