package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun TensionIndicator(score: Int, modifier: Modifier = Modifier) {
    // 张力评分 0-10，显示为小型数值标签
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Icon(
            imageVector = Icons.Filled.LocalFireDepartment,
            contentDescription = "张力",
            modifier = Modifier.size(16.dp),
            tint = when {
                score >= 7 -> MaterialTheme.colorScheme.error
                score >= 4 -> MaterialTheme.colorScheme.tertiary
                else -> MaterialTheme.colorScheme.onSurfaceVariant
            },
        )
        Text(
            text = "$score",
            style = MaterialTheme.typography.labelMedium,
        )
    }
}
