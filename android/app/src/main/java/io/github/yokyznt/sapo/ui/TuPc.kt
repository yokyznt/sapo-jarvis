package io.github.yokyznt.sapo.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import io.github.yokyznt.sapo.Enlace
import io.github.yokyznt.sapo.Fase
import io.github.yokyznt.sapo.PcEncontrada
import io.github.yokyznt.sapo.Store
import kotlinx.coroutines.launch

@Composable
fun TuPc() {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val v by Store.cambios.collectAsState()
    val estado by Enlace.estado.collectAsState()
    val pc = remember(v) { Store.ajustes.pc }
    val conectar = remember(v) { Store.ajustes.enlace }
    var buscando by remember { mutableStateOf(false) }
    var halladas by remember { mutableStateOf<List<PcEncontrada>?>(null) }
    var elegida by remember { mutableStateOf<PcEncontrada?>(null) }
    var codigo by remember { mutableStateOf("") }
    var vinculando by remember { mutableStateOf(false) }
    var mensaje by remember { mutableStateOf<String?>(null) }

    Tarjeta("Tu PC 💻") {
        Text(
            "Conecto el Sapo con el sapo de tu PC en la misma red Wi-Fi. Solo le paso tu perfil de estilo y si estás ocupado; " +
                "ella me avisa cuando estás jugando. Tus mensajes no salen del cel.",
            style = MaterialTheme.typography.bodySmall
        )
        if (pc != null) {
            Fila("Vinculada", pc.nombre)
            Fila("Estado", Enlace.texto(estado))
            if (estado.detalle.isNotBlank() && estado.fase != Fase.Conectado) {
                Text(estado.detalle, style = MaterialTheme.typography.bodySmall)
            }
            Interruptor("Conectar con mi PC", conectar) { Enlace.activar(ctx, it) }
            OutlinedButton(onClick = {
                Enlace.desvincular(ctx)
                halladas = null
                elegida = null
                codigo = ""
                mensaje = "Listo, ya no estoy vinculado con esa PC"
            }) { Text("Desvincular") }
        } else {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(
                    onClick = {
                        buscando = true
                        mensaje = null
                        scope.launch {
                            val r = runCatching { Enlace.buscar(ctx) }.getOrDefault(emptyList())
                            halladas = r
                            elegida = r.singleOrNull()
                            buscando = false
                        }
                    },
                    enabled = !buscando && !vinculando
                ) { Text(if (halladas == null) "Buscar mi PC" else "Buscar otra vez") }
                if (buscando) CircularProgressIndicator(Modifier.size(28.dp))
            }
            halladas?.let { lista ->
                if (lista.isEmpty()) {
                    Text(
                        "No encontré ninguna PC. Revisa que estén en la misma red y que en Preferencias del Sapo de tu PC esté prendido el enlace con el cel.",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                lista.forEach { p ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(selected = elegida == p, onClick = { elegida = p })
                        Text("${p.nombre} (${p.host})", style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            elegida?.let { p ->
                OutlinedTextField(
                    value = codigo,
                    onValueChange = { t -> codigo = t.filter { it.isDigit() }.take(6) },
                    label = { Text("Código de 6 dígitos que muestra tu PC") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    modifier = Modifier.fillMaxWidth()
                )
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(
                        onClick = {
                            vinculando = true
                            mensaje = null
                            scope.launch {
                                val error = runCatching { Enlace.vincular(ctx, p, codigo) }.getOrElse { it.message ?: "Algo tronó" }
                                mensaje = error ?: "¡Listo! Ya estoy vinculado con ${p.nombre} 🐸"
                                if (error == null) {
                                    halladas = null
                                    elegida = null
                                }
                                codigo = ""
                                vinculando = false
                            }
                        },
                        enabled = codigo.length == 6 && !vinculando
                    ) { Text("Vincular") }
                    if (vinculando) CircularProgressIndicator(Modifier.size(28.dp))
                }
            }
        }
        mensaje?.let { Text(it, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold) }
    }
}
