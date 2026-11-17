package io.github.yokyznt.sapo.core

object Contacts {
    private val skip = setOf(
        "mi", "mis", "a", "al", "el", "la", "los", "las", "de", "del", "con", "para", "su", "sus", "tu", "tus", "le", "les"
    )

    fun best(query: String, names: List<String>): String? {
        val q = Text.words(query).filter { it !in skip }
        if (q.isEmpty()) return null
        val scored = names.distinct().mapNotNull { n ->
            val s = score(q, Text.words(n).filter { it !in skip })
            if (s > 0) n to s else null
        }
        val top = scored.maxOfOrNull { it.second } ?: return null
        return scored.filter { it.second == top }.singleOrNull()?.first
    }

    private fun score(q: List<String>, w: List<String>): Int {
        if (w.isEmpty()) return 0
        var total = 0
        var hits = 0
        val covered = HashSet<Int>()
        for (a in q) {
            var bestScore = 0
            var bestIndex = -1
            w.forEachIndexed { i, b ->
                val m = match(a, b)
                if (m > bestScore) {
                    bestScore = m
                    bestIndex = i
                }
            }
            if (bestScore == 0) {
                total -= 2
            } else {
                total += bestScore
                hits++
                covered.add(bestIndex)
            }
        }
        if (hits == 0) return 0
        if (covered.size == w.size) total += 1
        return total
    }

    private fun match(a: String, b: String): Int = when {
        a == b -> 3
        a.length >= 2 && b.startsWith(a) -> 2
        b.length >= 3 && a.startsWith(b) -> 2
        a.length >= 5 && b.length >= 5 && oneEdit(a, b) -> 1
        else -> 0
    }

    private fun oneEdit(a: String, b: String): Boolean {
        if (a.length < b.length) return oneEdit(b, a)
        if (a.length - b.length > 1) return false
        var i = 0
        var j = 0
        var edits = 0
        while (i < a.length && j < b.length) {
            if (a[i] == b[j]) {
                i++
                j++
            } else {
                edits++
                if (edits > 1) return false
                if (a.length == b.length) j++
                i++
            }
        }
        edits += (a.length - i) + (b.length - j)
        return edits <= 1
    }
}
