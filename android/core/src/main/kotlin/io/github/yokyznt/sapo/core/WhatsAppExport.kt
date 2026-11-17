package io.github.yokyznt.sapo.core

import java.time.LocalDateTime

object WhatsAppExport {
    private const val DATE = "(\\d{1,2})[/.-](\\d{1,2})[/.-](\\d{2,4}),?\\s+(\\d{1,2})[:.](\\d{2})(?:[:.](\\d{2}))?\\s*([aApP]\\.?\\s?[mM]\\.?)?"
    private val plain = Regex("^$DATE\\s*[-–]\\s(.*)$")
    private val bracket = Regex("^\\[$DATE\\]\\s(.*)$")
    private val invisible = Regex("[\\u200e\\u200f\\u202a-\\u202e\\u2066-\\u2069\\ufeff]")
    private val spaces = Regex("[\\u00a0\\u202f\\u2007]")
    private val edited = Regex("\\s*<(Se editó este mensaje\\.|This message was edited)>\\s*$")
    private val loneLink = Regex("^(https?://|www\\.)\\S+$", RegexOption.IGNORE_CASE)
    private val bareCode = Regex("^\\d{4,8}$")
    private val otpWords = Regex("(c[oó]digo|code|otp|verificaci[oó]n|verification|clave)", RegexOption.IGNORE_CASE)
    private val otpDigits = Regex("(?<!\\d)\\d{3}[- ]?\\d{3}(?!\\d)|(?<!\\d)\\d{4,8}(?!\\d)")
    private val attachment = Regex("\\((archivo adjunto|file attached)\\)\\s*$", RegexOption.IGNORE_CASE)

    private val dropped = setOf(
        "<multimedia omitido>", "<media omitted>", "multimedia omitido", "imagen omitida", "video omitido",
        "audio omitido", "sticker omitido", "gif omitido", "documento omitido", "<adjunto omitido>",
        "se eliminó este mensaje.", "se eliminó este mensaje", "eliminaste este mensaje.", "eliminaste este mensaje",
        "this message was deleted", "this message was deleted.", "you deleted this message", "you deleted this message.",
        "null", "mensaje de voz omitido", "<se omitió el mensaje de voz>", "ubicación:", "llamada perdida",
        "llamada de voz perdida", "videollamada perdida", "missed voice call", "missed video call",
        "este mensaje fue eliminado", "se omitió este mensaje"
    )

    private val systemTexts = listOf(
        "cifrados de extremo a extremo", "end-to-end encrypted", "cambio su numero de telefono",
        "changed their phone number", "los mensajes temporales", "disappearing messages"
    )

    private class Raw(val time: LocalDateTime?, val author: String?, val sb: StringBuilder)

    fun parse(name: String, raw: String, me: String? = null): Chat {
        val entries = ArrayList<Raw>()
        for (line0 in raw.replace("\r\n", "\n").replace('\r', '\n').split('\n')) {
            val line = spaces.replace(invisible.replace(line0, ""), " ")
            val m = bracket.find(line) ?: plain.find(line)
            if (m == null) {
                val last = entries.lastOrNull() ?: continue
                last.sb.append('\n').append(line)
                continue
            }
            val g = m.groupValues
            val time = toTime(g[1], g[2], g[3], g[4], g[5], g[6], g[7])
            val rest = g[8]
            val idx = rest.indexOf(": ")
            val noColon = rest.endsWith(":") && !rest.contains(": ")
            if (idx <= 0 && !noColon) {
                entries.add(Raw(time, null, StringBuilder(rest)))
            } else if (noColon) {
                entries.add(Raw(time, rest.dropLast(1).trim(), StringBuilder()))
            } else {
                entries.add(Raw(time, rest.substring(0, idx).trim(), StringBuilder(rest.substring(idx + 2))))
            }
        }
        val lines = entries.mapNotNull { e ->
            val author = e.author ?: return@mapNotNull null
            if (author.isEmpty() || isSystemAuthor(author)) return@mapNotNull null
            val text = edited.replace(e.sb.toString(), "").trim()
            if (keep(text)) ChatLine(e.time, author, text) else null
        }
        val resolved = me ?: inferMe(name, lines)
        return Chat(name, resolved, lines)
    }

    fun guessMe(chats: List<Chat>): String? {
        val useful = chats.filter { it.lines.isNotEmpty() }
        if (useful.isEmpty()) return null
        if (useful.size == 1) return useful[0].me.ifBlank { null }
        val sets = useful.map { c -> c.lines.map { it.author }.toSet() }
        val common = sets.reduce { a, b -> a intersect b }
        if (common.isEmpty()) {
            val votes = useful.map { it.me }.filter { it.isNotBlank() }.groupingBy { it }.eachCount()
            return votes.maxByOrNull { it.value }?.key
        }
        val counts = HashMap<String, Int>()
        for (c in useful) for (l in c.lines) if (l.author in common) counts[l.author] = (counts[l.author] ?: 0) + 1
        return common.maxByOrNull { counts[it] ?: 0 }
    }

    private fun inferMe(name: String, lines: List<ChatLine>): String {
        val authors = lines.map { it.author }.distinct()
        val folded = Text.fold(name.trim())
        val others = authors.filter { Text.fold(it) != folded }
        return if (others.size == 1 && authors.size == 2) others[0] else ""
    }

    private fun isSystemAuthor(author: String): Boolean {
        val f = Text.fold(author)
        return f.contains("cifrad") || f.contains("encrypted") || author.length > 60
    }

    private fun keep(text: String): Boolean {
        if (text.isBlank()) return false
        val lower = text.lowercase()
        if (lower in dropped) return false
        if (lower.startsWith("<") && lower.endsWith(">") && lower.contains("omit")) return false
        if (attachment.containsMatchIn(text) && !text.trim().contains('\n')) return false
        if (lower.startsWith("ubicación: ") || lower.startsWith("location: ")) return false
        val folded = Text.fold(text)
        if (systemTexts.any { folded.contains(it) }) return false
        if (loneLink.matches(text.trim())) return false
        if (bareCode.matches(text.trim())) return false
        if (otpWords.containsMatchIn(text) && otpDigits.containsMatchIn(text)) return false
        return true
    }

    private fun toTime(d: String, mo: String, y: String, h: String, mi: String, s: String, ampm: String): LocalDateTime? {
        var day = d.toInt()
        var month = mo.toInt()
        if (month > 12 && day <= 12) {
            val t = day; day = month; month = t
        }
        var year = y.toInt()
        if (year < 100) year += 2000
        var hour = h.toInt()
        val minute = mi.toInt()
        val second = if (s.isEmpty()) 0 else s.toInt()
        if (ampm.isNotEmpty()) {
            val pm = ampm.trim().lowercase().startsWith("p")
            if (pm && hour < 12) hour += 12
            if (!pm && hour == 12) hour = 0
        }
        return try {
            LocalDateTime.of(year, month, day, hour, minute, second)
        } catch (e: Exception) {
            null
        }
    }
}
