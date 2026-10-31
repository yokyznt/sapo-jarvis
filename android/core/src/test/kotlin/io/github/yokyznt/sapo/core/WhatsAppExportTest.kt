package io.github.yokyznt.sapo.core

import java.time.LocalDateTime
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue
import org.junit.Test

class WhatsAppExportTest {
    @Test
    fun parsesAndroidFormatWithFilters() {
        val chat = WhatsAppExport.parse("Ana", Fixtures.androidAna)
        assertEquals("Yoki", chat.me)
        val texts = chat.lines.map { it.text }
        assertEquals(
            listOf(
                "hola",
                "oye ¿vas a ir a la fiesta del sábado?",
                "jajaja no sé todavía\nsi me da tiempo sí voy",
                "va, me avisas 😊",
                "sale 👍",
                "¿ya comiste?",
                "apenas jaja",
                "neta que no he dormido nada 😴"
            ),
            texts
        )
        assertEquals(LocalDateTime.of(2026, 10, 25, 14, 3), chat.lines[0].time)
        assertEquals(LocalDateTime.of(2026, 10, 26, 9, 20), chat.lines.last().time)
        assertTrue(chat.lines.none { it.text.contains("cifrados") })
    }

    @Test
    fun parsesBracketFormatWithAmPm() {
        val chat = WhatsAppExport.parse("Luis", Fixtures.bracketLuis)
        assertEquals("Yoki", chat.me)
        assertEquals(5, chat.lines.size)
        assertEquals(LocalDateTime.of(2026, 10, 24, 10, 2, 10), chat.lines[0].time)
        assertEquals(LocalDateTime.of(2026, 10, 24, 10, 3, 45), chat.lines[1].time)
        assertEquals(LocalDateTime.of(2026, 10, 24, 14, 3, 15), chat.lines[2].time)
        assertEquals("¿mañana jugamos fut?", chat.lines[2].text)
        assertEquals(LocalDateTime.of(2026, 10, 24, 0, 10, 0), chat.lines[4].time)
        assertEquals("Luis", chat.lines[0].author)
    }

    @Test
    fun parsesNarrowSpacesAndInvisibleMarks() {
        val raw = "\u200e[3/1/26, 9:05:00\u202fp.\u00a0m.] Ana: buenas\n[3/1/26, 9:06:00\u202fp.\u00a0m.] Yo: hola"
        val chat = WhatsAppExport.parse("Ana", raw, me = "Yo")
        assertEquals(2, chat.lines.size)
        assertEquals(LocalDateTime.of(2026, 1, 3, 21, 5), chat.lines[0].time)
        assertEquals("Yo", chat.me)
    }

    @Test
    fun parsesEnglishTwentyFourHourAndFourDigitYear() {
        val raw = "25/10/2026, 23:15 - Ana: Hi\n25/10/2026, 23:16 - Me: <Media omitted>\n25/10/2026, 23:17 - Me: hey"
        val chat = WhatsAppExport.parse("Ana", raw)
        assertEquals(listOf("Hi", "hey"), chat.lines.map { it.text })
        assertEquals(LocalDateTime.of(2026, 10, 25, 23, 15), chat.lines[0].time)
    }

    @Test
    fun groupDropsSystemAndAttachments() {
        val chat = WhatsAppExport.parse("Familia", Fixtures.group)
        assertEquals(listOf("Mamá", "Papá", "Yoki"), chat.lines.map { it.author })
        assertEquals("", chat.me)
    }

    @Test
    fun guessMeFindsCommonAuthor() {
        val chats = listOf(
            WhatsAppExport.parse("Ana", Fixtures.androidAna),
            WhatsAppExport.parse("Luis", Fixtures.bracketLuis),
            WhatsAppExport.parse("Familia", Fixtures.group)
        )
        assertEquals("Yoki", WhatsAppExport.guessMe(chats))
        assertNull(WhatsAppExport.guessMe(emptyList()))
    }
}
