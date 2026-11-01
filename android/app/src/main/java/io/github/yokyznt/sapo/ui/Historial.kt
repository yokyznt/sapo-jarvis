package io.github.yokyznt.sapo.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import io.github.yokyznt.sapo.Store
import java.text.DateFormat
import java.util.Date

@Composable
fun Historial() {
    val v by Store.cambios.collectAsState()
    val lista = remember(v) { Store.historial.asReversed() }
    val auto = remember(v) { Store.ajustes.auto }
    val formato = remember { DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT) }

    LazyColumn(
        Modifier.fillMaxSize().padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Encabezado(
                "Lo que contesté solo",
                when {
                    !auto.activo -> "El modo automático está apagado. Lo prendes en Ajustes."
                    auto.pausado -> "Estoy en pausa. No contesto solo hasta que me reactives."
                    else -> "Modo automático prendido. Aquí queda todo lo que mandé por ti."
                },
                Modifier.padding(top = 0.dp)
            )
        }
        if (lista.isEmpty()) {
            item {
                Column(
                    Modifier.fillMaxWidth().padding(top = 40.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Sapito(Modifier.size(110.dp))
                    Text(
                        "Todavía no he contestado nada por mi cuenta.",
                        style = MaterialTheme.typography.bodyMedium,
                        textAlign = TextAlign.Center
                    )
                }
            }
        } else {
            items(lista, key = { "${it.contacto}-${it.hora}" }) { r ->
                Tarjeta(r.contacto) {
                    Text(
                        "${formato.format(Date(r.hora))} · ${r.razon}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Text(r.entrante, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) {
                        Text(r.respuesta, Modifier.padding(horizontal = 14.dp, vertical = 10.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
                    }
                }
            }
        }
        item { Column(Modifier.padding(bottom = 12.dp)) {} }
    }
}
