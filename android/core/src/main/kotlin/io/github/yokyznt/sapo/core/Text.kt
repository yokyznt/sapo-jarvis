package io.github.yokyznt.sapo.core

import java.text.Normalizer

internal object Text {
    private val marks = Regex("\\p{M}+")
    private val nonWord = Regex("[^\\p{L}\\p{N}]+")
    private val repeats = Regex("(\\p{L})\\1{2,}")

    fun fold(s: String): String =
        marks.replace(Normalizer.normalize(s.lowercase(), Normalizer.Form.NFD), "")

    fun words(s: String): List<String> =
        nonWord.split(repeats.replace(fold(s), "$1")).filter { it.isNotEmpty() }

    fun isEmoji(cp: Int): Boolean =
        (cp in 0x1F300..0x1F5FF || cp in 0x1F600..0x1F64F || cp in 0x1F680..0x1F6FF ||
            cp in 0x1F900..0x1F9FF || cp in 0x1FA70..0x1FAFF || cp in 0x2600..0x27BF ||
            cp in 0x1F000..0x1F2FF) && cp !in 0x1F3FB..0x1F3FF

    fun emojis(s: String): List<String> {
        val out = ArrayList<String>()
        var i = 0
        while (i < s.length) {
            val cp = s.codePointAt(i)
            if (isEmoji(cp)) out.add(String(Character.toChars(cp)))
            i += Character.charCount(cp)
        }
        return out
    }
}
