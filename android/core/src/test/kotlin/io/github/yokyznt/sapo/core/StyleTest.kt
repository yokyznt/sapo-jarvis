package io.github.yokyznt.sapo.core

import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue
import org.junit.Test

class StyleTest {
    @Test
    fun detectsJaja() {
        val p = Style.profile(listOf("jajaja no manches", "jajaja sí", "va", "jaja ok"))
        assertEquals("jajaja", p.laugh)
        assertEquals(4, p.samples)
        assertEquals(1.0, p.lowercaseRate)
    }

    @Test
    fun detectsJsjsAndXd() {
        assertEquals("jsjs", Style.profile(listOf("jsjs qué risa", "jsjs", "nel")).laugh)
        assertEquals("xd", Style.profile(listOf("XD", "xd ya", "Bueno.")).laugh)
        assertNull(Style.profile(listOf("Hola.", "Gracias.")).laugh)
    }

    @Test
    fun countsEmojisAndPunctuation() {
        val p = Style.profile(listOf("sale 👍", "jaja 😂😂", "Ok.", "ya voy 😂"))
        assertEquals(0.75, p.emojiRate)
        assertEquals("😂", p.topEmojis.first())
        assertTrue("👍" in p.topEmojis)
        assertEquals(0.25, p.endsWithPunct)
        assertEquals(0.75, p.lowercaseRate)
    }

    @Test
    fun detectsFillers() {
        val p = Style.profile(listOf("neta wey", "sale wey", "neta no", "ok"))
        assertTrue("wey" in p.fillers)
        assertTrue("neta" in p.fillers)
    }

    @Test
    fun describeMentionsTraits() {
        val d = Style.describe(Style.profile(listOf("jajaja sale 😂", "va wey 😂", "sale wey")))
        assertTrue(d.contains("jajaja"))
        assertTrue(d.contains("😂"))
        assertTrue(d.contains("minúscula"))
        assertTrue(Style.describe(Style.profile(emptyList())).isNotBlank())
    }
}
