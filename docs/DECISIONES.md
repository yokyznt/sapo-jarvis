# Sapo-Jarvis: decisiones

Restricción global: 100% gratis.
Hardware PC: RTX 5060 Ti 8GB, i7-12700, 32GB RAM, Windows 11. Celular: Nothing Phone A059.

## Ronda 1
- Q1 Prioridad: todo igual (WhatsApp por mí, mascota que estorba, control PC/cel por voz).
- Q2 Orden: PC primero (sapo + cerebro), luego celular.
- Q3 Interacción: voz con palabra clave ("oye sapo") + texto.
- Q4 Juegos en pantalla completa: se duerme, no toca mouse/teclado, solo responde WhatsApp.
- Q5 Estilo: 2D kawaii vectorial con esqueleto.

## Ronda 2
- Motor PC: Godot 4 + C# (Skeleton2D, física, ventana transparente pequeña que sigue al sapo, Win32 por P/Invoke).
- WhatsApp: app en el Nothing con NotificationListener + respuesta directa (no Baileys en número personal).
- Autonomía WhatsApp: autónomo solo lista blanca + aviso 🤖, nunca grupos.
- Cerebro: Ollama qwen3.5:4b local + Groq gratis en modo juego. Gemini descartado.
- Tecla de pánico: sí.
- Estilo: RAG/few-shot primero, LoRA (Unsloth) después si no se parece.
- Celular: Kotlin nativo + permisos por adb + Tailscale.
- Confirmación en acciones peligrosas: NO marcada (pendiente R3).

## Ronda 3
- Confirmación: solo en lo irreversible (borrar archivos, pagos, llamar/escribir a alguien nuevo).
- Fase 1: sapo PC + cerebro + mini-app Android solo WhatsApp. Sapo del cel en fase 2.
- Aprendizaje: de mensajes ya enviados + adaptación continua con los nuevos (mecanismo pendiente R4).
- Molestia: según ánimo, molesta más si lo ignoras.
- Arte: SVG, bolita sin extremidades, ojitos, boca, pecas rojitas.

## Ronda 4
- Historial: el usuario exporta una vez 10–30 chats 1:1 .txt sin archivos.
- Mensajes nuevos propios: AccessibilityService lee lo que escribe en WhatsApp (local).
- Arrastre: lengua elástica (cursor, ventanas) + empuje con cuerpo gelatina. Anatomía: cuerpo soft-body, ojos, párpados, boca, mejillas, lengua.
- Ocupado: automático (juego, No molestar, cel sin uso X min) + comando manual.
- Personalidad: sarcástico y burlón.

## Restricción global nueva
- TODO público: PC + app Android instalables por cualquiera y funcionando con sus propias cuentas/datos. Reverificar decisiones contra esto.

## Ronda 5
- Licencia: MIT.
- Plataformas: solo Windows + Android.
- Idioma: español primero, i18n preparado.
- Sin GPU: detecta hardware; GPU → local, sin GPU → modelo chico en CPU o Groq BYOK.
- Sin telemetría, todo local, updates por GitHub Releases.
- Pendiente: research/06-publico.md (verificación devs Android 2026, restricted settings sin adb, firma Windows, licencias Moonshine/openWakeWord).

## Ronda 6 (sin respuesta en 60 min → se toman las recomendadas)
- Android: GitHub Releases + Obtainium; F-Droid después (sin Firebase/Play Services). Play descartado (política de accesibilidad).
- Verificación Google 2027 (MX): se decide en 2027; mientras tanto gratis.
- Windows: exe sin firmar en GitHub Releases + winget.
- Modo juego: qwen3.5:2b en CPU sin cuenta; Groq opcional BYOK.
- Wake word: sherpa-onnx KWS (Apache), palabra configurable. openWakeWord fuera (modelos NC).
- TTS: Kokoro + espeak-ng como componente GPL separado; repo MIT.
- STT: Moonshine streaming es (MIT), no "Spanish Base".
- Sin admin: no controla ventanas elevadas.

## Ronda 7 (v2)
- Gemini como cerebro y voz por defecto (plan gratis, key propia cifrada con DPAPI); Ollama/Kokoro de respaldo. Reemplaza el descarte de Gemini de la ronda 2.
- Diseño blob tipo Grok/Coucou, sin extremidades, con skins seleccionables.
- Arrastre entre monitores, nenúfar para fijarlo, energía ajustable (default calmado).
- Comentarios sobre la ventana en primer plano con límite de frecuencia y lista negra.
- Croacs procedurales, interacciones con Windows, clips nativos con FFmpeg (Medal/Game Bar opcionales).
- Ajustes + bandeja, Sapo.exe con instalador por usuario y autoinicio.
- Plan completo en PLAN-v2.md.
