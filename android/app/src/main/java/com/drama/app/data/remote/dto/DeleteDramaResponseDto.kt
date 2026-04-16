package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class DeleteDramaResponseDto(
    val status: String = "success",
    val message: String = "",
)
