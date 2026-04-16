package com.drama.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class StartDramaRequestDto(val theme: String)

@Serializable
data class ActionRequestDto(val description: String)

@Serializable
data class SpeakRequestDto(val actor_name: String, val situation: String)

@Serializable
data class SteerRequestDto(val direction: String)

@Serializable
data class AutoRequestDto(val num_scenes: Int = 3)

@Serializable
data class StormRequestDto(val focus: String? = null)

@Serializable
data class SaveRequestDto(val save_name: String = "")

@Serializable
data class LoadRequestDto(val save_name: String)

@Serializable
data class ExportRequestDto(val format: String = "markdown")
