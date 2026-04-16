package com.drama.app.domain.model

data class ServerConfig(
    val ip: String,
    val port: String,
    val token: String? = null,
    val lastConnected: Long? = null,
)
