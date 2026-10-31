package io.github.yokyznt.sapo.core

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.put

sealed interface LinkMsg {
    data class Paired(val token: String) : LinkMsg
    data class Pc(val gaming: Boolean, val app: String?, val away: Boolean) : LinkMsg
    data class Error(val why: String) : LinkMsg
    data object Ok : LinkMsg
    data class Unknown(val raw: String) : LinkMsg
}

object Link {
    const val PORT = 8766
    const val DISCOVERY_PORT = 8767
    const val PROBE = "SAPO?"

    fun hello(token: String, device: String): String = buildJsonObject {
        put("type", "hello")
        put("token", token)
        put("device", device)
    }.toString()

    fun pair(code: String, device: String): String = buildJsonObject {
        put("type", "pair")
        put("code", code)
        put("device", device)
    }.toString()

    fun style(p: StyleProfile, describe: String): String = buildJsonObject {
        put("type", "style")
        put("profile", buildJsonObject {
            put("avgWords", finite(p.avgWords))
            put("emojiRate", finite(p.emojiRate))
            put("topEmojis", buildJsonArray { p.topEmojis.forEach { add(JsonPrimitive(it)) } })
            put("lowercaseRate", finite(p.lowercaseRate))
            put("laugh", p.laugh)
            put("fillers", buildJsonArray { p.fillers.forEach { add(JsonPrimitive(it)) } })
            put("endsWithPunct", finite(p.endsWithPunct))
            put("samples", p.samples)
        })
        put("describe", describe)
    }.toString()

    fun phone(busy: BusyReason?, autoOn: Boolean): String = buildJsonObject {
        put("type", "phone")
        put("busy", busy?.name)
        put("auto", autoOn)
    }.toString()

    fun parse(json: String): LinkMsg {
        val o = try {
            Json.parseToJsonElement(json) as? JsonObject
        } catch (e: Exception) {
            null
        } ?: return LinkMsg.Unknown(json)
        return when (text(o, "type")) {
            "paired" -> text(o, "token")?.takeIf { it.isNotBlank() }?.let { LinkMsg.Paired(it) }
            "pc" -> flag(o, "gaming")?.let { LinkMsg.Pc(it, text(o, "app")?.takeIf { a -> a.isNotBlank() }, flag(o, "away") ?: false) }
            "error" -> LinkMsg.Error(text(o, "why") ?: "")
            "ok" -> LinkMsg.Ok
            else -> null
        } ?: LinkMsg.Unknown(json)
    }

    private fun finite(d: Double): Double = if (d.isFinite()) d else 0.0

    private fun text(o: JsonObject, key: String): String? {
        val e = o[key] as? JsonPrimitive ?: return null
        if (e is JsonNull || !e.isString) return null
        return e.contentOrNull
    }

    private fun flag(o: JsonObject, key: String): Boolean? {
        val e = o[key] as? JsonPrimitive ?: return null
        if (e is JsonNull || e.isString) return null
        return e.booleanOrNull
    }
}
