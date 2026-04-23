import re

with open('DramaListScreen.kt', 'r') as f:
    content = f.read()

# Find all GlassyMenuItem blocks with their exact line ranges
blocks = []
for m in re.finditer(r'/\*[\s\S]*?玻璃态菜单项[\s\S]*?\*/\s*@Composable\s*\nprivate fun GlassyMenuItem\s*\([^)]*\)\s*\{', content):
    blocks.append((m.start(), m.end()))

print(f'Found {len(blocks)} GlassyMenuItem blocks:')
for s, e in blocks:
    print(f'  Lines {s+1}-{e}')

# Remove ALL blocks from bottom to top (to preserve line numbers of earlier code)
for start, end in reversed(blocks):
    content = content[:start] + content[end:]

# Now add a SINGLE GlassyMenuItem at the very end
glassy = '''

/**
 * 玻璃态菜单项 — iOS 风格系统菜单行
 * 带图标、标签、悬停高亮效果
 */
@Composable
private fun GlassyMenuItem(
    icon: @Composable () -> Unit,
    label: String,
    labelColor: Color = MaterialTheme.colorScheme.onSurface,
    onClick: () -> Unit,
) {
    var isPressed by remember { mutableStateOf(false) }
    Surface(
        shape = RoundedCornerShape(10.dp),
        color = if (isPressed) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f) else Color.Transparent,
        modifier = Modifier
            .fillMaxWidth()
            .clickable(interactionSource = null, indication = null) { onClick() }
            .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            icon()
            Spacer(modifier = Modifier.width(12.dp))
            Text(text = label, style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium, color = labelColor)
        }
    }
}
'''

with open('DramaListScreen.kt', 'w') as f:
    f.write(content + glassy)

with open('DramaListScreen.kt', 'r') as f:
    c2 = f.read()
print(f'Final lines: {len(c2.splitlines())}')
print(f'GlassyMenuItem count: {len(re.findall(r"private fun GlassyMenuItem", c2))}')
