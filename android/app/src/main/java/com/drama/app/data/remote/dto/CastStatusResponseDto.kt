package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class CastStatusResponseDto(
    val status: String = "success",
    val actors: Map<String, JsonElement> = emptyMap(),
    val scene_cast: List<String>? = null,
)
