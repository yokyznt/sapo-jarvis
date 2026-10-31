package io.github.yokyznt.sapo

import android.content.Context
import io.github.yokyznt.sapo.core.Decision
import io.github.yokyznt.sapo.core.Delay
import io.github.yokyznt.sapo.core.Guard
import io.github.yokyznt.sapo.core.Policy
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.concurrent.ConcurrentHashMap
import kotlin.random.Random

object Autorespuesta {
    private val pendientes = ConcurrentHashMap<String, Job>()

    fun intentar(ctx: Context, contacto: String, entrante: String, grupo: Boolean): Boolean {
        val app = ctx.applicationContext
        val a = Store.ajustes.auto
        if (!a.activo) return false
        val razon = Modo.razon(app) ?: return false
        val decision = Policy.allow(
            contacto, Store.activo(contacto), grupo, a.pausado, Modo.enviados(), System.currentTimeMillis(), Modo.limites()
        )
        if (decision is Decision.No) {
            Store.anotar("No contesto solo a $contacto: ${decision.why}")
            return false
        }
        if (Respuestas.de(contacto) == null) return false
        val key = Llave.leer(app) ?: return false
        pendientes.remove(contacto)?.cancel()
        val motivo = Modo.nombre(razon)
        Store.anotar("Estás ocupado ($motivo); preparo respuesta para $contacto 🤖")
        val job = SapoApp.scope.launch(start = CoroutineStart.LAZY) {
            var limpio: String? = null
            try {
                limpio = Guard.clean(Gemini.generar(key, Store.ajustes.modelo, Sugeridor.prompt(contacto, entrante, auto = true)))
                if (limpio == null) {
                    Store.anotar("No se me ocurrió nada prudente para $contacto; mejor tú")
                    return@launch
                }
                delay(Delay.ms(limpio, Random.Default))
                enviar(app, contacto, entrante, limpio)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Store.anotar("No pude contestar solo a $contacto: ${e.message}")
                limpio?.let { Avisos.sugerencia(app, contacto, entrante, it) }
            }
        }
        pendientes[contacto] = job
        job.invokeOnCompletion { pendientes.remove(contacto, job) }
        job.start()
        return true
    }

    private fun enviar(ctx: Context, contacto: String, entrante: String, texto: String) {
        val a = Store.ajustes.auto
        val razon = Modo.razon(ctx)
        val decision = Policy.allow(
            contacto, Store.activo(contacto), false, a.pausado || !a.activo, Modo.enviados(), System.currentTimeMillis(), Modo.limites()
        )
        if (razon == null || decision is Decision.No) {
            Store.anotar("Ya no contesto solo a $contacto; te dejo la sugerencia")
            Avisos.sugerencia(ctx, contacto, entrante, texto)
            return
        }
        val marcado = Guard.mark(texto)
        pendientes.remove(contacto)
        if (!Respuestas.enviar(ctx, contacto, marcado)) {
            Store.anotar("No pude mandar la respuesta automática a $contacto")
            Avisos.sugerencia(ctx, contacto, entrante, texto)
            return
        }
        val ahora = System.currentTimeMillis()
        val app = Respuestas.de(contacto)?.app ?: "com.whatsapp"
        Store.agregar(contacto, app, Mensaje("Yo", marcado, ahora, true))
        Store.registrar(Respondido(contacto, entrante, marcado, ahora, Modo.nombre(razon)))
        Store.anotar("Le contesté solo a $contacto 🤖")
    }

    fun cancelar(contacto: String, porque: String) {
        val job = pendientes.remove(contacto) ?: return
        job.cancel()
        Store.anotar("Cancelé la respuesta automática a $contacto: $porque")
    }

    fun cancelarTodo(porque: String) {
        pendientes.keys.toList().forEach { cancelar(it, porque) }
    }

    fun pendiente(contacto: String) = pendientes.containsKey(contacto)
}
