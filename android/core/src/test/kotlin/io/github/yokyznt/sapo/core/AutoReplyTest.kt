package io.github.yokyznt.sapo.core

import java.time.LocalDateTime
import kotlin.random.Random
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue
import org.junit.Test

class AutoReplyTest {
    private val noon = LocalDateTime.of(2026, 10, 31, 12, 0)
    private val nowMs = 10_000_000_000L
    private val idle = BusyState(manual = false, dnd = false, screenOffSince = null, schedule = emptyList(), idleMinutes = 5)
    private val night = listOf(22 * 60..1439, 0..7 * 60 - 1)

    @Test
    fun busyPriorityManualFirst() {
        val s = idle.copy(manual = true, dnd = true, schedule = listOf(0..1439), screenOffSince = 0L)
        assertEquals(BusyReason.Manual, Busy.reason(s, noon, nowMs))
    }

    @Test
    fun busyPriorityDndBeforeScheduleAndScreen() {
        val s = idle.copy(dnd = true, schedule = listOf(0..1439), screenOffSince = 0L)
        assertEquals(BusyReason.NoMolestar, Busy.reason(s, noon, nowMs))
    }

    @Test
    fun busyPriorityScheduleBeforeScreen() {
        val s = idle.copy(schedule = listOf(0..1439), screenOffSince = 0L)
        assertEquals(BusyReason.Horario, Busy.reason(s, noon, nowMs))
    }

    @Test
    fun busyNullWhenNothingApplies() {
        assertNull(Busy.reason(idle, noon, nowMs))
        assertNull(Busy.reason(idle.copy(schedule = night), noon, nowMs))
    }

    @Test
    fun scheduleCrossingMidnight() {
        val s = idle.copy(schedule = night)
        assertEquals(BusyReason.Horario, Busy.reason(s, noon.withHour(23).withMinute(30), nowMs))
        assertEquals(BusyReason.Horario, Busy.reason(s, noon.withHour(0).withMinute(0), nowMs))
        assertEquals(BusyReason.Horario, Busy.reason(s, noon.withHour(6).withMinute(59), nowMs))
        assertNull(Busy.reason(s, noon.withHour(7).withMinute(0), nowMs))
        assertNull(Busy.reason(s, noon.withHour(21).withMinute(59), nowMs))
    }

    @Test
    fun screenOffRespectsThreshold() {
        val five = 5 * 60_000L
        assertNull(Busy.reason(idle.copy(screenOffSince = nowMs - five + 1), noon, nowMs))
        assertEquals(BusyReason.PantallaApagada, Busy.reason(idle.copy(screenOffSince = nowMs - five), noon, nowMs))
        assertEquals(BusyReason.PantallaApagada, Busy.reason(idle.copy(screenOffSince = nowMs - 3 * five), noon, nowMs))
    }

    private fun allow(
        contact: String = "Ana",
        whitelisted: Boolean = true,
        isGroup: Boolean = false,
        paused: Boolean = false,
        history: List<Sent> = emptyList(),
        limits: Limits = Limits()
    ) = Policy.allow(contact, whitelisted, isGroup, paused, history, nowMs, limits)

    private fun no(d: Decision): String = assertIs<Decision.No>(d).why

    private fun minAgo(m: Int) = nowMs - m * 60_000L

    @Test
    fun policyOkWhenAllGood() {
        assertEquals(Decision.Ok, allow())
        val history = listOf(Sent("Ana", minAgo(30)), Sent("Luis", minAgo(1)), Sent("Ana", minAgo(120)))
        assertEquals(Decision.Ok, allow(history = history))
    }

    @Test
    fun policyDeniesGroup() {
        assertEquals("grupo", no(allow(isGroup = true)))
    }

    @Test
    fun policyDeniesNotWhitelisted() {
        assertEquals("fuera de lista blanca", no(allow(whitelisted = false)))
    }

    @Test
    fun policyDeniesPaused() {
        assertEquals("pausado", no(allow(paused = true)))
    }

    @Test
    fun policyDeniesPerContactGap() {
        assertEquals("muy pronto para este contacto", no(allow(history = listOf(Sent("Ana", minAgo(9))))))
        assertEquals(Decision.Ok, allow(history = listOf(Sent("Ana", minAgo(10)))))
    }

    @Test
    fun policyDeniesPerContactHour() {
        val history = listOf(Sent("Ana", minAgo(50)), Sent("Ana", minAgo(35)), Sent("Ana", minAgo(20)))
        assertEquals("límite por hora del contacto", no(allow(history = history)))
        val older = listOf(Sent("Ana", minAgo(61)), Sent("Ana", minAgo(35)), Sent("Ana", minAgo(20)))
        assertEquals(Decision.Ok, allow(history = older))
    }

    @Test
    fun policyDeniesGlobalHour() {
        val history = (1..12).map { Sent("c$it", minAgo(it * 4)) }
        assertEquals("límite global por hora", no(allow(history = history)))
        assertEquals(Decision.Ok, allow(history = history.drop(1)))
    }

    @Test
    fun policyRespectsCustomLimits() {
        val limits = Limits(perContactGapMin = 0, perContactHour = 1, globalHour = 2)
        assertEquals("límite por hora del contacto", no(allow(history = listOf(Sent("Ana", minAgo(1))), limits = limits)))
        assertEquals("límite global por hora", no(allow(history = listOf(Sent("x", minAgo(1)), Sent("y", minAgo(2))), limits = limits)))
    }

    @Test
    fun delayWithinBounds() {
        val rnd = Random(7)
        repeat(500) {
            val text = "a".repeat(rnd.nextInt(0, 3000))
            val d = Delay.ms(text, rnd)
            assertTrue(d in 15_000L..90_000L, "fuera de rango: $d")
        }
        assertEquals(90_000L, Delay.ms("x".repeat(5000), Random(1)))
    }

    @Test
    fun delayGrowsWithLength() {
        val short = Delay.ms("hola", Random(42))
        val long = Delay.ms("hola ".repeat(80), Random(42))
        assertTrue(long > short)
        assertEquals((400 - 4) * 60L, long - short)
    }
}
