# 05 — Skills de agente y MCP servers para sapo-jarvis

Fecha: 2026-10-25. Fuente: https://skills.sh/ + `npx skills find <query>`. Instalación: `npx skills add <owner/repo@skill> -g -y`.

## Dónde quedaron instaladas

- Copia real: `C:\Users\yokis\.agents\skills\<skill>\SKILL.md`
- Symlink: `C:\Users\yokis\.claude\skills\<skill>`. El CLI además creó symlinks en otros agentes detectados (`.augment`, `.continue`, `.kiro`, `.roo`, `.trae`, `.openclaw`, etc.).
- En las 10 se comprobó que existe `SKILL.md` en las dos rutas.
- Aviso que no afecta nada: "PromptScript does not support global skill installation". Solo falló el destino PromptScript; los demás quedaron bien.

## Skills instaladas (10)

| # | Skill | Fuente (owner/repo) | Installs* | Tema | Ruta |
|---|-------|---------------------|-----------|------|------|
| 1 | mcp-builder | anthropics/skills (oficial) | 131K | Construir MCP servers (agentes/tools) | ~/.agents/skills/mcp-builder |
| 2 | tauri-v2 | nodnarbnitram/claude-code-extensions | 8K | Mascota de escritorio con Tauri 2 | ~/.agents/skills/tauri-v2 |
| 3 | godot-gdscript-patterns | wshobson/agents (repo muy popular) | 17.4K | Mascota con Godot / GDScript | ~/.agents/skills/godot-gdscript-patterns |
| 4 | android-cli | android/skills (oficial Google Android) | 2.9K | Tooling Android (build/adb/emulador) | ~/.agents/skills/android-cli |
| 5 | android-clean-architecture | affaan-m/ecc (everything-claude-code) | 12K | Arquitectura de app Kotlin | ~/.agents/skills/android-clean-architecture |
| 6 | huggingface-llm-trainer | huggingface/skills (oficial) | 2.2K | Fine-tuning de LLM (TRL/SFT/LoRA) | ~/.agents/skills/huggingface-llm-trainer |
| 7 | fine-tuning-expert | jeffallan/claude-skills | 4.2K | Fine-tuning general (LoRA/QLoRA, datasets) | ~/.agents/skills/fine-tuning-expert |
| 8 | openai-whisper | openclaw/openclaw (390K★) | 4.7–6.9K | STT local con el CLI de whisper | ~/.agents/skills/openai-whisper |
| 9 | whatsapp-automation | claude-office-skills/skills (536★) | 6.5K | Bots de WhatsApp (Business API) | ~/.agents/skills/whatsapp-automation |
| 10 | rive-interactive | freshtechbro/claudedesignskills | 2.6K | Animación Rive (state machines) | ~/.agents/skills/rive-interactive |

\*Installs según skills.sh/`npx skills find` el día de la búsqueda.

Desinstalar: `npx skills remove <skill> -g`.

## Candidatas evaluadas y descartadas

- **Unsloth**: todas tienen <120 installs (scientiacapital/skills@unsloth-training 117; nousresearch/hermes-agent@unsloth 21). Para fine-tuning se usan #6 y #7, más la documentación de Unsloth.
- **Ollama**: no hay ninguna skill específica de calidad. Mejor usar un MCP (abajo).
- **openai/skills@hatch-pet** (3.2K): está atada al pipeline `$imagegen` de Codex. Sirve como referencia de cómo armar un atlas de sprites para una mascota.
- **Pixel art**: layerai/skills@layer-pixel-art (3.4K) depende de la API de Layer; unity-technologies@2d-pixel-perfect es para Unity. Ninguna se instaló.
- **Voz/TTS**: ya existe la skill local `text-to-speech` (ElevenLabs). Hay una opción gratis: aahl/skills@edge-tts (8.2K), que no se instaló.
- **Overlay/Accessibility en Android**: no hay ninguna skill con tracción (<100 installs). Alternativas: android/skills (navigation-3, edge-to-edge, testing-setup) o jeffallan/claude-skills@kotlin-specialist (5.1K).
- **Electron**: no hay ninguna skill específica relevante.
- **WhatsApp (gokapso/*)**: depende del servicio de pago Kapso.

## MCP servers sugeridos (gratis, NO instalados)

| MCP | URL | Uso |
|-----|-----|-----|
| Windows-MCP (CursorTouch) | https://github.com/CursorTouch/Windows-MCP | Controlar Windows: UI, apps, teclado y mouse |
| adb-mcp (iksnerd) | https://github.com/iksnerd/adb-mcp | Manejar Android vía adb |
| android-mcp-server (minhalvp) | https://github.com/minhalvp/android-mcp-server | Controlar Android con adb (alternativa) |
| adb-mcp (srmorete) | https://github.com/srmorete/adb-mcp | Otra alternativa con adb |
| ollama-mcp (rawveg) | https://github.com/rawveg/ollama-mcp | Exponer Ollama local como tools MCP |
| ollama-mcp-server (hyzhak) | https://github.com/hyzhak/ollama-mcp-server | Alternativa para Ollama |
| whisper-mcp (jwulff) | https://github.com/jwulff/whisper-mcp | Transcripción local de audio |
| mcp-kokoro-tts | https://github.com/mrfqcentic/mcp-kokoro-tts | TTS local con Kokoro-82M |
| kokoro-tts-mcp (mberg) | https://github.com/mberg/kokoro-tts-mcp | TTS Kokoro (alternativa) |
| whatsapp-mcp (lharries) | https://github.com/lharries/whatsapp-mcp | WhatsApp personal vía whatsmeow (no oficial; riesgo de que baneen la cuenta) |

Antes de instalar cualquiera, revisa estrellas, actividad reciente y permisos. Ninguno necesita credenciales para evaluarlo.
