package io.github.yokyznt.sapo.core

import kotlin.math.ln
import kotlin.math.sqrt

class Examples(pairs: List<Pair>) {
    private val items = pairs
    private val idf: Map<String, Double>
    private val vectors: List<Map<String, Double>>

    init {
        val docs = items.map { Text.words(it.them) }
        val df = HashMap<String, Int>()
        for (d in docs) for (w in d.toSet()) df[w] = (df[w] ?: 0) + 1
        val n = docs.size.toDouble()
        idf = df.mapValues { ln((n + 1.0) / (it.value + 1.0)) + 1.0 }
        vectors = docs.map { vector(it) }
    }

    fun nearest(incoming: String, contact: String?, k: Int = 12): List<Pair> {
        if (items.isEmpty() || k <= 0) return emptyList()
        val q = vector(Text.words(incoming))
        val target = contact?.let { Text.fold(it.trim()) }
        val scored = items.indices.map { i ->
            val sim = cosine(q, vectors[i])
            val same = target != null && target.isNotEmpty() && Text.fold(items[i].contact.trim()) == target
            Scored(i, sim, same, sim + if (same) 0.5 else 0.0)
        }
        val ranked = scored.filter { it.sim > 0.0 || it.same }
            .sortedWith(compareByDescending<Scored> { it.score }.thenByDescending { it.same }.thenByDescending { it.index })
        return ranked.take(k).map { items[it.index] }
    }

    private class Scored(val index: Int, val sim: Double, val same: Boolean, val score: Double)

    private fun vector(words: List<String>): Map<String, Double> {
        if (words.isEmpty()) return emptyMap()
        val tf = HashMap<String, Int>()
        for (w in words) tf[w] = (tf[w] ?: 0) + 1
        val v = HashMap<String, Double>()
        for ((w, c) in tf) {
            val weight = idf[w] ?: continue
            v[w] = (1.0 + ln(c.toDouble())) * weight
        }
        val norm = sqrt(v.values.sumOf { it * it })
        if (norm == 0.0) return emptyMap()
        return v.mapValues { it.value / norm }
    }

    private fun cosine(a: Map<String, Double>, b: Map<String, Double>): Double {
        if (a.isEmpty() || b.isEmpty()) return 0.0
        val (small, big) = if (a.size <= b.size) a to b else b to a
        var s = 0.0
        for ((w, x) in small) s += x * (big[w] ?: 0.0)
        return s
    }
}
