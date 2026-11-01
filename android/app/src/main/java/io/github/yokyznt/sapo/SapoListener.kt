package io.github.yokyznt.sapo

import android.app.Notification
import android.content.Context
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import androidx.core.app.NotificationCompat
import io.github.yokyznt.sapo.core.Guard

class SapoListener : NotificationListenerService() {

    override fun onListenerConnected() {
        Store.init(this)
        Store.anotar("Escuchando WhatsApp 👂")
        Modo.escucharPantalla(this)
        Modo.refrescar(this)
        Enlace.arrancar(this)
        runCatching { activeNotifications }.getOrNull()?.forEach { runCatching { procesar(it, false) } }
    }

    override fun onListenerDisconnected() {
        Modo.dejarPantalla(this)
        Autorespuesta.cancelarTodo("se desconectó el lector")
        Store.anotar("Me desconectaron del lector de notificaciones")
    }

    override fun onDestroy() {
        Modo.dejarPantalla(this)
        super.onDestroy()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        runCatching { procesar(sbn, true) }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        runCatching {
            if (sbn.packageName !in APPS) return
            val n = sbn.notification ?: return
            if (n.flags and Notification.FLAG_GROUP_SUMMARY != 0) return
            val ex = n.extras ?: return
            val titulo = ex.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: return
            if (titulo in NOMBRES_APP) return
            val conv = ex.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)?.toString()
            val grupo = Guard.isGroup(titulo, conv, ex.getBoolean(Notification.EXTRA_IS_GROUP_CONVERSATION, false))
            val contacto = (if (grupo) Guard.groupName(titulo, conv) else limpiar(titulo)) ?: return
            if (Autorespuesta.pendiente(contacto)) Autorespuesta.cancelar(contacto, "abriste o quitaste el chat")
        }
    }

    private fun procesar(sbn: StatusBarNotification, sugerir: Boolean) {
        analizar(this, sbn.packageName, sbn.notification ?: return, sbn.postTime, sugerir)
    }

    companion object {
        val APPS = setOf("com.whatsapp", "com.whatsapp.w4b")
        val NOMBRES_APP = setOf("WhatsApp", "WhatsApp Business")

        fun analizar(ctx: Context, app: String, n: Notification, postTime: Long, sugerir: Boolean) {
            if (app !in APPS) return
            if (n.flags and Notification.FLAG_GROUP_SUMMARY != 0) return
            if (n.category == Notification.CATEGORY_CALL) return
            Store.init(ctx)
            val ex = n.extras ?: return
            val titulo = ex.getCharSequence(Notification.EXTRA_TITLE)?.toString()
            if (titulo == null || titulo in NOMBRES_APP) return
            val estilo = runCatching {
                NotificationCompat.MessagingStyle.extractMessagingStyleFromNotification(n)
            }.getOrNull()
            val conv = ex.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)?.toString()
                ?: estilo?.conversationTitle?.toString()
            val grupo = Guard.isGroup(titulo, conv, ex.getBoolean(Notification.EXTRA_IS_GROUP_CONVERSATION, false) || estilo?.isGroupConversation == true)
            val contacto = (if (grupo) Guard.groupName(titulo, conv) else limpiar(titulo)) ?: return
            val accion = buscarRespuesta(n)
            if (accion != null) Respuestas.poner(contacto, Respuesta(accion.actionIntent, accion.remoteInputs, app))
            val base = Store.ultimaHora(contacto)
            val previos = Store.conversaciones[contacto]?.mensajes.orEmpty()
            val nuevos = mensajes(estilo, ex, postTime, contacto, if (grupo) Guard.sender(titulo, conv) else null, grupo)
                .filter { it.hora > base }
                .filter { m -> previos.none { it.mio == m.mio && it.texto == m.texto && kotlin.math.abs(it.hora - m.hora) < 120_000 } }
            if (nuevos.isEmpty()) return
            nuevos.forEach { Store.agregar(contacto, app, it, grupo) }
            if (nuevos.any { it.mio }) Autorespuesta.cancelar(contacto, "contestaste tú")
            val ultimo = nuevos.last()
            if (ultimo.mio) return
            if (sugerir && Store.activo(contacto)) {
                val mencion = grupo && Guard.mentions(ultimo.texto, misNombres(estilo))
                if (!Autorespuesta.intentar(ctx, contacto, ultimo.texto, grupo, mencion)) Sugeridor.sugerir(ctx, contacto, ultimo.texto)
            } else if (sugerir) Store.anotar(if (grupo) "Mensaje en el grupo $contacto (apagado)" else "Mensaje de $contacto (no está en tu lista)")
        }

        private fun mensajes(
            estilo: NotificationCompat.MessagingStyle?,
            ex: Bundle,
            hora: Long,
            contacto: String,
            remitente: String?,
            grupo: Boolean
        ): List<Mensaje> {
            val yo = estilo?.user?.name?.toString()
            val lista = estilo?.messages.orEmpty().mapNotNull { m ->
                val t = m.text?.toString()?.trim().orEmpty()
                if (t.isEmpty() || basura(t)) return@mapNotNull null
                val autor = m.person?.name?.toString()
                val mio = m.person == null || (yo != null && autor == yo)
                Mensaje(if (mio) "Yo" else if (grupo) autor ?: remitente ?: contacto else contacto, t, m.timestamp, mio)
            }
            if (lista.isNotEmpty()) return lista.sortedBy { it.hora }
            val t = (ex.getCharSequence(Notification.EXTRA_BIG_TEXT) ?: ex.getCharSequence(Notification.EXTRA_TEXT))
                ?.toString()?.trim().orEmpty()
            if (t.isEmpty() || basura(t)) return emptyList()
            if (grupo && remitente == null && t.contains(": ")) return listOf(Mensaje(t.substringBefore(": ").trim(), t.substringAfter(": ").trim(), hora, false))
            return listOf(Mensaje(if (grupo) remitente ?: contacto else contacto, t, hora, false))
        }

        private fun misNombres(estilo: NotificationCompat.MessagingStyle?): List<String> = listOfNotNull(
            Store.importado.yo?.ifBlank { null },
            estilo?.user?.name?.toString()?.takeIf { it.isNotBlank() && it.lowercase() !in setOf("tú", "tu", "you", "yo") }
        )

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
    }
}