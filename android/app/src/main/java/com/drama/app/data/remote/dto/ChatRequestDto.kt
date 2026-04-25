package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

/** POST /drama/chat 请求体 — 群聊模式，支持主角身份标识 */
@Serializable
data class ChatRequestDto(
    val message: String,
    val mention: String? = null,
    /** 发送者类型标识 — 用于服务端识别主角身份 */
    val senderType: String = "user",
    /** 发送者名称 — 主角的自定义名称，默认"主角" */
    val senderName: String = "主角",
)
