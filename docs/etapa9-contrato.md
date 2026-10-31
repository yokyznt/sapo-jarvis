# Etapa 9 · Aprende de ti + enlace cel ↔ PC

## A. `:core` (JVM, con pruebas)

```kotlin
data class TypedEvent(val chat: String, val text: String, val atMs: Long)
class TypedCapture(val minChars: Int = 1) {
    fun onText(e: TypedEvent): String?
    fun onSendClick(chat: String, atMs: Long): String?
}

class Learner(maxMine: Int = 5000) {
    fun addMine(chat: String, text: String, atMs: Long, lastIncoming: ChatLine?)
    fun mine(): List<String>
    fun pairs(): List<Pair>
    fun profile(base: StyleProfile?): StyleProfile
    fun toJson(): String
    companion object { fun fromJson(s: String): Learner }
}

enum class BusyReason { Manual, NoMolestar, PantallaApagada, Horario, JugandoPC }
data class BusyState(..., val pcGaming: Boolean = false)

object Link {
    const val PORT = 8766
    const val DISCOVERY_PORT = 8767
    const val PROBE = "SAPO?"
    fun hello(token: String, device: String): String
    fun pair(code: String, device: String): String
    fun style(p: StyleProfile, describe: String): String
    fun phone(busy: BusyReason?, autoOn: Boolean): String
    fun parse(json: String): LinkMsg
}
sealed interface LinkMsg {
    data class Paired(val token: String) : LinkMsg
    data class Pc(val gaming: Boolean, val app: String?, val away: Boolean) : LinkMsg
    data class Error(val why: String) : LinkMsg
    data object Ok : LinkMsg
    data class Unknown(val raw: String) : LinkMsg
}
```

- `TypedCapture`: guarda el último texto por chat; el mensaje se da por enviado cuando el campo pasa de no vacío a vacío en < 1.5 s tras el último cambio, o con `onSendClick`. Devuelve el texto enviado una sola vez. Ignora textos que empiezan con "🤖".
- `Learner.addMine`: descarta vacíos, solo emojis no, enlaces sueltos, OTPs, duplicados exactos seguidos; si `lastIncoming` no es nulo y es de < 2 h crea un `Pair`. `profile` mezcla `base` (chats importados) con lo aprendido, ponderado por número de muestras.
- Prioridad de `Busy.reason`: `Manual` > `NoMolestar` > `JugandoPC` > `Horario` > `PantallaApagada`.

## B. Protocolo LAN (JSON por WebSocket, texto)

Cerebro de la PC escucha en `0.0.0.0:8766` **solo** si `phone.enabled` es `true` en `config.json`. Descubrimiento: el cel manda broadcast UDP `SAPO?` al puerto 8767; el cerebro responde `{"sapo":1,"port":8766,"name":"<equipo>"}`.

| Dirección | Mensaje |
|---|---|
| cel → PC | `{"type":"pair","code":"123456","device":"Nothing A059"}` (código de 6 dígitos que muestra Preferencias, vale 5 min, 5 intentos) |
| PC → cel | `{"type":"paired","token":"<64 hex>"}` o `{"type":"error","why":"..."}` |
| cel → PC | `{"type":"hello","token":"...","device":"..."}` primer mensaje de cada conexión; si falla, se cierra |
| cel → PC | `{"type":"style","profile":{...StyleProfile...},"describe":"..."}` |
| cel → PC | `{"type":"phone","busy":"Manual"|null,"auto":true}` |
| PC → cel | `{"type":"pc","gaming":true,"app":"FortniteClient-Win64-Shipping.exe","away":false}` al conectar y en cada cambio |
| PC → cel | `{"type":"ok"}` |

- Tokens guardados en `secrets.json` (DPAPI) como lista `phone_tokens` con nombre de dispositivo; Preferencias puede revocarlos.
- Mensajes > 64 KB o sin `hello` válido: cerrar. Máx. 3 conexiones.
- El cerebro usa `describe` del estilo para que el sapo de la PC hable "como tú" cuando `brain.persona == "como_yo"`.

## C. `:app`
- `SapoAccesibilidad` (AccessibilityService, solo `com.whatsapp` y `com.whatsapp.w4b`, eventos `TYPE_VIEW_TEXT_CHANGED` y `TYPE_VIEW_CLICKED`; campo `com.whatsapp:id/entry`, botón `com.whatsapp:id/send`, título del chat `com.whatsapp:id/conversation_contact_name`). Nada sale del teléfono salvo el perfil de estilo hacia tu PC vinculada.
- Pestaña Estilo: "Aprendido escribiendo: N mensajes", interruptor de aprender, borrar lo aprendido.
- Ajustes › "Tu PC": buscar, ingresar código, estado de conexión, desvincular. Servicio conectado mientras el modo automático o el enlace estén activos; reconexión con espera creciente.
