package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class DramaListResponseDto(
    val dramas: List<DramaItemDto> = emptyList(),
)
