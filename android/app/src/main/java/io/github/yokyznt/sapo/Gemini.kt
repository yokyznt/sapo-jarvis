package io.github.yokyznt.sapo

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.addJsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

object Gemini {
    const val PREDETERMINADO = "gemini-3.5-flash-lite"
    private val RESPALDO = listOf("gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-flash-latest", "gemma-4-26b-a4b-it")
    @Volatile private var bueno: String? = null

    suspend fun generar(key: String, modelo: String, prompt: String, json: Boolean = false): String {
        val orden = (listOfNotNull(bueno?.takeIf { it != modelo && retirado(modelo) }, modelo) + RESPALDO).distinct()
        var ultimo: IOException? = null
        for (m in orden) {
            for (pensar in 0..2) {
                try {
                    val r = llamar(key, m, prompt, pensar, json)
                    bueno = m
                    return r
                } catch (e: IOException) {
                    ultimo = e
                    val t = e.message.orEmpty()
                    if (t.startsWith("Gemini 400") && pensar < 2) continue
                    if (t.startsWith("Gemini 404") || t.startsWith("Gemini 400") || t.startsWith("Gemini 429") || t.startsWith("Gemini 5")) {
                        if (t.startsWith("Gemini 404")) retirados.add(m)
                        break
                    }
                    throw e
                }
            }
        }
        throw ultimo ?: IOException("Gemini sin modelos")
    }

    private val retirados = java.util.Collections.newSetFromMap(java.util.concurrent.ConcurrentHashMap<String, Boolean>())

    private fun retirado(m: String) = m in retirados || m.startsWith("gemini-2.") || m.startsWith("gemini-1.")

    private suspend fun llamar(key: String, modelo: String, prompt: String, pensar: Int, json: Boolean): String = withContext(Dispatchers.IO) {
        val url = URL("https://generativelanguage.googleapis.com/v1beta/models/$modelo:generateContent")
        val c = url.openConnection() as HttpURLConnection
        try {
            c.requestMethod = "POST"
            c.connectTimeout = 15000
            c.readTimeout = 40000
            c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            c.setRequestProperty("x-goog-api-key", key)
            val cuerpo = buildJsonObject {
                putJsonArray("contents") {
                    addJsonObject {
                        put("role", "user")
                        putJsonArray("parts") { addJsonObject { put("text", prompt) } }
                    }
                }
                putJsonObject("generationConfig") {
                    put("temperature", 0.9)
                    put("maxOutputTokens", if (json) 400 else 256)
                    if (json) put("responseMimeType", "application/json")
                    when (pensar) {
                        0 -> putJsonObject("thinkingConfig") { put("thinkingLevel", "minimal") }
                        1 -> putJsonObject("thinkingConfig") { put("thinkingBudget", 0) }
                    }
                }
            }
            c.outputStream.use { it.write(cuerpo.toString().toByteArray(Charsets.UTF_8)) }
            val codigo = c.responseCode
            val texto = (if (codigo in 200..299) c.inputStream else c.errorStream)
                ?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            if (codigo !in 200..299) throw IOException("Gemini $codigo: ${motivo(texto)}")
            val raiz = Json.parseToJsonElement(texto).jsonObject
            raiz["candidates"]?.jsonArray?.firstOrNull()?.jsonObject
                ?.get("content")?.jsonObject
                ?.get("parts")?.jsonArray
                ?.mapNotNull { it.jsonObject["text"]?.jsonPrimitive?.contentOrNull }
                ?.joinToString("")
                ?.trim()
                .orEmpty()
        } finally {
            c.disconnect()
        }
    }

    private fun motivo(texto: String): String = runCatching {
        Json.parseToJsonElement(texto).jsonObject["error"]?.jsonObject?.get("message")?.jsonPrimitive?.contentOrNull
    }.getOrNull() ?: texto.take(200)
}
