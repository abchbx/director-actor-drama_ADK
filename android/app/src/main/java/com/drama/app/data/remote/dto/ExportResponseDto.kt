package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class ExportResponseDto(
    val status: String = "success",
    val message: String = "",
    val export_path: String = "",
)
