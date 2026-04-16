package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class AuthVerifyResponseDto(
    val valid: Boolean = true,
    val mode: String = "token",  // "token" | "bypass"
)
