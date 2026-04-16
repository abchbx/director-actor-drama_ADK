package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.drama.app.data.remote.dto.SceneSummaryDto

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SceneHistorySheet(
    scenes: List<SceneSummaryDto>,
    onSceneClick: (Int) -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = false)

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Text(
            text = "场景历史",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )
        if (scenes.isEmpty()) {
            Box(
                Modifier.fillMaxWidth().padding(32.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text("暂无场景记录")
            }
        } else {
            LazyColumn(modifier = Modifier.padding(horizontal = 16.dp)) {
                items(scenes, key = { it.scene_number }) { scene ->
                    ListItem(
                        headlineContent = { Text("第 ${scene.scene_number} 场") },
                        supportingContent = {
                            if (scene.title.isNotBlank()) Text(scene.title)
                            if (scene.description.isNotBlank()) Text(
                                scene.description,
                                maxLines = 1,
                            )
                        },
                        modifier = Modifier.clickable { onSceneClick(scene.scene_number) },
                    )
                }
            }
        }
        Spacer(modifier = Modifier.height(32.dp))
    }
}
