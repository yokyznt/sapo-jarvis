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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.unit.dp
import io.github.yokyznt.sapo.Importador
import io.github.yokyznt.sapo.Store
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

            Tarjeta("Tu estilo") {
                Text(
                    imp.descripcion.ifBlank { "Aún no tengo mensajes tuyos para sacar tu estilo. Revisa que «Tú eres» esté bien." },
                    style = MaterialTheme.typography.bodyMedium
                )
            }

            OutlinedButton(
                onClick = { trabajar { Importador.borrar(ctx); "Borré los chats importados 🧹" } },
                enabled = !ocupado
            ) { Text("Borrar chats importados") }
        } else {
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
