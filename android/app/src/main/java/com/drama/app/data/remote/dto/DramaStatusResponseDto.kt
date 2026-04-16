package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class DramaStatusResponseDto(
    val theme: String = "",
    val drama_status: String = "",
    val current_scene: Int = 0,
    val num_scenes: Int = 0,
    val num_actors: Int = 0,
    val actors: List<String> = emptyList(),
    val drama_folder: String = "",
)
