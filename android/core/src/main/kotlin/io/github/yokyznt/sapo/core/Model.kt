package io.github.yokyznt.sapo.core

import java.time.LocalDateTime

data class ChatLine(val time: LocalDateTime?, val author: String, val text: String)

data class Chat(val name: String, val me: String, val lines: List<ChatLine>)

data class Pair(val them: String, val me: String, val contact: String)

data class StyleProfile(
    val avgWords: Double,
    val emojiRate: Double,
    val topEmojis: List<String>,
    val lowercaseRate: Double,
    val laugh: String?,
    val fillers: List<String>,
    val endsWithPunct: Double,
    val samples: Int
)
