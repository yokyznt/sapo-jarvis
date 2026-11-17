package io.github.yokyznt.sapo

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat

object Avisos {
    const val CANAL = "sugerencias"
    const val ENVIAR = "io.github.yokyznt.sapo.ENVIAR"
    const val DESCARTAR = "io.github.yokyznt.sapo.DESCARTAR"
    const val EXTRA_CONTACTO = "contacto"
    const val EXTRA_TEXTO = "texto"

    fun crearCanal(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        val canal = NotificationChannel(CANAL, "Sugerencias del Sapo", NotificationManager.IMPORTANCE_HIGH)
        canal.description = "Respuestas sugeridas para tus contactos de WhatsApp"
        nm.createNotificationChannel(canal)
    }

    private fun id(contacto: String) = contacto.hashCode() and 0x3fffffff

    private fun accion(ctx: Context, accion: String, contacto: String, texto: String, codigo: Int): PendingIntent =
        PendingIntent.getBroadcast(
            ctx,
            codigo,
            Intent(ctx, AccionReceiver::class.java)
                .setAction(accion)
                .putExtra(EXTRA_CONTACTO, contacto)
                .putExtra(EXTRA_TEXTO, texto),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

    fun sugerencia(ctx: Context, contacto: String, entrante: String, texto: String) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        val base = id(contacto)
        val abrir = PendingIntent.getActivity(
            ctx, 0, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE
        )
        val puedeEnviar = Respuestas.de(contacto) != null
        val b = NotificationCompat.Builder(ctx, CANAL)
            .setSmallIcon(R.drawable.ic_stat_sapo)
            .setColor(0xFF7ED957.toInt())
            .setContentTitle("🐸 Para $contacto")
            .setContentText(texto)
            .setStyle(NotificationCompat.BigTextStyle().bigText("$contacto: $entrante\n\nYo diría: $texto"))
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(abrir)
        if (puedeEnviar) b.addAction(0, "Enviar", accion(ctx, ENVIAR, contacto, texto, base * 2))
        b.addAction(0, "Descartar", accion(ctx, DESCARTAR, contacto, texto, base * 2 + 1))
        runCatching { NotificationManagerCompat.from(ctx).notify(base, b.build()) }
    }

    fun quitar(ctx: Context, contacto: String) {
        NotificationManagerCompat.from(ctx).cancel(id(contacto))
    }
}
