package com.drama.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// D-19: titleLarge 加粗，增强戏剧标题气势
// D-20: 形状沿用 MD3 默认 rounded，不做额外定制
val DramaTypography = Typography(
    titleLarge = TextStyle(
        fontWeight = FontWeight.Bold,  // D-19: 唯一定制
        fontSize = 22.sp,
        lineHeight = 28.sp,
        letterSpacing = 0.sp,
    ),
    // 其余全部沿用 MD3 默认值
)
