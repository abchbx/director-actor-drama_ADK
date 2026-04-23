package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

/** POST /drama/chat 请求体 — 群聊模式 */
@Serializable
data class ChatRequestDto(
    val message: String,
    val mention: String? = null,
)
