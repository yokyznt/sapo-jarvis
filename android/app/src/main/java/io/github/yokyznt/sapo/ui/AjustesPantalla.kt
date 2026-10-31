package io.github.yokyznt.sapo.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import io.github.yokyznt.sapo.Gemini
import io.github.yokyznt.sapo.Llave
import io.github.yokyznt.sapo.Permisos
import io.github.yokyznt.sapo.Store
import kotlinx.coroutines.launch

@Composable
fun AjustesPantalla() {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var key by remember { mutableStateOf("") }
    var tieneKey by remember { mutableStateOf(Llave.existe(ctx)) }
    var modelo by remember { mutableStateOf(Store.ajustes.modelo) }
    var mensaje by remember { mutableStateOf<String?>(null) }
    var probando by remember { mutableStateOf(false) }
    val version = remember {
        runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull().orEmpty()
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Ajustes", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        Tarjeta("Key de Gemini") {
            Text(
                "Con tu propia key le pregunto a Gemini qué contestar. Se guarda cifrada con el Keystore de Android y solo sale hacia Google.",
                style = MaterialTheme.typography.bodySmall
            )
            OutlinedTextField(
                value = key,
                onValueChange = { key = it },
                label = { Text(if (tieneKey) "Ya hay una guardada 🔒" else "Pega tu key") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                modifier = Modifier.fillMaxWidth()
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    mensaje = runCatching {
                        Llave.guardar(ctx, key.trim())
                        key = ""
                        tieneKey = Llave.existe(ctx)
                        Store.avisar()
                        "Guardada y cifradita 🔒"
                    }.getOrElse { "No pude guardarla: ${it.message}" }
                }, enabled = key.isNotBlank()) { Text("Guardar") }
                OutlinedButton(onClick = {
                    probando = true
                    scope.launch {
                        mensaje = runCatching {
                            val k = Llave.leer(ctx) ?: error("Primero guarda una key")
                            Gemini.generar(k, Store.ajustes.modelo, "Saluda en cinco palabras como un sapo mexicano simpático.")
                        }.fold({ "Gemini dice: $it" }, { "No jaló: ${it.message}" })
                        probando = false
                    }
                }, enabled = tieneKey && !probando) { Text(if (probando) "Probando…" else "Probar") }
                if (tieneKey) TextButton(onClick = {
                    Llave.borrar(ctx)
                    tieneKey = false
                    Store.avisar()
                    mensaje = "Key borrada"
                }) { Text("Borrar") }
            }
            mensaje?.let { Text(it, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold) }
            TextButton(onClick = { Permisos.abrirWeb(ctx, "https://aistudio.google.com/apikey") }) {
                Text("Sacar una key gratis en Google AI Studio")
            }
        }

        Tarjeta("Modelo") {
            OutlinedTextField(
                value = modelo,
                onValueChange = { modelo = it },
                label = { Text("Modelo de Gemini") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Button(
                onClick = {
                    Store.ponerModelo(modelo.trim())
                    modelo = Store.ajustes.modelo
                    mensaje = "Modelo: ${Store.ajustes.modelo}"
                },
                enabled = modelo.trim() != Store.ajustes.modelo
            ) { Text("Guardar modelo") }
        }

        TuPc()

        ModoAutomatico()

        Tarjeta("Cómo me porto") {
            Text(
                "• Solo leo WhatsApp y WhatsApp Business.\n" +
                    "• Nunca me meto en grupos.\n" +
                    "• Solo sugiero para contactos de tu lista; tú decides si se manda, salvo en modo automático.\n" +
                    "• Tus chats, tu estilo y tu historial se quedan en el cel.\n" +
                    "• Si vinculas tu PC, solo le mando tu perfil de estilo y si estás ocupado; nunca tus mensajes.",
                style = MaterialTheme.typography.bodyMedium
            )
        }

        Text("Sapo $version", style = MaterialTheme.typography.labelSmall)
    }
}
