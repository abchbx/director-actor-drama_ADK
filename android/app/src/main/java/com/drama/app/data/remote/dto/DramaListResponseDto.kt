package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class DramaListResponseDto(
    val dramas: List<Map<String, JsonElement>> = emptyList(),
)
