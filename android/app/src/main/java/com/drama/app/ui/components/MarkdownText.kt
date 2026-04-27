package com.drama.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import kotlinx.coroutines.delay
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.drama.app.ui.theme.DramaColors

/**
 * 支持 Markdown 渲染和链接点击的文本组件
 * 
 * 使用原生 Compose API 实现，支持：
 * - **加粗**
 * - *斜体*
 * - `行内代码`
 * - [链接](url)
 *
 * @param markdown Markdown 格式的文本
 * @param style 基础文本样式
 * @param modifier Compose 修饰符
 * @param enableLinks 是否启用链接点击
 * @param config Markdown 配置（可选）
 */
@Composable
fun MarkdownText(
    markdown: String,
    modifier: Modifier = Modifier,
    style: TextStyle = MaterialTheme.typography.bodyLarge,
    enableLinks: Boolean = true,
    config: MarkdownConfig = MarkdownConfig(),
) {
    val uriHandler = LocalUriHandler.current
    
    // 计算实际的强调色
    val actualPrimaryColor = config.actorColor.primary ?: style.color
    val actualSecondaryColor = config.actorColor.secondary ?: style.color.copy(alpha = 0.7f)
    val actualTertiaryColor = config.actorColor.tertiary ?: DramaColors.LinkBlue
    
    // 代码块背景色
    val codeBackgroundColor = config.quoteStyle.backgroundColor
        ?: actualSecondaryColor.copy(alpha = 0.12f)

    // 解析 Markdown 并构建 AnnotatedString
    val annotatedString = remember(markdown, style, config) {
        parseMarkdownToAnnotatedString(
            markdown = markdown,
            style = style,
            primaryColor = actualPrimaryColor,
            secondaryColor = actualSecondaryColor,
            tertiaryColor = actualTertiaryColor,
            codeBackgroundColor = codeBackgroundColor,
            enableLinks = enableLinks,
        )
    }

    SelectionContainer {
        Text(
            text = annotatedString,
            modifier = modifier.clickable {
                // 处理链接点击
                if (enableLinks) {
                    val linkPattern = Regex("""\[([^\]]+)\]\(([^)]+)\)""")
                    linkPattern.findAll(markdown).forEach { match ->
                        val url = match.groupValues[2]
                        try {
                            uriHandler.openUri(url)
                        } catch (e: Exception) {
                            // 静默处理
                        }
                    }
                }
            },
            style = style.copy(
                lineHeight = (style.fontSize.value * (if (config.mixedLanguage.enabled) config.mixedLanguage.lineHeightMultiplier else 1.5f)).sp,
                letterSpacing = if (config.mixedLanguage.enabled) config.mixedLanguage.letterSpacing.sp else 0.sp,
            ),
        )
    }
}

/**
 * 旁白专用的 MarkdownText，默认为斜体和淡色风格
 */
@Composable
fun NarrationMarkdownText(
    markdown: String,
    modifier: Modifier = Modifier,
    enableLinks: Boolean = true,
) {
    val baseStyle = MaterialTheme.typography.bodyLarge.copy(
        fontStyle = FontStyle.Italic,
        lineHeight = 24.sp,
        letterSpacing = 0.3.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )

    val narrationConfig = MarkdownConfig(
        actorColor = ActorEmphasizeColor(
            primary = Color(0xFF6A5ACD).copy(alpha = 0.9f),
        ),
        paragraphSpacing = ParagraphSpacing(
            enabled = true,
            paragraphTopSpacing = 8,
            paragraphBottomSpacing = 6,
        ),
        mixedLanguage = MixedLanguageConfig(
            enabled = true,
            letterSpacing = 0.3f,
            chineseLetterSpacing = 0.8f,
            lineHeightMultiplier = 1.6f,
        ),
    )

    MarkdownText(
        markdown = markdown,
        modifier = modifier,
        style = baseStyle,
        config = narrationConfig,
    )
}

/**
 * 微信引用风格的消息文本
 */
@Composable
fun WeChatQuoteText(
    text: String,
    modifier: Modifier = Modifier,
    quoteColor: Color = MaterialTheme.colorScheme.primary,
    backgroundColor: Color = MaterialTheme.colorScheme.surfaceVariant,
    style: TextStyle = MaterialTheme.typography.bodyLarge,
) {
    Row(modifier = modifier) {
        // 左侧引用条
        Box(
            modifier = Modifier
                .width(4.dp)
                .fillMaxWidth()
                .clip(RoundedCornerShape(2.dp))
                .background(quoteColor)
        )

        Spacer(modifier = Modifier.width(12.dp))

        MarkdownText(
            markdown = text,
            style = style.copy(
                lineHeight = 22.sp,
            ),
            config = MarkdownConfig(
                actorColor = ActorEmphasizeColor(
                    primary = quoteColor,
                    secondary = quoteColor.copy(alpha = 0.7f),
                ),
            ),
            modifier = Modifier.weight(1f),
        )
    }
}

/**
 * 带圆角背景的代码块文本
 */
@Composable
fun CodeBlockText(
    code: String,
    modifier: Modifier = Modifier,
    backgroundColor: Color = MaterialTheme.colorScheme.surfaceVariant,
    textColor: Color = MaterialTheme.colorScheme.onSurfaceVariant,
    showLineNumbers: Boolean = false,
) {
    Box(
        modifier = modifier
            .widthIn(max = 320.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(backgroundColor)
            .padding(12.dp)
    ) {
        if (showLineNumbers) {
            Row {
                val lines = code.lines()
                Column(
                    modifier = Modifier.padding(end = 12.dp),
                    horizontalAlignment = androidx.compose.ui.Alignment.End,
                ) {
                    lines.forEachIndexed { index, _ ->
                        Text(
                            text = "${index + 1}",
                            style = MaterialTheme.typography.bodySmall.copy(
                                fontFamily = FontFamily.Monospace,
                                color = textColor.copy(alpha = 0.5f),
                            ),
                        )
                    }
                }
                Spacer(modifier = Modifier.width(8.dp))
                Column {
                    lines.forEach { line ->
                        Text(
                            text = line,
                            style = MaterialTheme.typography.bodyMedium.copy(
                                fontFamily = FontFamily.Monospace,
                                color = textColor,
                            ),
                        )
                    }
                }
            }
        } else {
            Text(
                text = code,
                style = MaterialTheme.typography.bodyMedium.copy(
                    fontFamily = FontFamily.Monospace,
                    color = textColor,
                    lineHeight = 20.sp,
                ),
            )
        }
    }
}

/**
 * 解析 Markdown 文本为 AnnotatedString
 */
private fun parseMarkdownToAnnotatedString(
    markdown: String,
    style: TextStyle,
    primaryColor: Color,
    secondaryColor: Color,
    tertiaryColor: Color,
    codeBackgroundColor: Color,
    enableLinks: Boolean,
): androidx.compose.ui.text.AnnotatedString {
    return buildAnnotatedString {
        var currentIndex = 0
        val text = markdown
        
        // 处理每一行
        val lines = text.lines()
        lines.forEachIndexed { lineIndex, line ->
            appendLineContent(
                line = line,
                style = style,
                primaryColor = primaryColor,
                secondaryColor = secondaryColor,
                tertiaryColor = tertiaryColor,
                codeBackgroundColor = codeBackgroundColor,
                enableLinks = enableLinks,
            )
            if (lineIndex < lines.size - 1) {
                append("\n")
            }
        }
    }
}

private fun androidx.compose.ui.text.AnnotatedString.Builder.appendLineContent(
    line: String,
    style: TextStyle,
    primaryColor: Color,
    secondaryColor: Color,
    tertiaryColor: Color,
    codeBackgroundColor: Color,
    enableLinks: Boolean,
) {
    var currentLine = line
    
    // 处理代码块 ```...```
    if (currentLine.startsWith("```")) {
        withStyle(SpanStyle(fontFamily = FontFamily.Monospace)) {
            append(currentLine.removePrefix("```").removeSuffix("```"))
        }
        return
    }
    
    // 处理标题 # ## ###
    when {
        currentLine.startsWith("### ") -> {
            withStyle(SpanStyle(fontWeight = FontWeight.SemiBold, fontSize = (style.fontSize.value * 0.85f).sp)) {
                append(currentLine.removePrefix("### "))
            }
            return
        }
        currentLine.startsWith("## ") -> {
            withStyle(SpanStyle(fontWeight = FontWeight.Bold, fontSize = (style.fontSize.value * 0.9f).sp)) {
                append(currentLine.removePrefix("## "))
            }
            return
        }
        currentLine.startsWith("# ") -> {
            withStyle(SpanStyle(fontWeight = FontWeight.Bold, fontSize = (style.fontSize.value * 1.1f).sp)) {
                append(currentLine.removePrefix("# "))
            }
            return
        }
    }
    
    // 处理链接 [text](url)
    processInlineMarkdown(
        text = currentLine,
        style = style,
        primaryColor = primaryColor,
        secondaryColor = secondaryColor,
        tertiaryColor = tertiaryColor,
        codeBackgroundColor = codeBackgroundColor,
        enableLinks = enableLinks,
    )
}

private fun androidx.compose.ui.text.AnnotatedString.Builder.processInlineMarkdown(
    text: String,
    style: TextStyle,
    primaryColor: Color,
    secondaryColor: Color,
    tertiaryColor: Color,
    codeBackgroundColor: Color,
    enableLinks: Boolean,
) {
    // 正则匹配 Markdown 内联元素
    val patterns = mutableListOf<Triple<Regex, SpanStyle, Int>>()
    
    patterns.add(Triple(Regex("""\*\*([^*]+)\*\*"""), SpanStyle(fontWeight = FontWeight.Bold, color = primaryColor), 2))
    patterns.add(Triple(Regex("""\*([^*]+)\*"""), SpanStyle(fontStyle = FontStyle.Italic, color = secondaryColor), 1))
    patterns.add(Triple(Regex("""__([^_]+)__"""), SpanStyle(fontWeight = FontWeight.Bold), 2))
    patterns.add(Triple(Regex("""_([^_]+)_"""), SpanStyle(fontStyle = FontStyle.Italic), 1))
    patterns.add(Triple(Regex("""`([^`]+)`"""), SpanStyle(fontFamily = FontFamily.Monospace, background = primaryColor.copy(alpha = 0.1f)), 1))
    if (enableLinks) {
        patterns.add(Triple(Regex("""\[([^\]]+)\]\(([^)]+)\)"""), SpanStyle(color = tertiaryColor, textDecoration = TextDecoration.Underline), 0))
    }
    
    val matches = mutableListOf<Triple<IntRange, SpanStyle, String>>()
    
    patterns.forEach { (pattern, spanStyle) ->
        pattern.findAll(text).forEach { match ->
            matches.add(Triple(match.range, spanStyle, match.value))
        }
    }
    
    // 按起始位置排序
    matches.sortBy { it.first.first }
    
    // 移除重叠的匹配
    val nonOverlapping = mutableListOf<Triple<IntRange, SpanStyle, String>>()
    var lastEnd = -1
    matches.forEach { match ->
        if (match.first.first >= lastEnd) {
            nonOverlapping.add(match)
            lastEnd = match.first.last + 1
        }
    }
    
    // 构建结果
    var pos = 0
    nonOverlapping.forEach { (range, spanStyle, _) ->
        if (pos < range.first) {
            append(text.substring(pos, range.first))
        }
        withStyle(spanStyle) {
            append(text.substring(range))
        }
        pos = range.last + 1
    }
    
    if (pos < text.length) {
        append(text.substring(pos))
    }
    
    if (text.isEmpty()) {
        append("")
    }
}

/**
 * ★ 打字机效果 Markdown 文本 — 逐字显示，营造流式输出感
 *
 * @param id 气泡唯一 ID，用于保持打字状态
 * @param markdown 完整 Markdown 文本
 * @param typingSpeedMs 每字符延迟（默认 20ms）
 */
@Composable
fun TypewriterMarkdownText(
    id: String,
    markdown: String,
    modifier: Modifier = Modifier,
    style: TextStyle = MaterialTheme.typography.bodyLarge,
    enableLinks: Boolean = true,
    config: MarkdownConfig = MarkdownConfig(),
    typingSpeedMs: Long = 20L,
) {
    var visibleLength by remember(id) { mutableIntStateOf(0) }
    val targetLength = markdown.length

    LaunchedEffect(id, markdown) {
        visibleLength = 0
        while (visibleLength < targetLength) {
            delay(typingSpeedMs)
            visibleLength = (visibleLength + 1).coerceAtMost(targetLength)
        }
    }

    MarkdownText(
        markdown = markdown.take(visibleLength),
        modifier = modifier,
        style = style,
        enableLinks = enableLinks,
        config = config,
    )
}
