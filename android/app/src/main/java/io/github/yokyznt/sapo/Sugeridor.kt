package io.github.yokyznt.sapo

import android.content.Context
import io.github.yokyznt.sapo.core.ChatLine
import io.github.yokyznt.sapo.core.Guard
import io.github.yokyznt.sapo.core.Prompt
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId

object Sugeridor {
    fun sugerir(ctx: Context, contacto: String, entrante: String) {
        val app = ctx.applicationContext
        val key = Llave.leer(app)
        if (key == null) {
            Store.anotar("Te escribió $contacto. Sin key de Gemini no te sugiero nada, solo lo apunto")
            return
        }
        Store.anotar("Pensando qué contestarle a $contacto…")
        SapoApp.scope.launch {
            runCatching {
                val yo = Store.importado.yo?.ifBlank { null } ?: "Yo"
                val historia = Store.conversaciones[contacto]?.mensajes.orEmpty().dropLast(1).takeLast(15).map {
                    ChatLine(
                        LocalDateTime.ofInstant(Instant.ofEpochMilli(it.hora), ZoneId.systemDefault()),
                        if (it.mio) yo else contacto,
                        it.texto
                    )
                }
                val ejemplos = Store.ejemplos().nearest(entrante, contacto)
                val prompt = Prompt.reply(entrante, contacto, historia, Store.perfil(), ejemplos, auto = false)
                val bruto = Gemini.generar(key, Store.ajustes.modelo, prompt)
                val limpio = Guard.clean(bruto)
                if (limpio == null) {
                    Store.anotar("No se me ocurrió nada decente para $contacto")
                } else {
                    Avisos.sugerencia(app, contacto, entrante, limpio)
                    Store.anotar("Sugerencia lista para $contacto 🐸")
                }
            }.onFailure { Store.anotar("No pude sugerir: ${it.message}") }
        }
    }
}
