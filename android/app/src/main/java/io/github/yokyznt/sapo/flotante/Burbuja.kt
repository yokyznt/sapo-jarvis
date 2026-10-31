package io.github.yokyznt.sapo.flotante

import android.content.Context
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Handler
import android.os.Looper
import android.text.TextUtils
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import kotlin.math.max
import kotlin.math.min

data class Ancla(val x: Int, val y: Int, val tam: Int, val area: Rect)

class Burbuja(private val ctx: Context, private val wm: WindowManager) {
    private val mano = Handler(Looper.getMainLooper())
    private fun dp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, ctx.resources.displayMetrics).toInt()

    private val oido = TextView(ctx).apply {
        setTextColor(0xFF55624C.toInt())
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        setTypeface(typeface, Typeface.ITALIC)
        maxLines = 3
        ellipsize = TextUtils.TruncateAt.END
    }
    private val texto = TextView(ctx).apply {
        setTextColor(0xFF10200C.toInt())
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
        maxLines = 10
        ellipsize = TextUtils.TruncateAt.END
    }
    private val botones = LinearLayout(ctx).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.END
    }
    private val raiz = LinearLayout(ctx).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(14f), dp(10f), dp(14f), dp(10f))
        background = GradientDrawable().apply {
            setColor(0xFFFFFFFF.toInt())
            cornerRadius = dp(18f).toFloat()
            setStroke(dp(1.5f), 0xFF7ED957.toInt())
        }
        elevation = dp(6f).toFloat()
        addView(oido)
        addView(texto)
        addView(botones)
        setOnClickListener { if (botones.childCount == 0) esconder() }
    }

    private val params = WindowManager.LayoutParams(
        WindowManager.LayoutParams.WRAP_CONTENT,
        WindowManager.LayoutParams.WRAP_CONTENT,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
        PixelFormat.TRANSLUCENT
    ).apply {
        gravity = Gravity.TOP or Gravity.START
        title = "Sapito burbuja"
    }

    private var puesta = false
    private var ancla: Ancla? = null
    private val ocultar = Runnable { esconder() }

    val visible get() = puesta
    val pregunta get() = puesta && botones.childCount > 0

    fun mostrar(oyo: String?, dice: String, opciones: List<Pair<String, () -> Unit>> = emptyList(), dura: Long? = -1L) {
        mano.removeCallbacks(ocultar)
        oido.text = oyo?.let { "«$it»" }.orEmpty()
        oido.visibility = if (oyo.isNullOrBlank()) View.GONE else View.VISIBLE
        texto.text = dice
        botones.removeAllViews()
        botones.visibility = if (opciones.isEmpty()) View.GONE else View.VISIBLE
        opciones.forEachIndexed { i, (etiqueta, accion) ->
            botones.addView(boton(etiqueta, i == 0) {
                esconder()
                accion()
            }, LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                topMargin = dp(8f)
                marginStart = dp(6f)
            })
        }
        colocar()
        if (!puesta) {
            runCatching { wm.addView(raiz, params) }.onSuccess { puesta = true }
        } else {
            runCatching { wm.updateViewLayout(raiz, params) }
        }
        val tiempo = when {
            dura == null -> null
            dura >= 0 -> dura
            else -> (4_000L + dice.length * 70L).coerceAtMost(14_000L)
        }
        if (tiempo != null) mano.postDelayed(ocultar, tiempo)
    }

    private fun boton(etiqueta: String, principal: Boolean, accion: () -> Unit) = TextView(ctx).apply {
        text = etiqueta
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
        setTypeface(typeface, Typeface.BOLD)
        setTextColor(if (principal) 0xFF0D3A0A.toInt() else 0xFF2E3A28.toInt())
        setPadding(dp(16f), dp(8f), dp(16f), dp(8f))
        minWidth = dp(56f)
        gravity = Gravity.CENTER
        background = GradientDrawable().apply {
            setColor(if (principal) 0xFF7ED957.toInt() else 0xFFE1F2D3.toInt())
            cornerRadius = dp(16f).toFloat()
        }
        isClickable = true
        setOnClickListener { accion() }
    }

    fun seguir(a: Ancla) {
        ancla = a
        if (!puesta) return
        colocar()
        runCatching { wm.updateViewLayout(raiz, params) }
    }

    private fun colocar() {
        val a = ancla ?: return
        val hueco = dp(6f)
        val izquierda = a.x + a.tam / 2 < a.area.centerX()
        val disponible = if (izquierda) a.area.right - (a.x + a.tam) - hueco * 2 else a.x - a.area.left - hueco * 2
        val ancho = min(dp(280f), max(dp(160f), disponible))
        raiz.measure(
            View.MeasureSpec.makeMeasureSpec(ancho, View.MeasureSpec.AT_MOST),
            View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
        )
        val bw = raiz.measuredWidth
        val bh = raiz.measuredHeight
        params.width = bw
        params.x = if (izquierda) a.x + a.tam + hueco else a.x - bw - hueco
        params.x = params.x.coerceIn(a.area.left, max(a.area.left, a.area.right - bw))
        params.y = (a.y + a.tam / 2 - bh / 2).coerceIn(a.area.top, max(a.area.top, a.area.bottom - bh))
    }

    fun esconder() {
        mano.removeCallbacks(ocultar)
        if (!puesta) return
        runCatching { wm.removeView(raiz) }
        puesta = false
    }
}
