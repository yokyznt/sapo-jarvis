# Fase Android · Etapas 7–10

App `android/` (Kotlin + Compose, minSdk 26, target 36, paquete `io.github.yokyznt.sapo`). Pública, gratis, sin Firebase ni Play Services. Distribución: APK en GitHub Releases (Obtainium). Cada etapa = rama `etapa-N` + PR apilado.

| Etapa | Qué entrego | Qué pruebas tú | Necesito de ti |
|---|---|---|---|
| 7 · App base WhatsApp | Onboarding de permisos (notificaciones, batería), lector de notificaciones de WhatsApp/WhatsApp Business, lista blanca de contactos, importador de chats `.txt` exportados, perfil de estilo, sugerencia de respuesta con botón "Enviar" manual (RemoteInput) | Recibir un mensaje y mandar la sugerencia con un toque | Exportar 10–30 chats 1:1 sin archivos; key de Gemini en la app |
| 8 · Respuesta automática | Modo ocupado (manual, No molestar, juego en la PC, sin usar el cel X min), respuesta autónoma solo a lista blanca con 🤖, nunca grupos, límite por contacto, botón de pánico, historial | Dejarlo en ocupado y que conteste a 1 contacto de prueba | Elegir contactos de prueba |
| 9 · Aprende de ti | Accesibilidad que lee lo que tú escribes en WhatsApp (local) para mejorar el estilo, sincronía con el cerebro de la PC por la red local | Escribir normal unos días | Activar accesibilidad |
| 10 · Sapo en el cel | Sapito flotante (overlay), comandos de voz para el cel, llamadas y SMS con confirmación | Hablarle al sapo del cel | Permisos de overlay, llamadas, SMS |

## Reglas
- Nunca responde en grupos ni a quien no esté en la lista blanca.
- Toda respuesta automática lleva 🤖 al inicio.
- Datos (chats importados, estilo, historial) solo en el teléfono, en almacenamiento privado de la app; la key cifrada con Android Keystore.
- Gemini directo desde el teléfono (key propia); sin key no hay respuestas automáticas, solo sugerencias desde frases del propio estilo.
