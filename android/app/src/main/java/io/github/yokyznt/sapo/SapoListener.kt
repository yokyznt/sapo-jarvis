package io.github.yokyznt.sapo

import android.app.Notification
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import androidx.core.app.NotificationCompat
import io.github.yokyznt.sapo.core.Guard

class SapoListener : NotificationListenerService() {

    override fun onListenerConnected() {
        Store.init(this)
        Store.anotar("Escuchando WhatsApp 👂")
        runCatching { activeNotifications }.getOrNull()?.forEach { runCatching { procesar(it, false) } }
    }

    override fun onListenerDisconnected() {
        Store.anotar("Me desconectaron del lector de notificaciones")
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        runCatching { procesar(sbn, true) }
    }

    private fun procesar(sbn: StatusBarNotification, sugerir: Boolean) {
        val app = sbn.packageName
        if (app !in APPS) return
        val n = sbn.notification ?: return
        if (n.flags and Notification.FLAG_GROUP_SUMMARY != 0) return
        if (n.category == Notification.CATEGORY_CALL) return
        Store.init(this)
        val ex = n.extras ?: return
        val titulo = ex.getCharSequence(Notification.EXTRA_TITLE)?.toString()
        if (titulo == null || titulo in NOMBRES_APP) return
        val estilo = runCatching {
            NotificationCompat.MessagingStyle.extractMessagingStyleFromNotification(n)
        }.getOrNull()
        val conv = ex.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)?.toString()
            ?: estilo?.conversationTitle?.toString()
        val grupo = ex.getBoolean(Notification.EXTRA_IS_GROUP_CONVERSATION, false) || estilo?.isGroupConversation == true
        if (Guard.isGroup(titulo, conv, grupo)) return
        val contacto = limpiar(titulo) ?: return
        val accion = buscarRespuesta(n)
        if (accion != null) Respuestas.poner(contacto, Respuesta(accion.actionIntent, accion.remoteInputs, app))
        val base = Store.ultimaHora(contacto)
        val previos = Store.conversaciones[contacto]?.mensajes.orEmpty()
        val nuevos = mensajes(estilo, ex, sbn.postTime, contacto)
            .filter { it.hora > base }
            .filter { m -> previos.none { it.mio == m.mio && it.texto == m.texto && kotlin.math.abs(it.hora - m.hora) < 120_000 } }
        if (nuevos.isEmpty()) return
        nuevos.forEach { Store.agregar(contacto, app, it) }
        val ultimo = nuevos.last()
        if (ultimo.mio) return
        if (sugerir && Store.activo(contacto)) Sugeridor.sugerir(this, contacto, ultimo.texto)
        else if (sugerir) Store.anotar("Mensaje de $contacto (no está en tu lista)")
    }

    private fun mensajes(
        estilo: NotificationCompat.MessagingStyle?,
        ex: Bundle,
        hora: Long,
        contacto: String
    ): List<Mensaje> {
        val yo = estilo?.user?.name?.toString()
        val lista = estilo?.messages.orEmpty().mapNotNull { m ->
            val t = m.text?.toString()?.trim().orEmpty()
            if (t.isEmpty() || basura(t)) return@mapNotNull null
            val autor = m.person?.name?.toString()
            val mio = m.person == null || (yo != null && autor == yo)
            Mensaje(if (mio) "Yo" else contacto, t, m.timestamp, mio)
        }
        if (lista.isNotEmpty()) return lista.sortedBy { it.hora }
        val t = (ex.getCharSequence(Notification.EXTRA_BIG_TEXT) ?: ex.getCharSequence(Notification.EXTRA_TEXT))
            ?.toString()?.trim().orEmpty()
        if (t.isEmpty() || basura(t)) return emptyList()
        return listOf(Mensaje(contacto, t, hora, false))
    }

    private fun buscarRespuesta(n: Notification): Notification.Action? {
        val acciones = n.actions.orEmpty().filter { it.remoteInputs?.isNotEmpty() == true }
        val porNombre = acciones.firstOrNull { a ->
            val t = a.title?.toString()?.lowercase().orEmpty()
            t.contains("respond") || t.contains("reply") || t.contains("contestar")
        }
        return porNombre ?: acciones.firstOrNull()
            ?: Notification.WearableExtender(n).actions.firstOrNull { it.remoteInputs?.isNotEmpty() == true }
    }

    private fun limpiar(titulo: String): String? =
        titulo.replace(Regex("\\s*\\(\\d+\\s+\\S+\\)$"), "").trim().ifEmpty { null }

    private fun basura(t: String): Boolean {
        val l = t.lowercase()
        return l.startsWith("buscando mensajes nuevos") || l.startsWith("checking for new messages") ||
            Regex("^\\d+ (mensajes nuevos|new messages)").containsMatchIn(l)
    }

    companion object {
        val APPS = setOf("com.whatsapp", "com.whatsapp.w4b")
        val NOMBRES_APP = setOf("WhatsApp", "WhatsApp Business")
    }
}
