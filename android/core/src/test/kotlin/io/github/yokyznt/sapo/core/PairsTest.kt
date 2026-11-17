package io.github.yokyznt.sapo.core

import java.time.LocalDateTime
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import org.junit.Test

class PairsTest {
    private fun t(h: Int, m: Int) = LocalDateTime.of(2026, 10, 25, h, m)

    @Test
    fun groupsConsecutiveMessages() {
        val chat = WhatsAppExport.parse("Ana", Fixtures.androidAna)
        val pairs = Pairs.build(chat)
        assertEquals(
            Pair("hola\noye ¿vas a ir a la fiesta del sábado?", "jajaja no sé todavía\nsi me da tiempo sí voy", "Ana"),
            pairs[0]
        )
        assertEquals(Pair("va, me avisas 😊", "sale 👍", "Ana"), pairs[1])
        assertEquals(Pair("¿ya comiste?", "apenas jaja", "Ana"), pairs[2])
        assertEquals(3, pairs.size)
    }

    @Test
    fun cutsBySilenceOverNinetyMinutes() {
        val chat = Chat(
            "Ana", "Yo",
            listOf(
                ChatLine(t(10, 0), "Ana", "¿vienes?"),
                ChatLine(t(11, 31), "Yo", "perdón, apenas vi"),
                ChatLine(t(12, 0), "Ana", "ok"),
                ChatLine(t(13, 30), "Yo", "listo")
            )
        )
        val pairs = Pairs.build(chat)
        assertEquals(listOf(Pair("ok", "listo", "Ana")), pairs)
        assertEquals(2, Pairs.build(chat, gapMinutes = 120).size)
    }

    @Test
    fun silenceSplitsSameAuthorBlocks() {
        val chat = Chat(
            "Ana", "Yo",
            listOf(
                ChatLine(t(8, 0), "Ana", "buenos días"),
                ChatLine(t(10, 0), "Ana", "¿me pasas la tarea?"),
                ChatLine(t(10, 5), "Yo", "va")
            )
        )
        assertEquals(listOf(Pair("¿me pasas la tarea?", "va", "Ana")), Pairs.build(chat))
    }

    @Test
    fun emptyWhenMeUnknown() {
        assertTrue(Pairs.build(WhatsAppExport.parse("Familia", Fixtures.group)).isEmpty())
    }
}
