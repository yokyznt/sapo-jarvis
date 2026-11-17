package io.github.yokyznt.sapo.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val VerdeSapo = Color(0xFF7ED957)
val VerdeOscuro = Color(0xFF2E6B1F)
val Pecas = Color(0xFF4FA83A)
val Lengua = Color(0xFFFF5C7A)

private val claro = lightColorScheme(
    primary = Color(0xFF2E7D32),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFCDF5B8),
    onPrimaryContainer = Color(0xFF0D3A0A),
    secondary = Color(0xFF55624C),
    secondaryContainer = Color(0xFFE1F2D3),
    tertiary = Color(0xFFC2185B),
    background = Color(0xFFF1FBEA),
    surface = Color(0xFFF1FBEA),
    surfaceContainer = Color(0xFFE6F4DD),
    surfaceContainerHigh = Color(0xFFDDEFD2)
)

private val oscuro = darkColorScheme(
    primary = VerdeSapo,
    onPrimary = Color(0xFF0D3A0A),
    primaryContainer = Color(0xFF1F5214),
    onPrimaryContainer = Color(0xFFCDF5B8),
    secondaryContainer = Color(0xFF2B3A24),
    tertiary = Color(0xFFFF8FA6),
    background = Color(0xFF111A0E),
    surface = Color(0xFF111A0E),
    surfaceContainer = Color(0xFF1A2616),
    surfaceContainerHigh = Color(0xFF22301D)
)

@Composable
fun SapoTema(contenido: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) oscuro else claro, content = contenido)
}
