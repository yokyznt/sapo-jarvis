# 12 · Ejecutable y arranque

Etiqueta: `s12-instalador` · Archivos: packaging/

## Tareas
- [x] Export Godot → Sapo.exe que lanza y vigila sapo-core
- [x] PyInstaller onedir para cerebro + voz + clips
- [x] Instalador Inno Setup por usuario sin admin
- [x] Autoinicio en HKCU Run con interruptor
- [ ] GitHub Release

## Criterios de aceptación
- [x] Instalar en carpeta limpia y arrancar tras reinicio
- [x] Desinstalar no deja procesos

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|
| 2026-10-30 | El export no compilaba C# por falta de Sapo.sln | Arreglado | etapa-5 |
| 2026-10-30 | sapo-brain empaquetado caía con UnicodeEncodeError (cp1252) | Arreglado: entradas fuerzan UTF-8 | etapa-5 |
| 2026-10-30 | config.json guardaba comillas como \u0022 | Arreglado: UnsafeRelaxedJsonEscaping; verificado en instalación | etapa-5 |
| 2026-10-30 | Inno Setup: ConnectServer de WMI no compilaba | Arreglado: taskkill | etapa-5 |
| 2026-10-30 | Con arranque con Windows activo, Preferencias decía apagado | Arreglado: Sapo.exe sincroniza startup.autostart con HKCU Run; verificado | etapa-5 |
| 2026-10-30 | Con config.json roto Sapo.exe lo sobrescribía al arrancar y se perdían todas las preferencias | Arreglado: si el JSON es inválido usa valores por defecto, lo avisa en el log y no guarda; verificado con SAPO_HOME temporal: el exe exportado arranca, 0 ERROR en 30 s y el archivo queda intacto (el build anterior lo reemplazaba) | etapa-6 |
