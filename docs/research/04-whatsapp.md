# 04 — WhatsApp: clonar mi estilo de escritura y auto-responder cuando estoy ocupado (100% gratis)

> Contexto: Android Nothing Phone, PC con RTX 5060 Ti 8 GB + 32 GB RAM, México. Ya existe un gateway de WhatsApp en Hermes/Claude Code.
> Fecha de investigación: 2026-10-25. Fuentes primarias citadas en cada sección.

---

## 0. Lo que ya tienes: gateway WhatsApp de Hermes

Según la doc oficial (https://hermes-agent.nousresearch.com/docs/user-guide/messaging/whatsapp):

- **Librería:** puente propio basado en **Baileys** (emula una sesión de WhatsApp Web por WebSocket; **no** es la API oficial de Business). Requiere Node.js 18+, se vincula escaneando un QR en *Ajustes → Dispositivos vinculados*.
- **Dos modos:**
  - `bot`: número dedicado; la gente le escribe a ese número. **Es el modo recomendado** (menos riesgo de baneo).
  - `self-chat`: usas tu WhatsApp personal y te escribes a ti mismo para hablar con el agente. Pensado para uso de una sola persona y pruebas, **no** para responder a tus contactos.
- **Lee y responde:** sí, recibe mensajes entrantes y responde en el mismo chat (texto, notas de voz transcritas, encuestas, ubicación, respuestas en streaming).
- **Control de acceso:** `WHATSAPP_ALLOWED_USERS` (lista blanca de números con código de país, sin `+`). Si no configuras nada, **niega todo** por seguridad. `whatsapp.unauthorized_dm_behavior: ignore` deja callados a los desconocidos.
- **Aviso de IA:** por defecto antepone `⚕ Hermes Agent` a cada respuesta (`whatsapp.reply_prefix`). `send_read_receipts: false` por defecto.
- **Advertencia de la doc:** "WhatsApp no soporta oficialmente bots de terceros fuera de la Business API… riesgo pequeño de restricciones": usar número dedicado, no mandar mensajes masivos, no escribirle primero a quien no te escribió.
- La doc **no** describe un modo de "responder a mis contactos haciéndome pasar por mí" en tu número personal. Para eso habría que vincular tu número personal en modo bot con lista blanca, lo cual es justo lo que la doc desaconseja (riesgo de baneo en tu cuenta real).

---

## 1. Cómo sacar tus datos de WhatsApp

### 1.1 "Exportar chat" (oficial, la vía más simple y segura)
- Ruta Android: abrir chat → ⋮ → Más → **Exportar chat** → *Sin archivos* / *Incluir archivos* → compartir (Drive, correo, guardar en el teléfono). https://faq.whatsapp.com/1180414079177245
- Sale un **.txt** por chat, con líneas tipo `25/10/26, 14:03 - Nombre: mensaje`. El formato de fecha cambia según región e idioma del teléfono, así que el parser necesita un regex flexible (el repo kinggongzilla avisa justo de esto).
- **Límites:** WhatsApp no publica la cifra en su FAQ actual, pero varias fuentes secundarias coinciden: **~40,000 mensajes más recientes sin archivos** y **~10,000 con archivos** (p. ej. https://wachatplus.com/en/blog/why-whatsapp-export-stops-at-40000). Para entrenar el estilo sobra: exporta *sin archivos*.
- Es **un chat a la vez**. Prioriza tus 10–30 chats 1:1 más activos.
- No se puede volver a importar a WhatsApp, solo sirve como texto (lo dice la FAQ).

### 1.2 Backup cifrado (.crypt14 / .crypt15)
- Los backups van a Google Drive o al almacenamiento de WhatsApp, con cifrado de extremo a extremo opcional (en el almacenamiento de WhatsApp siempre va cifrado). Se protegen con passkey, contraseña o **clave de 64 dígitos**. https://faq.whatsapp.com/490592613091019
- Para leer la base `msgstore.db` completa (todo el historial, sin el tope de 40k) sirve **wa-crypt-tools** (open source, local): descifra .crypt12/14/15 **si tienes la clave de 64 caracteres o el archivo `key`**. https://github.com/ElDavoo/wa-crypt-tools
- Si usas contraseña o passkey en vez de la clave de 64 dígitos, no tienes la clave cruda. Lo práctico sería activar el backup E2E con **clave de 64 dígitos**, copiar el `msgstore.db.crypt15` local (`Android/media/com.whatsapp/WhatsApp/Databases/`) a la PC y descifrarlo ahí. Así lo haces con tus datos y tu clave, sin root. Es más trabajo que exportar; solo vale la pena si quieres *todo* el historial.

### 1.3 Librerías no oficiales: ¿traen historial viejo?
| Librería | Lenguaje | Historial antiguo | Fuente |
|---|---|---|---|
| **Baileys** (la de Hermes) | Node/TS, WebSocket | **Sí, parcial.** Al vincular llega `messaging-history.set`. Con `syncFullHistory: true` + `Browsers.macOS('Desktop')` WhatsApp manda bastante más; `sock.fetchMessageHistory()` pide mensajes más viejos bajo demanda. Lo decide el teléfono, no hay garantía de "todo". | https://baileys.wiki/advanced/history-sync |
| **whatsmeow** | Go | Sí: evento `events.HistorySync` con tipos `INITIAL_BOOTSTRAP`, `FULL`, `RECENT`, `PUSH_NAME`… lo que el teléfono decida enviar. | https://github.com/tulir/whatsmeow , https://pkg.go.dev/go.mau.fi/whatsmeow/types/events |
| **whatsapp-web.js** | Node + Puppeteer (Chrome) | `chat.fetchMessages({limit})` solo carga lo que WhatsApp Web tiene o sincroniza. Hay issues abiertos de resultados incompletos (`limit: Infinity` devuelve 1 msg; `syncHistory()` falla). | https://docs.wwebjs.dev/Chat.html , https://github.com/wwebjs/whatsapp-web.js/issues/2297 |

**Conclusión:** para el dataset de estilo, la **exportación .txt** es más fiable, no toca ToS y cero riesgo. Las librerías sirven para *leer en vivo*; el historial que traen es "best effort".

---

## 2. Riesgo de baneo y ToS

- **ToS de WhatsApp:** prohíbe usar el servicio con medios automatizados no autorizados y acceder a él con apps no autorizadas. https://www.whatsapp.com/legal/terms-of-service
- **FAQ oficial:** "Nuestros productos no están pensados para mensajería masiva **o automatizada**; ambas han sido siempre una violación de los Términos". Meta tiene detección automática y banea cuentas. https://faq.whatsapp.com/5957850900902049
- "Uso responsable": no mandar mensajes automatizados ni masivos; las cuentas reportadas varias veces se banean. https://faq.whatsapp.com/361005896189245
- **Realidad:** Baileys / whatsmeow / wwebjs son clientes no oficiales. El riesgo crece con volumen, mensajes salientes a desconocidos y reportes, y se reduce (pero **nunca llega a cero**) con uso conversacional y de bajo volumen. Un baneo en tu **número personal** significa perder tu cuenta real.

### WhatsApp Business Cloud API (oficial)
- Precio por mensaje desde el 1-jul-2025: se cobran **plantillas**; los mensajes de texto normales **dentro de la ventana de 24 h** que abre el cliente son **gratis**. https://developers.facebook.com/docs/whatsapp/pricing/
- **No sirve para tu cuenta personal:** requiere Meta Business, número dado de alta en la plataforma y webhook público (la doc de Hermes lo dice: "requires a Meta Business account and a public webhook URL"). Es para un número de empresa, no para que "tú" contestes a tus amigos desde tu WhatsApp. Técnicamente podría salir gratis (solo respuestas dentro de 24 h), pero no resuelve tu caso.
- **Gratis y oficial sin programar nada:** la **app WhatsApp Business** tiene "Mensaje de ausencia" con horario y destinatarios ("Solo enviar a…", "Todos excepto…"). Es una respuesta fija, no IA, y requiere pasar tu número a la app Business. https://faq.whatsapp.com/2565868990219715

---

## 3. Alternativa sin tocar el protocolo: notificaciones de Android

- **`NotificationListenerService`** lee las notificaciones de WhatsApp (remitente + texto) una vez que el usuario concede el acceso a notificaciones. https://developer.android.com/reference/android/service/notification/NotificationListenerService
- La notificación de WhatsApp trae una acción **"Responder"** con **`RemoteInput`**. Una app puede rellenar ese `RemoteInput` y disparar el `PendingIntent`, igual que si respondieras desde la notificación. https://developer.android.com/reference/android/app/RemoteInput
- **Ventajas:** no hay cliente no oficial ni sesión de WhatsApp Web; el mensaje lo envía la app oficial. El riesgo de detección es mucho menor (no es cero: sigue siendo automatización, el ToS no cambia). Ejemplo de este patrón: https://dev.to/prince_nebhwani_4ec88c602/how-i-built-an-ai-whatsapp-auto-responder-with-0-ban-risk-using-google-gemini-51ae (el "0% ban risk" es marketing; sería más correcto decir "bajo").
- **Limitaciones:**
  - Solo ves lo que trae la notificación: los últimos mensajes, sin historial completo, nada de chats silenciados ni de cuando tienes el chat abierto.
  - Los grupos llegan con el formato "Grupo: Nombre: msg"; hay que filtrarlos.
  - Nothing OS / Android mata servicios en segundo plano: hay que excluir la app de la optimización de batería.
  - La IA tiene que correr en el teléfono (pequeña) o en tu PC: el teléfono manda el texto a tu PC por LAN/Tailscale, la PC genera y devuelve la respuesta. Un `ollama serve` en la PC funciona como backend gratis.
- **Sin programar:** apps tipo "AutoResponder for WA" usan este mismo mecanismo, pero son freemium y de código cerrado (tus mensajes pasan por ellas). Mejor una app propia mínima en Kotlin, o **Tasker/MacroDroid + AutoNotification** (de pago, no cumple "100% gratis").

---

## 4. Aprender tu estilo

### 4.1 Opción A: few-shot / RAG (sin entrenar; empezar aquí)
- Extraes **tus** mensajes de los .txt, los partes en pares *(mensaje del otro → tu respuesta)* y los guardas en una base vectorial local (Chroma/LanceDB + embeddings `nomic-embed-text` o `bge-m3` vía Ollama).
- Por cada mensaje entrante recuperas los 10–20 pares más parecidos (idealmente **del mismo contacto**) y los pones en el prompt como ejemplos, más un "perfil de estilo" generado una vez: largo típico, emojis, muletillas, mayúsculas, "jaja" vs "jsjs", etc.
- Sirve con cualquier modelo local (Qwen3 8B, Llama 3.1 8B, Gemma) en Ollama sobre tus 8 GB. **Cero entrenamiento**, actualizable al instante, y el modelo sigue entendiendo instrucciones ("no prometas nada", "di que luego respondo").
- Con **unos cientos de pares** ya imita bastante bien el tono.

### 4.2 Opción B: fine-tuning LoRA/QLoRA
- **Unsloth** (gratis, open source) corre en Windows sin WSL. Soporta Blackwell / RTX 50 (necesita CUDA 12.8+) y Python 3.11–3.13. https://unsloth.ai/docs/get-started/fine-tuning-for-beginners/unsloth-requirements
  - Su tabla de requisitos indica ~5 GB de VRAM para QLoRA de 7–8B, así que **tu 5060 Ti de 8 GB alcanza** para Qwen2.5/Qwen3 7–8B o Llama 3.1 8B en 4-bit, con secuencias cortas (512–1024 tokens) y batch 1–2 con acumulación de gradiente. Un modelo de 3–4B va holgado.
  - Ojo: el `python` del sistema es 3.14, que no es compatible. Hay que crear un venv con `uv venv -p 3.12`.
- **Nube gratis:** Google Colab (T4 16 GB, sesiones limitadas) o **Kaggle** (P100 o 2×T4, **~30 h/semana**). https://www.kaggle.com/docs/efficient-gpu-usage. Implica subir tus chats a Google/Kaggle, lo cual choca con "todo local". Si lo usas, sube solo datos anonimizados.
- **Formato del dataset:** chat/ShareGPT en JSONL, con *tus* mensajes como `assistant` y los del otro como `user`. Agrupa varios mensajes seguidos de la misma persona en un turno y corta la conversación en "sesiones" cuando hay más de ~1–2 h de silencio. https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/datasets-guide
  ```json
  {"messages":[{"role":"system","content":"Eres <Yo>. Responde como yo en WhatsApp."},
               {"role":"user","content":"oye mañana sí vas?"},
               {"role":"assistant","content":"simon\nnomas q salgo como a las 6"}]}
  ```
- **¿Cuántos mensajes?** No hay cifra oficial. Los proyectos existentes usan de ~1,800 filas (Clone-Yourself) a decenas de miles. Como regla práctica: **≥2,000–5,000 turnos tuyos** limpios para que el estilo "pegue", de 10k en adelante mejor. Filtra "<Multimedia omitido>", "Se eliminó este mensaje", links, OTPs y mensajes de 1 carácter.
- **Desventaja:** el fine-tune aprende el estilo, pero **también alucina hechos de tu vida** ("sí, ahí nos vemos a las 5") e inventa compromisos. Para auto-responder es más peligroso que el RAG con instrucciones estrictas.

### 4.3 Repos open source existentes
| Repo | Qué hace | Notas |
|---|---|---|
| https://github.com/kinggongzilla/ai-clone-whatsapp | Preprocesa .txt exportados → ShareGPT, QLoRA con torchtune, chat por CLI | ~420★; Llama3-8B / Mistral-7B; el regex es para formato europeo (ajustar a MX) |
| https://github.com/Eviltr0N/Make-AI-Clone-of-Yourself | Notebook Colab con **Unsloth**: limpieza, filtrado, entrenamiento, export **GGUF → Ollama** | El más cercano a tu stack |
| https://github.com/aalizelau/Clone-Yourself | .txt 1:1 → JSONL, QLoRA sobre Qwen-7B | Advierte que la T4 gratis de Colab puede quedarse corta de memoria |
| https://github.com/Ads97/WhatsApp-Llama | Fork de llama-recipes, Llama-2 7B | Viejo, solo como referencia |
| https://github.com/Amal-David/whatsapp-llm | Toolkit local-first para modelar a una persona desde chats autorizados | Experimental |

---

## 5. Privacidad

- Los chats contienen **datos personales de terceros** que no consintieron. En México aplica la LFPDPPP. El uso personal y doméstico es la zona más segura, pero **no publiques el modelo ni el dataset** (un LoRA puede regurgitar frases textuales de otros).
- **Todo local:** parseo, embeddings, entrenamiento (Unsloth en la 5060 Ti) e inferencia (Ollama). No mandes los chats a APIs en la nube (Claude/GPT/Gemini) ni a Colab/Kaggle sin anonimizar.
- **Anonimizar antes de entrenar:** reemplaza nombres y números de los demás por `<CONTACTO_n>` y teléfonos, emails, direcciones, CURP/RFC y cuentas bancarias por placeholders (regex + Microsoft Presidio, open source, con modelo de spaCy en español). Elimina chats sensibles (salud, pareja, trabajo confidencial).
- Entrena solo con **tus** mensajes como objetivo. Los del otro sirven de contexto y no se aprenden como salida.
- Cifra la carpeta del dataset (BitLocker/VeraCrypt) y **nunca** subas al repo `research/` ni la sesión de Baileys (`~/.hermes/platforms/whatsapp/session` da acceso total a la cuenta).

---

## 6. Diseño de auto-respuesta segura

1. **Interruptor "modo ocupado"** explícito (comando `/ocupado on 2h` en tu self-chat de Hermes, o un toggle en la app Android) con expiración automática. Nunca encendido por defecto.
2. **Lista blanca** de contactos (familia o amigos que saben del experimento). Todos los demás se ignoran. En Hermes: `WHATSAPP_ALLOWED_USERS` + `unauthorized_dm_behavior: ignore`.
3. **No responder grupos**, estados, canales, ni números desconocidos.
4. **Aviso transparente:** prefijo tipo `🤖 (respuesta automática, Yokis está ocupado)` mediante `reply_prefix` en Hermes. No te hagas pasar por humano.
5. **Aprobación previa (human-in-the-loop) por defecto:** la IA redacta, te llega el borrador (notificación o self-chat) y tú apruebas con ✅ o editas. El envío autónomo queda solo para respuestas "seguras" de bajo riesgo.
6. **Respuestas acotadas:** la IA solo puede acusar recibo, decir que luego contestas, o responder algo trivial con los ejemplos del RAG. **Prohibido** aceptar planes, dar dinero, datos personales, contraseñas, ubicaciones o compromisos. Si detecta cualquiera de eso, escala a ti sin contestar.
7. **Límites:** máximo 1 respuesta automática por contacto cada X min y N por día, un retraso aleatorio de 30–120 s, y **nunca** iniciar conversaciones. Esto también baja el riesgo de baneo.
8. **Log local** de todo lo que se respondió, para revisar después.
9. **Kill switch:** si vuelves a escribir en ese chat manualmente, la IA se calla en ese chat.

---

## 7. Recomendación

- **Datos:** exporta tus 10–30 chats 1:1 principales como .txt *sin archivos*. Usa backup + wa-crypt-tools solo si de verdad quieres todo el historial.
- **Estilo:** empieza con **RAG + few-shot local** (Ollama + Qwen3 8B + Chroma) usando tus pares anonimizados. Si después de probarlo quieres más parecido, haz **QLoRA con Unsloth en tu 5060 Ti** (modelo 4–8B, venv Python 3.12), basándote en el notebook de Eviltr0N, y exporta a GGUF para Ollama.
- **Canal:** no conectes Baileys a tu número personal para responder a terceros, porque arriesgas tu cuenta real. Las opciones más seguras, de mejor a peor:
  - (a) **App Android propia con NotificationListener + RemoteInput** que llama a tu PC (Ollama) y deja borradores para aprobación;
  - (b) el gateway Hermes **solo en modo self-chat** para que te muestre borradores que tú copias;
  - (c) un mensaje de ausencia fijo de WhatsApp Business como respaldo sin IA.
- **Siempre:** lista blanca, sin grupos, aviso "respondido por IA", aprobación previa, límites, todo local.

---

**Archivo:** `C:\Users\yokis\Trabajos\Proyectos\sapo-jarvis\research\04-whatsapp.md`

**Recomendación en 5 líneas:**
1. Datos: "Exportar chat" .txt sin archivos de tus chats 1:1 principales (~40k mensajes por chat); anonimiza todo localmente.
2. Estilo: RAG + few-shot con Ollama (Qwen3 8B) primero; QLoRA con Unsloth en la 5060 Ti solo si hace falta.
3. Canal: NotificationListener + RemoteInput en el Nothing Phone → tu PC. No uses Baileys/Hermes sobre tu número personal (ToS y baneo).
4. Seguridad: modo ocupado temporal, lista blanca, nada de grupos, prefijo "🤖 respuesta automática", borrador con aprobación y rate limit.
5. Cloud API oficial no aplica a cuenta personal; el gateway Hermes queda para self-chat o un número bot dedicado.
