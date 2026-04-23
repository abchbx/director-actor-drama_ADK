package com.drama.app.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.graphics.Color
import androidx.core.view.WindowCompat

// 🎭 Light — 白色舞台 + 帷幕红
private val LightColorScheme = lightColorScheme(
    primary = DramaRed,
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFFFCDD2),
    onPrimaryContainer = Color(0xFF7F0000),
    secondary = DramaGold,
    onSecondary = Color(0xFF3E2E00),
    secondaryContainer = Color(0xFFFFE082),
    onSecondaryContainer = Color(0xFF5C4600),
    tertiary = DramaBlueLight,
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFC5CAE9),
    onTertiaryContainer = Color(0xFF0D1452),
    background = DramaSurface,
    onBackground = DramaOnSurface,
    surface = DramaSurface,
    onSurface = DramaOnSurface,
    surfaceVariant = DramaSurfaceVariant,
    onSurfaceVariant = Color(0xFF49454F),
    error = DramaError,
    onError = DramaOnError,
    errorContainer = DramaErrorContainer,
    onErrorContainer = DramaOnErrorContainer,
    outline = Color(0xFF79747E),
    outlineVariant = Color(0xFFCAC4D0),
)

// 🎭 Dark — 深色剧场 + 金色高光
private val DarkColorScheme = darkColorScheme(
    primary = DarkDramaRed,
    onPrimary = Color(0xFF690005),
    primaryContainer = Color(0xFFB71C1C),
    onPrimaryContainer = Color(0xFFFFDAD6),
    secondary = DarkDramaGold,
    onSecondary = Color(0xFF4A3800),
    secondaryContainer = Color(0xFF6B5000),
    onSecondaryContainer = Color(0xFFFFE082),
    tertiary = DarkDramaBlue,
    onTertiary = Color(0xFF1A237E),
    tertiaryContainer = Color(0xFF3949AB),
    onTertiaryContainer = Color(0xFFE0E0FF),
    background = DarkDramaSurface,
    onBackground = DarkDramaOnSurface,
    surface = DarkDramaSurface,
    onSurface = DarkDramaOnSurface,
    surfaceVariant = DarkDramaSurfaceVariant,
    onSurfaceVariant = Color(0xFFCAC4D0),
    error = DarkDramaError,
    onError = DarkDramaOnError,
    errorContainer = DarkDramaErrorContainer,
    onErrorContainer = DarkDramaOnErrorContainer,
    outline = Color(0xFF938F99),
    outlineVariant = Color(0xFF49454F),
)

@Composable
fun DramaTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    // Edge-to-edge
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = android.graphics.Color.TRANSPARENT
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = DramaTypography,
        content = content,
    )
}
