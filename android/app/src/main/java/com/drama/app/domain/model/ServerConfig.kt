package com.drama.app.domain.model

data class ServerConfig(
    val ip: String,
    val port: String,
    val token: String? = null,
    val lastConnected: Long? = null,
    /** Full base URL for cloud-hosted servers (e.g. "https://xxx.cloudstudio.club/").
     *  When non-null, takes precedence over ip:port for REST and WS connections. */
    val baseUrl: String? = null,
) {
    /** Build the REST API base URL (always ends with /api/v1/). */
    fun toApiBaseUrl(): String {
        if (!baseUrl.isNullOrBlank()) {
            val base = baseUrl.trimEnd('/')
            return "$base/api/v1/"
        }
        return "http://$ip:$port/api/v1/"
    }

    /** Build the WebSocket URL. */
    fun toWsUrl(token: String?): String {
        if (!baseUrl.isNullOrBlank()) {
            val base = baseUrl.trimEnd('/')
            // https:// → wss://, http:// → ws://
            val wsBase = base.replace("https://", "wss://").replace("http://", "ws://")
            return if (token != null) "$wsBase/api/v1/ws?token=$token" else "$wsBase/api/v1/ws"
        }
        return if (token != null)
            "ws://$ip:$port/api/v1/ws?token=$token"
        else
            "ws://$ip:$port/api/v1/ws"
    }
}
