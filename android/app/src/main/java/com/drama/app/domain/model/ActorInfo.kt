package com.drama.app.domain.model

data class ActorInfo(
    val name: String,
    val role: String = "",
    val personality: String = "",
    val background: String = "",
    val emotions: String = "neutral",
    val memorySummary: String = "",
    val isA2ARunning: Boolean = false,
    val a2aPort: Int = 0,
)
