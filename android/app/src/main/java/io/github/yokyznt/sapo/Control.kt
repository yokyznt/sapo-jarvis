package io.github.yokyznt.sapo

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import io.github.yokyznt.sapo.core.Command
import io.github.yokyznt.sapo.core.Contacts
import java.text.Normalizer

data class Nodo(
    val info: AccessibilityNodeInfo,
    val texto: String,
    val clic: Boolean,
    val editable: Boolean,
    val desplazable: Boolean,
    val caja: Rect
)

object Control {
    private val s get() = SapoAccesibilidad.activo

    fun listo(): Boolean = s != null

    private fun plano(t: String): String = Normalizer.normalize(t.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "").trim()

    fun global(accion: String): Boolean {
        val svc = s ?: return false
        val g = when (accion) {
            Command.Screen.BACK -> AccessibilityService.GLOBAL_ACTION_BACK
            Command.Screen.HOME -> AccessibilityService.GLOBAL_ACTION_HOME
            Command.Screen.RECENTS -> AccessibilityService.GLOBAL_ACTION_RECENTS
            Command.Screen.NOTIFICATIONS -> AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS
            Command.Screen.QUICK -> AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS
            Command.Screen.SCREENSHOT -> if (Build.VERSION.SDK_INT >= 28) AccessibilityService.GLOBAL_ACTION_TAKE_SCREENSHOT else return false
            Command.Screen.LOCK -> if (Build.VERSION.SDK_INT >= 28) AccessibilityService.GLOBAL_ACTION_LOCK_SCREEN else return false
            else -> return false
        }
        return svc.performGlobalAction(g)
    }

    fun raiz(): AccessibilityNodeInfo? {
        val svc = s ?: return null
        val propia = svc.packageName
        val ventanas = runCatching { svc.windows }.getOrNull().orEmpty()
            .filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION || it.type == AccessibilityWindowInfo.TYPE_SYSTEM }
            .sortedByDescending { (if (it.isActive) 4 else 0) + (if (it.isFocused) 2 else 0) + (if (it.type == AccessibilityWindowInfo.TYPE_APPLICATION) 1 else 0) }
        for (v in ventanas) {
            val r = runCatching { v.root }.getOrNull() ?: continue
            if (r.packageName?.toString() != propia) return r.also { runCatching { it.refresh() } }
        }
        return svc.rootInActiveWindow?.takeIf { it.packageName?.toString() != propia }?.also { runCatching { it.refresh() } }
    }

    fun app(): String = raiz()?.packageName?.toString().orEmpty()

    fun nodos(): List<Nodo> {
        val r = raiz() ?: return emptyList()
        val out = ArrayList<Nodo>()
        fun visitar(n: AccessibilityNodeInfo, hondo: Int) {
            if (hondo > 40 || out.size >= 120) return
            if (!n.isVisibleToUser) return
            val t = listOfNotNull(n.text?.toString(), n.contentDescription?.toString(), if (n.isEditable) n.hintText?.toString() else null)
                .map { it.trim().replace(Regex("\\s+"), " ") }.filter { it.isNotEmpty() }.distinct().joinToString(" / ")
                .ifEmpty { if (n.isClickable || n.isEditable) n.viewIdResourceName?.substringAfter(":id/")?.replace('_', ' ')?.let { "($it)" }.orEmpty() else "" }
            val caja = Rect().also { n.getBoundsInScreen(it) }
            val estado = if (n.isCheckable) (if (n.isChecked) " [prendido]" else " [apagado]") else ""
            if ((t.isNotEmpty() || n.isCheckable || n.isEditable || n.isScrollable || (n.isClickable && n.childCount == 0)) && caja.width() > 0 && caja.height() > 0) {
                out.add(Nodo(n, t.take(80) + estado, n.isClickable || n.isLongClickable, n.isEditable, n.isScrollable, caja))
            }
            for (i in 0 until n.childCount) n.getChild(i)?.let { visitar(it, hondo + 1) }
        }
        visitar(r, 0)
        return out
    }

    fun buscar(objetivo: String): Nodo? {
        val lista = nodos().filter { it.texto.isNotEmpty() }
        if (lista.isEmpty()) return null
        val q = plano(objetivo).trim()
        lista.firstOrNull { plano(it.texto) == q }?.let { return it }
        lista.firstOrNull { plano(it.texto).split(" / ").any { p -> p == q } }?.let { return it }
        lista.filter { plano(it.texto).contains(q) }.minByOrNull { it.texto.length }?.let { return it }
        val mejor = Contacts.best(objetivo, lista.map { it.texto }) ?: return null
        return lista.firstOrNull { it.texto == mejor }
    }

    fun tocar(n: Nodo): Boolean {
        var x: AccessibilityNodeInfo? = n.info
        var subidas = 0
        while (x != null && subidas < 6) {
            if (x.isClickable && x.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
            x = x.parent
            subidas++
        }
        return gesto(n.caja.exactCenterX(), n.caja.exactCenterY(), n.caja.exactCenterX(), n.caja.exactCenterY(), 60)
    }

    fun escribir(texto: String, destino: Nodo? = null): Boolean {
        val r = raiz() ?: return false
        val campo = destino?.info?.takeIf { it.isEditable }
            ?: r.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)?.takeIf { it.isEditable }
            ?: nodos().firstOrNull { it.editable }?.info
            ?: return false
        campo.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, texto) }
        return campo.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    fun enter(): Boolean {
        val r = raiz() ?: return false
        val campo = r.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return false
        if (Build.VERSION.SDK_INT >= 30) return campo.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id)
        return false
    }

    fun deslizar(abajo: Boolean): Boolean {
        val lista = nodos().filter { it.desplazable }
        val n = lista.maxByOrNull { it.caja.width() * it.caja.height() }
        val accion = if (abajo) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        if (n != null && n.info.performAction(accion)) return true
        val svc = s ?: return false
        val m = svc.resources.displayMetrics
        val x = m.widthPixels / 2f
        val alto = m.heightPixels.toFloat()
        return if (abajo) gesto(x, alto * 0.72f, x, alto * 0.28f, 320) else gesto(x, alto * 0.28f, x, alto * 0.72f, 320)
    }

    fun textoPantalla(): String = nodos().map { it.texto }.filter { it.isNotEmpty() }.distinct().joinToString(" · ").take(1800)

    private fun gesto(x1: Float, y1: Float, x2: Float, y2: Float, ms: Long): Boolean {
        val svc = s ?: return false
        val p = Path().apply {
            moveTo(x1, y1)
            lineTo(x2, y2)
        }
        val g = GestureDescription.Builder().addStroke(GestureDescription.StrokeDescription(p, 0, ms)).build()
        return svc.dispatchGesture(g, null, null)
    }
}
