package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class CastResponseDto(
    val status: String = "success",
    val actors: Map<String, JsonElement> = emptyMap(),
)
