# Sapo-Jarvis: plan

Público, MIT, 100% gratis. Windows + Android. Español primero (i18n). Sin telemetría. Ver DECISIONES.md y research/01–06.

## Arquitectura
```
[Godot 4 C# — sapo PC]  <--WebSocket localhost-->  [Cerebro (Python/uv)]  <--WebSocket Tailscale/LAN-->  [App Android Kotlin]
  ventana transparente                              Ollama (4b GPU | 2b CPU | Groq BYOK)                 NotificationListener (responder WA)
  soft-body + lengua                                memoria sqlite-vec + reflexiones + ánimo             Accessibility (leer lo que escribes en WA, tocar)
  Win32: mouse, ventanas, taskbar                   voz: sherpa-onnx KWS → Silero VAD → Moonshine es      Overlay sapo (fase 2), llamadas, SMS
  tecla de pánico, modo juego                       → Kokoro (espeak-ng aparte)                         
                                                    herramientas: Windows-MCP, adb/app, WhatsApp
                                                    estilo: RAG con tus chats exportados
```

## Fases
1. **Sapo PC**: SVG bolita (ojos, párpados, boca, pecas, lengua) → Godot soft-body, saltos sobre ventanas/taskbar, lengua que jala cursor y ventanas, ánimo (molesta más si lo ignoras), tecla de pánico, detección de juego → duerme sin tocar input.
2. **Cerebro**: servidor local, perfiles de hardware, personalidad sarcástica, memoria, chat texto + "oye sapo", herramientas PC con confirmación solo en irreversible.
3. **Mini-app Android WhatsApp**: notificaciones + respuesta directa, lista blanca, 🤖, nunca grupos, modo ocupado (juego / No molestar / sin uso X min / manual), accesibilidad para aprender tus mensajes nuevos, importador de .txt exportados.
4. **LoRA opcional** (Unsloth, Python 3.11–3.13, CUDA 12.8) si el RAG no se parece.
5. **Sapo en Android**: overlay, control del cel, llamadas, SMS.
6. **Publicación**: GitHub Releases + winget + Obtainium; F-Droid; onboarding de permisos sin adb.

## Organización con subagentes (por fase)
- Agente arte/animación (SVG + Godot rig) · agente Win32 · agente cerebro/voz · agente Android · agente revisor (code-review + tests).
- Skills: godot-gdscript-patterns, windows-desktop-apps, mcp-builder, openai-whisper, android-cli, android-clean-architecture, fine-tuning-expert, huggingface-llm-trainer, tdd, code-review, animate.

## Lo que tienes que hacer tú (cuando toque)
- Fase 3: exportar 10–30 chats 1:1 (.txt sin archivos).
- Opcional: key de Groq (18+).
