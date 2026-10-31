package io.github.yokyznt.sapo.core

import java.time.ZoneId
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

class Learner(maxMine: Int = 5000) {
    private val max = maxMine.coerceAtLeast(1)
    private val mineList = ArrayList<String>()
    private val pairList = ArrayList<Pair>()

    @Synchronized
    fun addMine(chat: String, text: String, atMs: Long, lastIncoming: ChatLine?) {
        val t = text.trim()
        if (!keep(t)) return
        if (mineList.lastOrNull() == t) return
        mineList.add(t)
        trim(mineList)
        val incoming = lastIncoming ?: return
        val time = incoming.time ?: return
        val them = incoming.text.trim()
        if (them.isEmpty()) return
        val inMs = time.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
        val diff = atMs - inMs
        if (diff < -SKEW_MS || diff >= PAIR_WINDOW_MS) return
        pairList.add(Pair(them, t, chat))
        trim(pairList)
    }

    @Synchronized
    fun mine(): List<String> = ArrayList(mineList)

    @Synchronized
    fun pairs(): List<Pair> = ArrayList(pairList)

    @Synchronized
    fun profile(base: StyleProfile?): StyleProfile {
        val learned = Style.profile(mineList)
        if (base == null || base.samples <= 0) return learned
        if (learned.samples == 0) return base
        val wb = base.samples.toDouble()
        val wl = learned.samples.toDouble()
        val total = wb + wl
        fun mix(a: Double, b: Double) = (a * wb + b * wl) / total
        return StyleProfile(
            avgWords = mix(base.avgWords, learned.avgWords),
            emojiRate = mix(base.emojiRate, learned.emojiRate),
            topEmojis = rank(base.topEmojis, wb, learned.topEmojis, wl, 5),
            lowercaseRate = mix(base.lowercaseRate, learned.lowercaseRate),
            laugh = if (wl > wb) learned.laugh ?: base.laugh else base.laugh ?: learned.laugh,
            fillers = rank(base.fillers, wb, learned.fillers, wl, 6),
            endsWithPunct = mix(base.endsWithPunct, learned.endsWithPunct),
            samples = base.samples + learned.samples
        )
    }

    @Synchronized
    fun toJson(): String = buildJsonObject {
        put("v", 1)
        put("max", max)
        put("mine", buildJsonArray { mineList.forEach { add(JsonPrimitive(it)) } })
        put("pairs", buildJsonArray {
            pairList.forEach {
                add(buildJsonObject {
                    put("them", it.them)
                    put("me", it.me)
                    put("contact", it.contact)
                })
            }
        })
    }.toString()

    private fun <T> trim(list: MutableList<T>) {
        if (list.size > max) list.subList(0, list.size - max).clear()
    }

    private fun rank(a: List<String>, wa: Double, b: List<String>, wb: Double, n: Int): List<String> {
        val score = LinkedHashMap<String, Double>()
        a.forEachIndexed { i, x -> score[x] = (score[x] ?: 0.0) + wa / (i + 1) }
        b.forEachIndexed { i, x -> score[x] = (score[x] ?: 0.0) + wb / (i + 1) }
        return score.entries.sortedByDescending { it.value }.take(n).map { it.key }
    }

    companion object {
        private const val PAIR_WINDOW_MS = 2 * 3_600_000L
        private const val SKEW_MS = 60_000L
        private val loneLink = Regex("^(https?://|www\\.)\\S+$", RegexOption.IGNORE_CASE)
        private val bareCode = Regex("^\\d{4,8}$")
        private val otpWords = Regex("(c[oó]digo|code|otp|verificaci[oó]n|verification|clave)", RegexOption.IGNORE_CASE)
        private val otpDigits = Regex("(?<!\\d)\\d{3}[- ]?\\d{3}(?!\\d)|(?<!\\d)\\d{4,8}(?!\\d)")

        private fun keep(t: String): Boolean {
            if (t.isEmpty()) return false
            if (t.startsWith("🤖")) return false
            if (loneLink.matches(t)) return false
            if (bareCode.matches(t)) return false
            if (otpWords.containsMatchIn(t) && otpDigits.containsMatchIn(t)) return false
            return true
        }

        fun fromJson(s: String): Learner {
            val o = try {
                Json.parseToJsonElement(s).jsonObject
            } catch (e: Exception) {
                return Learner()
            }
            val maxMine = (o["max"] as? JsonPrimitive)?.intOrNull ?: 5000
            val l = Learner(maxMine)
            (o["mine"] as? JsonArray)?.forEach { e ->
                val t = (e as? JsonPrimitive)?.contentOrNull
                if (t != null && t.isNotEmpty()) l.mineList.add(t)
            }
            (o["pairs"] as? JsonArray)?.forEach { e ->
                val p = e as? JsonObject ?: return@forEach
                val them = (p["them"] as? JsonPrimitive)?.contentOrNull ?: return@forEach
                val me = (p["me"] as? JsonPrimitive)?.contentOrNull ?: return@forEach
                val contact = (p["contact"] as? JsonPrimitive)?.contentOrNull ?: ""
                l.pairList.add(Pair(them, me, contact))
            }
            l.trim(l.mineList)
            l.trim(l.pairList)
            return l
        }
    }
}
