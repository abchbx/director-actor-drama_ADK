package com.drama.app.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// D-18: Light theme 使用深靛蓝品牌色
private val LightColorScheme = lightColorScheme(
    primary = DeepIndigoPrimary,
    onPrimary = DeepIndigoOnPrimary,
    primaryContainer = DeepIndigoPrimaryContainer,
    onPrimaryContainer = DeepIndigoOnPrimaryContainer,
    secondary = DeepIndigoSecondary,
    onSecondary = DeepIndigoOnSecondary,
    secondaryContainer = DeepIndigoSecondaryContainer,
    onSecondaryContainer = DeepIndigoOnSecondaryContainer,
    tertiary = DeepIndigoTertiary,
    onTertiary = DeepIndigoOnTertiary,
    tertiaryContainer = DeepIndigoTertiaryContainer,
    onTertiaryContainer = DeepIndigoOnTertiaryContainer,
    error = DeepIndigoError,
    onError = DeepIndigoOnError,
    errorContainer = DeepIndigoErrorContainer,
    onErrorContainer = DeepIndigoOnErrorContainer,
)

// D-18: Dark theme 使用调亮的品牌色
private val DarkColorScheme = darkColorScheme(
    primary = DarkDeepIndigoPrimary,
    onPrimary = DarkDeepIndigoOnPrimary,
    primaryContainer = DarkDeepIndigoPrimaryContainer,
    onPrimaryContainer = DarkDeepIndigoOnPrimaryContainer,
    secondary = DarkDeepIndigoSecondary,
    onSecondary = DarkDeepIndigoOnSecondary,
    secondaryContainer = DarkDeepIndigoSecondaryContainer,
    onSecondaryContainer = DarkDeepIndigoOnSecondaryContainer,
    tertiary = DarkDeepIndigoTertiary,
    onTertiary = DarkDeepIndigoOnTertiary,
    tertiaryContainer = DarkDeepIndigoTertiaryContainer,
    onTertiaryContainer = DarkDeepIndigoOnTertiaryContainer,
    error = DarkDeepIndigoError,
    onError = DarkDeepIndigoOnError,
    errorContainer = DarkDeepIndigoErrorContainer,
    onErrorContainer = DarkDeepIndigoOnErrorContainer,
)

@Composable
fun DramaTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),  // D-17: 跟随系统
    dynamicColor: Boolean = true,                  // D-16: Dynamic Color 启用
    content: @Composable () -> Unit,
) {
    // D-16: Dynamic Color 仅 API 31+ 可用，Pitfall 6 防护
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context)
            else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    // Edge-to-edge 配置：状态栏和导航栏透明
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
        typography = DramaTypography,  // D-19
        content = content,
    )
}
