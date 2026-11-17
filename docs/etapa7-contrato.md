# Etapa 7 · contrato del módulo `:core` (Kotlin JVM puro, sin Android)

Paquete `io.github.yokyznt.sapo.core`. Lo usa la app (`:app`) y se prueba con JUnit en la PC.

```kotlin
data class ChatLine(val time: java.time.LocalDateTime?, val author: String, val text: String)
data class Chat(val name: String, val me: String, val lines: List<ChatLine>)
data class Pair(val them: String, val me: String, val contact: String)

object WhatsAppExport {
    fun parse(name: String, raw: String, me: String? = null): Chat
    fun guessMe(chats: List<Chat>): String?
}

object Pairs { fun build(chat: Chat, gapMinutes: Long = 90): List<Pair> }

data class StyleProfile(
    val avgWords: Double, val emojiRate: Double, val topEmojis: List<String>,
    val lowercaseRate: Double, val laugh: String?, val fillers: List<String>,
    val endsWithPunct: Double, val samples: Int
)
object Style { fun profile(myMessages: List<String>): StyleProfile; fun describe(p: StyleProfile): String }

class Examples(pairs: List<Pair>) { fun nearest(incoming: String, contact: String?, k: Int = 12): List<Pair> }

object Prompt {
    fun reply(incoming: String, contact: String, history: List<ChatLine>, style: StyleProfile, examples: List<Pair>, auto: Boolean): String
}

object Guard {
    fun isGroup(title: String?, conversationTitle: String?, isGroupConversation: Boolean): Boolean
    fun clean(reply: String, maxChars: Int = 300): String?
    fun mark(reply: String): String
}
```

- `parse` acepta los formatos de exportación de Android en español e inglés (`dd/MM/yy, HH:mm - Autor: texto`, `[dd/MM/yy, h:mm:ss a. m.] Autor: texto`, 12/24 h, `a. m.`/`p. m.`, años de 2 o 4 dígitos), líneas de continuación multilínea, y descarta `<Multimedia omitido>`, `Se eliminó este mensaje`, mensajes de sistema, OTPs y enlaces sueltos.
- `Examples.nearest`: similitud TF-IDF de palabras normalizadas (sin acentos, minúsculas), prioriza el mismo contacto.
- `Prompt.reply`: instrucciones en español, "eres <me> respondiendo por WhatsApp", perfil de estilo, ejemplos, últimos mensajes, reglas: no inventar planes, horarios ni compromisos; si piden algo importante, decir que luego responde; nada de datos personales; 1–2 frases.
- `Guard.clean`: recorta, quita comillas/prefijos tipo "Yo:", rechaza vacíos o respuestas que digan ser IA. `mark` antepone "🤖 ".
