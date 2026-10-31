package io.github.yokyznt.sapo.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import io.github.yokyznt.sapo.Auto
import io.github.yokyznt.sapo.Modo
import io.github.yokyznt.sapo.Store

@Composable
fun ModoAutomatico() {
    val ctx = LocalContext.current
    val v by Store.cambios.collectAsState()
    val a = remember(v) { Store.ajustes.auto }
    val cambiar: ((Auto) -> Auto) -> Unit = { Modo.cambiar(ctx, it) }

    Tarjeta("Modo automático 🤖", color = MaterialTheme.colorScheme.errorContainer) {
        Text(
            "⚠️ Riesgo real: WhatsApp prohíbe la automatización y puede suspender o banear tu número. " +
                "Úsalo con muy pocos contactos de confianza y bajo tu propio riesgo. " +
                "Cada respuesta automática sale marcada con 🤖.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onErrorContainer
        )
    }

    Tarjeta("Responder solo cuando esté ocupado") {
        Interruptor("Prendido", a.activo) { on -> cambiar { it.copy(activo = on, pausado = false) } }
        if (a.activo) {
            Text(
                if (a.pausado) "En pausa ⏸ (pánico). No contesto nada." else "Contesto solo a tu lista blanca y nunca en grupos.",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold
            )
            OutlinedButton(onClick = { Modo.pausar(ctx, !a.pausado) }) {
                Text(if (a.pausado) "Reactivar" else "Parar al sapo")
            }
        }
    }

    Tarjeta("¿Cuándo estás ocupado?") {
        Interruptor("Ocupado ya (manual)", a.manual) { on -> cambiar { it.copy(manual = on) } }
        Interruptor("Cuando tengo No molestar", a.dnd) { on -> cambiar { it.copy(dnd = on) } }
        Interruptor("Con la pantalla apagada", a.pantalla) { on -> cambiar { it.copy(pantalla = on) } }
        if (a.pantalla) Paso("Apagada al menos", "${a.minutosPantalla} min", { cambiar { it.copy(minutosPantalla = (it.minutosPantalla - 5).coerceAtLeast(5)) } }) {
            cambiar { it.copy(minutosPantalla = (it.minutosPantalla + 5).coerceAtMost(240)) }
        }
        Interruptor("En un horario", a.horario) { on -> cambiar { it.copy(horario = on) } }
        if (a.horario) {
            Paso("Desde", hora(a.desde), { cambiar { it.copy(desde = mover(it.desde, -30)) } }) {
                cambiar { it.copy(desde = mover(it.desde, 30)) }
            }
            Paso("Hasta", hora(a.hasta), { cambiar { it.copy(hasta = mover(it.hasta, -30)) } }) {
                cambiar { it.copy(hasta = mover(it.hasta, 30)) }
            }
        }
    }

    Tarjeta("Topes") {
        Paso("Entre respuestas al mismo contacto", "${a.separacion} min", { cambiar { it.copy(separacion = (it.separacion - 5).coerceAtLeast(5)) } }) {
            cambiar { it.copy(separacion = (it.separacion + 5).coerceAtMost(180)) }
        }
        Paso("Máximo por contacto en una hora", "${a.porContacto}", { cambiar { it.copy(porContacto = (it.porContacto - 1).coerceAtLeast(1)) } }) {
            cambiar { it.copy(porContacto = (it.porContacto + 1).coerceAtMost(10)) }
        }
        Paso("Máximo total en una hora", "${a.global}", { cambiar { it.copy(global = (it.global - 1).coerceAtLeast(1)) } }) {
            cambiar { it.copy(global = (it.global + 1).coerceAtMost(40)) }
        }
    }
}

private fun mover(min: Int, delta: Int) = ((min + delta) % 1440 + 1440) % 1440

private fun hora(min: Int) = "%02d:%02d".format(min / 60, min % 60)

@Composable
private fun Interruptor(texto: String, valor: Boolean, cambio: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(texto, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        Switch(checked = valor, onCheckedChange = cambio)
    }
}

@Composable
private fun Paso(texto: String, valor: String, menos: () -> Unit, mas: () -> Unit) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(texto, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        OutlinedButton(onClick = menos) { Text("−") }
        Text(valor, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
        OutlinedButton(onClick = mas) { Text("+") }
    }
}
