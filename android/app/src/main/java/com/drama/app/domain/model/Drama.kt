package com.drama.app.domain.model

data class Drama(
    val folder: String,
    val theme: String,
    val status: String,
    val updatedAt: String,
    val currentScene: Int,
    val snapshots: List<String> = emptyList(),
)
