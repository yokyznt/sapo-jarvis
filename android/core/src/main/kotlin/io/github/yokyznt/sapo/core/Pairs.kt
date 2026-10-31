package io.github.yokyznt.sapo.core

import java.time.Duration
import java.time.LocalDateTime

object Pairs {
    private class Block(val mine: Boolean, val start: LocalDateTime?, var end: LocalDateTime?, val texts: MutableList<String>)

    fun build(chat: Chat, gapMinutes: Long = 90): List<Pair> {
        if (chat.me.isBlank()) return emptyList()
        val blocks = ArrayList<Block>()
        for (line in chat.lines) {
            val mine = line.author == chat.me
            val last = blocks.lastOrNull()
            if (last != null && last.mine == mine && !gap(last.end, line.time, gapMinutes)) {
                last.texts.add(line.text)
                if (line.time != null) last.end = line.time
            } else {
                blocks.add(Block(mine, line.time, line.time, mutableListOf(line.text)))
            }
        }
        val out = ArrayList<Pair>()
        for (i in 0 until blocks.size - 1) {
            val a = blocks[i]
            val b = blocks[i + 1]
            if (a.mine || !b.mine) continue
            if (gap(a.end, b.start, gapMinutes)) continue
            out.add(Pair(a.texts.joinToString("\n"), b.texts.joinToString("\n"), chat.name))
        }
        return out
    }

    private fun gap(a: LocalDateTime?, b: LocalDateTime?, gapMinutes: Long): Boolean {
        if (a == null || b == null) return false
        return Duration.between(a, b).toMinutes() > gapMinutes
    }
}
