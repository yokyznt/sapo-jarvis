package io.github.yokyznt.sapo

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.widget.Toast

class AccionReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        Store.init(ctx)
        when (intent.action) {
            Modo.PARAR -> {
                Modo.pausar(ctx, true)
                return
            }
            Modo.REANUDAR -> {
                Modo.pausar(ctx, false)
                return
            }
        }
        val contacto = intent.getStringExtra(Avisos.EXTRA_CONTACTO) ?: return
        when (intent.action) {
            Avisos.ENVIAR -> {
                val texto = intent.getStringExtra(Avisos.EXTRA_TEXTO).orEmpty()
                if (texto.isBlank()) return
                val app = Respuestas.de(contacto)?.app ?: "com.whatsapp"
                if (Respuestas.enviar(ctx, contacto, texto)) {
                    Store.agregar(contacto, app, Mensaje("Yo", texto, System.currentTimeMillis(), true))
                    Store.anotar("Le mandé tu respuesta a $contacto ✅")
                    Avisos.quitar(ctx, contacto)
                } else {
                    Store.anotar("No pude responderle a $contacto desde aquí")
                    Toast.makeText(ctx, "Ya no puedo contestar desde la notificación; ábrelo en WhatsApp", Toast.LENGTH_LONG).show()
                }
            }
            Avisos.DESCARTAR -> {
                Avisos.quitar(ctx, contacto)
                Store.anotar("Descartaste la sugerencia para $contacto")
            }
        }
    }
}
