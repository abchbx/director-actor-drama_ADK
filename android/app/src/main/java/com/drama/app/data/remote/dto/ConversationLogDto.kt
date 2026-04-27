package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class ConversationLogEntryDto(
    val speaker: String = "",
    val content: String = "",
    val type: String = "dialogue",
    val scene: Int = 0,
    val timestamp: String = "",
)

@Serializable
data class ConversationLogResponseDto(
    val status: String = "success",
    val entries: List<ConversationLogEntryDto> = emptyList(),
    val count: Int = 0,
)
