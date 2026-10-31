package io.github.yokyznt.sapo.core

data class TypedEvent(val chat: String, val text: String, val atMs: Long)

class TypedCapture(val minChars: Int = 1) {
    private class Draft(val text: String, val atMs: Long, val shrinking: Boolean)

    private class Cleared(val text: String, val atMs: Long)

    private val drafts = HashMap<String, Draft>()
    private val cleared = HashMap<String, Cleared>()

    @Synchronized
    fun onText(e: TypedEvent): String? {
        val text = e.text.trim()
        val prev = drafts[e.chat]
        if (text.isNotEmpty()) {
            val shrinking = prev != null && text.length < prev.text.length && prev.text.startsWith(text)
            drafts[e.chat] = Draft(text, e.atMs, shrinking)
            cleared.remove(e.chat)
            return null
        }
        drafts.remove(e.chat)
        if (prev == null || prev.shrinking) {
            cleared.remove(e.chat)
            return null
        }
        if (e.atMs - prev.atMs in 0 until WINDOW_MS) {
            cleared.remove(e.chat)
            return accept(prev.text)
        }
        cleared[e.chat] = Cleared(prev.text, e.atMs)
        return null
    }

    @Synchronized
    fun onSendClick(chat: String, atMs: Long): String? {
        val draft = drafts.remove(chat)
        val gone = cleared.remove(chat)
        if (draft != null) return accept(draft.text)
        if (gone != null && atMs - gone.atMs in 0 until WINDOW_MS) return accept(gone.text)
        return null
    }

    private fun accept(text: String): String? {
        if (text.startsWith(ROBOT)) return null
        if (text.length < minChars.coerceAtLeast(1)) return null
        return text
    }

    private companion object {
        const val WINDOW_MS = 1_500L
        const val ROBOT = "🤖"
    }
}
