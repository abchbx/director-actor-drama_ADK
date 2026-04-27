package com.drama.app.data.remote.ws

/**
 * WebSocket 连接状态密封类。
 *
 * 替代之前的 Boolean connectionState + Boolean isReconnecting 双状态组合，
 * 提供更精确的连接生命周期描述，供 UI 消费。
 */
sealed class ConnectionState {
    /** 正在建立首次连接 */
    data object Connecting : ConnectionState()

    /** 连接已建立，可正常收发消息 */
    data object Connected : ConnectionState()

    /** 连接已断开（主动断开或重连耗尽） */
    data object Disconnected : ConnectionState()

    /** 非主动断开后正在指数退避重连 */
    data class Reconnecting(
        val retry: Int,
        val maxRetry: Int,
    ) : ConnectionState()

    /** 连接失败，携带诊断信息供 UI 展示和用户排查 */
    data class Failed(
        val code: Int = 0,
        val reason: String = "",
        val isAuthError: Boolean = false,
        val isConnectionRefused: Boolean = false,
    ) : ConnectionState()
}
