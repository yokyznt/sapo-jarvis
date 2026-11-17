package io.github.yokyznt.sapo.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp

@Composable
fun Sapito(modifier: Modifier = Modifier.size(120.dp), brinca: Boolean = true) {
    val t = rememberInfiniteTransition(label = "sapito")
    val salto by t.animateFloat(
        initialValue = 0f,
        targetValue = if (brinca) 1f else 0f,
        animationSpec = infiniteRepeatable(tween(1400), RepeatMode.Reverse),
        label = "salto"
    )
    Canvas(modifier) {
        val u = size.minDimension / 108f
        val ox = (size.width - 108f * u) / 2f
        val oy = (size.height - 108f * u) / 2f - salto * 3f * u
        fun p(x: Float, y: Float) = Offset(ox + x * u, oy + y * u)

        drawCircle(VerdeSapo, 11f * u, p(42f, 36f))
        drawCircle(VerdeSapo, 11f * u, p(66f, 36f))
        drawCircle(VerdeSapo, 25f * u, p(54f, 60f))

        drawOval(Color(0xFF111111), p(37f, 29f), Size(10f * u, 14f * u))
        drawOval(Color(0xFF111111), p(61f, 29f), Size(10f * u, 14f * u))
        drawCircle(Color.White, 1.8f * u, p(43.8f, 33f))
        drawCircle(Color.White, 1.8f * u, p(67.8f, 33f))

        listOf(38f to 60f, 70f to 60f).forEach { (x, y) -> drawCircle(Pecas, 2.2f * u, p(x, y)) }
        listOf(34f to 66f, 41f to 66f, 74f to 66f, 67f to 66f).forEach { (x, y) -> drawCircle(Pecas, 1.6f * u, p(x, y)) }

        val lengua = Path().apply {
            moveTo(p(51f, 73f).x, p(51f, 73f).y)
            quadraticTo(p(53f, 88f + salto * 2f).x, p(53f, 88f + salto * 2f).y, p(59f, 86f + salto * 2f).x, p(59f, 86f + salto * 2f).y)
            quadraticTo(p(63f, 84f).x, p(63f, 84f).y, p(58f, 73f).x, p(58f, 73f).y)
            close()
        }
        drawPath(lengua, Lengua)

        val boca = Path().apply {
            moveTo(p(40f, 69f).x, p(40f, 69f).y)
            quadraticTo(p(54f, 79f).x, p(54f, 79f).y, p(68f, 69f).x, p(68f, 69f).y)
        }
        drawPath(boca, VerdeOscuro, style = Stroke(width = 2.5f * u, cap = StrokeCap.Round))
    }
}
