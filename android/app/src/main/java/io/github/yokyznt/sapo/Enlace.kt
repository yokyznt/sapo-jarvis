package io.github.yokyznt.sapo

import android.content.Context
import android.os.Build
import io.github.yokyznt.sapo.core.Link
import io.github.yokyznt.sapo.core.LinkMsg
import io.github.yokyznt.sapo.core.Style
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.SocketTimeoutException
import java.util.concurrent.TimeUnit

data class PcEncontrada(val nombre: String, val host: String, val puerto: Int)

enum class Fase { SinVincular, Apagado, Conectando, Conectado, Esperando, Rechazado }

data class EstadoPc(
    val fase: Fase = Fase.SinVincular,
    val detalle: String = "",
    val jugando: Boolean = false,
    val app: String? = null,
    val ausente: Boolean = false
)

object Enlace {
    private const val TOKEN = "pc.token"
    private const val MIN_ESPERA = 5_000L
    private const val MAX_ESPERA = 300_000L

    private val _estado = MutableStateFlow(EstadoPc())
    val estado: StateFlow<EstadoPc> = _estado

    @Volatile var jugando = false
        private set

    private var trabajo: Job? = null
    private var observador: Job? = null
    @Volatile private var socket: WebSocket? = null
    private var ultimoEstilo: String? = null
    private var ultimoTel: String? = null

    private val cliente by lazy {
        OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS)
            .pingInterval(30, TimeUnit.SECONDS)
            .build()
    }
    private val json = Json { ignoreUnknownKeys = true }

    private enum class Fin { Conectado, Fallo, Rechazado }

    fun dispositivo(): String {
        val marca = Build.MANUFACTURER.orEmpty().replaceFirstChar { it.uppercase() }
        val modelo = Build.MODEL.orEmpty()
        return if (modelo.startsWith(marca, true)) modelo else "$marca $modelo".trim()
    }

    fun vinculado(ctx: Context): Boolean = Store.ajustes.pc != null && Llave.leerDe(ctx.applicationContext, TOKEN) != null

    @Synchronized
    fun arrancar(ctx: Context) {
        val app = ctx.applicationContext
        Store.init(app)
        if (!vinculado(app)) {
            parar(Fase.SinVincular, "")
            return
        }
        if (!Store.ajustes.enlace) {
            parar(Fase.Apagado, "Enlace apagado")
            return
        }
        if (trabajo?.isActive == true) return
        trabajo = SapoApp.scope.launch { bucle(app) }
        if (observador?.isActive != true) observador = SapoApp.scope.launch { observar(app) }
    }

    @Synchronized
    private fun parar(fase: Fase, detalle: String) {
        trabajo?.cancel()
        trabajo = null
        observador?.cancel()
        observador = null
        socket?.close(1000, null)
        socket = null
        jugando = false
        _estado.value = EstadoPc(fase, detalle)
    }

    fun activar(ctx: Context, on: Boolean) {
        Store.ponerEnlace(on)
        arrancar(ctx)
    }

    fun desvincular(ctx: Context) {
        parar(Fase.SinVincular, "")
        Llave.borrarDe(ctx.applicationContext, TOKEN)
        Store.ponerPc(null)
        Store.anotar("Desvinculé tu PC")
    }

    suspend fun buscar(ctx: Context): List<PcEncontrada> = withContext(Dispatchers.IO) {
        val destinos = (difusiones() + InetAddress.getByName("255.255.255.255")).distinct()
        val halladas = LinkedHashMap<String, PcEncontrada>()
        DatagramSocket().use { s ->
            s.broadcast = true
            val datos = Link.PROBE.toByteArray(Charsets.UTF_8)
            destinos.forEach { d -> runCatching { s.send(DatagramPacket(datos, datos.size, d, Link.DISCOVERY_PORT)) } }
            val fin = System.currentTimeMillis() + 2_000
            val buf = ByteArray(4096)
            while (true) {
                val falta = fin - System.currentTimeMillis()
                if (falta <= 0) break
                s.soTimeout = falta.toInt().coerceAtLeast(1)
                val p = DatagramPacket(buf, buf.size)
                try {
                    s.receive(p)
                } catch (e: SocketTimeoutException) {
                    break
                }
                val host = p.address?.hostAddress ?: continue
                leerRespuesta(String(p.data, 0, p.length, Charsets.UTF_8), host)?.let { halladas[host] = it }
            }
        }
        halladas.values.toList()
    }

    private fun leerRespuesta(texto: String, host: String): PcEncontrada? = runCatching {
        val o = json.parseToJsonElement(texto).jsonObject
        if (o["sapo"]?.jsonPrimitive?.intOrNull == null) return null
        val puerto = o["port"]?.jsonPrimitive?.intOrNull ?: Link.PORT
        val nombre = o["name"]?.jsonPrimitive?.contentOrNull?.ifBlank { null } ?: host
        PcEncontrada(nombre, host, puerto)
    }.getOrNull()

    private fun difusiones(): List<InetAddress> = runCatching {
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback }
            .flatMap { it.interfaceAddresses }
            .mapNotNull { it.broadcast }
    }.getOrDefault(emptyList())

    private fun url(host: String, puerto: Int) = "ws://${if (host.contains(':')) "[$host]" else host}:$puerto/"

    suspend fun vincular(ctx: Context, pc: PcEncontrada, codigo: String): String? {
        val app = ctx.applicationContext
        parar(Fase.SinVincular, "")
        val respuesta = CompletableDeferred<LinkMsg>()
        val ws = cliente.newWebSocket(Request.Builder().url(url(pc.host, pc.puerto)).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                webSocket.send(Link.pair(codigo.trim(), dispositivo()))
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                when (val m = runCatching { Link.parse(text) }.getOrNull()) {
                    is LinkMsg.Paired, is LinkMsg.Error -> respuesta.complete(m)
                    else -> {}
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                respuesta.complete(LinkMsg.Error("La PC cerró la conexión"))
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                respuesta.complete(LinkMsg.Error("No pude conectar con ${pc.nombre}: ${t.message ?: "sin respuesta"}"))
            }
        })
        val m = withTimeoutOrNull(10_000) { respuesta.await() } ?: LinkMsg.Error("La PC no contestó")
        ws.close(1000, null)
        return when (m) {
            is LinkMsg.Paired -> {
                withContext(Dispatchers.IO) { Llave.guardarEn(app, TOKEN, m.token) }
                Store.ponerPc(PcVinculada(pc.nombre, pc.host, pc.puerto))
                Store.anotar("Vinculado con tu PC ${pc.nombre} 💻")
                arrancar(app)
                null
            }
            is LinkMsg.Error -> motivo(m.why)
            else -> "Respuesta rara de la PC"
        }
    }

    private suspend fun bucle(ctx: Context) {
        var espera = MIN_ESPERA
        while (kotlin.coroutines.coroutineContext.isActive) {
            val pc = Store.ajustes.pc ?: return
            val token = withContext(Dispatchers.IO) { Llave.leerDe(ctx, TOKEN) } ?: return
            _estado.value = EstadoPc(Fase.Conectando, "Conectando con ${pc.nombre}…")
            when (conectar(ctx, pc, token)) {
                Fin.Rechazado -> {
                    jugando = false
                    _estado.value = EstadoPc(Fase.Rechazado, "Tu PC ya no reconoce este cel; vuelve a vincularlo")
                    Store.anotar("Tu PC rechazó la conexión; vuelve a vincularla")
                    return
                }
                Fin.Conectado -> espera = MIN_ESPERA
                Fin.Fallo -> redescubrir(ctx, pc)
            }
            jugando = false
            _estado.value = EstadoPc(Fase.Esperando, "Sin conexión; reintento en ${espera / 1000} s")
            delay(espera)
            espera = (espera * 2).coerceAtMost(MAX_ESPERA)
        }
    }

    private suspend fun redescubrir(ctx: Context, pc: PcVinculada) {
        val nueva = runCatching { buscar(ctx) }.getOrDefault(emptyList()).firstOrNull { it.nombre == pc.nombre } ?: return
        if (nueva.host != pc.host || nueva.puerto != pc.puerto) Store.ponerPc(PcVinculada(pc.nombre, nueva.host, nueva.puerto))
    }

    private suspend fun conectar(ctx: Context, pc: PcVinculada, token: String): Fin {
        val fin = CompletableDeferred<Fin>()
        var listo = false
        val ws = cliente.newWebSocket(Request.Builder().url(url(pc.host, pc.puerto)).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                webSocket.send(Link.hello(token, dispositivo()))
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                val m = runCatching { Link.parse(text) }.getOrNull() ?: return
                if (!listo && (m is LinkMsg.Pc || m is LinkMsg.Ok)) {
                    listo = true
                    socket = webSocket
                    _estado.update { it.copy(fase = Fase.Conectado, detalle = "Conectado con ${pc.nombre}") }
                    Store.anotar("Conectado con tu PC ${pc.nombre} 💻")
                    synchronized(this@Enlace) {
                        ultimoEstilo = null
                        ultimoTel = null
                    }
                    revisar(ctx)
                }
                when (m) {
                    is LinkMsg.Pc -> recibirPc(m)
                    is LinkMsg.Error -> if (!listo) {
                        fin.complete(Fin.Rechazado)
                        webSocket.close(1000, null)
                    }
                    else -> {}
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                fin.complete(if (listo) Fin.Conectado else Fin.Fallo)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                fin.complete(if (listo) Fin.Conectado else Fin.Fallo)
            }
        })
        return try {
            fin.await()
        } finally {
            if (socket === ws) socket = null
            ws.cancel()
        }
    }

    private fun recibirPc(m: LinkMsg.Pc) {
        val antes = jugando
        jugando = m.gaming
        _estado.update { it.copy(jugando = m.gaming, app = m.app, ausente = m.away) }
        if (antes != m.gaming) {
            Store.anotar(if (m.gaming) "Tu PC: jugando ${juego(m.app) ?: "algo"} 🎮" else "Tu PC: ya no estás jugando")
        }
    }

    private suspend fun observar(ctx: Context) = coroutineScope {
        launch {
            Store.cambios.collect {
                delay(3_000)
                revisar(ctx)
            }
        }
        launch {
            while (isActive) {
                delay(30_000)
                revisar(ctx)
            }
        }
    }

    @Synchronized
    private fun revisar(ctx: Context) {
        val ws = socket ?: return
        runCatching {
            val perfil = Store.perfil()
            val estilo = Link.style(perfil, Style.describe(perfil))
            if (estilo != ultimoEstilo && ws.send(estilo)) ultimoEstilo = estilo
        }
        runCatching {
            val tel = Link.phone(Modo.razon(ctx), Store.ajustes.auto.corriendo)
            if (tel != ultimoTel && ws.send(tel)) ultimoTel = tel
        }
    }

    fun texto(e: EstadoPc): String = when (e.fase) {
        Fase.SinVincular -> "Sin vincular"
        Fase.Apagado -> "Enlace apagado"
        Fase.Conectando -> "Conectando…"
        Fase.Esperando -> "Desconectada"
        Fase.Rechazado -> "Hay que volver a vincular"
        Fase.Conectado -> when {
            e.jugando -> "jugando ${juego(e.app) ?: "algo"} 🎮"
            e.ausente -> "conectada, estás lejos de ella"
            else -> "conectada ✅"
        }
    }

    private val conocidos = mapOf(
        "fortniteclient" to "Fortnite",
        "valorant" to "VALORANT",
        "leagueclient" to "League of Legends",
        "league of legends" to "League of Legends",
        "cs2" to "Counter-Strike 2",
        "csgo" to "Counter-Strike",
        "r5apex" to "Apex Legends",
        "gta5" to "GTA V",
        "rocketleague" to "Rocket League",
        "robloxplayerbeta" to "Roblox",
        "dota2" to "Dota 2",
        "overwatch" to "Overwatch 2",
        "eldenring" to "Elden Ring",
        "minecraft" to "Minecraft",
        "cod" to "Call of Duty",
        "rainbowsix" to "Rainbow Six Siege",
        "eafc" to "EA FC"
    )

    fun juego(app: String?): String? {
        val base = app?.substringAfterLast('\\')?.substringAfterLast('/')?.trim()
            ?.replace(Regex("\\.exe$", RegexOption.IGNORE_CASE), "")?.ifBlank { null } ?: return null
        val raiz = base.split('-', '_', '.').first()
        conocidos[raiz.lowercase()]?.let { return it }
        conocidos[base.lowercase()]?.let { return it }
        val limpio = raiz.replace(Regex("(Client|Win64|Shipping|Launcher)$"), "").ifBlank { raiz }
        return limpio.replace(Regex("(?<=[a-z])(?=[A-Z])"), " ")
    }

    fun motivo(why: String): String = when (why) {
        "bad_code" -> "Ese código no es. Revísalo en Preferencias › Celular"
        "expired", "no_code" -> "El código ya caducó. Genera otro en Preferencias › Celular"
        "too_many" -> "Demasiados intentos. Genera un código nuevo en la PC"
        "bad_token", "revoked" -> "Tu PC ya no reconoce este cel. Vuelve a vincularlo"
        "busy" -> "La PC tiene demasiadas conexiones. Intenta en un rato"
        "need_hello" -> "La PC no recibió el saludo a tiempo. Intenta otra vez"
        "unavailable" -> "El enlace con el celular está apagado en la PC"
        "" -> "La PC no aceptó el código"
        else -> "La PC respondió: $why"
    }
}
