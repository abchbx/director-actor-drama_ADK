package com.drama.app.ui.screens.dramalist

import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

@HiltViewModel  // APP-13, APP-14
class DramaListViewModel @Inject constructor() : ViewModel() {
    private val _uiState = MutableStateFlow("戏剧列表 - 占位")
    val uiState = _uiState.asStateFlow()
}
