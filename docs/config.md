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
  "startup": { "autostart": false, "command": "" },
  "phone": { "enabled": false, "name": "" }
}
```

`size`: 0 chico, 1 mediano, 2 grande. Valores faltantes o inválidos = default.

`brain.personality: "como_yo"` (también se acepta `brain.persona: "como_yo"`): el sapo habla como escribe el usuario usando el `describe` que mandó el celular (`phone_style.json`). Sin estilo guardado habla neutral.

## Enlace con el celular (etapa 9)

- `phone.enabled` (default `false`): el cerebro abre `ws://0.0.0.0:8766` y el descubrimiento UDP en `8767` solo mientras esté en `true`; se enciende y apaga en vivo (revisión cada 1 s). Al apagarlo cierra las conexiones (código 1001). `phone.name`: nombre que responde el descubrimiento; vacío = nombre del equipo.
- Descubrimiento: el cel manda `SAPO?` por UDP a 8767; respuesta `{"sapo":1,"port":8766,"name":"<equipo>"}`.
- Windows puede pedir permiso de firewall la primera vez (sin admin; el usuario acepta "Redes privadas").
- Límites: mensajes de texto ≤ 64 KB (más grande cierra con 1009), máx. 3 conexiones (la 4.ª cierra con 1013), el primer mensaje debe ser `hello` o `pair` en ≤ 10 s; si no, `{"type":"error","why":...}` y cierre 1008. Conexiones con `Origin` (navegadores) se rechazan.
- Tras `hello` válido: `{"type":"ok"}` y luego `{"type":"pc",...}`; tras `pair` válido: `{"type":"paired","token":...}` y luego `pc` (la conexión queda autenticada). `pc` se reenvía cuando cambia: `gaming` = el sapo está en modo juego, `app` = nombre del ejecutable en primer plano solo si `gaming` (y no está en la lista negra), `away` = sin teclado/ratón ≥ 5 min según la atención (false si la atención está apagada).
- `why` posibles: `no_code`, `bad_code`, `expired`, `too_many`, `bad_token`, `need_hello`, `bad_msg`, `bad_style`, `bad_phone`, `unknown`, `unavailable`.
- `style` → se guarda en `%APPDATA%\Sapo\phone_style.json` `{"profile":{...},"describe":"...","device":"...","at":"..."}` (describe limpio, máx. 2000 caracteres). `phone` → se guarda en memoria del cerebro (`busy`, `auto`).

### Código de vinculación

Lo genera Preferencias (botón "Vincular celular"): 6 dígitos con `SystemRandom`, vale 5 min. Se guarda **cifrado** en `secrets.json` como `"phone_pair": base64(DPAPI(json {"code":"123456","expires":<epoch s>,"tries":0}))`. El cerebro lo lee en cada `pair`: si vence o llega a 5 intentos fallidos lo borra; cada fallo incrementa `tries` (persistido); al acertar lo borra y agrega el token. Comparación con `hmac.compare_digest`.

### Tokens

`secrets.json` → `"phone_tokens": [{"id":"<8 hex>","device":"Nothing A059","date":"2026-10-31T12:00:00","token":"<base64 DPAPI del token de 64 hex>"}]` (máx. 20). Preferencias lista `device`/`date` y revoca borrando la entrada; el cerebro relee el archivo cuando cambia y cierra (1008) las conexiones de tokens revocados.

## Secretos

`%APPDATA%\Sapo\secrets.json`: `{"gemini_api_key": "<base64 de CryptProtectData(utf-8, scope usuario)>", "phone_pair": "...", "phone_tokens": [...]}` (ver arriba). Nunca en `config.json`, nunca en el repo, nunca en logs. Lo escribe Preferencias (el cerebro solo toca `phone_pair` y `phone_tokens`); lo lee el cerebro con `CryptUnprotectData`. Variable de entorno `GEMINI_API_KEY` tiene prioridad (desarrollo).
