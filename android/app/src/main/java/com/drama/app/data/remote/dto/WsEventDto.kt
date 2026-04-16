package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class WsEventDto(
    val type: String,
    val timestamp: String,
    val data: Map<String, JsonElement> = emptyMap(),
)

@Serializable
data class ReplayMessageDto(
    val type: String = "replay",
    val events: List<WsEventDto> = emptyList(),
)

@Serializable
data class HeartbeatMessageDto(
    val type: String = "ping",
)
