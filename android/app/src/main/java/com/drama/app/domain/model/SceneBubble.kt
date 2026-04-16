package com.drama.app.domain.model

sealed class SceneBubble {
    abstract val id: String

    data class Narration(
        override val id: String,
        val text: String,
    ) : SceneBubble()

    data class Dialogue(
        override val id: String,
        val actorName: String,
        val text: String,
        val emotion: String = "",       // D-10: emotion tag
    ) : SceneBubble()

    data class SceneDivider(
        override val id: String,
        val sceneNumber: Int,
        val sceneTitle: String = "",
    ) : SceneBubble()
}
