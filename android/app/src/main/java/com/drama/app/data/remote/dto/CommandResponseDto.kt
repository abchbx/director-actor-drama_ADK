package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class CommandResponseDto(
    val final_response: String = "",
    val tool_results: List<Map<String, JsonElement>> = emptyList(),
    val status: String = "success",
    val message: String = "",
)
