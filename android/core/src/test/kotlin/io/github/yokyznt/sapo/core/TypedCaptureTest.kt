package io.github.yokyznt.sapo.core

import kotlin.test.assertEquals
import kotlin.test.assertNull
import org.junit.Test

class TypedCaptureTest {
    private fun ev(text: String, at: Long, chat: String = "Ana") = TypedEvent(chat, text, at)

    @Test
    fun fastClearSendsOnce() {
        val c = TypedCapture()
        assertNull(c.onText(ev("h", 0)))
        assertNull(c.onText(ev("hola", 300)))
        assertEquals("hola", c.onText(ev("", 1_000)))
        assertNull(c.onText(ev("", 1_100)))
        assertNull(c.onSendClick("Ana", 1_200))
    }

    @Test
    fun slowClearDoesNotSend() {
        val c = TypedCapture()
        c.onText(ev("hola", 0))
        assertNull(c.onText(ev("", 1_500)))
        assertNull(c.onSendClick("Ana", 5_000))
    }

    @Test
    fun clickSendsDraftOnce() {
        val c = TypedCapture()
        c.onText(ev("ya voy", 0))
        assertEquals("ya voy", c.onSendClick("Ana", 10_000))
        assertNull(c.onText(ev("", 10_050)))
        assertNull(c.onSendClick("Ana", 10_100))
    }

    @Test
    fun clickRightAfterSlowClearStillSends() {
        val c = TypedCapture()
        c.onText(ev("pensado", 0))
        assertNull(c.onText(ev("", 8_000)))
        assertEquals("pensado", c.onSendClick("Ana", 8_100))
        assertNull(c.onSendClick("Ana", 8_200))
    }

    @Test
    fun deletingCharByCharIsNotASend() {
        val c = TypedCapture()
        c.onText(ev("hola", 0))
        c.onText(ev("hol", 100))
        c.onText(ev("ho", 200))
        c.onText(ev("h", 300))
        assertNull(c.onText(ev("", 400)))
        assertNull(c.onSendClick("Ana", 450))
    }

    @Test
    fun ignoresRobotTexts() {
        val c = TypedCapture()
        c.onText(ev("🤖 luego te escribo", 0))
        assertNull(c.onText(ev("", 200)))
        c.onText(ev("🤖 ok", 1_000))
        assertNull(c.onSendClick("Ana", 1_100))
    }

    @Test
    fun chatsAreIndependent() {
        val c = TypedCapture()
        c.onText(ev("para ana", 0, "Ana"))
        c.onText(ev("para luis", 100, "Luis"))
        assertEquals("para luis", c.onText(ev("", 200, "Luis")))
        assertEquals("para ana", c.onSendClick("Ana", 300))
    }

    @Test
    fun respectsMinChars() {
        val c = TypedCapture(minChars = 3)
        c.onText(ev("si", 0))
        assertNull(c.onText(ev("", 100)))
        c.onText(ev("sale", 1_000))
        assertEquals("sale", c.onText(ev("", 1_100)))
    }
}
