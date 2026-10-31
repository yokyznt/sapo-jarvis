package io.github.yokyznt.sapo

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.PowerManager
import android.service.quicksettings.TileService
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import io.github.yokyznt.sapo.core.Busy
import io.github.yokyznt.sapo.core.BusyReason
import io.github.yokyznt.sapo.core.BusyState
import io.github.yokyznt.sapo.core.Limits
import io.github.yokyznt.sapo.core.Sent
import java.time.LocalDateTime

object Modo {
    const val CANAL = "modo_auto"
    const val PARAR = "io.github.yokyznt.sapo.PARAR"
    const val REANUDAR = "io.github.yokyznt.sapo.REANUDAR"
    private const val ID = 0x50A9

    @Volatile var apagadaDesde: Long? = null
        private set

    private val pantalla = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            when (intent.action) {
                Intent.ACTION_SCREEN_OFF -> apagadaDesde = System.currentTimeMillis()
                Intent.ACTION_SCREEN_ON -> apagadaDesde = null
            }
        }
    }
    private var escuchando = false

    fun crearCanal(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        val canal = NotificationChannel(CANAL, "Modo automático", NotificationManager.IMPORTANCE_LOW)
        canal.description = "Aviso fijo mientras el Sapo contesta por ti"
        canal.setShowBadge(false)
        nm.createNotificationChannel(canal)
    }

    @Synchronized
    fun escucharPantalla(ctx: Context) {
        if (escuchando) return
        val filtro = IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_OFF)
            addAction(Intent.ACTION_SCREEN_ON)
        }
        runCatching {
            ContextCompat.registerReceiver(ctx.applicationContext, pantalla, filtro, ContextCompat.RECEIVER_NOT_EXPORTED)
            escuchando = true
        }
        val encendida = ctx.getSystemService(PowerManager::class.java)?.isInteractive ?: true
        apagadaDesde = if (encendida) null else apagadaDesde ?: System.currentTimeMillis()
    }

    @Synchronized
    fun dejarPantalla(ctx: Context) {
        if (!escuchando) return
        runCatching { ctx.applicationContext.unregisterReceiver(pantalla) }
        escuchando = false
    }

    private fun noMolestar(ctx: Context): Boolean {
        val f = ctx.getSystemService(NotificationManager::class.java)?.currentInterruptionFilter
            ?: return false
        return f != NotificationManager.INTERRUPTION_FILTER_ALL && f != NotificationManager.INTERRUPTION_FILTER_UNKNOWN
    }

    fun razon(ctx: Context): BusyReason? {
        val a = Store.ajustes.auto
        if (!a.activo) return null
        val estado = BusyState(
            manual = a.manual,
            dnd = a.dnd && noMolestar(ctx),
            screenOffSince = if (a.pantalla && escuchando) apagadaDesde else null,
            schedule = a.rangos(),
            idleMinutes = a.minutosPantalla,
            pcGaming = a.pcJuego && Enlace.jugando
        )
        return Busy.reason(estado, LocalDateTime.now(), System.currentTimeMillis())
    }

    fun limites(): Limits = Store.ajustes.auto.let { Limits(it.separacion, it.porContacto, it.global) }

    fun enviados(): List<Sent> = Store.historial.map { Sent(it.contacto, it.hora) }

    fun nombre(r: BusyReason): String = when (r) {
        BusyReason.Manual -> "Modo ocupado manual"
        BusyReason.NoMolestar -> "No molestar"
        BusyReason.PantallaApagada -> "Pantalla apagada"
        BusyReason.Horario -> "Horario ocupado"
        BusyReason.JugandoPC -> "Jugando en la PC"
    }

    fun cambiar(ctx: Context, cambio: (Auto) -> Auto) {
        Store.init(ctx)
        val antes = Store.ajustes.auto
        Store.ponerAuto(cambio)
        val ahora = Store.ajustes.auto
        if (antes.corriendo && !ahora.corriendo) Autorespuesta.cancelarTodo("pausaste al sapo")
        refrescar(ctx)
    }

    fun pausar(ctx: Context, pausa: Boolean) {
        cambiar(ctx) { it.copy(pausado = pausa) }
        Store.anotar(if (pausa) "Sapo en pausa ⏸ no contesto solo" else "Sapo de vuelta: contesto por ti cuando estés ocupado 🤖")
    }

    fun refrescar(ctx: Context) {
        val app = ctx.applicationContext
        val a = Store.ajustes.auto
        if (a.activo) aviso(app, a.pausado) else NotificationManagerCompat.from(app).cancel(ID)
        runCatching { TileService.requestListeningState(app, ComponentName(app, SapoTile::class.java)) }
    }

    private fun aviso(ctx: Context, pausado: Boolean) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        val abrir = PendingIntent.getActivity(ctx, 1, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val accion = PendingIntent.getBroadcast(
            ctx,
            2,
            Intent(ctx, AccionReceiver::class.java).setAction(if (pausado) REANUDAR else PARAR),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val b = NotificationCompat.Builder(ctx, CANAL)
            .setSmallIcon(R.drawable.ic_stat_sapo)
            .setColor(0xFF7ED957.toInt())
            .setContentTitle(if (pausado) "Sapo en pausa ⏸" else "El sapo contesta por ti 🤖")
            .setContentText(if (pausado) "No contesto solo hasta que me reactives" else "Solo a tu lista blanca y cuando estés ocupado")
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setContentIntent(abrir)
            .addAction(0, if (pausado) "Reactivar" else "Parar al sapo", accion)
        runCatching { NotificationManagerCompat.from(ctx).notify(ID, b.build()) }
    }
}
