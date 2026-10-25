# 02 — Sapito asistente en Android (Nothing Phone A059, Nothing OS / Android 15)

> Objetivo: una mascota (sapito) que flote sobre todas las apps y pueda **controlar el celular** (abrir apps, cambiar ajustes, llamar, mandar mensajes, tocar la pantalla).
> Restricción: **100 % gratis**, sin cuenta de Google Play Developer (25 USD). Se instala por **sideload / `adb install`** (ya hay adb inalámbrico vinculado).
> Fecha de la investigación: 25-oct-2026. Fuentes primarias citadas inline. Lo marcado **[verificar]** no se pudo confirmar en una fuente oficial.

---

## TL;DR

| Capacidad | API / mecanismo | ¿Funciona sideloaded y gratis? |
|---|---|---|
| Sapito flotante | `SYSTEM_ALERT_WINDOW` + `TYPE_APPLICATION_OVERLAY` (o overlay de `TYPE_ACCESSIBILITY_OVERLAY` desde el AccessibilityService) | Sí |
| Mantenerse vivo | Foreground service tipo `specialUse` + sacar la app de optimización de batería | Sí |
| Tocar, deslizar, leer pantalla, Atrás/Inicio/Recientes, captura | `AccessibilityService` (`dispatchGesture`, `getRootInActiveWindow`, `performGlobalAction`, `takeScreenshot`) | Sí, pero hay que pasar "Ajustes restringidos" (Android 13+) |
| Abrir apps | `PackageManager.getLaunchIntentForPackage()` + intents | Sí |
| Cambiar ajustes | Intents a `Settings.*`; `WRITE_SETTINGS`; para wifi/datos/bluetooth reales: Shizuku o adb | Parcial (lo que no deja la API se hace con la accesibilidad o con Shizuku) |
| Llamar | `ACTION_CALL` + `CALL_PHONE` | Sí |
| Contestar / colgar | `TelecomManager.acceptRingingCall()` (deprecado en API 29, todavía funciona) / `endCall()` + `ANSWER_PHONE_CALLS`; o volverse app de teléfono predeterminada (`InCallService`) | Sí |
| SMS | `SmsManager` + `SEND_SMS` | Sí |
| WhatsApp | `NotificationListenerService` + `RemoteInput` (respuesta rápida) o la accesibilidad para mandar mensajes nuevos | Sí, con limitaciones |
| Voz offline | Vosk / sherpa-onnx / whisper.cpp (STT), TTS del sistema o sherpa-onnx (TTS), openWakeWord (wake word) | Sí. **Porcupine ya no es opción gratis** (el plan Free se cerró el 30-jun-2026) |
| PC ↔ celular | WebSocket en LAN, Tailscale (plan Personal gratis), adb inalámbrico, KDE Connect | Sí |

---

## 1. Overlay flotante (el sapito encima de todo)

### 1.1 Permiso y tipo de ventana
- Permiso `android.permission.SYSTEM_ALERT_WINDOW` ("Mostrar sobre otras apps"). Se pide mandando al usuario a `Settings.ACTION_MANAGE_OVERLAY_PERMISSION`; para revisarlo se usa `Settings.canDrawOverlays(context)`.
- Desde Android 8 (API 26) el único tipo de ventana permitido para apps normales es `WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY`.
- El sapito es una `View` (o `ComposeView`) que se agrega con `WindowManager.addView()` usando las flags `FLAG_NOT_FOCUSABLE | FLAG_LAYOUT_NO_LIMITS`. Para que se pueda arrastrar se mueven `params.x/y` en `onTouch` y se llama `updateViewLayout()`.
- **Toques "no confiables" (Android 12+):** si la ventana tapa otra app, el sistema bloquea los toques que pasan *a través* de ella. Por eso la ventana del sapito tiene que ser **chica (`WRAP_CONTENT`)** y no de pantalla completa, o si no las apps de abajo dejan de recibir toques. https://developer.android.com/about/versions/12/behavior-changes-all (sección *Untrusted touch events are blocked*).
- Alternativa: si ya existe un `AccessibilityService`, este puede dibujar con `TYPE_ACCESSIBILITY_OVERLAY` **sin** pedir `SYSTEM_ALERT_WINDOW`, y además la ventana vive mientras viva el servicio. Con esto hay un permiso menos.

### 1.2 Foreground service (Android 14/15)
- Desde Android 14 cada foreground service **tiene que declarar un tipo** en el manifest y pedir su permiso `FOREGROUND_SERVICE_<TIPO>`. https://developer.android.com/develop/background-work/services/fgs/service-types
- Para una mascota/overlay el tipo que corresponde es **`specialUse`**: declarar `FOREGROUND_SERVICE_SPECIAL_USE` y una `<property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE" android:value="floating assistant pet"/>` dentro del `<service>`. No tiene requisitos en tiempo de ejecución (misma URL). Ese texto solo lo revisa Google Play; con sideload no importa.
- Si va a escuchar el micrófono (wake word) se le suma el tipo `microphone` (`FOREGROUND_SERVICE_MICROPHONE` + `RECORD_AUDIO`). Ese tipo es "while-in-use": el servicio tiene que arrancar mientras la app está visible, o desde una de las excepciones. https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- **Cambio de Android 15 importante:** antes, tener `SYSTEM_ALERT_WINDOW` bastaba para arrancar un FGS desde segundo plano. Con target 35, además hay que **tener una ventana overlay visible en ese momento**. https://developer.android.com/about/versions/15/behavior-changes-15 y https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
  → Orden correcto: primero `addView(sapito)` y después `startForegroundService()`. Otra opción es arrancar el servicio desde la Activity.
- Android 15 también limita `dataSync` y `mediaProcessing` a 6 h cada 24 h (misma URL de behavior-changes-15). **No usar esos tipos** para el sapito.
- Hay que mostrar una notificación persistente obligatoria (puede ser de baja prioridad, por ejemplo "Sapito despierto 🐸").

### 1.3 Batería (Nothing OS)
- Pedir `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` → `Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`. Con sideload no aplica la política de Play, así que se puede usar sin problema.
- Desde la PC: `adb shell dumpsys deviceidle whitelist +com.yokis.sapo`.
- En el teléfono: Ajustes → Apps → Sapo → Batería → **Sin restricciones**. Nothing OS es bastante cercano a AOSP; la guía general está en https://dontkillmyapp.com/general **[verificar si Nothing agrega un "app freezer" propio]**.
- Un AccessibilityService activo es por sí mismo un proceso al que el sistema le da prioridad alta y casi nunca mata. Es el mejor "ancla" para que todo siga vivo.

---

## 2. Controlar el teléfono

### 2.1 AccessibilityService (el núcleo)
Referencia: https://developer.android.com/reference/android/accessibilityservice/AccessibilityService
- **Leer la pantalla:** `getRootInActiveWindow()` / `getWindows()` → árbol de `AccessibilityNodeInfo` (texto, `viewIdResourceName`, bounds, si se puede hacer clic). Se serializa a JSON y se le pasa al LLM. Así trabajan droidrun-portal y Blurr.
- **Actuar sobre nodos:** `node.performAction(ACTION_CLICK | ACTION_SET_TEXT | ACTION_SCROLL_FORWARD …)`. Es más confiable que tocar coordenadas.
- **Gestos:** `dispatchGesture(GestureDescription)` para tocar o deslizar en coordenadas (API 24+). Requiere `android:canPerformGestures="true"` en el XML de config.
- **Acciones globales:** `performGlobalAction(GLOBAL_ACTION_BACK | HOME | RECENTS | NOTIFICATIONS | QUICK_SETTINGS | LOCK_SCREEN | TAKE_SCREENSHOT …)`.
- **Captura de pantalla para modelos con visión:** `takeScreenshot()` (API 30+), sin MediaProjection. Requiere `android:canTakeScreenshot="true"`.
- **Abrir apps:** no hace falta la accesibilidad; basta `startActivity(pm.getLaunchIntentForPackage(pkg))`. En Android 11+ hay que declarar `<queries>` o `QUERY_ALL_PACKAGES` (con sideload no hay revisión de Play, se puede usar).
- **Ajustes:** abrir la pantalla con `Settings.ACTION_WIFI_SETTINGS`, `ACTION_BLUETOOTH_SETTINGS`, etc. y luego tocar el switch con la accesibilidad. También se puede usar el panel de Ajustes rápidos (`GLOBAL_ACTION_QUICK_SETTINGS` + clic en el tile). El brillo y el timeout salen con `WRITE_SETTINGS`; volumen y "no molestar" con `AudioManager` / `NotificationManager` (para DND hace falta el permiso de acceso a DND).

### 2.2 "Ajustes restringidos" en Android 13+ (sideload)
- Android 13+ bloquea activar **Accesibilidad** y **Acceso a notificaciones** en apps que se instalaron "fuera de una tienda". El switch aparece gris con el texto "Ajuste restringido".
- **Cómo habilitarlo en el teléfono:** Ajustes → Apps → (la app) → menú ⋮ → **Permitir ajustes restringidos** → confirmar con PIN/huella. Después ya se puede activar la accesibilidad. Fuente oficial: https://support.google.com/android/answer/12623953?hl=en
- **Qué instalaciones caen en la restricción:** se basa en si el instalador usó la API de instalación "por sesión" (tiendas) o la que no es por sesión (navegadores, gestores de archivos). Android 15 agregó "Enhanced Confirmation Mode" para cerrar ese hueco. https://www.androidauthority.com/android-15-enhanced-confirmation-mode-3436697/
- **Con `adb install` normalmente NO aparece la restricción.** Varios proyectos lo recomiendan por eso, por ejemplo https://github.com/Magi-Labs/mobilemcp y https://github.com/chamalkalakshan/App-Locker/blob/main/DISTRIBUTION.md **[verificar en el A059; si aparece gris, usar los comandos de abajo]**.
- Desde la PC (adb), todo se puede otorgar sin pasar por la UI:
  ```bash
  adb install -r app-debug.apk
  adb shell appops set com.yokis.sapo ACCESS_RESTRICTED_SETTINGS allow
  adb shell appops set com.yokis.sapo SYSTEM_ALERT_WINDOW allow
  adb shell settings put secure enabled_accessibility_services com.yokis.sapo/.SapoAccessibilityService
  adb shell settings put secure accessibility_enabled 1
  adb shell cmd notification allow_listener com.yokis.sapo/.SapoNotificationListener
  adb shell dumpsys deviceidle whitelist +com.yokis.sapo
  adb shell pm grant com.yokis.sapo android.permission.CALL_PHONE   # y SEND_SMS, RECORD_AUDIO, ANSWER_PHONE_CALLS…
  ```
  Ojo: `enabled_accessibility_services` **reemplaza** la lista completa. Si hay otros servicios activos, leer antes con `settings get` y concatenar con `:`.
- Riesgo a futuro: el **Advanced Protection Mode** (Android 16+) limita la accesibilidad a apps verificadas. Es opcional y viene apagado; no hay que activarlo. https://support.google.com/android/answer/16339980?hl=en

### 2.3 Shizuku (poderes de adb dentro del teléfono, sin PC)
- https://github.com/RikkaApps/Shizuku. Corre un proceso con permisos de **shell/adb** y las apps lo usan por IPC (API: https://github.com/RikkaApps/Shizuku-API).
- En Android 11+ arranca **por depuración inalámbrica, sin PC**. Hay que volver a arrancarlo después de cada reinicio. https://shizuku.rikka.app/guide/setup/
- Sirve para lo que la accesibilidad no puede hacer bien: `cmd wifi set-wifi-enabled`, `svc data enable`, `input tap/text/keyevent`, `am start`, `pm grant`, `settings put global …`, `cmd bluetooth_manager enable`. Es gratis y open source.
- Uso recomendado: hacerlo **opcional**. Si Shizuku está corriendo, el sapito usa comandos directos; si no, vuelve a la accesibilidad.

### 2.4 ADB desde la PC
- Ya está vinculado por adb inalámbrico. Desde la PC se puede todo: `adb shell input tap x y`, `input text`, `am start -n`, `uiautomator dump` (árbol de UI), `screencap`. Es el modo que usan droidrun (sin Portal), AppAgent y Mobile-Agent.
- Desventaja: depende de que la PC esté prendida y en la misma red (o con Tailscale), y el puerto de depuración inalámbrica cambia al reiniciar. Conviene como **modo desarrollo / "Jarvis desde la PC"**, no como base del sapito.

---

## 3. Llamadas y SMS

- **Hacer una llamada:** `Intent(Intent.ACTION_CALL, Uri.parse("tel:5512345678"))` + permiso peligroso `CALL_PHONE` (en runtime). Si se usa `ACTION_DIAL` no hace falta el permiso, pero el usuario tiene que tocar "llamar".
- **Contestar/colgar:** `TelecomManager.acceptRingingCall()` está **deprecado desde API 29**, pero sigue disponible. `endCall()` también existe, con permiso `ANSWER_PHONE_CALLS`. https://developer.android.com/reference/android/telecom/TelecomManager
  - Para detectar que suena: `TelephonyCallback` (API 31+) con `READ_PHONE_STATE`, y `READ_CALL_LOG` si se quiere el número.
  - Plan B: con la accesibilidad, tocar el botón "Contestar" de la UI de llamada.
- **Ser la app de teléfono predeterminada:** `RoleManager.ROLE_DIALER` + implementar `InCallService`. Da control total (UI propia, contestar, colgar, poner en espera, DTMF), pero hay que **reimplementar todo el marcador**. https://developer.android.com/develop/connectivity/telecom/dialer-app · https://developer.android.com/reference/android/telecom/InCallService → **No vale la pena para v1.** Una alternativa más ligera es `ROLE_CALL_SCREENING` (`CallScreeningService`), que permite filtrar y anunciar quién llama.
- **SMS:** `SmsManager.sendTextMessage()` + `SEND_SMS`. Funciona sin ser la app de SMS predeterminada (la escritura en el proveedor de SMS sí la requiere). Para leer: `RECEIVE_SMS` / `READ_SMS`. Con sideload no hay restricción de Play.
- **WhatsApp (mensaje nuevo):** abrir `https://wa.me/52XXXXXXXXXX?text=...` (o `Intent.ACTION_SEND` con `setPackage("com.whatsapp")`) y después tocar el botón **Enviar** con la accesibilidad (buscar el nodo `com.whatsapp:id/send`; el id puede cambiar entre versiones).

---

## 4. Leer/responder WhatsApp con NotificationListenerService + RemoteInput

- `NotificationListenerService` recibe `onNotificationPosted(sbn)`. De ahí se saca remitente/texto (`Notification.EXTRA_TITLE`, `EXTRA_TEXT`, `EXTRA_MESSAGES` de `MessagingStyle`). Se habilita en Ajustes → Acceso a notificaciones (también cae en "ajustes restringidos") o con `adb shell cmd notification allow_listener`.
- **Respuesta directa:** buscar en `notification.actions` la acción que tenga `remoteInputs`. Llenar un `Bundle` con `RemoteInput.addResultsToIntent(remoteInputs, intent, bundle)` y luego `action.actionIntent.send(context, 0, intent)`. Ejemplos reales: https://github.com/Jorge262007/NanamyV2, https://github.com/MMohamme/Whatsappagent
- **Limitaciones:**
  - Solo se puede responder a chats que **tengan una notificación activa**. No se puede iniciar una conversación nueva (para eso, sección 3: wa.me + accesibilidad).
  - Si el usuario abre el chat o descarta la notificación, la acción desaparece.
  - Los grupos o los mensajes agrupados pueden traer solo el resumen ("5 mensajes nuevos"). Usar `EXTRA_MESSAGES`.
  - No da acceso a multimedia ni al historial; solo lo que trae la notificación.
  - **Android 15 — redacción de OTP:** para listeners "no confiables", el sistema oculta el contenido de las notificaciones que tienen códigos de un solo uso. https://developer.android.com/about/versions/15/behavior-changes-all (sección *OTP Redaction*). Los mensajes normales de WhatsApp no se afectan.
  - Debe haber alguna persona entre "leer" y "responder" (pedir confirmación hablada), para no mandar mensajes que alucinó el LLM.

---

## 5. Voz offline gratis

| Pieza | Opción | Notas |
|---|---|---|
| STT ligero, streaming | **Vosk** — https://alphacephei.com/vosk/models · Android: https://github.com/alphacep/vosk-space/blob/master/android.md | Modelo pequeño en español ~40-50 MB, en tiempo real en CPU. Apache 2.0. Ideal para comandos. |
| STT de calidad | **whisper.cpp** — https://github.com/ggml-org/whisper.cpp/blob/master/examples/whisper.android/README.md | `tiny`/`base` cuantizados andan en un SoC de gama media; no hace streaming real (graba un segmento y lo transcribe). MIT. |
| STT+TTS+VAD+KWS todo en uno | **sherpa-onnx** — https://github.com/k2-fsa/sherpa-onnx | APKs de ejemplo para Android, modelos de streaming, TTS (Piper/VITS en español), VAD y keyword spotting. Apache 2.0. **El más completo.** |
| STT del sistema | `SpeechRecognizer.createOnDeviceSpeechRecognizer()` (API 31+) — https://developer.android.com/reference/android/speech/SpeechRecognizer | Gratis, pero depende del servicio de Google instalado y de que esté el paquete de idioma offline. No sirve para escuchar todo el tiempo. |
| TTS | `android.speech.tts.TextToSpeech` (motor del sistema, voces en español descargables offline) | Gratis y cero dependencias. Para una voz de "sapito" con personalidad: Piper vía sherpa-onnx, o subirle el `setPitch()` al TTS del sistema. |
| Wake word | **openWakeWord** (Apache 2.0) — ports a Kotlin: https://github.com/msnilsen/openwakeword-android, https://github.com/Re-MENTIA/openwakeword-android-kt | Se puede entrenar un "Oye sapito" personalizado con datos sintéticos (el notebook de openWakeWord corre en Colab gratis). ONNX Runtime. |
| Wake word (alternativa) | Keyword spotting de sherpa-onnx o Vosk con gramática cerrada `["oye sapito"]` | Sin entrenar nada; consume más CPU. |
| ❌ Porcupine | https://github.com/Picovoice/porcupine/issues/1574 | El plan Free requería AccessKey (validación online) y, según ese issue, **se cerró el 30-jun-2026**. Ya no cumple con "100 % gratis". |

Pipeline sugerido: openWakeWord (siempre activo, FGS `microphone`) → VAD → Vosk/sherpa-onnx streaming → LLM (en la PC o en la nube) → TTS del sistema. Tener el micrófono abierto todo el tiempo gasta batería: dar la opción de "solo al tocar el sapito".

---

## 6. Proyectos open source similares

| Proyecto | Qué es | Cómo controla | Licencia | Para qué sirve aquí |
|---|---|---|---|---|
| **droidrun / mobilerun** — https://github.com/droidrun/mobilerun | Agente LLM agnóstico (Python), ~9.7k ⭐ | adb + **Portal app** (AccessibilityService que expone el árbol de UI) | MIT | Copiar cómo serializa la UI y su set de herramientas (tap, swipe, input, launch). Se puede correr desde la PC ya mismo. |
| **droidrun-portal** — https://github.com/droidrun/droidrun-portal | La app Android de accesibilidad de droidrun | AccessibilityService + overlay que dibuja los bounds | MIT | **Plantilla directa** para el servicio de accesibilidad del sapito. |
| **Blurr / "Panda"** — https://github.com/Ayush0Chaudhary/blurr | Agente de teléfono **en el dispositivo**, con voz, en Kotlin | AccessibilityService + LLM (Gemini o proxy) | **Personal Use** (cambió de MIT) | Lo más parecido al sapito (overlay + voz + accesibilidad). Sirve para estudiarlo y para uso personal, no para redistribuir. |
| **hanxi/droidrun-agent** — https://github.com/hanxi/droidrun-agent | "Sin root, sin ADB, la IA controla tu Android" | Accesibilidad en el dispositivo | ver repo | Ejemplo de agente 100 % en el teléfono. |
| **mobilemcp** — https://github.com/Magi-Labs/mobilemcp | Servidor MCP en el teléfono para que agentes lo usen | AccessibilityService | ver repo | Exponer el sapito como **MCP** para el Jarvis de la PC. |
| **AppAgent** (Tencent) — https://github.com/TencentQQGYLab/AppAgent | Agente multimodal de investigación (CHI 2025) | adb + capturas + etiquetas | MIT | Ideas de "exploración y documentación" de apps. |
| **Mobile-Agent** (X-PLUG/Alibaba) — https://github.com/X-PLUG/MobileAgent | Familia de agentes GUI con percepción visual | adb + visión | MIT | Planificación con varios agentes y reflexión. |
| **KDE Connect** — https://github.com/KDE/kdeconnect-android | Puente PC↔teléfono | Accesibilidad para "Remote input" | GPL | Referencia de emparejamiento y protocolo en LAN. |

---

## 7. Stack recomendado

| Opción | Overlay | AccessibilityService | Voz offline | Encaje con lo que ya tienes |
|---|---|---|---|---|
| **Kotlin nativo** | Nativo (WindowManager / Compose) | Nativo | Todos los SDK son Kotlin/Java/JNI | Gradle + JDK 21 + SDK ya instalados |
| Capacitor | **No**: el WebView vive en la Activity; el overlay y los servicios hay que escribirlos en Kotlin de todos modos | Plugin nativo propio | Plugin nativo | Ya tienes `build-apk.js` |
| Flutter | Plugins como `flutter_overlay_window` (el overlay corre en otro isolate y se complica) | Hay plugins, pero son limitados | Plugins limitados | Hay que aprender Dart |

**Recomendación: Kotlin nativo** para el núcleo: `SapoOverlayService` (FGS `specialUse|microphone`), `SapoAccessibilityService`, `SapoNotificationListener`, módulos de voz y un servidor WebSocket. Todo lo que importa (overlay, accesibilidad, notificaciones, telecom, voz) es código Android de sistema, y en Capacitor o Flutter igual terminarías escribiéndolo en Kotlin, con un puente encima.
- Variante híbrida si quieres reutilizar web: dibujar el sapito (sprite o animación) en un **`WebView` dentro de la ventana overlay** (con HTML/Canvas/Lottie) y dejar la lógica en Kotlin. Es posible, pero una animación nativa (Lottie Android o AnimatedVectorDrawable) gasta menos batería.
- Compilar sin Android Studio: `gradlew assembleDebug` + `adb install -r`. Firma: el keystore de debug alcanza para sideload, pero hay que **usar siempre el mismo keystore** o cada actualización obliga a desinstalar.

---

## 8. Comunicación PC ↔ celular

- **WebSocket en LAN:** el teléfono corre un servidor (Ktor server o `NanoHTTPD`/`Java-WebSocket`) dentro del FGS, o un cliente que se conecta al Jarvis de la PC. Agregar un token compartido y, si se puede, TLS. Protocolo sugerido: JSON-RPC o el formato de herramientas de MCP (`tap`, `open_app`, `call`, `send_sms`, `read_screen`…).
- **Tailscale:** el plan **Personal es gratis "para siempre"**, con dispositivos ilimitados y hasta 6 usuarios. https://tailscale.com/pricing → el WebSocket y el adb (`adb connect 100.x.y.z:puerto`) funcionan también fuera de casa. Ojo: en Android usa el slot de VPN.
- **adb inalámbrico:** ya vinculado. Ideal para desarrollo y para el modo "la PC manda" (droidrun). El puerto cambia al reiniciar.
- **KDE Connect:** gratis y open source; trae notificaciones, portapapeles, "Ejecutar comando" e input remoto. https://github.com/KDE/kdeconnect-android. Sirve como puente rápido sin código, pero no como canal del agente (no da acceso al árbol de UI).
- Arquitectura sugerida: **el cerebro (LLM) en la PC** y el teléfono como "manos + ojos + boca" por WebSocket sobre Tailscale. Si la PC no responde, el sapito pasa a modo local con comandos fijos (Vosk con gramática cerrada: "llama a mamá", "abre WhatsApp", "linterna").

---

## 9. Plan de implementación mínimo (v0 → v1)

1. **v0 (1 tarde):** app Kotlin con Activity de permisos + `SapoAccessibilityService` que dibuja el sapito con `TYPE_ACCESSIBILITY_OVERLAY` (se puede arrastrar; al tocarlo muestra un menú). Instalar con `adb install`.
2. Agregar las herramientas: `open_app`, `tap(x,y)`, `click(text)`, `back/home`, `read_screen` → JSON.
3. Servidor WebSocket + token. Probar desde la PC (`websocat`) o conectar droidrun-style a un LLM.
4. Llamadas (`ACTION_CALL`) y SMS (`SmsManager`), con confirmación por voz.
5. `NotificationListenerService` + `RemoteInput` para WhatsApp.
6. Voz: TTS del sistema → Vosk para comandos → openWakeWord "oye sapito".
7. (Opcional) integración con Shizuku para wifi, datos y bluetooth.

## Recomendación (5 líneas)
1. **Kotlin nativo**; nada de Capacitor ni Flutter para el núcleo. Overlay, accesibilidad, notificaciones y telecom son APIs de sistema que igual se escriben en Kotlin.
2. El sapito vive **dentro de un AccessibilityService** (`TYPE_ACCESSIBILITY_OVERLAY` + `dispatchGesture` + `takeScreenshot`), más un FGS `specialUse|microphone` sin restricción de batería.
3. Instalar y otorgar todo con **adb** (`appops ACCESS_RESTRICTED_SETTINGS allow`, `settings put secure enabled_accessibility_services`, `cmd notification allow_listener`); se paga 0 y no se toca la UI de "ajustes restringidos".
4. Llamadas con `ACTION_CALL`, SMS con `SmsManager`, WhatsApp con `RemoteInput` (responder) y wa.me + accesibilidad (mensaje nuevo). Shizuku es opcional, para ajustes duros.
5. Voz offline: Vosk o sherpa-onnx + TTS del sistema + **openWakeWord** (Porcupine ya no es gratis). El cerebro LLM va en la PC, conectado por **WebSocket sobre Tailscale (gratis)**. Usar droidrun-portal y Blurr como código de referencia.
