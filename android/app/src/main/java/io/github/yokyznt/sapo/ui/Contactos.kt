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
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
        Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        item {
            Column(Modifier.padding(top = 20.dp, bottom = 6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Tu lista blanca", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(
                    "Quien te escriba por WhatsApp aparece aquí. Prende a los que quieras que te ayude a contestar. En grupos, jamás me meto.",
                    style = MaterialTheme.typography.bodyMedium
                )
            }
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
                        "Todavía nadie te ha escrito desde que me prendiste. Aquí te espero, bien sapo 🐸",
                        textAlign = TextAlign.Center
                    )
                }
            }
        }
        items(lista, key = { it.contacto }) { c ->
            val on = c.contacto in activos
            val ultimo = c.mensajes.lastOrNull()
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = if (on) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainerHigh
                ),
                shape = MaterialTheme.shapes.large
            ) {
                Row(
                    Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(c.contacto, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            (if (c.app == "com.whatsapp.w4b") "WhatsApp Business · " else "WhatsApp · ") + formato.format(Date(c.ultima)),
                            style = MaterialTheme.typography.labelSmall
                        )
                        if (ultimo != null) {
                            Text(
                                (if (ultimo.mio) "Tú: " else "") + ultimo.texto,
                                style = MaterialTheme.typography.bodySmall,
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
