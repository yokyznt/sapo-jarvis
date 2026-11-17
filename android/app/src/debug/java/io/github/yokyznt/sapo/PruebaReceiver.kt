package io.github.yokyznt.sapo

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.Person
import io.github.yokyznt.sapo.core.Intents
import io.github.yokyznt.sapo.flotante.Ejecutor
import kotlinx.coroutines.launch
import java.time.LocalDateTime

class PruebaReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, i: Intent) {
        val app = ctx.applicationContext
        Store.init(app)
        SapoApp.scope.launch {
            runCatching {
                i.getStringExtra("llave")?.let { Llave.guardar(app, it); Log.i("SapoPrueba", "llave guardada") }
                i.getStringExtra("diag")?.let {
                    val svc = SapoAccesibilidad.activo
                    val info = svc?.serviceInfo
                    Log.i("SapoPrueba", "DIAG svc=$svc flags=${info?.flags} caps=${info?.capabilities} pkgs=${info?.packageNames?.toList()} ventanas=${runCatching { svc?.windows?.size }.getOrNull()} raiz=${svc?.rootInActiveWindow?.packageName} control=${Control.app()} nodos=${Control.nodos().map { it.texto + "|" + it.caja.top }}")
                    Log.i("SapoPrueba", "VENTANAS " + svc?.windows?.joinToString { "t=${it.type} act=${it.isActive} foc=${it.isFocused} capa=${it.layer} pkg=${it.root?.packageName} hijos=${it.root?.childCount}" })
                    val g = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Main) { svc?.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS) }
                    Log.i("SapoPrueba", "DIAG global main=$g")
                }
                i.getStringExtra("activar")?.let { Store.activar(it, true); Log.i("SapoPrueba", "activado $it") }
                i.getStringExtra("orden")?.let { o ->
                    val c = Intents.parse(o, LocalDateTime.now())
                    val r = Ejecutor(app).hacer(c)
                    Log.i("SapoPrueba", "ORDEN «$o» -> $c -> $r")
                }
                i.getStringExtra("grupo")?.let { g ->
                    val quien = i.getStringExtra("de") ?: "Luis"
                    val texto = i.getStringExtra("texto") ?: "hola"
                    val yo = Person.Builder().setName("Tú").build()
                    val estilo = NotificationCompat.MessagingStyle(yo)
                        .setConversationTitle(g)
                        .setGroupConversation(true)
                        .addMessage(texto, System.currentTimeMillis(), Person.Builder().setName(quien).build())
                    val n = NotificationCompat.Builder(app, "prueba")
                        .setSmallIcon(R.drawable.ic_stat_sapo)
                        .setContentTitle(g)
                        .setContentText("$quien: $texto")
                        .setStyle(estilo)
                        .build()
                    SapoListener.analizar(app, "com.whatsapp", n, System.currentTimeMillis(), true)
                    kotlinx.coroutines.delay(1500)
                    Log.i("SapoPrueba", "GRUPO $g -> ${Store.conversaciones[g]} | evento: ${Store.evento}")
                }
            }.onFailure { Log.e("SapoPrueba", "falló", it) }
        }
    }
}
