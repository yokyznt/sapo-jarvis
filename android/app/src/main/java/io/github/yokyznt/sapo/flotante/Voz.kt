package io.github.yokyznt.sapo.flotante

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import java.util.Locale

class Voz(ctx: Context) {
    private var tts: TextToSpeech? = null
    private var lista = false
    private var pendiente: String? = null

    init {
        tts = TextToSpeech(ctx.applicationContext) { estado ->
            val t = tts
            if (estado == TextToSpeech.SUCCESS && t != null) {
                val r = t.setLanguage(Locale.forLanguageTag("es-MX"))
                if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) t.setLanguage(Locale.forLanguageTag("es"))
                lista = true
                pendiente?.let { decir(it) }
            }
            pendiente = null
        }
    }

    fun decir(texto: String) {
        val limpio = limpiar(texto)
        if (limpio.isBlank()) return
        if (!lista) {
            pendiente = limpio
            return
        }
        tts?.speak(limpio, TextToSpeech.QUEUE_FLUSH, null, "sapo")
    }

    fun callar() {
        pendiente = null
        tts?.stop()
    }

    fun cerrar() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        lista = false
    }

    private val simbolos = Regex("[\\p{So}\\p{Sk}\\p{Cs}\\x{FE0F}\\x{200D}\\x{1F000}-\\x{1FFFF}«»*_#]")

    private fun limpiar(t: String) = t.replace(simbolos, "").replace(Regex("\\s+"), " ").trim()
}

class Oreja(
    private val ctx: Context,
    private val listo: () -> Unit,
    private val parcial: (String) -> Unit,
    private val final: (String) -> Unit,
    private val fallo: (String) -> Unit
) {
    private var sr: SpeechRecognizer? = null
    private var sinRed = true
    var escuchando = false
        private set

    fun escuchar(offline: Boolean = true) {
        if (!SpeechRecognizer.isRecognitionAvailable(ctx)) {
            fallo("Tu cel no tiene reconocimiento de voz 😕 Instala o activa la app de Google")
            return
        }
        sr?.destroy()
        val r = runCatching { SpeechRecognizer.createSpeechRecognizer(ctx) }.getOrNull()
        if (r == null) {
            fallo("No pude abrir el oído 😕")
            return
        }
        sr = r
        r.setRecognitionListener(oyente)
        val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "es-MX")
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "es-MX")
            .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, offline)
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            .putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, ctx.packageName)
        sinRed = offline
        escuchando = true
        runCatching { r.startListening(i) }.onFailure {
            escuchando = false
            fallo("No pude escucharte 😕")
        }
    }

    fun parar() {
        escuchando = false
        runCatching { sr?.cancel() }
    }

    fun cerrar() {
        escuchando = false
        runCatching { sr?.destroy() }
        sr = null
    }

    private val oyente = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) = listo()
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {}
        override fun onEvent(eventType: Int, params: Bundle?) {}

        override fun onPartialResults(partialResults: Bundle?) {
            primero(partialResults)?.let(parcial)
        }

        override fun onResults(results: Bundle?) {
            escuchando = false
            val t = primero(results)
            if (t.isNullOrBlank()) fallo("No te oí bien, tócame y repite 🐸") else final(t)
        }

        override fun onError(error: Int) {
            if (!escuchando) return
            escuchando = false
            if (sinRed && error in setOf(4, 11, 12, 13)) {
                escuchar(false)
                return
            }
            fallo(mensaje(error))
        }
    }

    private fun primero(b: Bundle?): String? =
        b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.trim()?.ifBlank { null }

    private fun mensaje(e: Int) = when (e) {
        SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Sin internet no te entiendo 📶"
        SpeechRecognizer.ERROR_AUDIO -> "No pude usar el micrófono 🎙️"
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT, SpeechRecognizer.ERROR_NO_MATCH -> "No te oí bien, tócame y repite 🐸"
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Estoy ocupado oyendo, espérame tantito"
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Me falta el permiso del micrófono 🎙️"
        SpeechRecognizer.ERROR_CLIENT -> "Se me trabó el oído, tócame otra vez"
        12, 13 -> "Tu cel no entiende español de México todavía 😕"
        else -> "No te entendí (error $e)"
    }
}
