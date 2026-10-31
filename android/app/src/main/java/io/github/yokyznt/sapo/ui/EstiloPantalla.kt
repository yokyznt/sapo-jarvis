package io.github.yokyznt.sapo.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import io.github.yokyznt.sapo.Importador
import io.github.yokyznt.sapo.Permisos
import io.github.yokyznt.sapo.Store
import io.github.yokyznt.sapo.core.Style
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun EstiloPantalla() {
    val ctx = LocalContext.current
    val v by Store.cambios.collectAsState()
    val imp = remember(v) { Store.importado }
    val scope = rememberCoroutineScope()
    var ocupado by remember { mutableStateOf(false) }
    var resultado by remember { mutableStateOf<String?>(null) }
    var yo by remember(imp.yo) { mutableStateOf(imp.yo.orEmpty()) }
    var tick by remember { mutableIntStateOf(0) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { tick++ }
    val accesible = remember(tick) { Permisos.accesibilidad(ctx) }
    val aprendidos = remember(v) { Store.aprendidos() }
    val aprender = remember(v) { Store.ajustes.aprender }
    val perfil = remember(v) { Store.perfil() }

    fun trabajar(accion: () -> String) {
        ocupado = true
        scope.launch {
            resultado = runCatching { withContext(Dispatchers.IO) { accion() } }
                .getOrElse { "Uy, algo tronó: ${it.message}" }
            ocupado = false
        }
    }

    val abrir = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        if (uris.isNotEmpty()) trabajar {
            val n = Importador.importar(ctx, uris)
            if (n == 0) "No encontré ningún chat en esos archivos 🤔" else "¡Listo! Me aprendí $n chat(s) 🐸"
        }
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Cómo escribes tú", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(
            "Pásame chats exportados y aprendo tu forma de escribir: tus emojis, cómo te ríes, qué tan largo contestas. Todo se queda en tu cel.",
            style = MaterialTheme.typography.bodyMedium
        )

        Tarjeta("Cómo exportar un chat") {
            Text(
                "En WhatsApp abre un chat de persona (no grupo) → ⋮ → Más → Exportar chat → Sin archivos. " +
                    "Guárdalo en tu cel y tráelo aquí. Puedes elegir varios .txt o .zip de una vez; entre 10 y 30 chats está chido.",
                style = MaterialTheme.typography.bodyMedium
            )
        }

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(
                onClick = { abrir.launch(arrayOf("text/plain", "application/zip", "text/*")) },
                enabled = !ocupado
            ) { Text("Importar chats") }
            if (ocupado) CircularProgressIndicator(Modifier.size(28.dp))
        }
        resultado?.let { Text(it, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold) }

        Tarjeta("Aprendo mientras escribes") {
            Text(
                "Con el permiso de accesibilidad veo lo que mandas en WhatsApp y aprendo cómo escribes. " +
                    "Solo miro el cuadro de texto y el botón de enviar. Nada sale del cel, salvo tu perfil de estilo hacia tu PC vinculada.",
                style = MaterialTheme.typography.bodySmall
            )
            Text(
                "Aprendido escribiendo: $aprendidos mensajes",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold
            )
            Interruptor("Aprender de lo que escribo", aprender) { Store.ponerAprender(it) }
            Fila("Accesibilidad", if (accesible) "Activa ✅" else "Apagada")
            if (!accesible) {
                Text(
                    "Si el interruptor sale gris, entra a la info de la app, toca ⋮ y elige «Permitir ajustes restringidos».",
                    style = MaterialTheme.typography.bodySmall
                )
                FilledTonalButton(onClick = { Permisos.abrirAccesibilidad(ctx) }) { Text("Abrir ajustes de accesibilidad") }
            }
            if (aprendidos > 0) OutlinedButton(
                onClick = { trabajar { Store.borrarAprendido(); "Borré lo que aprendí mientras escribías 🧹" } },
                enabled = !ocupado
            ) { Text("Borrar lo aprendido") }
        }

        if (imp.chats > 0 || aprendidos > 0) {
            Tarjeta("Tu estilo") {
                Text(
                    if (perfil.samples > 0) Style.describe(perfil)
                    else "Aún no tengo mensajes tuyos para sacar tu estilo. Revisa que «Tú eres» esté bien.",
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }

        if (imp.chats > 0) {
            Tarjeta("Tú eres") {
                Text(
                    "Adiviné tu nombre como aparece en los chats. Si me equivoqué, corrígelo.",
                    style = MaterialTheme.typography.bodySmall
                )
                OutlinedTextField(
                    value = yo,
                    onValueChange = { yo = it },
                    label = { Text("Tú eres") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Button(
                    onClick = {
                        trabajar {
                            Store.ponerYo(yo)
                            Importador.reconstruir(ctx)
                            "Va, ya sé que eres ${Store.importado.yo ?: "tú"} 😎"
                        }
                    },
                    enabled = !ocupado && yo.isNotBlank() && yo.trim() != imp.yo
                ) { Text("Guardar") }
            }

            Tarjeta("Lo que aprendí") {
                Fila("Chats", imp.chats.toString())
                Fila("Mensajes leídos", imp.mensajes.toString())
                Fila("Mensajes tuyos", imp.mios.toString())
                Fila("Ejemplos de respuesta", imp.pares.toString())
            }

            OutlinedButton(
                onClick = { trabajar { Importador.borrar(ctx); "Borré los chats importados 🧹" } },
                enabled = !ocupado
            ) { Text("Borrar chats importados") }
        } else if (aprendidos == 0) {
            Column(
                Modifier.fillMaxWidth().padding(top = 12.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Sapito(Modifier.size(100.dp))
                TextButton(onClick = { abrir.launch(arrayOf("text/plain", "application/zip", "text/*")) }) {
                    Text("Todavía no me enseñas nada, ándale")
                }
            }
        }
    }
}
