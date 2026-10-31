package io.github.yokyznt.sapo.core

object Guard {
    private const val ROBOT = "🤖 "
    private val prefix = Regex(
        "^\\s*(yo|me|tu|tú|respuesta|reply|answer|sapo|bot|asistente|assistant|mensaje)\\s*:\\s*",
        RegexOption.IGNORE_CASE
    )
    private val quotes = "\"'“”‘’«»`"
    private val aiPatterns = listOf(
        "como ia", "como una ia", "como un ia", "soy una ia", "soy un ia", "soy un modelo", "soy una inteligencia",
        "modelo de lenguaje", "inteligencia artificial", "soy un asistente", "soy una asistente", "soy un bot",
        "as an ai", "i am an ai", "i'm an ai", "language model", "as a language model", "openai", "chatgpt",
        "no tengo sentimientos", "no puedo tener opiniones"
    )
    private val groupTitle = Regex("^.+\\s\\(\\d+\\s(mensajes|messages)\\):\\s.+$", RegexOption.IGNORE_CASE)

    fun isGroup(title: String?, conversationTitle: String?, isGroupConversation: Boolean): Boolean {
        if (isGroupConversation) return true
        val t = title?.trim().orEmpty()
        val c = conversationTitle?.trim().orEmpty()
        if (c.isNotEmpty() && t.isNotEmpty() && c != t && !c.startsWith(t)) return true
        if (groupTitle.matches(t)) return true
        if (c.isEmpty() && t.contains(": ")) return true
        return false
    }

    fun clean(reply: String, maxChars: Int = 300): String? {
        var s = reply.trim()
        var changed = true
        while (changed && s.isNotEmpty()) {
            val before = s
            s = prefix.replace(s, "").trim()
            if (s.length >= 2 && s.first() in quotes && s.last() in quotes) s = s.substring(1, s.length - 1).trim()
            changed = s != before
        }
        s = s.replace(Regex("[ \\t]+"), " ").replace(Regex("\\n{3,}"), "\n\n").trim()
        if (s.isEmpty()) return null
        if (s.length == 1 && s[0] in quotes) return null
        val folded = Text.fold(s)
        if (aiPatterns.any { folded.contains(Text.fold(it)) }) return null
        if (maxChars > 0 && s.length > maxChars) s = cut(s, maxChars)
        return s.ifBlank { null }
    }

    fun mark(reply: String): String = if (reply.startsWith("🤖")) reply else ROBOT + reply

    private fun cut(s: String, max: Int): String {
        val head = s.substring(0, max)
        val sentence = head.indexOfLast { it == '.' || it == '!' || it == '?' || it == '…' }
        if (sentence >= max / 2) return head.substring(0, sentence + 1).trim()
        val space = head.lastIndexOf(' ')
        val body = if (space >= max / 2) head.substring(0, space) else head.substring(0, max - 1)
        return body.trimEnd(' ', ',', ';', ':') + "…"
    }
}
