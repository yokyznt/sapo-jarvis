# 06 — Publicar sapo-jarvis gratis para cualquiera (Windows + Android)

Fecha: 2026-10-25. Fuentes primarias (Google, Microsoft, F-Droid, IzzyOnDroid, repos/licencias oficiales). Donde algo viene de prensa o no se pudo confirmar, se marca **[secundaria]** o **[verificar]**.

Stack evaluado: PC Windows Godot 4 + C# (SendInput/Win32), Ollama `qwen3.5:4b` + Groq BYOK, openWakeWord + Silero VAD + Moonshine ES + Kokoro TTS, sqlite-vec. Android Kotlin con AccessibilityService, NotificationListenerService, CALL_PHONE, SMS, overlay, foreground service.

---

## 1. Android: verificación obligatoria de desarrolladores

**Calendario (oficial):**
- Marzo 2026: verificación abierta a todos en Play Console y en la nueva **Android Developer Console (ADC)**. Agosto 2026: salen las cuentas de *limited distribution*, la API de la ADC y el **"advanced flow"** para instalar apps no verificadas. https://developer.android.com/blog/posts/android-developer-verification-building-a-safer-ecosystem-together
- **30-sep-2026**: se aplica solo en **Brasil, Indonesia, Singapur y Tailandia**, y solo a instalaciones desde 7 tiendas (Google Play, HONOR, OPPO, Galaxy Store, Palm Store, vivo, Xiaomi GetApps). Misma fuente y https://support.google.com/android-developer-console/answer/16561738
- **2027**: expansión "global para todas las apps en dispositivos Android certificados". **Sin mes ni orden de países publicados** (al 2-oct-2026, según https://anoni.net/news/en/2026/10/fdroid-2-android-developer-verification/ [secundaria]).
- **México**: no está en la primera ola. Hoy no cambia nada si el APK se instala desde un navegador o desde F-Droid: "If you distribute your app through other stores, or if users sideload your app directly, these new verification requirements won't apply to your app yet" (FAQ, actualizado 15-jul-2026). https://developer.android.com/developer-verification/guides/faq

**Costo y tipos de cuenta (FAQ y guía oficiales):**
| Cuenta | Costo | ID oficial | Alcance |
|---|---|---|---|
| ADC **Full distribution** | **US$25** único ("similar to Play's $25 registration fee") | Sí | Pública, sin límite |
| ADC **Limited distribution** (estudiantes/aficionados) | **Gratis** | No (pide cuenta Google con 2FA, perfil de pagos con nombre legal/dirección y email) | **Máx. 20 dispositivos** autorizados uno por uno con QR o enlace |
| Play Console | US$25 (https://support.google.com/googleplay/android-developer/answer/6112435) | Sí | Play + sideload |

Fuentes: https://developer.android.com/developer-verification/guides/limited-distribution · FAQ arriba. La cuenta limitada se puede pasar a full, pero no al revés.

**Qué hace el usuario si el desarrollador no está verificado (desde 2027 en su país):**
- **Advanced flow** (pasa una sola vez por dispositivo): activar Opciones de desarrollador → Sistema → Opciones de desarrollador → "Allow apps from unverified developers" → **espera de seguridad de 24 h** → elegir activo por 7 días o indefinido → al instalar, tocar "Install anyway". https://support.google.com/android/answer/17588095
- Si después se apaga el advanced flow, **las actualizaciones de apps no registradas fallan** (FAQ).
- **ADB** sigue funcionando sin verificación y sin la espera (FAQ).
- No aplica a dispositivos AOSP o no certificados (https://support.google.com/android-developer-console/answer/16561738).

**GitHub Releases / F-Droid / Obtainium:**
- **GitHub Releases** cuenta como sideload: hasta 2027 no cambia nada. Después, el usuario necesita que el paquete esté registrado ($25 + ID) o hacer el advanced flow.
- **F-Droid**: Google publicó una guía en la que el desarrollador registra su `packageName` y añade el SHA-256 de la llave con la que F-Droid re-firma; así "your users continue with the same install experience". Pide cuenta ADC o Play, o sea full = $25. https://developer.android.com/developer-verification/guides/open-source-app-registration (actualizado 23-oct-2026)
- F-Droid se opone y pide a los desarrolladores **no registrarse**: https://f-droid.org/en/2026/02/24/open-letter-opposing-developer-verification.html

---

## 2. "Restricted settings" (Android 13–17) con APK de navegador o gestor de archivos

**Qué se bloquea (CDD oficial, requisito 9.8/H-0-1):** aplica a apps instaladas desde un archivo descargado (`PACKAGE_SOURCE_DOWNLOADED_FILE`) o un archivo local (`PACKAGE_SOURCE_LOCAL_FILE`):
- Accesibilidad, **Notification listener**, administrador del dispositivo, **mostrar sobre otras apps (SYSTEM_ALERT_WINDOW)**, acceso de uso.
- Roles predeterminados de **Teléfono** y **SMS**.
- **Permiso en tiempo de ejecución del grupo SMS**.
Fuentes: https://source.android.com/docs/compatibility/15/android-15-cdd · https://source.android.com/docs/compatibility/16/android-16-cdd · https://source.android.com/docs/compatibility/17/android-17-cdd
- En Android 13 y 14 solo estaban Accesibilidad y Notificaciones (Kaspersky [secundaria]: https://www.kaspersky.com/blog/android-restricted-settings/49991/). Android 15 sumó overlay, SMS y lo demás (Android Authority [secundaria]: https://www.androidauthority.com/android-15-restricted-settings-sideloading-3481098/).
- **CALL_PHONE no aparece en la lista.**

→ sapo-jarvis pega en **4 de sus permisos clave**: accesibilidad, notificaciones, overlay y SMS.

**Cómo lo desbloquea un usuario normal, sin ADB** (https://support.google.com/android/answer/12623953):
1. Intentar activar el permiso (p. ej., Accesibilidad → sapo-jarvis). Sale el diálogo "Configuración restringida" y hay que aceptarlo. *Ese primer intento es lo que hace aparecer la opción del paso 3* (comportamiento confirmado por la comunidad [secundaria]: https://discuss.grapheneos.org/d/825-restricted-setting).
2. Ajustes → Apps → sapo-jarvis (o "Ver todas las apps" / "Info de la app").
3. Menú ⋮ → **"Permitir configuración restringida"** → confirmar con PIN o huella.
4. Volver y activar Accesibilidad, Notificaciones, Overlay y SMS. Un solo desbloqueo libera todos los permisos de esa app.

**Exención:** las tiendas que instalan con la API de sesiones de `PackageInstaller` (F-Droid, por ejemplo) **no** quedan marcadas como archivo local, así que sus apps no sufren restricted settings ([secundaria] Android Authority, arriba). Obtainium también instala por sesión, pero que quede exento **[verificar en un dispositivo real]**.

**Conclusión práctica:** el onboarding de la app debe incluir una pantalla guiada con capturas que lleve directo a `Settings.ACTION_APPLICATION_DETAILS_SETTINGS`.

---

## 3. Tiendas Android

### Google Play: no viable para la app tal como está diseñada
- **Accesibilidad**: solo las herramientas para personas con discapacidad pueden declarar `isAccessibilityTool`. Las demás necesitan divulgación destacada, consentimiento, formulario de declaración y video. Además, desde la política vigente: *"Any use of the Accessibility API that enables an app to **autonomously initiate, plan, and execute actions or decisions is strictly prohibited**"*. Solo se permite automatización determinista ("si X, haz Y"). **Un agente LLM que toca la pantalla choca de frente con esta regla.** https://support.google.com/googleplay/android-developer/answer/10964491
- **SMS / Call Log**: solo para la app que sea **handler predeterminado de SMS, Teléfono o Asistente**, más excepciones con formulario. Entre los usos inválidos figuran "speech/voice to text" y el control remoto, salvo que la app sea el handler. Alternativa sin permiso: `ACTION_DIAL` / `ACTION_SENDTO`. https://support.google.com/googleplay/android-developer/answer/10208820
  - Si la app se registra como **Asistente predeterminado** (rol `ROLE_ASSISTANT`), en teoría entra en la excepción. Pero la regla de accesibilidad autónoma sigue bloqueando. **[verificar]**
- **Costo**: US$25 único. https://support.google.com/googleplay/android-developer/answer/6112435
- **Cuentas personales nuevas**: prueba cerrada con **12 testers durante 14 días seguidos** antes de pedir producción. https://support.google.com/googleplay/android-developer/answer/14151465
- **Veredicto**: no viable, salvo una variante "Play-lite" sin accesibilidad autónoma ni SMS, que además rompe la regla de costo cero.

### F-Droid (repo oficial): viable, con cambios
- Requisitos: 100% FLOSS (licencias DFSG/FSF/OSI). F-Droid **compila desde el código fuente**; los binarios precompilados solo se aceptan de Maven Central, Google Maven y fuentes similares, y deben ser libres. **Prohibido**: Google Play Services, Firebase, Crashlytics y SDKs de tracking propietarios; se puede ofrecer un *flavor* sin ellos. https://f-droid.org/docs/Inclusion_Policy/
- **Accesibilidad**: la política no prohíbe AccessibilityService; muchas apps de F-Droid la usan.
- **Anti-features esperables**: **`NonFreeNet`** si Groq es parte central (servicio de red propietario). Si Groq es opcional/BYOK y lo local es lo predeterminado, el caso es discutible **[verificar con revisores]**. Assets con licencia no comercial = `NonFreeAssets`, y eso evita los modelos CC BY-NC. https://f-droid.org/docs/Anti-Features/
- **Reproducible builds**: no son obligatorios. Si se configuran, F-Droid publica el APK **con la firma del autor**, lo que conserva actualizaciones cruzadas con GitHub. Conviene hacerlo desde la v1. https://f-droid.org/tr/docs/FAQ_-_App_Developers/
- **Modelos ONNX** (Moonshine, Silero, wake word) dentro del APK: tienen que venir de una fuente libre y declarada. Mejor descargarlos en el primer arranque. **[verificar con revisores]**
- **IA**: F-Droid no tiene política contra apps hechas con IA. Hay un debate abierto sobre etiquetar apps con LLM como anti-feature (https://gitlab.com/fdroid/admin/-/work_items/641). Riesgo reputacional: auditorías comunitarias marcan como "Mostly AI" los repos con setup de Claude Code/Codex (https://glonce.com/f-droid-apps-get-rated-for-how-much/ [secundaria]).

### IzzyOnDroid: probablemente rechazada
- La política dice textualmente: *"Vibe-coded apps will be rejected"* y *"Apps acting as front-end for LLMs … or integrate with such services, will be rejected"*. Límite de ~30 MB por APK. https://izzyondroid.org/docs/general/AppInclusionPolicy/
- **No contar con IzzyOnDroid.**

### Obtainium: sí, sin pedir permiso a nadie
- Instala y actualiza directo desde GitHub Releases (y Codeberg, GitLab, etc.). No hace falta inclusión ni revisión. https://github.com/ImranR98/Obtainium
- Desde 2027 seguirá sujeto a la verificación de Google si el paquete no está registrado (Obtainium es un instalador más).

---

## 4. Windows

**SmartScreen y firma** (https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options):
- Un `.exe` sin firmar o con reputación nueva muestra "Windows protegió su PC". El usuario debe pulsar *Más información → Ejecutar de todas formas*.
- **Desde 2024 los certificados EV ya no saltan SmartScreen**: todos construyen reputación con el tiempo.
- **Microsoft Store con MSIX**: **gratis, mundial, la Store re-firma el paquete, "No warnings"**. Es la única vía sin costo y sin aviso de SmartScreen.
- **Azure Artifact Signing** (antes Trusted Signing): ~US$9.99/mes. **Individuos: solo EE. UU. y Canadá. México queda fuera.** https://azure.microsoft.com/en-us/pricing/details/artifact-signing/
- **SignPath Foundation** (gratis para OSS), requisitos (https://signpath.org/terms.html):
  - Licencia OSI sin dual-licensing comercial; ningún componente propietario.
  - Build automatizado desde el repo (GitHub Actions) y MFA para todo el equipo.
  - Roles definidos: autores, revisores y aprobador.
  - Página "Code signing policy" en el sitio.
  - Política de privacidad mostrada al instalar si se envían datos a sistemas que el usuario no eligió (Groq BYOK lo elige el usuario, así que se declara).
  - Proyecto **ya publicado, mantenido y con "verifiable reputation"**. **Un proyecto recién nacido no califica**: hay que solicitarlo después de algunos releases.

**Microsoft Store, registro individual:** **gratis** (se eliminó la cuota de US$19). Pide ID oficial + selfie y está disponible en ~200 mercados. Solo funciona entrando por https://storedeveloper.microsoft.com. https://learn.microsoft.com/en-us/windows/apps/publish/whats-new-individual-developer
- Godot + C# empaquetado como MSIX corre como *full trust* (Desktop Bridge), así que SendInput funciona igual. https://learn.microsoft.com/en-us/windows/msix/group-policy-msix

**winget**: el repo comunitario acepta MSIX/MSI/EXE y portables. Todos pasan escaneos de seguridad, con política estricta contra **PUA** (aplicaciones potencialmente no deseadas). La firma no es obligatoria. https://github.com/microsoft/winget-pkgs/blob/master/doc/Policies.md

**Antivirus y la inyección de input:**
- `SendInput` es una API normal. Está sujeta a **UIPI**: no puede inyectar en ventanas elevadas (Administrador), y falla en silencio. https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
- Para controlar ventanas elevadas haría falta `uiAccess=true`, y eso exige **firma Authenticode + instalación en Program Files**: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview. Se descarta.
- Los heurísticos marcan con frecuencia, como falso positivo, los ejecutables sin firmar que combinan hooks de teclado, inyección de input, micrófono y red. Les pasa a los AutoHotkey compilados (https://blog.gridinsoft.com/autohotkey-malware-or-false-positive/ [secundaria]).
- Mitigaciones:
  - No usar `SetWindowsHookEx` global si no hace falta.
  - No empaquetar con packers como UPX.
  - Publicar el código y los hashes.
  - Enviar cada release como falso positivo, gratis, en https://www.microsoft.com/en-us/wdsi/filesubmission

---

## 5. Licencias para redistribuir gratis públicamente

| Componente | Licencia | ¿Redistribuible gratis? | Nota |
|---|---|---|---|
| Godot 4 | MIT | Sí | Incluir aviso de licencia y créditos de terceros. https://docs.godotengine.org/en/stable/about/complying_with_licenses.html |
| Ollama | MIT | Sí | El usuario lo instala aparte. https://github.com/ollama/ollama |
| qwen3.5 (0.8b/2b/4b…) | **Apache-2.0** | Sí (incluso comercial) | https://huggingface.co/Qwen/Qwen3.5-4B · licencia en Ollama: https://ollama.com/library/qwen3.5:4b/blobs/7339fa418c9a |
| Moonshine **ES streaming** (Tiny 34M / Small 123M) | **MIT** | **Sí** | El único modelo ES no comercial es el **legacy "Spanish Base" (non-streaming)**: Moonshine Community License, no comercial. **Usar los streaming.** https://github.com/moonshine-ai/moonshine/blob/main/docs/license.md · https://github.com/moonshine-ai/moonshine/blob/main/docs/models/available-models.md |
| Kokoro-82M | Apache-2.0 | Sí | El español (`lang_code='e'`, voces `ef_dora`, `em_alex`) usa **espeak-ng (GPL-3.0+)** para fonemas. Si se empaqueta, entregarlo como binario separado con su licencia y su código. https://huggingface.co/hexgrad/Kokoro-82M · https://github.com/hexgrad/kokoro · https://github.com/espeak-ng/espeak-ng |
| openWakeWord (código) | Apache-2.0 | Sí | https://github.com/dscripka/openWakeWord |
| openWakeWord **modelos pre-entrenados** | **CC BY-NC-SA 4.0** | **Solo no comercial**, compartir igual | Además son solo en inglés ("hey jarvis" etc.). Bloquean F-Droid (`NonFreeAssets`) y SignPath. |
| Wake word propio "oye sapo" con el notebook oficial | El modelo resultante hereda el riesgo | **Dudoso** | El pipeline usa las features negativas **ACAV100M (CC BY-NC-SA 4.0)** (https://huggingface.co/datasets/davidscripka/openwakeword_features) y el TTS por defecto es inglés `en_US-libritts_r`. Para hacerlo limpio: generar positivos con voces Piper `es_MX` de licencia libre (p. ej., `es_MX-ald`, dataset Unlicense: https://huggingface.co/rhasspy/piper-voices/blob/main/es/es_MX/ald/medium/MODEL_CARD) y **negativos de fuentes libres propias**. Alternativas: **microWakeWord (Apache-2.0)** (https://github.com/kahrendt/microWakeWord; licencia de sus features en HF **[verificar]**) o el KWS de **sherpa-onnx (Apache-2.0)**, que no requiere entrenamiento. |
| Silero VAD | MIT | Sí | https://github.com/snakers4/silero-vad |
| sqlite-vec | MIT o Apache-2.0 | Sí | https://github.com/asg017/sqlite-vec |
| Groq API (BYOK) | Términos de servicio | N/A, no se redistribuye | **Edad mínima 18 años**. "Not for consumer use", rol de "Customer". Prohíbe revender o redistribuir el servicio; con BYOK cada usuario acepta su propio contrato. El usuario es responsable de las acciones agénticas (§4.6). https://console.groq.com/docs/legal/services-agreement · Límites del free tier por organización: https://console.groq.com/docs/rate-limits |

**Implicaciones:**
- La app nunca debe incluir una API key del autor.
- Mostrar "requiere 18+ y tu propia cuenta Groq".
- El modo local, sin Groq, debe funcionar para menores o para quien no quiera cuenta.

---

## 6. Usuarios sin GPU: mínimos y fallback

- **Ollama en Windows**: Windows 10 22H2 o superior; GPU NVIDIA/AMD opcional (Vulkan como respaldo); ≥4 GB de disco para el binario, más los modelos. https://docs.ollama.com/windows
- **Tamaños qwen3.5 en Ollama**: 0.8b ≈ 1.2–1.3 GB · 2b ≈ 2.7–3.1 GB · 4b (q4_K_M) ≈ 3.3 GB. https://ollama.com/library/qwen3.5
- **Perfiles propuestos** (estimación propia; medir con `ollama run --verbose`):

| Perfil | Hardware | Cerebro | Voz |
|---|---|---|---|
| **A: GPU** | ≥6 GB VRAM, 16 GB RAM | `qwen3.5:4b` local | Moonshine Small streaming + Kokoro |
| **B: solo CPU** | CPU x64 con AVX2 (requisito citado por terceros, [secundaria]: https://www.techspot.com/downloads/7772-ollama.html), 8–16 GB RAM | `qwen3.5:2b` o `0.8b`, respuestas cortas, sin modo juego | Moonshine **Tiny** streaming |
| **C: PC débil** (≤8 GB RAM, sin AVX2) | — | **Sin LLM local**: solo Groq BYOK free tier | Moonshine Tiny + Silero (son ligeros) |

- El instalador debe detectar RAM, VRAM y AVX2 y elegir perfil. La memoria sqlite-vec y el VAD corren en cualquier perfil.

---

## Tabla: bloqueo / costo / alternativa gratis

| Bloqueo | Costo si se paga | Alternativa gratis |
|---|---|---|
| Verificación de Google para sideload (México: global en **2027**, fecha sin anunciar) | US$25 único + ID (ADC full) | Hasta 2027 nada cambia. Después: advanced flow del usuario (24 h, una vez) o ADB. La cuenta limitada gratis solo cubre 20 dispositivos |
| Restricted settings (accesibilidad, notificaciones, overlay, SMS) al instalar APK | — | Tutorial in-app: ⋮ → "Permitir configuración restringida". O distribuir vía F-Droid (instalador por sesión, exento) |
| Google Play: accesibilidad autónoma prohibida + SMS solo para handlers | US$25 + 12 testers × 14 días, y aun así rechazo probable | No usar Play. F-Droid + GitHub Releases + Obtainium |
| IzzyOnDroid rechaza apps front-end de LLM | — | F-Droid oficial (sin esa regla) o repo F-Droid propio en GitHub Pages |
| F-Droid: `NonFreeNet` por Groq; prohibido GMS/Firebase | — | Lo local como predeterminado, Groq opcional; sin libs de Google; build reproducible |
| SmartScreen con .exe sin firmar | Artifact Signing ~US$9.99/mes (**no disponible para individuos en MX**) / certificado OV comercial | **Microsoft Store MSIX (gratis, sin avisos)**; más adelante SignPath Foundation (gratis OSS, tras ganar reputación); winget |
| Falso positivo de AV por SendInput/micrófono | — | Sin packers ni hooks globales; código abierto; enviar a Microsoft WDSI |
| No inyectar input en ventanas elevadas (UIPI) | uiAccess exige firma + Program Files | Aceptar la limitación y avisar "no controlo apps en modo Administrador" |
| openWakeWord pre-entrenado y su dataset ACAV100M: no comerciales | — | Entrenar "oye sapo" con Piper es_MX (Unlicense) y negativos libres, o microWakeWord / sherpa-onnx KWS (Apache-2.0) |
| Moonshine Spanish Base legacy: no comercial | — | Moonshine **Tiny/Small Streaming ES (MIT)** |
| Kokoro ES depende de espeak-ng GPL-3 | — | Distribuir espeak-ng como binario aparte con su fuente, o usar Piper es_MX |
| Groq: 18+ y uso no consumidor | Plan de pago de Groq | BYOK opcional; modo 100% local para todos |
| PCs sin GPU | — | Perfiles 2b/0.8b en CPU o solo Groq BYOK |

## Recomendación (6 líneas)

1. Android: publicar APK en **GitHub Releases + Obtainium** ya, y enviar a **F-Droid oficial** con build reproducible, sin GMS y con Groq opcional. Olvidar Play e IzzyOnDroid.
2. Meter en la app un **asistente de permisos** para "Permitir configuración restringida" (accesibilidad, notificaciones, overlay, SMS) y preparar la guía del **advanced flow** para 2027.
3. Re-evaluar en 2027 si pagar los US$25 de la ADC full: es lo único que conserva la instalación sin fricción para usuarios normales. Hasta entonces, gratis.
4. Windows: publicar como **MSIX en Microsoft Store** (cuenta individual gratis; sin SmartScreen) más ZIP portable o winget en GitHub. Solicitar **SignPath** cuando haya releases y usuarios.
5. Licencias: usar **Moonshine streaming ES (MIT)**, qwen3.5 (Apache), Kokoro/Silero/sqlite-vec. **No incluir modelos openWakeWord pre-entrenados**: entrenar "oye sapo" con datos libres o usar sherpa-onnx KWS.
6. Groq solo como BYOK opcional (18+). Modo local con perfiles autodetectados (4b GPU / 2b-0.8b CPU / solo API) para que cualquier PC funcione.
