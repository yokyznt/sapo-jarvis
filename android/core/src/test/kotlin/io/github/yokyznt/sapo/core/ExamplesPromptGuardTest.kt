package io.github.yokyznt.sapo.core

import java.time.LocalDateTime
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import org.junit.Test

class ExamplesPromptGuardTest {
    private val pairs = listOf(
        Pair("¿vamos al cine el viernes?", "va, ¿a qué hora?", "Luis"),
        Pair("¿quieres ir al cine?", "sí, me late", "Ana"),
        Pair("¿ya comiste?", "apenas jaja", "Ana"),
        Pair("pásame la tarea de cálculo", "ahorita te la mando", "Luis"),
        Pair("feliz cumpleaños!!", "graciaas 🥳", "Mamá")
    )

    @Test
    fun nearestFindsSimilarIgnoringAccents() {
        val r = Examples(pairs).nearest("oye y la TAREA de calculo?", null, 2)
        assertEquals("pásame la tarea de cálculo", r.first().them)
    }

    @Test
    fun nearestPrioritizesSameContact() {
        val r = Examples(pairs).nearest("¿vamos al cine?", "Ana", 3)
        assertEquals("Ana", r.first().contact)
        assertTrue(r.any { it.contact == "Luis" })
        assertEquals(3, Examples(pairs).nearest("cine", "Ana", 3).size)
        assertTrue(Examples(emptyList()).nearest("hola", "Ana").isEmpty())
    }

    @Test
    fun promptContainsRulesAndExamples() {
        val history = listOf(
            ChatLine(LocalDateTime.of(2026, 10, 25, 14, 3), "Ana", "hola"),
            ChatLine(LocalDateTime.of(2026, 10, 25, 14, 4), "Yoki", "qué onda")
        )
        val style = Style.profile(listOf("jajaja va", "sale 😂"))
        val p = Prompt.reply("¿vamos al cine?", "Ana", history, style, pairs.take(2), auto = true)
        assertTrue(p.contains("Eres Yoki respondiendo por WhatsApp"))
        assertTrue(p.contains("No inventes planes, horarios"))
        assertTrue(p.contains("compromisos"))
        assertTrue(p.contains("luego le respondes"))
        assertTrue(p.contains("datos personales"))
        assertTrue(p.contains("1 o 2 frases"))
        assertTrue(p.contains("¿quieres ir al cine?"))
        assertTrue(p.contains("sí, me late"))
        assertTrue(p.contains("Ana: hola"))
        assertTrue(p.contains("jajaja"))
        assertTrue(p.contains("automáticamente"))
        assertFalse(Prompt.reply("x", "Ana", history, style, emptyList(), auto = false).contains("automáticamente"))
    }

    @Test
    fun isGroupDetection() {
        assertTrue(Guard.isGroup("Ana", "Familia", true))
        assertTrue(Guard.isGroup("Ana", "Familia", false))
        assertTrue(Guard.isGroup("Familia: Ana", null, false))
        assertTrue(Guard.isGroup("Familia (3 mensajes): Ana", null, false))
        assertFalse(Guard.isGroup("Ana", null, false))
        assertFalse(Guard.isGroup("Ana", "Ana", false))
        assertFalse(Guard.isGroup(null, null, false))
    }

    @Test
    fun cleanRemovesPrefixesAndQuotes() {
        assertEquals("va, ahorita te digo", Guard.clean("Yo: \"va, ahorita te digo\""))
        assertEquals("sale", Guard.clean("  “sale”  "))
        assertEquals("ok", Guard.clean("Respuesta: Yo: 'ok'"))
    }

    @Test
    fun cleanRejectsEmptyAndAi() {
        assertNull(Guard.clean("   "))
        assertNull(Guard.clean("\"\""))
        assertNull(Guard.clean("Como IA no puedo ir al cine"))
        assertNull(Guard.clean("Lo siento, soy un modelo de lenguaje"))
        assertNull(Guard.clean("como una inteligencia artificial..."))
    }

    @Test
    fun cleanTrimsLength() {
        val long = "ahorita no puedo hablar. " + "bla ".repeat(100)
        val r = Guard.clean(long, 40)!!
        assertTrue(r.length <= 40)
        assertEquals("ahorita no puedo hablar.", r)
        val words = Guard.clean("palabra ".repeat(50), 40)!!
        assertTrue(words.length <= 40)
        assertTrue(words.endsWith("…"))
    }

    @Test
    fun markPrependsRobot() {
        assertEquals("🤖 hola", Guard.mark("hola"))
        assertEquals("🤖 hola", Guard.mark("🤖 hola"))
    }
}
