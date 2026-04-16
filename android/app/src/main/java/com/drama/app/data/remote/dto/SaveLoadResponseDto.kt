package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class SaveLoadResponseDto(
    val status: String = "success",
    val message: String = "",
    val theme: String = "",
    val drama_status: String = "",
    val current_scene: Int = 0,
    val num_actors: Int = 0,
    val num_scenes: Int = 0,
    val actors_list: List<String> = emptyList(),
)
