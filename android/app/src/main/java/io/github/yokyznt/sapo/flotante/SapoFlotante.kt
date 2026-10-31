package io.github.yokyznt.sapo.flotante

import android.Manifest
import android.animation.ValueAnimator
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.content.res.Configuration
import android.graphics.PixelFormat
import android.graphics.Rect
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.TypedValue
import android.view.Choreographer
import android.view.Gravity
import android.view.MotionEvent
import android.view.VelocityTracker
import android.view.ViewConfiguration
import android.view.WindowInsets
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
import android.widget.Toast
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import io.github.yokyznt.sapo.MainActivity
import io.github.yokyznt.sapo.Permisos
import io.github.yokyznt.sapo.R
import io.github.yokyznt.sapo.Store
import io.github.yokyznt.sapo.core.Command
import io.github.yokyznt.sapo.core.Intents
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDateTime
import kotlin.math.exp
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.roundToInt

class SapoFlotante : Service() {
    private val mano = Handler(Looper.getMainLooper())
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private lateinit var wm: WindowManager
    private lateinit var vista: SapoVista
    private lateinit var burbuja: Burbuja
    private lateinit var oreja: Oreja
    private lateinit var ejecutor: Ejecutor
    private var voz: Voz? = null
    private lateinit var params: WindowManager.LayoutParams

    private var puesto = false
    private var tam = 0
    private var tamAjuste = -1
    private var derecha = true
    private var oyo: String? = null
    private var trabajo: Job? = null
    private var pendiente: Pair<String, () -> Unit>? = null
    private var ultimaActividad = System.currentTimeMillis()

    private val coreo = Choreographer.getInstance()
    private var vuelo: Vuelo? = null
    private var pegado: ValueAnimator? = null
    private var rastreo: VelocityTracker? = null
    private var bajaX = 0f
    private var bajaY = 0f
    private var inicioX = 0
    private var inicioY = 0
    private var arrastrando = false
    private var largo = false
    private val holgura by lazy { ViewConfiguration.get(this).scaledTouchSlop }
    private val maxVuelo by lazy { ViewConfiguration.get(this).scaledMaximumFlingVelocity.toFloat() }

    private val toqueLargo = Runnable {
        largo = true
        vista.performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS)
        menu()
    }

    private val sueno = object : Runnable {
        override fun run() {
            val quieto = System.currentTimeMillis() - ultimaActividad
            if (quieto >= DORMIR && vista.animo == Animo.Normal && !burbuja.visible) vista.animo = Animo.Dormido
            mano.postDelayed(this, 10_000)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        Store.init(this)
        promover()
        vivo = this
        wm = getSystemService(WindowManager::class.java)
        vista = SapoVista(this)
        burbuja = Burbuja(this, wm)
        ejecutor = Ejecutor(this)
        oreja = Oreja(
            this,
            listo = { burbuja.mostrar(null, "Te escucho… 👂", dura = null); anclar() },
            parcial = { burbuja.mostrar(it, "…", dura = null); anclar() },
            final = { procesar(it) },
            fallo = { decir(it) }
        )
        tam = tamano()
        tamAjuste = Store.ajustes.tamano
        params = WindowManager.LayoutParams(
            tam,
            tam,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            title = "Sapito"
            val a = area()
            x = a.right - tam
            y = a.top + (a.height() * 0.35f).roundToInt()
        }
        vista.setOnTouchListener { _, e -> tocando(e) }
        vista.setOnClickListener { tocar() }
        vista.setOnLongClickListener {
            menu()
            true
        }
        scope.launch {
            Store.cambios.collect {
                if (!Store.ajustes.flotante) {
                    stopSelf()
                    return@collect
                }
                if (Store.ajustes.tamano != tamAjuste) redimensionar()
                if (!Store.ajustes.voz) voz?.callar()
            }
        }
        mano.postDelayed(sueno, 10_000)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!Permisos.encima(this)) {
            stopSelf()
            return START_NOT_STICKY
        }
        when (intent?.action) {
            QUITAR -> {
                Store.ponerFlotante(false)
                stopSelf()
                return START_NOT_STICKY
            }
            ESCONDER -> esconder()
            MOSTRAR -> mostrar()
            else -> if (!puesto) mostrar()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        vivo = null
        mano.removeCallbacksAndMessages(null)
        vuelo = null
        pegado?.cancel()
        trabajo?.cancel()
        scope.cancel()
        oreja.cerrar()
        voz?.cerrar()
        burbuja.esconder()
        if (puesto) runCatching { wm.removeView(vista) }
        puesto = false
        super.onDestroy()
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        if (!puesto) return
        mano.postDelayed({ if (puesto) acomodar(true) }, 300)
    }

    private fun dp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, resources.displayMetrics).roundToInt()

    private fun tamano() = dp(
        when (Store.ajustes.tamano) {
            0 -> 56f
            2 -> 92f
            else -> 72f
        }
    )

    private fun area(): Rect {
        if (Build.VERSION.SDK_INT >= 30) {
            val m = getSystemService(WindowManager::class.java).currentWindowMetrics
            val i = m.windowInsets.getInsetsIgnoringVisibility(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
            return Rect(i.left, i.top, m.bounds.width() - i.right, m.bounds.height() - i.bottom)
        }
        val dm = resources.displayMetrics
        return Rect(0, dp(24f), dm.widthPixels, dm.heightPixels)
    }

    private fun promover() {
        val n = aviso()
        val base = if (Build.VERSION.SDK_INT >= 34) ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE else 0
        val mic = Build.VERSION.SDK_INT >= 30 && Permisos.tiene(this, Manifest.permission.RECORD_AUDIO)
        val conMic = if (mic) base or ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else base
        val ok = runCatching { ServiceCompat.startForeground(this, ID, n, conMic) }.isSuccess
        if (!ok) runCatching { ServiceCompat.startForeground(this, ID, n, base) }
    }

    private fun canal() {
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CANAL) != null) return
        val c = NotificationChannel(CANAL, "Sapito flotante", NotificationManager.IMPORTANCE_MIN)
        c.description = "Aviso fijo mientras el sapito flota en tu pantalla"
        c.setShowBadge(false)
        nm.createNotificationChannel(c)
    }

    private fun aviso(): Notification {
        canal()
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        val abrir = PendingIntent.getActivity(this, 10, Intent(this, MainActivity::class.java), flags)
        val alternar = PendingIntent.getService(
            this, 11, Intent(this, SapoFlotante::class.java).setAction(if (puesto) ESCONDER else MOSTRAR), flags
        )
        val quitar = PendingIntent.getService(this, 12, Intent(this, SapoFlotante::class.java).setAction(QUITAR), flags)
        return NotificationCompat.Builder(this, CANAL)
            .setSmallIcon(R.drawable.ic_stat_sapo)
            .setColor(0xFF7ED957.toInt())
            .setContentTitle("Sapito flotante 🐸")
            .setContentText(if (puesto) "Tócalo y háblale; déjalo apretado para el menú" else "Escondido; toca aquí para que vuelva")
            .setOngoing(true)
            .setSilent(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setContentIntent(if (puesto) abrir else alternar)
            .addAction(0, if (puesto) "Esconder" else "Mostrar", alternar)
            .addAction(0, "Quitar", quitar)
            .build()
    }

    private fun refrescarAviso() {
        runCatching { getSystemService(NotificationManager::class.java).notify(ID, aviso()) }
    }

    private fun mostrar() {
        if (puesto) return
        acomodar(false)
        puesto = runCatching { wm.addView(vista, params) }.isSuccess
        if (!puesto) {
            Toast.makeText(this, "No pude mostrar al sapito; revisa el permiso de mostrarse encima", Toast.LENGTH_LONG).show()
            stopSelf()
            return
        }
        actividad()
        refrescarAviso()
    }

    private fun esconder() {
        if (!puesto) return
        callar()
        vuelo = null
        pegado?.cancel()
        burbuja.esconder()
        runCatching { wm.removeView(vista) }
        puesto = false
        refrescarAviso()
        Toast.makeText(this, "Me escondí 🐸 Tócame en la notificación para volver", Toast.LENGTH_SHORT).show()
    }

    private fun redimensionar() {
        tamAjuste = Store.ajustes.tamano
        val centroX = params.x + tam / 2
        val centroY = params.y + tam / 2
        tam = tamano()
        params.width = tam
        params.height = tam
        params.x = centroX - tam / 2
        params.y = centroY - tam / 2
        acomodar(true)
    }

    private fun acomodar(aplicar: Boolean) {
        val a = area()
        params.x = if (derecha) a.right - tam else a.left
        params.y = params.y.coerceIn(a.top, max(a.top, a.bottom - tam))
        if (aplicar && puesto) runCatching { wm.updateViewLayout(vista, params) }
        anclar()
    }

    private fun mover(x: Int, y: Int, a: Rect = area()) {
        params.x = x.coerceIn(a.left, max(a.left, a.right - tam))
        params.y = y.coerceIn(a.top, max(a.top, a.bottom - tam))
        if (puesto) runCatching { wm.updateViewLayout(vista, params) }
        burbuja.seguir(Ancla(params.x, params.y, tam, a))
    }

    private fun anclar() = burbuja.seguir(Ancla(params.x, params.y, tam, area()))

    private fun actividad() {
        ultimaActividad = System.currentTimeMillis()
        if (vista.animo == Animo.Dormido) vista.animo = Animo.Normal
    }

    private fun tocando(e: MotionEvent): Boolean {
        val copia = MotionEvent.obtain(e).apply { setLocation(e.rawX, e.rawY) }
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                actividad()
                vuelo = null
                pegado?.cancel()
                rastreo?.recycle()
                rastreo = VelocityTracker.obtain().also { it.addMovement(copia) }
                bajaX = e.rawX
                bajaY = e.rawY
                inicioX = params.x
                inicioY = params.y
                arrastrando = false
                largo = false
                mano.postDelayed(toqueLargo, ViewConfiguration.getLongPressTimeout().toLong())
                vista.animate().scaleX(0.9f).scaleY(0.9f).setDuration(90).start()
            }
            MotionEvent.ACTION_MOVE -> {
                rastreo?.addMovement(copia)
                val dx = e.rawX - bajaX
                val dy = e.rawY - bajaY
                if (!arrastrando && !largo && hypot(dx, dy) > holgura) {
                    arrastrando = true
                    mano.removeCallbacks(toqueLargo)
                    if (!burbuja.pregunta) burbuja.esconder()
                }
                if (arrastrando) mover(inicioX + dx.roundToInt(), inicioY + dy.roundToInt())
            }
            MotionEvent.ACTION_UP -> {
                rastreo?.addMovement(copia)
                mano.removeCallbacks(toqueLargo)
                vista.animate().scaleX(1f).scaleY(1f).setDuration(140).start()
                if (arrastrando) {
                    val r = rastreo
                    r?.computeCurrentVelocity(1000, maxVuelo)
                    val vx = r?.xVelocity ?: 0f
                    val vy = r?.yVelocity ?: 0f
                    if (hypot(vx, vy) > 700f) aventar(vx, vy) else pegar()
                } else if (!largo) {
                    vista.performClick()
                }
                rastreo?.recycle()
                rastreo = null
            }
            MotionEvent.ACTION_CANCEL -> {
                mano.removeCallbacks(toqueLargo)
                vista.animate().scaleX(1f).scaleY(1f).setDuration(140).start()
                rastreo?.recycle()
                rastreo = null
                if (arrastrando) pegar()
            }
        }
        copia.recycle()
        return true
    }

    private fun aventar(vx: Float, vy: Float) {
        val v = Vuelo(vx.coerceIn(-6000f, 6000f), vy.coerceIn(-6000f, 6000f))
        vuelo = v
        coreo.postFrameCallback(v)
    }

    private inner class Vuelo(var vx: Float, var vy: Float) : Choreographer.FrameCallback {
        private var antes = 0L
        private var x = params.x.toFloat()
        private var y = params.y.toFloat()
        private val a = area()

        override fun doFrame(t: Long) {
            if (vuelo !== this || !puesto) return
            if (antes == 0L) {
                antes = t
                coreo.postFrameCallback(this)
                return
            }
            val dt = ((t - antes) / 1_000_000_000f).coerceIn(0f, 0.034f)
            antes = t
            x += vx * dt
            y += vy * dt
            val minX = a.left.toFloat()
            val maxX = (a.right - tam).toFloat()
            val minY = a.top.toFloat()
            val maxY = (a.bottom - tam).toFloat()
            if (x < minX) {
                x = minX + (minX - x) * REBOTE
                vx = -vx * REBOTE
            } else if (x > maxX) {
                x = maxX - (x - maxX) * REBOTE
                vx = -vx * REBOTE
            }
            if (y < minY) {
                y = minY + (minY - y) * REBOTE
                vy = -vy * REBOTE
            } else if (y > maxY) {
                y = maxY - (y - maxY) * REBOTE
                vy = -vy * REBOTE
            }
            val f = exp(-FRICCION * dt)
            vx *= f
            vy *= f
            mover(x.roundToInt(), y.roundToInt(), a)
            if (hypot(vx, vy) < 260f) {
                vuelo = null
                pegar()
            } else {
                coreo.postFrameCallback(this)
            }
        }
    }

    private fun pegar() {
        val a = area()
        derecha = params.x + tam / 2 >= a.centerX()
        val destino = if (derecha) a.right - tam else a.left
        pegado?.cancel()
        pegado = ValueAnimator.ofInt(params.x, destino).apply {
            duration = 260
            interpolator = DecelerateInterpolator(1.6f)
            addUpdateListener { mover(it.animatedValue as Int, params.y, a) }
            start()
        }
        actividad()
    }

    private fun tocar() {
        actividad()
        if (oreja.escuchando) {
            oreja.parar()
            vista.animo = Animo.Normal
            burbuja.esconder()
            return
        }
        voz?.callar()
        trabajo?.cancel()
        if (!Permisos.tiene(this, Manifest.permission.RECORD_AUDIO)) {
            pedir(
                Manifest.permission.RECORD_AUDIO,
                "Para oírte cuando me tocas necesito el micrófono. Solo escucho mientras ves el aro verde alrededor de mí."
            ) { escuchar() }
            return
        }
        escuchar()
    }

    private fun escuchar() {
        oyo = null
        vista.animo = Animo.Escuchando
        burbuja.mostrar(null, "Te escucho… 👂", dura = null)
        anclar()
        oreja.escuchar()
    }

    private fun menu() {
        oreja.parar()
        vista.animo = Animo.Normal
        burbuja.mostrar(
            null,
            "¿Qué hago? 🐸",
            listOf(
                "Callar" to { callar() },
                "Abrir app" to { abrirApp() },
                "Esconder" to { esconder() }
            ),
            dura = 8_000
        )
        anclar()
    }

    private fun callar() {
        voz?.callar()
        oreja.parar()
        trabajo?.cancel()
        burbuja.esconder()
        vista.animo = Animo.Normal
    }

    private fun abrirApp() {
        runCatching {
            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT))
        }
    }

    private fun hablar(texto: String) {
        if (!Store.ajustes.voz) return
        val v = voz ?: Voz(this).also { voz = it }
        v.decir(texto)
    }

    private fun decir(texto: String) {
        vista.animo = Animo.Normal
        burbuja.mostrar(oyo, texto)
        anclar()
        hablar(texto)
        actividad()
    }

    private fun procesar(texto: String) {
        oyo = texto
        val c = runCatching { Intents.parse(texto, LocalDateTime.now()) }.getOrElse { Command.Chat(texto) }
        when {
            Intents.needsConfirm(c) -> conContacto(c)
            else -> {
                vista.animo = Animo.Pensando
                burbuja.mostrar(oyo, if (c is Command.Pc) "Le pregunto a tu PC… 💻" else "Déjame ver… 🤔", dura = null)
                anclar()
                trabajo?.cancel()
                trabajo = scope.launch {
                    val r = runCatching { ejecutor.hacer(c) }.getOrElse { "Algo me salió mal 😵 ${it.message.orEmpty()}".trim() }
                    decir(r)
                }
            }
        }
    }

    private fun quien(c: Command) = when (c) {
        is Command.Call -> c.who
        is Command.Sms -> c.who
        is Command.WhatsApp -> c.who
        else -> ""
    }

    private fun conContacto(c: Command) {
        val who = quien(c)
        if (!Permisos.tiene(this, Manifest.permission.READ_CONTACTS)) {
            pedir(
                Manifest.permission.READ_CONTACTS,
                "Para encontrar a «$who» en tus contactos necesito leerlos. Solo busco el número; nada sale del cel."
            ) { conContacto(c) }
            return
        }
        vista.animo = Animo.Pensando
        trabajo?.cancel()
        trabajo = scope.launch {
            val k = withContext(Dispatchers.IO) { runCatching { ejecutor.contacto(who) }.getOrNull() }
            if (k == null) {
                decir("No encontré a «$who» en tus contactos 🤔")
                return@launch
            }
            confirmar(c, k)
        }
    }

    private fun confirmar(c: Command, k: Contacto) {
        val pregunta = runCatching { Intents.confirmText(c) }.getOrElse { "¿Lo hago?" }
        vista.animo = Animo.Normal
        burbuja.mostrar(
            oyo,
            "$pregunta\n${k.nombre} · ${k.numero}",
            listOf("Sí" to { confirmado(c, k) }, "No" to { decir("Va, no hago nada 👍") }),
            dura = 30_000
        )
        anclar()
        hablar(pregunta)
    }

    private fun confirmado(c: Command, k: Contacto) {
        voz?.callar()
        when (c) {
            is Command.Call -> if (!Permisos.tiene(this, Manifest.permission.CALL_PHONE)) {
                pedir(Manifest.permission.CALL_PHONE, "Para marcarle a ${k.nombre} directo necesito permiso de hacer llamadas.") { confirmado(c, k) }
            } else {
                decir(ejecutor.llamar(k))
            }
            is Command.Sms -> if (!Permisos.tiene(this, Manifest.permission.SEND_SMS)) {
                pedir(Manifest.permission.SEND_SMS, "Para mandarle el SMS a ${k.nombre} necesito permiso de enviar mensajes. Solo mando lo que confirmes.") { confirmado(c, k) }
            } else {
                decir(ejecutor.sms(k, c.text))
            }
            is Command.WhatsApp -> decir(ejecutor.whatsapp(k, c.text))
            else -> {}
        }
    }

    private fun pedir(permiso: String, razon: String, luego: () -> Unit) {
        pendiente = permiso to luego
        vista.animo = Animo.Normal
        burbuja.mostrar(oyo, "Necesito un permiso; te lo pido en pantalla 🙏", dura = 6_000)
        anclar()
        val i = Intent(this, PermisoActivity::class.java)
            .putExtra(PermisoActivity.PERMISO, permiso)
            .putExtra(PermisoActivity.RAZON, razon)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS)
        if (runCatching { startActivity(i) }.isFailure) {
            pendiente = null
            decir("Ábreme la app para darme el permiso 🙏")
        }
    }

    private fun trasPermiso(permiso: String, ok: Boolean) {
        if (ok && permiso == Manifest.permission.RECORD_AUDIO) promover()
        val p = pendiente ?: return
        if (p.first != permiso) return
        pendiente = null
        if (ok) p.second() else decir("Sin ese permiso no puedo hacerlo 😔")
    }

    companion object {
        const val ESCONDER = "io.github.yokyznt.sapo.flotante.ESCONDER"
        const val MOSTRAR = "io.github.yokyznt.sapo.flotante.MOSTRAR"
        const val QUITAR = "io.github.yokyznt.sapo.flotante.QUITAR"
        private const val CANAL = "flotante"
        private const val ID = 0x5A70
        private const val DORMIR = 120_000L
        private const val REBOTE = 0.55f
        private const val FRICCION = 2.4f

        @Volatile private var vivo: SapoFlotante? = null

        val activo get() = vivo != null

        fun sincronizar(ctx: Context) {
            val app = ctx.applicationContext
            Store.init(app)
            val quiere = Store.ajustes.flotante && Permisos.encima(app)
            if (quiere && vivo == null) {
                runCatching { ContextCompat.startForegroundService(app, Intent(app, SapoFlotante::class.java)) }
            } else if (!quiere && vivo != null) {
                app.stopService(Intent(app, SapoFlotante::class.java))
            }
        }

        fun permisoListo(permiso: String, ok: Boolean) {
            Handler(Looper.getMainLooper()).post { vivo?.trasPermiso(permiso, ok) }
        }
    }
}
