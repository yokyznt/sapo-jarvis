package io.github.yokyznt.sapo

import android.content.Context
import io.github.yokyznt.sapo.core.Examples
import io.github.yokyznt.sapo.core.StyleProfile
import io.github.yokyznt.sapo.core.Pair as ParCore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File

@Serializable
data class Mensaje(val autor: String, val texto: String, val hora: Long, val mio: Boolean)

@Serializable
data class Conversacion(
    val contacto: String,
    val app: String,
    val mensajes: List<Mensaje> = emptyList(),
    val ultima: Long = 0
)

@Serializable
data class ParGuardado(val them: String, val me: String, val contact: String)

@Serializable
data class EstiloGuardado(
    val avgWords: Double = 0.0,
    val emojiRate: Double = 0.0,
    val topEmojis: List<String> = emptyList(),
    val lowercaseRate: Double = 0.0,
    val laugh: String? = null,
    val fillers: List<String> = emptyList(),
    val endsWithPunct: Double = 0.0,
    val samples: Int = 0
) {
    fun perfil() = StyleProfile(avgWords, emojiRate, topEmojis, lowercaseRate, laugh, fillers, endsWithPunct, samples)

    companion object {
        fun de(p: StyleProfile) = EstiloGuardado(
            p.avgWords, p.emojiRate, p.topEmojis, p.lowercaseRate, p.laugh, p.fillers, p.endsWithPunct, p.samples
        )
    }
}

@Serializable
data class Importado(
    val yo: String? = null,
    val chats: Int = 0,
    val mensajes: Int = 0,
    val mios: Int = 0,
    val pares: Int = 0,
    val descripcion: String = ""
)

@Serializable
data class Auto(
    val activo: Boolean = false,
    val pausado: Boolean = false,
    val manual: Boolean = false,
    val dnd: Boolean = true,
    val pantalla: Boolean = false,
    val minutosPantalla: Int = 10,
    val horario: Boolean = false,
    val desde: Int = 22 * 60,
    val hasta: Int = 7 * 60,
    val separacion: Int = 10,
    val porContacto: Int = 3,
    val global: Int = 12
) {
    val corriendo get() = activo && !pausado

    fun rangos(): List<IntRange> = when {
        !horario || desde == hasta -> emptyList()
        desde < hasta -> listOf(desde until hasta)
        hasta == 0 -> listOf(desde..1439)
        else -> listOf(desde..1439, 0 until hasta)
    }
}

@Serializable
data class Respondido(
    val contacto: String,
    val entrante: String,
    val respuesta: String,
    val hora: Long,
    val razon: String
)

@Serializable
data class Ajustes(
    val modelo: String = "gemini-2.5-flash",
    val lista: Set<String> = emptySet(),
    val yoManual: String? = null,
    val auto: Auto = Auto()
)

object Store {
    private const val CONV = "conversaciones.json"
    private const val AJUSTES = "ajustes.json"
    private const val IMPORTADO = "importado.json"
    private const val PARES = "pares.json"
    private const val ESTILO = "estilo.json"
    private const val HISTORIAL = "historial.json"
    private const val MAX_HISTORIAL = 300
    private const val MAX_MENSAJES = 40
    private const val MAX_CONV = 80

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    private var dir: File? = null
    private val _cambios = MutableStateFlow(0)
    val cambios: StateFlow<Int> = _cambios

    @Volatile var conversaciones: Map<String, Conversacion> = emptyMap()
        private set
    @Volatile var ajustes = Ajustes()
        private set
    @Volatile var importado = Importado()
        private set
    @Volatile var pares: List<ParGuardado> = emptyList()
        private set
    @Volatile var estilo: EstiloGuardado? = null
        private set
    @Volatile var historial: List<Respondido> = emptyList()
        private set
    @Volatile var evento: String = "Recién despierto 🐸"
        private set
    private var ejemplos: Examples? = null

    @Synchronized
    fun init(ctx: Context) {
        if (dir != null) return
        dir = ctx.applicationContext.filesDir
        conversaciones = leer<List<Conversacion>>(CONV)?.associateBy { it.contacto } ?: emptyMap()
        ajustes = leer<Ajustes>(AJUSTES) ?: Ajustes()
        importado = leer<Importado>(IMPORTADO) ?: Importado()
        pares = leer<List<ParGuardado>>(PARES) ?: emptyList()
        estilo = leer<EstiloGuardado>(ESTILO)
        historial = leer<List<Respondido>>(HISTORIAL) ?: emptyList()
    }

    private inline fun <reified T> leer(nombre: String): T? {
        val f = File(dir ?: return null, nombre)
        if (!f.exists()) return null
        return runCatching { json.decodeFromString<T>(f.readText()) }.getOrNull()
    }

    private inline fun <reified T> guardar(nombre: String, valor: T) {
        val d = dir ?: return
        val destino = File(d, nombre)
        val tmp = File(d, "$nombre.tmp")
        tmp.writeText(json.encodeToString(valor))
        if (!tmp.renameTo(destino)) {
            destino.writeText(tmp.readText())
            tmp.delete()
        }
    }

    fun avisar() = _cambios.update { it + 1 }

    @Synchronized
    fun agregar(contacto: String, app: String, m: Mensaje) {
        val previa = conversaciones[contacto]
        val lista = ((previa?.mensajes ?: emptyList()) + m).takeLast(MAX_MENSAJES)
        val nueva = Conversacion(contacto, app, lista, maxOf(previa?.ultima ?: 0L, m.hora))
        conversaciones = (conversaciones + (contacto to nueva)).values
            .sortedByDescending { it.ultima }
            .take(MAX_CONV)
            .associateBy { it.contacto }
        guardar(CONV, conversaciones.values.toList())
        avisar()
    }

    fun ultimaHora(contacto: String): Long = conversaciones[contacto]?.mensajes?.maxOfOrNull { it.hora } ?: 0L

    fun activo(contacto: String) = contacto in ajustes.lista

    @Synchronized
    fun activar(contacto: String, on: Boolean) {
        ajustes = ajustes.copy(lista = if (on) ajustes.lista + contacto else ajustes.lista - contacto)
        guardar(AJUSTES, ajustes)
        avisar()
    }

    @Synchronized
    fun ponerModelo(modelo: String) {
        ajustes = ajustes.copy(modelo = modelo.ifBlank { "gemini-2.5-flash" })
        guardar(AJUSTES, ajustes)
        avisar()
    }

    @Synchronized
    fun ponerYo(yo: String?) {
        ajustes = ajustes.copy(yoManual = yo?.trim()?.ifEmpty { null })
        guardar(AJUSTES, ajustes)
        avisar()
    }

    @Synchronized
    fun ponerAuto(cambio: (Auto) -> Auto) {
        ajustes = ajustes.copy(auto = cambio(ajustes.auto))
        guardar(AJUSTES, ajustes)
        avisar()
    }

    @Synchronized
    fun registrar(r: Respondido) {
        historial = (historial + r).takeLast(MAX_HISTORIAL)
        guardar(HISTORIAL, historial)
        avisar()
    }

    @Synchronized
    fun guardarImportacion(i: Importado, p: List<ParGuardado>, e: EstiloGuardado?) {
        importado = i
        pares = p
        estilo = e
        ejemplos = null
        guardar(IMPORTADO, i)
        guardar(PARES, p)
        val d = dir
        if (e != null) guardar(ESTILO, e) else if (d != null) File(d, ESTILO).delete()
        avisar()
    }

    fun anotar(texto: String) {
        evento = texto
        avisar()
    }

    fun perfil(): StyleProfile = (estilo ?: EstiloGuardado()).perfil()

    @Synchronized
    fun ejemplos(): Examples =
        ejemplos ?: Examples(pares.map { ParCore(it.them, it.me, it.contact) }).also { ejemplos = it }
}
