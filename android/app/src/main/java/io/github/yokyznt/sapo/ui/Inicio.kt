package io.github.yokyznt.sapo.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import io.github.yokyznt.sapo.Llave
import io.github.yokyznt.sapo.Permisos
import io.github.yokyznt.sapo.Store

@Composable
fun Inicio(irA: (Int) -> Unit) {
    val ctx = LocalContext.current
    val v by Store.cambios.collectAsState()
    var tick by remember { mutableIntStateOf(0) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { tick++ }
    val lector = remember(tick) { Permisos.lector(ctx) }
    val avisos = remember(tick) { Permisos.avisos(ctx) }
    val bateria = remember(tick) { Permisos.bateria(ctx) }
    val llave = remember(tick, v) { Llave.existe(ctx) }
    var pedido by rememberSaveable { mutableStateOf(false) }
    val pedir = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { tick++ }
    val listo = lector && avisos

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Sapito(Modifier.size(150.dp))
        Text(
            "¡Quiúbole! Soy el Sapo",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold
        )
        Text(
            if (listo) "Ya estoy al tiro con tu WhatsApp. Cuando te escriba alguien de tu lista, te paso una sugerencia y tú decides si la mandas."
            else "Me faltan unos permisitos para echarte la mano. Dale uno por uno 👇",
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyLarge
        )

        Permiso(
            "Leer notificaciones",
            "Así veo los mensajes que te llegan de WhatsApp y WhatsApp Business. Los grupos ni los pelo.",
            lector,
            "Dar acceso"
        ) { Permisos.abrirLector(ctx) }

        Permiso(
            "Mandarte avisos",
            "Para enseñarte la sugerencia con su botón de Enviar.",
            avisos,
            "Permitir"
        ) {
            if (Build.VERSION.SDK_INT >= 33 && !pedido) {
                pedido = true
                pedir.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                Permisos.abrirAvisos(ctx)
            }
        }

        Permiso(
            "Sin ahorro de batería",
            "Para que Android no me duerma a media plática.",
            bateria,
            "Quitar ahorro"
        ) { Permisos.pedirBateria(ctx) }

        if (!lector) {
            Tarjeta("¿El interruptor sale gris?", color = MaterialTheme.colorScheme.secondaryContainer) {
                Text(
                    "Android bloquea los permisos delicados en apps que no vienen de la Play Store. " +
                        "Entra a la info de la app, toca los tres puntitos ⋮ de arriba y elige «Permitir ajustes restringidos». " +
                        "Luego regresa aquí y dale otra vez a «Dar acceso».",
                    style = MaterialTheme.typography.bodyMedium
                )
                FilledTonalButton(onClick = { Permisos.abrirApp(ctx) }) { Text("Abrir info de la app") }
            }
        }

        Tarjeta("Cómo voy") {
            Fila("Contactos en tu lista", Store.ajustes.lista.size.toString())
            Fila("Chats que me aprendí", Store.importado.chats.toString())
            Fila("Key de Gemini", if (llave) "Lista 🔒" else "Falta")
            Text("Último: ${Store.evento}", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!llave) TextButton(onClick = { irA(3) }) { Text("Poner key") }
                if (Store.importado.chats == 0) TextButton(onClick = { irA(2) }) { Text("Importar chats") }
                TextButton(onClick = { irA(1) }) { Text("Contactos") }
            }
        }
    }
}

@Composable
private fun Permiso(titulo: String, texto: String, ok: Boolean, boton: String, accion: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (ok) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainerHigh
        ),
        shape = MaterialTheme.shapes.large
    ) {
        Row(
            Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(if (ok) "✅" else "🟡", fontSize = 24.sp)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(titulo, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(texto, style = MaterialTheme.typography.bodyMedium)
                if (!ok) Button(onClick = accion) { Text(boton) }
            }
        }
    }
}
