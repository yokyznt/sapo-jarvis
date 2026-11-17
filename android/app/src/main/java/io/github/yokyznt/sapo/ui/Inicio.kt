package io.github.yokyznt.sapo.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import io.github.yokyznt.sapo.Enlace
import io.github.yokyznt.sapo.Fase
import io.github.yokyznt.sapo.Llave
import io.github.yokyznt.sapo.Permisos
import io.github.yokyznt.sapo.Store
import io.github.yokyznt.sapo.flotante.SapoFlotante

private class Paso(val titulo: String, val texto: String, val boton: String, val listo: Boolean, val accion: () -> Unit)

@Composable
fun Inicio(irA: (Int) -> Unit, verHistorial: () -> Unit) {
    val ctx = LocalContext.current
    val v by Store.cambios.collectAsState()
    var tick by remember { mutableIntStateOf(0) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { tick++ }
    val lector = remember(tick) { Permisos.lector(ctx) }
    val avisos = remember(tick) { Permisos.avisos(ctx) }
    val bateria = remember(tick) { Permisos.bateria(ctx) }
    val llave = remember(tick, v) { Llave.existe(ctx) }
    val accesible = remember(tick) { Permisos.accesibilidad(ctx) }
    val aprendidos = remember(v) { Store.aprendidos() }
    val pc = Enlace.estado.collectAsState().value
    var pedido by rememberSaveable { mutableStateOf(false) }
    val pedir = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { tick++ }

    val pasos = listOf(
        Paso("Leer notificaciones", "Así veo lo que te llega por WhatsApp. Los grupos no los toco.", "Activar", lector) { Permisos.abrirLector(ctx) },
        Paso("Mandarte avisos", "Para enseñarte la respuesta con su botón de Enviar.", "Permitir", avisos) {
            if (Build.VERSION.SDK_INT >= 33 && !pedido) {
                pedido = true
                pedir.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                Permisos.abrirAvisos(ctx)
            }
        },
        Paso("Quitar ahorro de batería", "Para que Android no me duerma.", "Quitar", bateria) { Permisos.pedirBateria(ctx) },
        Paso("Poner tu key de Gemini", "Es gratis y se guarda cifrada en tu cel.", "Poner", llave) { irA(3) }
    )
    val faltan = pasos.filterNot { it.listo }
    val listo = lector && avisos

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Column(
            Modifier.fillMaxWidth().padding(top = 28.dp, bottom = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Sapito(Modifier.size(128.dp))
            Spacer(Modifier.height(4.dp))
            Text(if (listo) "Todo listo" else "Hola, soy el Sapo", style = MaterialTheme.typography.headlineMedium)
            Text(
                if (listo) "Cuando alguien de tu lista te escriba, te paso una respuesta y tú decides si se manda."
                else "Te ayudo a contestar WhatsApp con tu forma de escribir.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
        }

        if (faltan.isNotEmpty()) Pasos(pasos, faltan, mostrarTruco = !lector)

        SapitoFlotante(tick, v) { tick++ }

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Dato(Store.ajustes.lista.size.toString(), "contactos", Modifier.weight(1f)) { irA(1) }
            Dato(Store.importado.chats.toString(), "chats leídos", Modifier.weight(1f)) { irA(2) }
            Dato(aprendidos.toString(), "aprendidos", Modifier.weight(1f)) { irA(2) }
        }

        Tarjeta(null) {
            if (Store.ajustes.pc != null) {
                Renglon(
                    "Tu PC",
                    Enlace.texto(pc).replace(" ✅", "").replace(" 🎮", ""),
                    inicio = { Punto(pc.fase == Fase.Conectado) }
                )
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
            Renglon(
                "Aprender cómo escribes",
                if (accesible) "Activo. Nada sale del cel." else "Opcional: miro solo el cuadro de texto de WhatsApp.",
                inicio = { Punto(accesible) }
            ) {
                if (!accesible) TextButton(onClick = { Permisos.abrirAccesibilidad(ctx) }) { Text("Activar") }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Renglon("Lo que contesté solo", Store.evento) {
                TextButton(onClick = verHistorial) { Text("Ver") }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun Pasos(pasos: List<Paso>, faltan: List<Paso>, mostrarTruco: Boolean) {
    val ctx = LocalContext.current
    var truco by rememberSaveable { mutableStateOf(false) }
    val hechos = pasos.size - faltan.size
    Tarjeta(null, color = MaterialTheme.colorScheme.surfaceContainerLowest) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Para empezar", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
            Text("$hechos de ${pasos.size}", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        LinearProgressIndicator(
            progress = { hechos / pasos.size.toFloat() },
            modifier = Modifier.fillMaxWidth(),
            trackColor = MaterialTheme.colorScheme.surfaceContainerHigh,
            drawStopIndicator = {}
        )
        faltan.forEachIndexed { i, p ->
            if (i > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Renglon(
                p.titulo,
                p.texto,
                inicio = { Numero(i + 1) }
            ) {
                val relleno = PaddingValues(horizontal = 16.dp, vertical = 8.dp)
                if (i == 0) Button(onClick = p.accion, contentPadding = relleno) { Text(p.boton) }
                else FilledTonalButton(onClick = p.accion, contentPadding = relleno) { Text(p.boton) }
            }
        }
        if (mostrarTruco) {
            TextButton(onClick = { truco = !truco }, modifier = Modifier.padding(start = 0.dp)) {
                Text(if (truco) "Ocultar ayuda" else "¿El interruptor sale gris?")
            }
            AnimatedVisibility(truco) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "Android bloquea esos permisos en apps que no vienen de la Play Store. En la info de la app toca ⋮ y elige «Permitir ajustes restringidos», luego regresa.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    FilledTonalButton(onClick = { Permisos.abrirApp(ctx) }) { Text("Abrir info de la app") }
                }
            }
        }
    }
}

@Composable
private fun Numero(n: Int) {
    Surface(Modifier.size(30.dp), shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer) {
        Box(contentAlignment = Alignment.Center) {
            Text(n.toString(), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
        }
    }
}

@Composable
private fun Dato(valor: String, nombre: String, modifier: Modifier = Modifier, alTocar: () -> Unit) {
    Surface(
        onClick = alTocar,
        modifier = modifier,
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surfaceContainerLowest
    ) {
        Column(Modifier.padding(vertical = 16.dp, horizontal = 14.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(valor, style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
            Text(nombre, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun SapitoFlotante(tick: Int, v: Int, refrescar: () -> Unit) {
    val ctx = LocalContext.current
    val quiere = remember(v) { Store.ajustes.flotante }
    val encima = remember(tick) { Permisos.encima(ctx) }
    val mic = remember(tick) { Permisos.tiene(ctx, Manifest.permission.RECORD_AUDIO) }
    val pedir = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        refrescar()
        if (Store.ajustes.flotante && !Permisos.encima(ctx)) Permisos.abrirEncima(ctx)
        SapoFlotante.sincronizar(ctx)
    }
    LaunchedEffect(tick, v) { SapoFlotante.sincronizar(ctx) }

    Tarjeta(null, color = if (quiere && encima) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainerLowest) {
        Renglon("Sapito flotante", "Flota encima de todo. Tócalo y háblale; déjalo apretado para su menú.") {
            Switch(checked = quiere, onCheckedChange = { on ->
                Store.ponerFlotante(on)
                if (!on) {
                    SapoFlotante.sincronizar(ctx)
                } else {
                    val faltan = buildList {
                        if (!Permisos.tiene(ctx, Manifest.permission.RECORD_AUDIO)) add(Manifest.permission.RECORD_AUDIO)
                        if (Build.VERSION.SDK_INT >= 33 && !Permisos.avisos(ctx)) add(Manifest.permission.POST_NOTIFICATIONS)
                    }
                    when {
                        faltan.isNotEmpty() -> pedir.launch(faltan.toTypedArray())
                        !Permisos.encima(ctx) -> Permisos.abrirEncima(ctx)
                        else -> SapoFlotante.sincronizar(ctx)
                    }
                }
            })
        }
        if (quiere && !encima) {
            Text(
                "Me falta «Mostrar encima de otras apps» para poder flotar.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            FilledTonalButton(onClick = { Permisos.abrirEncima(ctx) }) { Text("Dar permiso") }
        }
        if (quiere && encima && !mic) {
            Text(
                "Sin micrófono no te oigo; te lo pido cuando me toques.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
