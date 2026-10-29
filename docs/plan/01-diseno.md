# 01 · Diseño y skins

Etiqueta: `s01-diseno` · Archivos: pc/src/FrogDraw.cs, pc/src/Jelly.cs, pc/skins.json (+ skins propios en %APPDATA%\Sapo\skins\*.json), assets/skins/

## Tareas
- [x] Blob único estilo Grok/Coucou sin extremidades (silueta, jorobas de ojos, contorno uniforme)
- [x] Resortes más suaves: rebote corto, respiración visible, parpadeo espaciado
- [x] Skins en JSON (pc/skins.json): Clásico, Menta, Rosa, Noche, Dorado, Axolote, Hojita, Gotita
- [x] Carga y cambio de skin en vivo
- [x] Generar assets/skins/*.svg desde el JSON

## Criterios de aceptación
- [x] Captura x4 de cada skin sin artefactos
- [x] Cambio de skin sin reiniciar
- [x] 0 advertencias de compilación

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|
| 2026-10-25 | Contorno doble entre ojos y cabeza | Arreglado: silueta única por unión de polígonos | etapa-1 |
