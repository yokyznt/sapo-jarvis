package io.github.yokyznt.sapo.flotante

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.view.View
import android.view.animation.LinearInterpolator
import kotlin.math.min
import kotlin.random.Random

enum class Animo { Normal, Escuchando, Pensando, Dormido }

class SapoVista(ctx: Context) : View(ctx) {
    var animo = Animo.Normal
        set(v) {
            if (field == v) return
            field = v
            cambiarAnimo()
        }

    private val verde = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFF7ED957.toInt() }
    private val sombra = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0x33000000 }
    private val negro = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFF111111.toInt() }
    private val blanco = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt() }
    private val pecas = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFF4FA83A.toInt() }
    private val lengua = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFF5C7A.toInt() }
    private val trazo = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF2E6B1F.toInt()
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val parpadoCerrado = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF111111.toInt()
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val aro = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF7ED957.toInt()
        style = Paint.Style.STROKE
    }
    private val zeta = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF2E6B1F.toInt()
        isFakeBoldText = true
        textAlign = Paint.Align.CENTER
    }
    private val camino = Path()
    private val ovalo = RectF()

    private var parpado = 1f
    private var pulso = 0f
    private var zFase = 0

    private val parpadeo = ValueAnimator.ofFloat(1f, 0.08f, 1f).apply {
        duration = 190
        addUpdateListener {
            parpado = it.animatedValue as Float
            invalidate()
        }
    }

    private val latido = ValueAnimator.ofFloat(0f, 1f).apply {
        duration = 1000
        repeatCount = ValueAnimator.INFINITE
        interpolator = LinearInterpolator()
        addUpdateListener {
            pulso = it.animatedValue as Float
            invalidate()
        }
    }

    private val ronquido = object : Runnable {
        override fun run() {
            if (animo != Animo.Dormido) return
            zFase = (zFase + 1) % 4
            invalidate()
            postDelayed(this, 650)
        }
    }

    private val siguienteParpadeo = object : Runnable {
        override fun run() {
            if (animo != Animo.Dormido && !parpadeo.isRunning) parpadeo.start()
            postDelayed(this, 2_500L + Random.nextLong(3_500))
        }
    }

    init {
        contentDescription = "Sapito"
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        removeCallbacks(siguienteParpadeo)
        postDelayed(siguienteParpadeo, 1_500)
        cambiarAnimo()
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(siguienteParpadeo)
        removeCallbacks(ronquido)
        parpadeo.cancel()
        latido.cancel()
        super.onDetachedFromWindow()
    }

    private fun cambiarAnimo() {
        removeCallbacks(ronquido)
        when (animo) {
            Animo.Escuchando, Animo.Pensando -> if (!latido.isStarted) latido.start()
            else -> latido.cancel()
        }
        if (animo == Animo.Dormido) {
            parpadeo.cancel()
            zFase = 0
            postDelayed(ronquido, 650)
        } else {
            parpado = 1f
        }
        invalidate()
    }

    override fun onDraw(c: Canvas) {
        val s = min(width, height).toFloat()
        if (s <= 0f) return
        val u = s / 68f
        val ox = width / 2f - 55f * u
        val oy = height / 2f - 58f * u
        fun x(v: Float) = ox + v * u
        fun y(v: Float) = oy + v * u

        if (animo == Animo.Escuchando) {
            aro.strokeWidth = 2.5f * u
            aro.alpha = ((1f - pulso) * 200).toInt()
            c.drawCircle(x(54f), y(58f), (27f + 6f * pulso) * u, aro)
        }

        ovalo.set(x(32f), y(80f), x(76f), y(88f))
        c.drawOval(ovalo, sombra)

        c.drawCircle(x(42f), y(36f), 11f * u, verde)
        c.drawCircle(x(66f), y(36f), 11f * u, verde)
        c.drawCircle(x(54f), y(60f), 25f * u, verde)

        if (animo == Animo.Dormido) {
            parpadoCerrado.strokeWidth = 2.2f * u
            listOf(42f, 66f).forEach { cx ->
                camino.reset()
                camino.moveTo(x(cx - 5f), y(36f))
                camino.quadTo(x(cx), y(41f), x(cx + 5f), y(36f))
                c.drawPath(camino, parpadoCerrado)
            }
        } else {
            val medio = 7f * parpado
            listOf(42f, 66f).forEach { cx ->
                ovalo.set(x(cx - 5f), y(36f - medio), x(cx + 5f), y(36f + medio))
                c.drawOval(ovalo, negro)
                if (parpado > 0.5f) c.drawCircle(x(cx + 1.8f), y(33f), 1.8f * u, blanco)
            }
        }

        c.drawCircle(x(38f), y(60f), 2.2f * u, pecas)
        c.drawCircle(x(70f), y(60f), 2.2f * u, pecas)
        listOf(34f, 41f, 67f, 74f).forEach { px -> c.drawCircle(x(px), y(66f), 1.6f * u, pecas) }

        if (animo != Animo.Dormido) {
            camino.reset()
            camino.moveTo(x(51f), y(73f))
            camino.quadTo(x(53f), y(88f), x(59f), y(86f))
            camino.quadTo(x(63f), y(84f), x(58f), y(73f))
            camino.close()
            c.drawPath(camino, lengua)
        }

        trazo.strokeWidth = 2.5f * u
        camino.reset()
        camino.moveTo(x(40f), y(69f))
        camino.quadTo(x(54f), y(if (animo == Animo.Dormido) 74f else 79f), x(68f), y(69f))
        c.drawPath(camino, trazo)

        if (animo == Animo.Pensando) {
            for (i in 0..2) {
                val fase = ((pulso * 3f) - i).let { if (it < 0f) it + 3f else it }
                negro.alpha = if (fase < 1f) 230 else 90
                c.drawCircle(x(46f + i * 8f), y(27f), 2f * u, negro)
            }
            negro.alpha = 255
        }

        if (animo == Animo.Dormido) {
            for (i in 0 until zFase) {
                zeta.textSize = (6f + i * 2.5f) * u
                c.drawText("z", x(76f + i * 4f), y(30f - i * 5f), zeta)
            }
        }
    }
}
