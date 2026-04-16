package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class DramaItemDto(
    val folder: String = "",
    val theme: String = "",
    val status: String = "unknown",
    val updated_at: String = "Unknown",
    val current_scene: Int = 0,
    val snapshots: List<String> = emptyList(),
)
