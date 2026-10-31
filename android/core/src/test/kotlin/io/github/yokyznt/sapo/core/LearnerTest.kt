package io.github.yokyznt.sapo.core

import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue
import org.junit.Test

class LearnerTest {
    private val t0 = 1_800_000_000_000L
    private val minute = 60_000L

    private fun at(ms: Long): LocalDateTime = LocalDateTime.ofInstant(Instant.ofEpochMilli(ms), ZoneId.systemDefault())

    private fun incoming(text: String, ms: Long) = ChatLine(at(ms), "Ana", text)

    @Test
    fun filtersJunk() {
        val l = Learner()
        l.addMine("Ana", "   ", t0, null)
        l.addMine("Ana", "https://example.com/x", t0, null)
        l.addMine("Ana", "www.example.com", t0, null)
        l.addMine("Ana", "482913", t0, null)
        l.addMine("Ana", "tu código es 123 456", t0, null)
        l.addMine("Ana", "🤖 luego te escribo", t0, null)
        l.addMine("Ana", "va que va", t0, null)
        l.addMine("Ana", "va que va", t0 + 1, null)
        l.addMine("Ana", "😂😂", t0 + 2, null)
        l.addMine("Ana", "mira esto https://example.com", t0 + 3, null)
        l.addMine("Ana", "va que va", t0 + 4, null)
        assertEquals(listOf("va que va", "😂😂", "mira esto https://example.com", "va que va"), l.mine())
    }

    @Test
    fun pairsOnlyWithinTwoHours() {
        val l = Learner()
        l.addMine("Ana", "sí voy", t0, incoming("vienes?", t0 - 30 * minute))
        l.addMine("Ana", "ya llegué", t0, incoming("dónde andas", t0 - 121 * minute))
        l.addMine("Ana", "sin tiempo", t0, ChatLine(null, "Ana", "hola"))
        l.addMine("Ana", "nada", t0, null)
        assertEquals(listOf(Pair("vienes?", "sí voy", "Ana")), l.pairs())
        assertEquals(4, l.mine().size)
    }

    @Test
    fun junkDoesNotCreatePairs() {
        val l = Learner()
        l.addMine("Ana", "https://x.com/y", t0, incoming("pásame el link", t0 - minute))
        assertTrue(l.pairs().isEmpty())
        assertTrue(l.mine().isEmpty())
    }

    @Test
    fun capsMine() {
        val l = Learner(maxMine = 3)
        for (i in 1..5) l.addMine("Ana", "mensaje $i", t0 + i, incoming("q $i", t0))
        assertEquals(listOf("mensaje 3", "mensaje 4", "mensaje 5"), l.mine())
        assertEquals(3, l.pairs().size)
    }

    @Test
    fun profileWithoutBaseIsLearned() {
        val l = Learner()
        listOf("jajaja sale", "ok wey", "ya voy wey").forEachIndexed { i, s -> l.addMine("Ana", s, t0 + i, null) }
        assertEquals(Style.profile(l.mine()), l.profile(null))
    }

    @Test
    fun profileWithEmptyLearnedIsBase() {
        val base = StyleProfile(10.0, 0.5, listOf("😂"), 0.2, "jaja", listOf("bueno"), 0.8, 40)
        assertEquals(base, Learner().profile(base))
    }

    @Test
    fun profileMixesWeighted() {
        val l = Learner()
        repeat(10) { l.addMine("Ana", "va ${"x".repeat(it + 1)}", t0 + it, null) }
        val learned = Style.profile(l.mine())
        val base = StyleProfile(10.0, 1.0, listOf("😂", "🔥"), 0.0, "jaja", listOf("bueno"), 1.0, 30)
        val p = l.profile(base)
        assertEquals(40, p.samples)
        assertEquals((10.0 * 30 + learned.avgWords * 10) / 40, p.avgWords, 1e-9)
        assertEquals((1.0 * 30 + learned.emojiRate * 10) / 40, p.emojiRate, 1e-9)
        assertEquals((0.0 * 30 + learned.lowercaseRate * 10) / 40, p.lowercaseRate, 1e-9)
        assertEquals((1.0 * 30 + learned.endsWithPunct * 10) / 40, p.endsWithPunct, 1e-9)
        assertEquals(listOf("😂", "🔥"), p.topEmojis)
        assertEquals("jaja", p.laugh)
        assertTrue("bueno" in p.fillers)
    }

    @Test
    fun jsonRoundTrip() {
        val l = Learner(maxMine = 50)
        l.addMine("Ana", "sí voy \"ya\"", t0, incoming("vienes?\nrápido", t0 - minute))
        l.addMine("Luis", "😂😂", t0 + 1, null)
        l.addMine("Luis", "luego", t0 + 2, incoming("y eso?", t0 - 10 * minute))
        val back = Learner.fromJson(l.toJson())
        assertEquals(l.mine(), back.mine())
        assertEquals(l.pairs(), back.pairs())
        assertEquals(l.toJson(), back.toJson())
    }

    @Test
    fun brokenJsonGivesEmptyLearner() {
        val l = Learner.fromJson("{no es json")
        assertTrue(l.mine().isEmpty())
        assertTrue(l.pairs().isEmpty())
        assertTrue(Learner.fromJson("[]").mine().isEmpty())
    }

    @Test
    fun learnedDuplicateNotPairedTwice() {
        val l = Learner()
        l.addMine("Ana", "sale", t0, incoming("vamos?", t0 - minute))
        l.addMine("Ana", "sale", t0 + 1, incoming("vamos?", t0 - minute))
        assertEquals(1, l.pairs().size)
        assertNull(l.pairs().firstOrNull { it.me != "sale" })
    }
}
