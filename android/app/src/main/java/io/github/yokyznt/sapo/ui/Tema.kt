package io.github.yokyznt.sapo.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val VerdeSapo = Color(0xFF89B56E)
val VerdeOscuro = Color(0xFF2F5A22)

private val claro = lightColorScheme(
    primary = Color(0xFF3D6E2C),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDDF0CF),
    onPrimaryContainer = Color(0xFF14300B),
    secondary = Color(0xFF5B6653),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFEDF3E6),
    onSecondaryContainer = Color(0xFF1F2A19),
    tertiary = Color(0xFFB4504D),
    tertiaryContainer = Color(0xFFFDE3E1),
    onTertiaryContainer = Color(0xFF4A1210),
    background = Color(0xFFF6F8F3),
    onBackground = Color(0xFF1B1F18),
    surface = Color(0xFFF6F8F3),
    onSurface = Color(0xFF1B1F18),
    onSurfaceVariant = Color(0xFF5E665A),
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color(0xFFF0F4EC),
    surfaceContainer = Color(0xFFEAF0E5),
    surfaceContainerHigh = Color(0xFFE4EBDE),
    outlineVariant = Color(0xFFDCE3D6)
)

private val oscuro = darkColorScheme(
    primary = Color(0xFFA9D68F),
    onPrimary = Color(0xFF14300B),
    primaryContainer = Color(0xFF2A4A1E),
    onPrimaryContainer = Color(0xFFDDF0CF),
    secondary = Color(0xFFBFCAB5),
    secondaryContainer = Color(0xFF2B3326),
    onSecondaryContainer = Color(0xFFDCE6D2),
    tertiary = Color(0xFFF7A3A0),
    tertiaryContainer = Color(0xFF5C2422),
    onTertiaryContainer = Color(0xFFFDE3E1),
    background = Color(0xFF121511),
    onBackground = Color(0xFFE2E6DD),
    surface = Color(0xFF121511),
    onSurface = Color(0xFFE2E6DD),
    onSurfaceVariant = Color(0xFFA9B1A3),
    surfaceContainerLowest = Color(0xFF1A1E18),
    surfaceContainerLow = Color(0xFF1C211A),
    surfaceContainer = Color(0xFF20261E),
    surfaceContainerHigh = Color(0xFF262D23),
    outlineVariant = Color(0xFF333B2F)
)

private val formas = Shapes(
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(32.dp)
)

private val base = Typography()

private val letras = base.copy(
    headlineMedium = base.headlineMedium.copy(fontWeight = FontWeight.SemiBold, fontSize = 26.sp, lineHeight = 32.sp),
    headlineSmall = base.headlineSmall.copy(fontWeight = FontWeight.SemiBold),
    titleMedium = base.titleMedium.copy(fontWeight = FontWeight.SemiBold),
    titleSmall = base.titleSmall.copy(fontWeight = FontWeight.SemiBold),
    bodyMedium = base.bodyMedium.copy(lineHeight = 21.sp)
)

@Composable
fun SapoTema(contenido: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) oscuro else claro,
        shapes = formas,
        typography = letras,
        content = contenido
    )
}
