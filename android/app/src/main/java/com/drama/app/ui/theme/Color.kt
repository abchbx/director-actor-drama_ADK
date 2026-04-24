package com.drama.app.ui.theme

import androidx.compose.ui.graphics.Color

// ═══════════════════════════════════════════════════════════
// 🎭 Drama Theme — 戏剧感配色
// 灵感：深红帷幕 + 金色聚光灯 + 午夜蓝舞台
// ═══════════════════════════════════════════════════════════

// Light Theme — 白色舞台 + 帷幕红点缀
val DramaRed = Color(0xFFB71C1C)              // 帷幕深红
val DramaRedLight = Color(0xFFEF5350)          // 浅红
val DramaGold = Color(0xFFFFB300)               // 聚光灯金
val DramaGoldLight = Color(0xFFFFD54F)          // 浅金
val DramaBlue = Color(0xFF1A237E)              // 午夜蓝
val DramaBlueLight = Color(0xFF5C6BC0)          // 浅靛蓝
val DramaSurface = Color(0xFFFAFAFA)            // 舞台白
val DramaOnSurface = Color(0xFF1C1B1F)          // 深墨
val DramaSurfaceVariant = Color(0xFFF5F0EB)     // 暖灰

// Dark Theme — 深色剧场 + 金色高光
val DarkDramaRed = Color(0xFFEF9A9A)            // 暗色红
val DarkDramaGold = Color(0xFFFFD54F)            // 暗色金
val DarkDramaBlue = Color(0xFF9FA8DA)            // 暗色蓝
val DarkDramaSurface = Color(0xFF121212)         // 纯黑舞台
val DarkDramaOnSurface = Color(0xFFE6E1E5)       // 月光白
val DarkDramaSurfaceVariant = Color(0xFF1E1E2E)  // 深紫灰

// 语义色
val DramaError = Color(0xFFB3261E)
val DramaOnError = Color(0xFFFFFFFF)
val DramaErrorContainer = Color(0xFFF9DEDC)
val DramaOnErrorContainer = Color(0xFF410E0B)

val DarkDramaError = Color(0xFFF2B8B5)
val DarkDramaOnError = Color(0xFF601410)
val DarkDramaErrorContainer = Color(0xFF8C1D18)
val DarkDramaOnErrorContainer = Color(0xFFF9DEDC)

// 演员色板 — 为角色头像生成丰富的色调
val ActorPalette = listOf(
    Color(0xFFE57373),  // 珊瑚红
    Color(0xFF64B5F6),  // 天蓝
    Color(0xFF81C784),  // 草绿
    Color(0xFFFFB74D),  // 琥珀
    Color(0xFFBA68C8),  // 紫兰
    Color(0xFF4DD0E1),  // 青碧
    Color(0xFFF06292),  // 粉红
    Color(0xFFAED581),  // 黄绿
    Color(0xFF9575CD),  // 薰衣草
    Color(0xFFFF8A65),  // 橘红
)

// ═══════════════════════════════════════════════════════════
// 📎 Markdown 链接颜色
// ═══════════════════════════════════════════════════════════
object DramaColors {
    val LinkBlue = Color(0xFF1976D2)           // 标准链接蓝
    val LinkBlueDark = Color(0xFF90CAF9)       // 深色主题链接
    val MentionBlue = Color(0xFF0288D1)        // @提及蓝
    val CodeBackground = Color(0xFFF5F5F5)     // 代码块背景
    val DarkCodeBackground = Color(0xFF2D2D2D) // 深色代码背景
}

// ═══════════════════════════════════════════════════════════
// 📝 Markdown 视觉排版配色
// ═══════════════════════════════════════════════════════════
object MarkdownColors {

    // 引用块配色
    object Quote {
        val LightBackground = Color(0xFFF8F9FA)   // 浅色引用背景
        val DarkBackground = Color(0xFF2D2D30)    // 深色引用背景
        val LightBorder = Color(0xFFE0E0E0)       // 浅色左边框
        val DarkBorder = Color(0xFF4A4A4D)        // 深色左边框
        val LightText = Color(0xFF6B7280)          // 浅色引用文字
        val DarkText = Color(0xFF9CA3AF)           // 深色引用文字
    }

    // 代码块配色
    object Code {
        val LightBackground = Color(0xFFF3F4F6)   // 浅色代码背景
        val DarkBackground = Color(0xFF1E1E1E)    // 深色代码背景
        val LightText = Color(0xFF374151)          // 浅色代码文字
        val DarkText = Color(0xFFD4D4D4)           // 深色代码文字
        val InlineBackground = Color(0xFFE8EAED)  // 行内代码背景
    }

    // 强调色
    object Emphasis {
        val LightPrimary = Color(0xFF1F2937)      // 浅色主强调
        val DarkPrimary = Color(0xFFE5E7EB)        // 深色主强调
        val LightSecondary = Color(0xFF4B5563)    // 浅色次强调
        val DarkSecondary = Color(0xFF9CA3AF)      // 深色次强调
    }

    // 标题配色
    object Heading {
        val LightH1 = Color(0xFF111827)           // 浅色 H1
        val LightH2 = Color(0xFF1F2937)            // 浅色 H2
        val LightH3 = Color(0xFF374151)            // 浅色 H3
        val DarkH1 = Color(0xFFF9FAFB)              // 深色 H1
        val DarkH2 = Color(0xFFE5E7EB)              // 深色 H2
        val DarkH3 = Color(0xFFD1D5DB)              // 深色 H3
    }

    // 微信引用风格配色
    object WeChat {
        val LightBubbleBg = Color(0xFFF0F0F0)      // 浅色气泡背景
        val DarkBubbleBg = Color(0xFF3A3A3C)       // 深色气泡背景
        val LightQuoteBar = Color(0xFF07C160)      // 浅色引用条（微信绿）
        val DarkQuoteBar = Color(0xFF4CAF50)       // 深色引用条
    }
}
