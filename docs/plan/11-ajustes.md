# 11 · Ajustes y bandeja

Etiqueta: `s11-ajustes` · Archivos: pc/src/Settings*.cs, pc/src/Tray.cs, brain/sapo/config.py

## Tareas
- [x] Icono en bandeja: Ajustes, Calmar, Fijar/Soltar, Clipear, Salir
- [x] Ventana de ajustes: SapoPreferencias.exe (pywebview) con pestañas Sapo, Cerebro, Voz, Inicio, Acerca de; Sonidos y Clips se agregan en etapas 3–4
- [x] config.json único en %APPDATA%\Sapo, cambios en vivo por WebSocket

## Criterios de aceptación
- [x] Cada opción cambia sin reiniciar
- [x] Config corrupta → valores por defecto

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|
| 2026-10-31 | "Arrancar con Windows" decía "No encontré Sapo.exe" en la PC del usuario (usa el lanzador %APPDATA%\Sapo\iniciar.vbs, no el instalador) | Arreglado: si no hay Sapo.exe usa `wscript.exe "%APPDATA%\Sapo\iniciar.vbs"` y lo valida; activado para el usuario (HKCU Run \"Sapo\"); 44 pruebas ×3 | etapa-13 |
