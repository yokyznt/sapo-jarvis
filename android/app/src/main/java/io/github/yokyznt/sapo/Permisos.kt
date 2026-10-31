package io.github.yokyznt.sapo

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat

object Permisos {
    fun lector(ctx: Context) = NotificationManagerCompat.getEnabledListenerPackages(ctx).contains(ctx.packageName)

    fun avisos(ctx: Context) = Build.VERSION.SDK_INT < 33 ||
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    fun bateria(ctx: Context) =
        ctx.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(ctx.packageName)

    fun accesibilidad(ctx: Context): Boolean {
        val activos = Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
            ?: return false
        val yo = ComponentName(ctx, SapoAccesibilidad::class.java)
        return activos.split(':').any { ComponentName.unflattenFromString(it) == yo }
    }

    fun abrirAccesibilidad(ctx: Context) = abrir(ctx, Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))

    private fun abrir(ctx: Context, vararg intents: Intent) {
        for (i in intents) {
            val ok = runCatching { ctx.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }.isSuccess
            if (ok) return
        }
    }

    fun abrirLector(ctx: Context) = abrir(ctx, Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))

    fun abrirAvisos(ctx: Context) = abrir(
        ctx,
        Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName),
        detalles(ctx)
    )

    fun pedirBateria(ctx: Context) = abrir(
        ctx,
        Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + ctx.packageName)),
        Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
    )

    fun abrirApp(ctx: Context) = abrir(ctx, detalles(ctx))

    fun abrirWeb(ctx: Context, url: String) = abrir(ctx, Intent(Intent.ACTION_VIEW, Uri.parse(url)))

    private fun detalles(ctx: Context) =
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", ctx.packageName, null))
}
