package com.drama.app.domain.model

sealed class ConnectionStatus {
    data object Idle : ConnectionStatus()
    data object Connecting : ConnectionStatus()
    data object Connected : ConnectionStatus()
    data class Error(val message: String, val type: ErrorType) : ConnectionStatus()
}

enum class ErrorType {
    NETWORK_UNREACHABLE,   // D-03: 网络不可达
    AUTH_FAILED,           // D-03: 401 认证失败
    TIMEOUT,               // D-03: 连接超时
    UNKNOWN,
}
