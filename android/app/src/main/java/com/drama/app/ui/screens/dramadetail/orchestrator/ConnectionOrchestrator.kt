package com.drama.app.ui.screens.dramadetail.orchestrator

import android.util.Log
import com.drama.app.data.remote.dto.WsEventDto
import com.drama.app.data.remote.ws.ConnectionState
import com.drama.app.data.remote.ws.WebSocketManager
import com.drama.app.data.local.ServerPreferences
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * WS 连接编排子组件（per D-23-01, D-23-02）。
 * 管理连接/重连/心跳/轮询降级，通过 SharedFlow 上报连接事件给主 VM。
 * 暴露 isWsConnected 状态供 BubbleMerger 实现数据源策略（per ARCH-10）。
 *
 * 架构选择：使用 @Inject constructor 而非 ViewModelSubComponent 基类。
 * 理由：@Inject 使子组件可独立测试（直接 new），无需 Hilt 测试运行器；
 * cleanup() 由主 VM onCleared 显式调用，等价于 ViewModelSubComponent.onCleared()。
 */
class ConnectionOrchestrator @Inject constructor(
    private val webSocketManager: WebSocketManager,
    private val serverPreferences: ServerPreferences,
) {
    /** D-23-02: 子组件通信用 SharedFlow 事件上报 */
    sealed class ConnectionEvent {
        data class Connected(val dramaId: String) : ConnectionEvent()
        data class Disconnected(val reason: String) : ConnectionEvent()
        data class Error(val message: String) : ConnectionEvent()
        data class Reconnecting(val attempt: Int) : ConnectionEvent()
        data class EventReceived(val event: WsEventDto) : ConnectionEvent()
        data class Reconnected(val serverScene: Int) : ConnectionEvent()
        data class PermanentFailure(
            val code: Int = 0,
            val reason: String = "",
            val isAuthError: Boolean = false,
            val isConnectionRefused: Boolean = false,
        ) : ConnectionEvent()
    }

    private val _events = MutableSharedFlow<ConnectionEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<ConnectionEvent> = _events

    /**
     * ARCH-10: 暴露 WS 连接状态，供 BubbleMerger 判断数据源。
     * D-23-16: 独立 MutableStateFlow，从 WebSocketManager.connectionState 派生，
     * 避免每次访问创建新 Flow 实例。
     */
    private val _isWsConnected = MutableStateFlow(false)
    val isWsConnected: StateFlow<Boolean> = _isWsConnected

    /** 直接暴露 WebSocketManager 的连接状态 */
    val connectionState: StateFlow<ConnectionState> = webSocketManager.connectionState

    private var wsJob: Job? = null
    private var connectionStateJob: Job? = null
    private var connectGeneration = 0
    private var hasCalledConnect = false

    /** 连接 WS，失败时降级为 REST 轮询 */
    fun connect(dramaId: String, token: String, scope: CoroutineScope) {
        disconnect()
        connectGeneration++
        hasCalledConnect = true

        val isAlreadyConnected = webSocketManager.connectionState.value == ConnectionState.Connected

        // D-23-06: acquire 引用计数
        webSocketManager.acquire()

        // 设置回调
        webSocketManager.onReconnected = {
            _isWsConnected.value = true
            _events.tryEmit(ConnectionEvent.Reconnected(serverScene = 0))
        }
        webSocketManager.onPermanentFailure = {
            _isWsConnected.value = false
            _events.tryEmit(ConnectionEvent.PermanentFailure())
        }

        if (isAlreadyConnected) {
            Log.i(TAG, "WS already connected, reusing existing connection")
            _isWsConnected.value = true
            wsJob = scope.launch {
                webSocketManager.events
                    .collect { event -> _events.tryEmit(ConnectionEvent.EventReceived(event)) }
            }
        } else {
            _isWsConnected.value = false
            wsJob = scope.launch {
                val config = serverPreferences.serverConfig.first() ?: return@launch
                webSocketManager.connect(config.ip, config.port, config.token, config.baseUrl)
                    .collect { event -> _events.tryEmit(ConnectionEvent.EventReceived(event)) }
            }
        }

        // 收集 ConnectionState — D-23-16: 同步更新 _isWsConnected
        connectionStateJob = scope.launch {
            webSocketManager.connectionState.collect { state ->
                when (state) {
                    is ConnectionState.Connected -> {
                        _isWsConnected.value = true
                        _events.tryEmit(ConnectionEvent.Connected(dramaId))
                    }
                    is ConnectionState.Disconnected -> {
                        _isWsConnected.value = false
                        _events.tryEmit(ConnectionEvent.Disconnected("连接断开"))
                    }
                    is ConnectionState.Reconnecting -> {
                        _isWsConnected.value = false
                        _events.tryEmit(ConnectionEvent.Reconnecting(state.retry))
                    }
                    is ConnectionState.Connecting -> { /* 等待 */ }
                    is ConnectionState.Failed -> {
                        _isWsConnected.value = false
                        _events.tryEmit(ConnectionEvent.PermanentFailure(
                            code = state.code,
                            reason = state.reason,
                            isAuthError = state.isAuthError,
                            isConnectionRefused = state.isConnectionRefused,
                        ))
                    }
                }
            }
        }
    }

    /** 断开连接 */
    fun disconnect() {
        connectGeneration++
        wsJob?.cancel()
        wsJob = null
        connectionStateJob?.cancel()
        connectionStateJob = null
        webSocketManager.onReconnected = null
        webSocketManager.onPermanentFailure = null
        hasCalledConnect = false
        _isWsConnected.value = false
    }

    /** 是否已调用过 connect */
    fun hasConnected(): Boolean = hasCalledConnect

    /** 标记已调用 connect（防抖） */
    fun markConnected() {
        hasCalledConnect = true
    }

    /** 重置连接标记（断开时） */
    fun resetConnectedFlag() {
        hasCalledConnect = false
    }

    /** D-23-04: 主 VM onCleared 时调用统一清理 */
    fun cleanup() {
        disconnect()
        // D-23-06: release 引用计数
        webSocketManager.release()
    }

    companion object {
        private const val TAG = "ConnectionOrchestrator"
    }
}
