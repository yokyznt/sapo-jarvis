# Configuración compartida

Archivo: `%APPDATA%\Sapo\config.json` (o `%SAPO_HOME%\config.json`). JSON UTF-8, se escribe atómico (`.tmp` + rename). Cada programa solo toca su sección y conserva las demás. Cambios en vivo: el sapo y el cerebro releen el archivo cuando cambia su fecha de modificación (sondeo cada 1 s).

```json
{
  "pc": {
    "skin": "clasico",
    "energy": "Zen | Normal | Travieso",
    "size": 0,
    "monitor": "auto | <índice>",
    "pin": { "x": 960, "y": -250 },
    "sounds": true,
    "volume": 0.6
  },
  "brain": {
    "provider": "gemini | ollama",
    "gemini_model": "gemini-flash-latest",
    "gemini_lite_model": "gemini-flash-lite-latest",
    "ollama_model": "qwen3.5:4b",
    "ollama_game_model": "qwen3.5:2b",
    "personality": "sarcastico | tierno | tranquilo",
    "comment_minutes": 10,
    "attention": true,
    "vision": true,
    "blacklist": ["keepass", "1password", "bitwarden", "bbva", "banamex", "santander", "banorte", "whatsapp", "outlook", "gmail", "inprivate", "incógnito", "hermes"]
  },
  "voice": {
    "enabled": true,
    "wake": "oye sapo",
    "engine": "gemini | local",
    "voice": "ef_dora",
    "pitch": 2.5,
    "speed": 1.08,
    "mic": "",
    "speaker": ""
  },
  "clips": {
    "enabled": false,
    "method": "obs | native | medal | gamebar",
    "seconds": 30,
    "buffer": 120,
    "fps": 30,
    "folder": "",
    "monitor": 0,
    "medal_hotkey": "F8",
    "audio": true
  },
  "startup": { "autostart": false, "command": "" }
}
```

`size`: 0 chico, 1 mediano, 2 grande. Valores faltantes o inválidos = default.

## Secretos

`%APPDATA%\Sapo\secrets.json`: `{"gemini_api_key": "<base64 de CryptProtectData(utf-8, scope usuario)>"}`. Nunca en `config.json`, nunca en el repo, nunca en logs. Lo escribe Preferencias; lo lee el cerebro con `CryptUnprotectData`. Variable de entorno `GEMINI_API_KEY` tiene prioridad (desarrollo).
