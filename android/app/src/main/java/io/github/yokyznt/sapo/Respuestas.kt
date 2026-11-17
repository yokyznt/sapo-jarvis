package io.github.yokyznt.sapo

import android.app.PendingIntent
import android.app.RemoteInput
import android.content.Context
import android.content.Intent
import android.os.Bundle
import java.util.concurrent.ConcurrentHashMap

class Respuesta(val intent: PendingIntent, val entradas: Array<RemoteInput>, val app: String)

object Respuestas {
    private val mapa = ConcurrentHashMap<String, Respuesta>()

    fun poner(contacto: String, r: Respuesta) {
        mapa[contacto] = r
    }

    fun de(contacto: String): Respuesta? = mapa[contacto]

    fun enviar(ctx: Context, contacto: String, texto: String): Boolean {
        val r = mapa[contacto] ?: return false
        val intent = Intent().addFlags(Intent.FLAG_RECEIVER_FOREGROUND)
        val datos = Bundle()
        r.entradas.forEach { datos.putCharSequence(it.resultKey, texto) }
        RemoteInput.addResultsToIntent(r.entradas, intent, datos)
        return runCatching {
            r.intent.send(ctx, 0, intent)
            true
        }.getOrElse {
            mapa.remove(contacto)
            false
        }
    }
}
