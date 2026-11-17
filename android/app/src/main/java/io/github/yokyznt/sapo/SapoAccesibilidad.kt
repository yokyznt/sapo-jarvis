package io.github.yokyznt.sapo

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import io.github.yokyznt.sapo.core.ChatLine
import io.github.yokyznt.sapo.core.TypedCapture
import io.github.yokyznt.sapo.core.TypedEvent
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId

class SapoAccesibilidad : AccessibilityService() {
    private val captura = TypedCapture()
    private val usados = HashMap<String, Long>()
    private var chat = ""

    override fun onServiceConnected() {
        Store.init(this)
        Store.anotar("Aprendiendo cómo escribes ✍️")
    }

    override fun onInterrupt() {}

    override fun onAccessibilityEvent(e: AccessibilityEvent?) {
        if (e == null) return
        runCatching { procesar(e) }
    }

    private fun procesar(e: AccessibilityEvent) {
        val app = e.packageName?.toString() ?: return
        if (app !in SapoListener.APPS) return
        Store.init(this)
        if (!Store.ajustes.aprender) return
        val nodo = e.source ?: return
        val id = nodo.viewIdResourceName ?: return
        val ahora = System.currentTimeMillis()
        val enviado = when (e.eventType) {
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED -> {
                if (!id.endsWith(":id/entry")) return
                val c = chatActual(app)
                captura.onText(TypedEvent(c, texto(e, nodo), ahora))?.let { c to it }
            }
            AccessibilityEvent.TYPE_VIEW_CLICKED -> {
                if (!id.endsWith(":id/send")) return
                val c = chatActual(app)
                captura.onSendClick(c, ahora)?.let { c to it }
            }
            else -> null
        } ?: return
        aprender(enviado.first, enviado.second, ahora)
    }

    private fun texto(e: AccessibilityEvent, nodo: AccessibilityNodeInfo): String {
        if (nodo.isShowingHintText) return ""
        val t = e.text.orEmpty().joinToString("") { it?.toString().orEmpty() }
        return t.ifEmpty { nodo.text?.toString().orEmpty() }
    }

    private fun chatActual(app: String): String {
        val raiz = rootInActiveWindow ?: return chat
        val nombre = runCatching {
            raiz.findAccessibilityNodeInfosByViewId("$app:id/conversation_contact_name")
                ?.firstOrNull()?.text?.toString()?.trim()
        }.getOrNull()
        if (!nombre.isNullOrEmpty()) chat = nombre
        return chat
    }

    private fun aprender(contacto: String, texto: String, hora: Long) {
        val entrante = Store.conversaciones[contacto]?.mensajes?.lastOrNull { !it.mio }
        val linea = entrante?.takeIf { usados[contacto] != it.hora }?.let {
            usados[contacto] = it.hora
            ChatLine(LocalDateTime.ofInstant(Instant.ofEpochMilli(it.hora), ZoneId.systemDefault()), contacto, it.texto)
        }
        if (contacto.isNotEmpty() && Autorespuesta.pendiente(contacto)) Autorespuesta.cancelar(contacto, "contestaste tú")
        SapoApp.scope.launch { runCatching { Store.aprender(contacto, texto, hora, linea) } }
    }
}
