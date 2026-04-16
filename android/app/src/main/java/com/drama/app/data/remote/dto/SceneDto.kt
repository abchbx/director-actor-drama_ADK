package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class SceneSummaryDto(
    val scene_number: Int = 0,
    val title: String = "",
    val description: String = "",
)

@Serializable
data class ScenesResponseDto(
    val scenes: List<SceneSummaryDto> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class SceneDetailDto(
    val scene_number: Int = 0,
    val title: String = "",
    val narration: String = "",
    val dialogue: List<Map<String, JsonElement>> = emptyList(),
)
