# Etapa 10 · Sapo en el cel

## A. `:core` (JVM, con pruebas)

```kotlin
sealed interface Command {
    data class Call(val who: String) : Command
    data class Sms(val who: String, val text: String) : Command
    data class WhatsApp(val who: String, val text: String) : Command
    data class OpenApp(val name: String) : Command
    data class Alarm(val hour: Int, val minute: Int, val label: String?) : Command
    data class Timer(val seconds: Int) : Command
    data class Torch(val on: Boolean) : Command
    data class Volume(val level: Int?) : Command
    data class Settings(val panel: String) : Command
    data object Time : Command
    data object Battery : Command
    data class Pc(val text: String) : Command
    data class Chat(val text: String) : Command
}
object Intents {
    fun parse(text: String, now: java.time.LocalDateTime): Command
    fun needsConfirm(c: Command): Boolean
    fun confirmText(c: Command): String
}
object Contacts { fun best(query: String, names: List<String>): String? }
```

- `parse` en español informal: "llama a mi mamá", "márcale a Juan", "mándale un mensaje a Ana que ya voy", "dile por WhatsApp a Luis que…", "abre Spotify", "pon una alarma a las 7 y media", "despiértame a las 6 am", "pon un temporizador de 5 minutos", "prende/apaga la linterna", "sube/baja el volumen", "volumen al 50", "abre el wifi/bluetooth", "qué hora es", "cuánta pila tengo", "en la PC …"/"en la compu …" → `Pc`, todo lo demás → `Chat`. Sin acentos y sin mayúsculas al comparar. Hora: "7 y media", "7:30", "6 am", "8 de la noche", "mediodía"; si la hora ya pasó hoy no importa (la alarma del sistema lo resuelve).
- `needsConfirm`: `Call`, `Sms`, `WhatsApp` → `true`; lo demás `false`.
- `Contacts.best`: coincidencia sin acentos, por palabra, tolera "mi mamá" ↔ "Mamá", "ma" ↔ "Mamá ❤️", errores de 1 letra en nombres ≥ 5 letras; `null` si hay empate o nada.

## B. Enlace (agrega a la tabla de la etapa 9)

| Dirección | Mensaje |
|---|---|
| cel → PC | `{"type":"ask","id":"<uuid>","text":"abre spotify"}` |
| PC → cel | `{"type":"reply","id":"<uuid>","text":"Listo, abrí Spotify 🎵"}` |

- El cerebro lo procesa igual que el chat de la PC (con sus herramientas y sus confirmaciones en la PC); tope de 1 pregunta a la vez por cel, 60 s.
- `Link.ask(id, text)` y `LinkMsg.Reply(id, text)` en `:core`.

## C. `:app`
- `SapoFlotante`: servicio en primer plano (`specialUse`) con ventana `TYPE_APPLICATION_OVERLAY` chica (`WRAP_CONTENT`), el sapito dibujado con `Canvas` en una `View` (mismo diseño de la app), se arrastra, se avienta y rebota en los bordes, se pega al borde más cercano al soltarlo, parpadea, se duerme tras 2 min quieto.
- Toque = escuchar (`SpeechRecognizer`, `es-MX`, con `EXTRA_PREFER_OFFLINE`), burbuja con lo que oyó y la respuesta; voz con `TextToSpeech` `es-MX` (se puede apagar). Toque largo = menú (esconder, abrir la app, callar).
- Comandos: llamadas con `ACTION_CALL` (permiso `CALL_PHONE`) tras confirmar con botones Sí/No en la burbuja; SMS con `SmsManager` (permiso `SEND_SMS`) tras confirmar; WhatsApp abre `https://wa.me/<número>?text=` y el usuario toca enviar; contactos con `READ_CONTACTS`; alarma/temporizador con `AlarmClock`; linterna con `CameraManager.setTorchMode`; volumen con `AudioManager`; ajustes con `Settings.Panel`/`ACTION_*_SETTINGS`; `Pc` por el enlace; `Chat` con Gemini (persona del sapo, corto, español mexicano) o, sin key, frase fija.
- Inicio: interruptor "Sapito flotante" que pide `SYSTEM_ALERT_WINDOW`, micrófono, notificaciones; ajustes de voz y tamaño.
