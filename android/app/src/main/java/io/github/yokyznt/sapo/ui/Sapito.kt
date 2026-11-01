package io.github.yokyznt.sapo.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.unit.dp
import kotlin.math.abs

@Composable
fun Sapito(modifier: Modifier = Modifier.size(120.dp), brinca: Boolean = true) {
    val pintor = remember { PintorSapo() }
    val t = rememberInfiniteTransition(label = "sapito")
    val salto by t.animateFloat(
        initialValue = 0f,
        targetValue = if (brinca) 1f else 0f,
        animationSpec = infiniteRepeatable(tween(1400), RepeatMode.Reverse),
        label = "salto"
    )
    val reloj by t.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(4200, easing = LinearEasing), RepeatMode.Restart),
        label = "reloj"
    )
    Canvas(modifier) {
        val d = abs(reloj - 0.95f) / 0.025f
        val parpado = if (d < 1f) 0.08f + 0.92f * d else 1f
        val u = size.minDimension / 272f
        drawIntoCanvas { c ->
            val n = c.nativeCanvas
            n.save()
            n.translate(size.width / 2f - 128f * u, size.height / 2f - 140f * u - salto * 8f * u)
            n.scale(u, u)
            pintor.pintar(n, parpado)
            n.restore()
        }
    }
}
