package io.github.yokyznt.sapo.ui

import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader

class PintorSapo {
    val silueta: Path = Path().apply {
        moveTo(20f, 152f)
        lineTo(20f, 144f)
        arcTo(RectF(20f, 70f, 168f, 218f), 180f, 39.002f)
        arcTo(RectF(34f, 40f, 120f, 126f), 160.395f, 182.008f)
        lineTo(138.012f, 70f)
        arcTo(RectF(136f, 40f, 222f, 126f), 197.597f, 182.008f)
        arcTo(RectF(88f, 70f, 236f, 218f), 320.998f, 39.002f)
        lineTo(236f, 152f)
        arcTo(RectF(88f, 78f, 236f, 226f), 0f, 90f)
        lineTo(94f, 226f)
        arcTo(RectF(20f, 78f, 168f, 226f), 90f, 90f)
        close()
    }

    private val sombra = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        shader = RadialGradient(128f, 227f, 94f, intArrayOf(0x32000000, 0x28000000, 0), floatArrayOf(0f, 0.8f, 1f), Shader.TileMode.CLAMP)
    }
    private val cuerpo = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        shader = LinearGradient(210.3f, 30f, 45.7f, 226f, 0xFFB9F58C.toInt(), 0xFF5FC03F.toInt(), Shader.TileMode.CLAMP)
    }
    private val borde = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeJoin = Paint.Join.ROUND
    }
    private val capasBorde = List(15) { (64 - 4 * it).toFloat() to 5 }
    private val brillo = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        shader = RadialGradient(178f, 99f, 44f, intArrayOf(0x5FFFFFFF, 0x4BFFFFFF, 0x00FFFFFF), floatArrayOf(0f, 0.45f, 1f), Shader.TileMode.CLAMP)
    }
    private val tinta = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFF1A1412.toInt() }
    private val blanco = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt() }
    private val cerrado = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF1A1412.toInt()
        style = Paint.Style.STROKE
        strokeWidth = 6.5f
        strokeCap = Paint.Cap.ROUND
    }
    private val halo = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0x50F7A3A0 }
    private val cachete = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xD2F7A3A0.toInt() }
    private val boca = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF7A2236.toInt()
        style = Paint.Style.STROKE
        strokeWidth = 7f
        strokeCap = Paint.Cap.ROUND
    }
    private val r = RectF()

    fun pintar(c: Canvas, parpado: Float = 1f, dormido: Boolean = false) {
        c.save()
        c.scale(1f, 0.16f, 128f, 227f)
        c.drawCircle(128f, 227f, 94f, sombra)
        c.restore()

        c.drawPath(silueta, cuerpo)
        c.save()
        c.clipPath(silueta)
        capasBorde.forEach { (ancho, alfa) ->
            borde.strokeWidth = ancho
            borde.color = (alfa shl 24) or 0x2F8A1C
            c.drawPath(silueta, borde)
        }
        c.scale(1f, 0.85f, 178f, 99f)
        c.drawCircle(178f, 99f, 44f, brillo)
        c.restore()

        listOf(80f, 176f).forEach { cx ->
            if (dormido || parpado < 0.3f) {
                r.set(cx - 18.6f, 83.8f - 18.6f, cx + 18.6f, 83.8f + 18.6f)
                c.drawArc(r, 32f, 116f, false, cerrado)
            } else {
                c.save()
                c.scale(1f, parpado.coerceIn(0.25f, 1.05f), cx, 93f)
                r.set(cx - 15f, 70f, cx + 15f, 116f)
                c.drawRoundRect(r, 15f, 15f, tinta)
                c.drawCircle(cx + 4f, 82f, 6f, blanco)
                c.restore()
            }
        }

        listOf(62f, 194f).forEach { cx ->
            r.set(cx - 22f, 122f, cx + 22f, 148f)
            c.drawOval(r, halo)
            r.set(cx - 20f, 124f, cx + 20f, 146f)
            c.drawOval(r, cachete)
        }

        r.set(110f, 112f, 146f, 140f)
        if (dormido) c.drawArc(r, 40f, 100f, false, boca) else c.drawArc(r, 20f, 140f, false, boca)
    }
}
