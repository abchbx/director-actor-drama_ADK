package com.drama.app.domain.model

enum class CommandType(val prefix: String, val needsArgument: Boolean) {
    NEXT("/next", false),
    ACTION("/action", true),
    SPEAK("/speak", true),
    END("/end", false),
    CAST("/cast", false),
    SAVE("/save", true),
    LOAD("/load", true),
    LIST("/list", false),
    DELETE("/delete", true),
    STEER("/steer", true),
    AUTO("/auto", true),
    STORM("/storm", false),
    FREE_TEXT("", false);

    companion object {
        fun fromInput(input: String): CommandType {
            val trimmed = input.trimStart()
            return entries.firstOrNull { it.prefix.isNotEmpty() && trimmed.startsWith(it.prefix) } ?: FREE_TEXT
        }
    }
}
