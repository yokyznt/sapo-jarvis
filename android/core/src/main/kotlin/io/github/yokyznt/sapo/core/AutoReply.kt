package io.github.yokyznt.sapo.core

import java.time.LocalDateTime
import kotlin.random.Random

enum class BusyReason { Manual, NoMolestar, PantallaApagada, Horario }

data class BusyState(
    val manual: Boolean,
    val dnd: Boolean,
    val screenOffSince: Long?,
    val schedule: List<IntRange>,
    val idleMinutes: Int
)

object Busy {
    fun reason(s: BusyState, now: LocalDateTime, nowMs: Long): BusyReason? {
        if (s.manual) return BusyReason.Manual
        if (s.dnd) return BusyReason.NoMolestar
        val minute = now.hour * 60 + now.minute
        if (s.schedule.any { minute in it }) return BusyReason.Horario
        val off = s.screenOffSince
        if (off != null && nowMs - off >= s.idleMinutes.coerceAtLeast(0) * 60_000L) return BusyReason.PantallaApagada
        return null
    }
}

data class Sent(val contact: String, val atMs: Long)

data class Limits(val perContactGapMin: Int = 10, val perContactHour: Int = 3, val globalHour: Int = 12)

sealed interface Decision {
    data object Ok : Decision
    data class No(val why: String) : Decision
}

object Policy {
    private const val HOUR = 3_600_000L

    fun allow(
        contact: String,
        whitelisted: Boolean,
        isGroup: Boolean,
        paused: Boolean,
        history: List<Sent>,
        nowMs: Long,
        limits: Limits = Limits()
    ): Decision {
        if (isGroup) return Decision.No("grupo")
        if (!whitelisted) return Decision.No("fuera de lista blanca")
        if (paused) return Decision.No("pausado")
        val recent = history.filter { it.atMs in (nowMs - HOUR + 1)..nowMs }
        val mine = history.filter { it.contact == contact && it.atMs <= nowMs }
        val last = mine.maxOfOrNull { it.atMs }
        if (last != null && nowMs - last < limits.perContactGapMin * 60_000L) return Decision.No("muy pronto para este contacto")
        if (recent.count { it.contact == contact } >= limits.perContactHour) return Decision.No("límite por hora del contacto")
        if (recent.size >= limits.globalHour) return Decision.No("límite global por hora")
        return Decision.Ok
    }
}

object Delay {
    private const val MIN_BASE = 15_000L
    private const val MAX_BASE = 45_000L
    private const val PER_CHAR = 60L
    private const val CAP = 90_000L

    fun ms(text: String, rnd: Random): Long {
        val base = rnd.nextLong(MIN_BASE, MAX_BASE + 1)
        return (base + text.length * PER_CHAR).coerceAtMost(CAP)
    }
}
