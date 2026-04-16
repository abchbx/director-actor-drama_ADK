package com.drama.app.ui.screens.dramadetail

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

@Composable
fun DramaDetailScreen(
    dramaId: String,
    viewModel: DramaDetailViewModel = androidx.hilt.navigation.compose.hiltViewModel(),
) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = "戏剧详情: $dramaId")
    }
}
