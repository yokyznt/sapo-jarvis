package io.github.yokyznt.sapo.flotante

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.view.View
import android.view.animation.LinearInterpolator
import io.github.yokyznt.sapo.ui.PintorSapo
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

    private val pintor = PintorSapo()
    private val punto = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFF1A1412.toInt() }
    private val aro = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF89B56E.toInt()
        style = Paint.Style.STROKE
        strokeWidth = 6f
    }
    private val zeta = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF5A8246.toInt()
        isFakeBoldText = true
        textAlign = Paint.Align.CENTER
    }

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
        val u = s / 290f
        c.save()
        c.translate(width / 2f - 128f * u, height / 2f - 134f * u)
        c.scale(u, u)

        if (animo == Animo.Escuchando) {
            aro.alpha = ((1f - pulso) * 200).toInt()
            c.drawCircle(128f, 134f, 118f + 18f * pulso, aro)
        }

        pintor.pintar(c, parpado, animo == Animo.Dormido)

        if (animo == Animo.Pensando) {
            for (i in 0..2) {
                val fase = ((pulso * 3f) - i).let { if (it < 0f) it + 3f else it }
                punto.alpha = if (fase < 1f) 230 else 90
                c.drawCircle(106f + i * 22f, 22f, 7f, punto)
            }
            punto.alpha = 255
        }

        if (animo == Animo.Dormido) {
            for (i in 0 until zFase) {
                zeta.textSize = 22f + i * 7f
                c.drawText("z", 232f + i * 10f, 62f - i * 18f, zeta)
            }
        }
        c.restore()
    }
}
