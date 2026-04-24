package com.drama.app.ui.components

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Markdown 渲染配置 — 统一管理 Markdown 视觉样式
 *
 * 支持：
 * - 角色强调色（ActorEmphasizeColor）
 * - 圆角背景样式（WeChatStyleQuote）
 * - 段落间距（ParagraphSpacing）
 * - 中英文混排（MixedLanguageSupport）
 */
data class MarkdownConfig(
    // ═══════════════════════════════════════════════════════════
    // 角色强调色配置
    // ═══════════════════════════════════════════════════════════
    val actorColor: ActorEmphasizeColor = ActorEmphasizeColor(),
    val useActorColorForEmphasis: Boolean = true,  // 是否将角色色用于 **加粗** 文字

    // ═══════════════════════════════════════════════════════════
    // 圆角背景样式（微信引用消息风格）
    // ═══════════════════════════════════════════════════════════
    val quoteStyle: QuoteStyle = QuoteStyle(),

    // ═══════════════════════════════════════════════════════════
    // 段落间距配置
    // ═══════════════════════════════════════════════════════════
    val paragraphSpacing: ParagraphSpacing = ParagraphSpacing(),

    // ═══════════════════════════════════════════════════════════
    // 中英文混排配置
    // ═══════════════════════════════════════════════════════════
    val mixedLanguage: MixedLanguageConfig = MixedLanguageConfig(),

    // ═══════════════════════════════════════════════════════════
    // 链接颜色
    // ═══════════════════════════════════════════════════════════
    val linkColor: Color? = null,  // null 时使用默认色
)

/**
 * 角色强调色配置
 * 用于区分不同角色的对话内容
 */
data class ActorEmphasizeColor(
    val primary: Color? = null,      // 主强调色（加粗文字）
    val secondary: Color? = null,     // 次强调色（引用块左边框）
    val tertiary: Color? = null,      // 第三强调色（链接）
)

/**
 * 圆角背景样式（微信引用消息风格）
 */
data class QuoteStyle(
    val enabled: Boolean = true,
    val cornerRadius: Int = 12,           // 圆角大小
    val backgroundColor: Color? = null,   // null 时使用半透明主色
    val leftBorderWidth: Int = 3,          // 左边框宽度
    val padding: Int = 12,                 // 内边距
    val showQuoteBar: Boolean = true,     // 是否显示左侧引用条
)

/**
 * 段落间距配置
 * 解决 Markdown 输出文字拥挤问题
 */
data class ParagraphSpacing(
    val enabled: Boolean = true,
    val paragraphTopSpacing: Int = 8,    // 段落顶部间距 dp
    val paragraphBottomSpacing: Int = 4, // 段落底部间距 dp
    val listItemSpacing: Int = 6,          // 列表项间距 dp
    val headingBottomMargin: Int = 8,      // 标题下方间距 dp
)

/**
 * 中英文混排配置
 */
data class MixedLanguageConfig(
    val enabled: Boolean = true,
    val englishFontFamily: FontFamily = FontFamily.Default,  // 英文/数字字体
    val chineseFontFamily: FontFamily = FontFamily.Default, // 中文字体
    val letterSpacing: Float = 0f,            // 英文字符间距
    val chineseLetterSpacing: Float = 0.5f,   // 中文字符间距（改善阅读）
    val lineHeightMultiplier: Float = 1.5f,   // 行高倍数
)

/**
 * 预设的 MarkdownConfig 工厂方法
 */
object MarkdownConfigs {

    /** 默认配置（浅色主题） */
    val Default = MarkdownConfig()

    /** 旁白/叙事风格 — 淡雅斜体 */
    val Narration = MarkdownConfig(
        actorColor = ActorEmphasizeColor(
            primary = Color(0xFF6B7280),    // 灰色
            secondary = Color(0xFF9CA3AF),
            tertiary = Color(0xFF6B7280),
        ),
        mixedLanguage = MixedLanguageConfig(
            letterSpacing = 0.3f,
            chineseLetterSpacing = 0.8f,
            lineHeightMultiplier = 1.6f,
        ),
    )

    /** 代码风格 — 等宽字体，适合技术内容 */
    val Code = MarkdownConfig(
        quoteStyle = QuoteStyle(
            cornerRadius = 8,
            backgroundColor = Color(0xFFF3F4F6),
            leftBorderWidth = 0,
        ),
        mixedLanguage = MixedLanguageConfig(
            englishFontFamily = FontFamily.Monospace,
            lineHeightMultiplier = 1.4f,
        ),
    )

    /** 微信引用风格 — 圆角气泡 */
    val WeChatQuote = MarkdownConfig(
        quoteStyle = QuoteStyle(
            enabled = true,
            cornerRadius = 16,
            backgroundColor = Color(0xFFF8F9FA),
            leftBorderWidth = 4,
            padding = 14,
            showQuoteBar = true,
        ),
    )

    /**
     * 根据角色名创建配置
     * 使用角色的主题色作为强调色
     */
    fun forActor(
        actorName: String,
        primaryColor: Color,
        backgroundColor: Color = Color.Transparent,
    ): MarkdownConfig {
        return MarkdownConfig(
            actorColor = ActorEmphasizeColor(
                primary = primaryColor,
                secondary = primaryColor.copy(alpha = 0.7f),
                tertiary = primaryColor.copy(alpha = 0.85f),
            ),
            quoteStyle = QuoteStyle(
                enabled = true,
                cornerRadius = 12,
                backgroundColor = backgroundColor,
                leftBorderWidth = 3,
                padding = 12,
                showQuoteBar = true,
            ),
        )
    }

    /**
     * 根据场景类型创建配置
     */
    fun forScene(sceneType: SceneType): MarkdownConfig {
        return when (sceneType) {
            SceneType.DIALOGUE -> Default
            SceneType.NARRATION -> Narration
            SceneType.CODE_BLOCK -> Code
            SceneType.QUOTE -> WeChatQuote
        }
    }
}

/** 场景类型枚举 */
enum class SceneType {
    DIALOGUE,   // 对话
    NARRATION, // 旁白/叙事
    CODE_BLOCK, // 代码块
    QUOTE,      // 引用
}
