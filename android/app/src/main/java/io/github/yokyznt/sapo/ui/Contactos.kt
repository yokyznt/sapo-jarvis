package io.github.yokyznt.sapo.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Surface
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.yokyznt.sapo.Store
import java.text.DateFormat
import java.util.Date

@Composable
fun Contactos() {
    val v by Store.cambios.collectAsState()
    val lista = remember(v) { Store.conversaciones.values.sortedByDescending { it.ultima } }
    val activos = remember(v) { Store.ajustes.lista }
    val formato = remember { DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT) }

    LazyColumn(
        Modifier.fillMaxSize().padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            Encabezado("Contactos", "Prende a quien quieras que te ayude a contestar. En los grupos que prendas te sugiero respuesta, y solo contesto solo cuando te mencionan.")
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
                        "Todavía nadie te ha escrito desde que me prendiste. Aquí van a salir.",
                        textAlign = TextAlign.Center
                    )
                }
            }
        }
        items(lista, key = { it.contacto }) { c ->
            val on = c.contacto in activos
            val ultimo = c.mensajes.lastOrNull()
            Surface(
                color = MaterialTheme.colorScheme.surfaceContainerLowest,
                shape = MaterialTheme.shapes.large
            ) {
                Row(
                    Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Inicial(c.contacto, on)
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(c.contacto, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            (if (c.grupo) "Grupo · " else "") + (if (c.app == "com.whatsapp.w4b") "WhatsApp Business · " else "WhatsApp · ") + formato.format(Date(c.ultima)),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        if (ultimo != null) {
                            Text(
                                (if (ultimo.mio) "Tú: " else if (c.grupo) "${ultimo.autor}: " else "") + ultimo.texto,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                    Switch(checked = on, onCheckedChange = { Store.activar(c.contacto, it) })
                }
            }
        }
        item { Text("", Modifier.padding(bottom = 12.dp)) }
    }
}

@Composable
private fun Inicial(nombre: String, on: Boolean) {
    Surface(
        Modifier.size(42.dp),
        shape = CircleShape,
        color = if (on) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainerHigh
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                nombre.trim().firstOrNull { it.isLetterOrDigit() }?.uppercase() ?: "?",
                style = MaterialTheme.typography.titleMedium,
                color = if (on) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
