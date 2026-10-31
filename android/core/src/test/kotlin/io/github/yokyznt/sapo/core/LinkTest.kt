package io.github.yokyznt.sapo.core

import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Test

class LinkTest {
    private fun obj(s: String): JsonObject = Json.parseToJsonElement(s).jsonObject

    private fun str(o: JsonObject, k: String) = o.getValue(k).jsonPrimitive.content

    @Test
    fun constants() {
        assertEquals(8766, Link.PORT)
        assertEquals(8767, Link.DISCOVERY_PORT)
        assertEquals("SAPO?", Link.PROBE)
    }

    @Test
    fun helloAndPair() {
        val h = obj(Link.hello("ab\"c", "Nothing A059"))
        assertEquals("hello", str(h, "type"))
        assertEquals("ab\"c", str(h, "token"))
        assertEquals("Nothing A059", str(h, "device"))
        val p = obj(Link.pair("123456", "Nothing A059"))
        assertEquals("pair", str(p, "type"))
        assertEquals("123456", str(p, "code"))
        assertEquals("Nothing A059", str(p, "device"))
    }

    @Test
    fun styleCarriesProfile() {
        val sp = StyleProfile(4.5, 0.25, listOf("😂", "🔥"), 0.8, null, listOf("wey"), 0.1, 120)
        val o = obj(Link.style(sp, "Estilo \"corto\"\ny casual"))
        assertEquals("style", str(o, "type"))
        assertEquals("Estilo \"corto\"\ny casual", str(o, "describe"))
        val p = o.getValue("profile").jsonObject
        assertEquals(4.5, p.getValue("avgWords").jsonPrimitive.double)
        assertEquals(0.25, p.getValue("emojiRate").jsonPrimitive.double)
        assertEquals(listOf("😂", "🔥"), p.getValue("topEmojis").jsonArray.map { it.jsonPrimitive.content })
        assertEquals(0.8, p.getValue("lowercaseRate").jsonPrimitive.double)
        assertEquals(JsonNull, p.getValue("laugh"))
        assertEquals(listOf("wey"), p.getValue("fillers").jsonArray.map { it.jsonPrimitive.content })
        assertEquals(0.1, p.getValue("endsWithPunct").jsonPrimitive.double)
        assertEquals(120, p.getValue("samples").jsonPrimitive.int)
    }

    @Test
    fun phoneBusyOrNull() {
        val a = obj(Link.phone(BusyReason.JugandoPC, true))
        assertEquals("phone", str(a, "type"))
        assertEquals("JugandoPC", str(a, "busy"))
        assertEquals(true, a.getValue("auto").jsonPrimitive.boolean)
        val b = obj(Link.phone(null, false))
        assertEquals(JsonNull, b.getValue("busy"))
        assertEquals(false, b.getValue("auto").jsonPrimitive.boolean)
    }

    @Test
    fun parsePaired() {
        assertEquals(LinkMsg.Paired("f".repeat(64)), Link.parse("""{"type":"paired","token":"${"f".repeat(64)}"}"""))
        assertIs<LinkMsg.Unknown>(Link.parse("""{"type":"paired"}"""))
    }

    @Test
    fun parsePc() {
        assertEquals(
            LinkMsg.Pc(true, "FortniteClient-Win64-Shipping.exe", false),
            Link.parse("""{"type":"pc","gaming":true,"app":"FortniteClient-Win64-Shipping.exe","away":false}""")
        )
        assertEquals(LinkMsg.Pc(false, null, true), Link.parse("""{"type":"pc","gaming":false,"app":null,"away":true}"""))
        assertEquals(LinkMsg.Pc(false, null, false), Link.parse("""{"type":"pc","gaming":false}"""))
        assertIs<LinkMsg.Unknown>(Link.parse("""{"type":"pc","app":"x.exe"}"""))
    }

    @Test
    fun parseErrorAndOk() {
        assertEquals(LinkMsg.Error("código inválido"), Link.parse("""{"type":"error","why":"código inválido"}"""))
        assertEquals(LinkMsg.Error(""), Link.parse("""{"type":"error"}"""))
        assertEquals(LinkMsg.Ok, Link.parse("""{"type":"ok"}"""))
    }

    @Test
    fun parseUnknownAndBroken() {
        val cases = listOf(
            """{"type":"nuevo","x":1}""",
            """{"sin":"tipo"}""",
            """{"type":"ok"""",
            "no es json",
            "",
            "[1,2]",
            "\"ok\""
        )
        for (c in cases) assertEquals(LinkMsg.Unknown(c), Link.parse(c))
    }

    @Test
    fun outgoingIsCompactSingleLine() {
        val sp = StyleProfile(1.0, 0.0, emptyList(), 0.0, "jaja", emptyList(), 0.0, 1)
        for (m in listOf(Link.hello("t", "d"), Link.pair("1", "d"), Link.style(sp, "a\nb"), Link.phone(null, true))) {
            assertTrue('\n' !in m)
            assertTrue(obj(m).containsKey("type"))
        }
    }
}
