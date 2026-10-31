package io.github.yokyznt.sapo.core

import java.util.Locale

object Style {
    private val laughRegex = Regex(
        "\\b(?:(?:j+[aeiou]+){2,}j*|(?:[aeiou]?j+[aeiou]+j+[aeiou]*)|(?:js){2,}j?|(?:h+[ae]+){2,}h*|x+d+|lol+|lmao+)\\b",
        RegexOption.IGNORE_CASE
    )
    private val fillerWords = listOf(
        "wey", "guey", "we", "neta", "pues", "bueno", "osea", "va", "sale", "ok", "oki", "oye", "bro",
        "carnal", "chido", "vale", "tipo", "literal", "nmms", "alv", "simon", "nel", "equis", "porfa", "ntp",
        "obvio", "aja", "mmm", "ah", "eh", "este", "bueeno", "dale", "listo", "orale", "ya"
    )

    fun profile(myMessages: List<String>): StyleProfile {
        val msgs = myMessages.map { it.trim() }.filter { it.isNotEmpty() }
        val n = msgs.size
        if (n == 0) return StyleProfile(0.0, 0.0, emptyList(), 0.0, null, emptyList(), 0.0, 0)
        val avgWords = msgs.sumOf { m -> m.split(Regex("\\s+")).count { it.isNotEmpty() } }.toDouble() / n
        val emojiCounts = HashMap<String, Int>()
        var withEmoji = 0
        for (m in msgs) {
            val e = Text.emojis(m)
            if (e.isNotEmpty()) withEmoji++
            for (x in e) emojiCounts[x] = (emojiCounts[x] ?: 0) + 1
        }
        val topEmojis = emojiCounts.entries.sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key })
            .take(5).map { it.key }
        var withLetter = 0
        var lower = 0
        for (m in msgs) {
            val c = m.firstOrNull { it.isLetter() } ?: continue
            withLetter++
            if (c.isLowerCase()) lower++
        }
        val laughCounts = HashMap<String, Int>()
        for (m in msgs) for (r in laughRegex.findAll(m)) {
            val k = r.value.lowercase(Locale.ROOT)
            laughCounts[k] = (laughCounts[k] ?: 0) + 1
        }
        val laugh = laughCounts.entries.sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key })
            .firstOrNull()?.key
        val fillerCounts = HashMap<String, Int>()
        for (m in msgs) {
            val ws = Text.words(m).toSet()
            for (f in fillerWords) if (f in ws) fillerCounts[f] = (fillerCounts[f] ?: 0) + 1
        }
        val minCount = maxOf(2, (n * 0.03).toInt())
        val fillers = fillerCounts.entries.filter { it.value >= minCount }
            .sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key })
            .take(6).map { it.key }
        val punct = msgs.count { it.last() in ".!?…" }
        return StyleProfile(
            avgWords = avgWords,
            emojiRate = withEmoji.toDouble() / n,
            topEmojis = topEmojis,
            lowercaseRate = if (withLetter == 0) 0.0 else lower.toDouble() / withLetter,
            laugh = laugh,
            fillers = fillers,
            endsWithPunct = punct.toDouble() / n,
            samples = n
        )
    }

    fun describe(p: StyleProfile): String {
        if (p.samples == 0) return "Sin muestras de estilo: escribe breve, casual y natural."
        val parts = ArrayList<String>()
        val len = when {
            p.avgWords < 5 -> "mensajes muy cortos"
            p.avgWords < 12 -> "mensajes cortos"
            p.avgWords < 25 -> "mensajes de longitud media"
            else -> "mensajes largos"
        }
        parts.add("$len (unas ${Math.round(p.avgWords)} palabras en promedio)")
        parts.add(
            when {
                p.lowercaseRate >= 0.7 -> "casi siempre empieza en minúscula"
                p.lowercaseRate >= 0.4 -> "a veces empieza en minúscula"
                else -> "suele empezar con mayúscula"
            }
        )
        parts.add(
            when {
                p.endsWithPunct >= 0.6 -> "suele cerrar con punto o signo"
                p.endsWithPunct >= 0.25 -> "a veces cierra con puntuación"
                else -> "casi nunca pone punto final"
            }
        )
        if (p.emojiRate >= 0.05 && p.topEmojis.isNotEmpty()) {
            parts.add("usa emojis en ${Math.round(p.emojiRate * 100)}% de sus mensajes, sobre todo ${p.topEmojis.joinToString(" ")}")
        } else {
            parts.add("casi no usa emojis")
        }
        if (p.laugh != null) parts.add("se ríe escribiendo \"${p.laugh}\"")
        if (p.fillers.isNotEmpty()) parts.add("muletillas frecuentes: ${p.fillers.joinToString(", ")}")
        return "Estilo (de ${p.samples} mensajes): " + parts.joinToString("; ") + "."
    }
}
