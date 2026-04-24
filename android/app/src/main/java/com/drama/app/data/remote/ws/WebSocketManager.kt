package com.drama.app.data.remote.ws

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.util.Log
import com.drama.app.data.remote.dto.ReplayMessageDto
import com.drama.app.data.remote.dto.WsEventDto
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import javax.inject.Inject

class WebSocketManager @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val json: Json,
    @ApplicationContext private val context: Context,
) {
    private var webSocket: WebSocket? = null
    private var currentHost: String = ""
    private var currentPort: String = ""
    private var currentToken: String? = null
    private var currentBaseUrl: String? = null

    // D-14: Exponential backoff state
    private var currentDelayMs = 1000L  // Initial 1s
    private val maxDelayMs = 30_000L    // Cap at 30s
    private val reconnectScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var reconnectJob: Job? = null
    private var isIntentionalDisconnect = false
    // ★ 修复竞态：连接代数计数器，每次 connectInternal() 递增
    // 回调中比对代数，忽略旧代数的回调
    @Volatile private var connectGeneration = 0L

    // D-15: ConnectivityManager NetworkCallback
    private val connectivityManager by lazy {
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    }
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var isNetworkCallbackRegistered = false

    // ★ 修复：重连失败计数器，用于判断是否需要降级到 REST
    private var consecutiveFailures = 0
    private val maxConsecutiveFailures = 5  // 连续失败 5 次后降级
    var onPermanentFailure: (() -> Unit)? = null  // 回调通知 UI 降级

    // Event flow for reconnection-aware consumption
    private val _events = MutableSharedFlow<WsEventDto>(extraBufferCapacity = 64)
    val events: Flow<WsEventDto> = _events.asSharedFlow()

    // Connection state tracking for UI indicator
    private val _connectionState = MutableStateFlow(false)
    val connectionState: StateFlow<Boolean> = _connectionState.asStateFlow()

    // ★ 修复：添加 isReconnecting 状态，区分"正在重连"和"已降级到 REST"
    private val _isReconnecting = MutableStateFlow(false)
    val isReconnecting: StateFlow<Boolean> = _isReconnecting.asStateFlow()

    // ★ 修复竞态：在 WebSocketManager 内部追踪是否是首次连接
    // onOpen 时 isFirstConnection=true → 不回调 onReconnected
    // 后续 onOpen（重连）时 isFirstConnection=false → 回调 onReconnected
    private var isFirstConnection = true

    // Callback for reconnect success
    var onReconnected: (() -> Unit)? = null

    fun connect(host: String, port: String, token: String?, baseUrl: String? = null): Flow<WsEventDto> {
        currentHost = host
        currentPort = port
        currentToken = token
        currentBaseUrl = baseUrl
        isIntentionalDisconnect = false
        currentDelayMs = 1000L  // D-14: Reset on new connect
        isFirstConnection = true  // ★ 重置首次连接标志
        consecutiveFailures = 0  // ★ 修复：重置失败计数

        Log.d(TAG, "WS connect: host=$host port=$port baseUrl=$baseUrl hasToken=${token != null}")
        registerNetworkCallback()  // D-15
        connectInternal()

        return _events.asSharedFlow()
    }

    private fun connectInternal() {
        // Close existing connection before creating a new one to prevent resource leaks
        webSocket?.close(1000, "Replacing with new connection")
        webSocket = null

        // ★ 修复竞态：递增连接代数，回调中比对，忽略旧代数回调
        val thisGeneration = ++connectGeneration

        val baseUrl = currentBaseUrl
        val token = currentToken
        val url = if (!baseUrl.isNullOrBlank()) {
            val base = baseUrl.trimEnd('/')
            val wsBase = base.replace("https://", "wss://").replace("http://", "ws://")
            if (token != null) "$wsBase/api/v1/ws?token=$token" else "$wsBase/api/v1/ws"
        } else if (token != null) {
            "ws://$currentHost:$currentPort/api/v1/ws?token=$token"
        } else {
            "ws://$currentHost:$currentPort/api/v1/ws"
        }
        Log.d(TAG, "WS connectInternal: url=$url, generation=$thisGeneration")
        val request = Request.Builder().url(url).build()

        // ★ 修复竞态：记录当前 WS 实例，在回调中比对，忽略旧连接的回调
        val newWebSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                if (thisGeneration != connectGeneration) {
                    Log.w(TAG, "WS onOpen: ignored stale callback, generation=$thisGeneration, current=$connectGeneration")
                    return  // 忽略旧代数回调
                }
                currentDelayMs = 1000L  // D-14: Reset backoff on successful connect
                consecutiveFailures = 0  // ★ 修复：重置失败计数器
                _connectionState.value = true
                _isReconnecting.value = false  // ★ 清除重连状态
                Log.i(TAG, "WS onOpen: CONNECTED, generation=$thisGeneration, isFirstConnection=$isFirstConnection, " +
                        "url=${webSocket.request().url}, responseCode=${response.code}")
                // ★ 修复竞态：使用 WebSocketManager 内部的 isFirstConnection 标志
                // 首次连接时不触发 onReconnected，仅重连时触发
                if (isFirstConnection) {
                    isFirstConnection = false
                    Log.d(TAG, "WS onOpen: first connection established")
                } else {
                    Log.d(TAG, "WS onOpen: reconnected, triggering onReconnected callback")
                    onReconnected?.invoke()
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                if (thisGeneration != connectGeneration) return  // 忽略旧代数回调
                // D-14: Respond to server application-level heartbeat ping
                if (text.contains("\"type\"") && text.contains("\"ping\"")) {
                    webSocket.send("""{"type":"pong"}""")
                    return
                }
                // ★ 修复：处理 replay 消息，将事件逐个投递到 Flow
                // 之前直接丢弃 replay 消息，导致重连后丢失断连期间的历史事件
                if (text.contains("\"type\"") && text.contains("\"replay\"")) {
                    try {
                        val replayMsg = json.decodeFromString<ReplayMessageDto>(text)
                        replayMsg.events.forEach { event ->
                            _events.tryEmit(event)
                        }
                    } catch (e: Exception) {
                        Log.e(TAG, "Failed to parse replay message: $text", e)
                    }
                    return
                }
                try {
                    val event = json.decodeFromString<WsEventDto>(text)
                    _events.tryEmit(event)
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to deserialize WS message: $text", e)
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                if (thisGeneration != connectGeneration) {
                    Log.w(TAG, "WS onClosing: ignored stale callback, generation=$thisGeneration")
                    return  // 忽略旧代数回调
                }
                Log.d(TAG, "WS onClosing: code=$code reason=$reason, generation=$thisGeneration")
                webSocket.close(1000, "Ack closing")
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (thisGeneration != connectGeneration) {
                    Log.w(TAG, "WS onClosed: ignored stale callback, generation=$thisGeneration")
                    return  // 忽略旧代数回调
                }
                Log.w(TAG, "WS onClosed: code=$code reason=$reason, generation=$thisGeneration, isIntentional=$isIntentionalDisconnect")
                _connectionState.value = false
                _isReconnecting.value = false  // ★ 清除重连状态
                if (!isIntentionalDisconnect) {
                    consecutiveFailures++  // ★ 修复：服务器关闭连接也计入失败
                    scheduleReconnect()  // Server closed connection, auto-reconnect
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (thisGeneration != connectGeneration) {
                    Log.w(TAG, "WS onFailure: ignored stale callback, generation=$thisGeneration")
                    return  // 忽略旧代数回调
                }
                // ★ 修复：增强 onFailure 日志，输出完整的 Throwable 堆栈
                Log.e(TAG, """
                    |WS onFailure: ${t.message}
                    |  generation=$thisGeneration
                    |  responseCode=${response?.code}
                    |  responseBody=${response?.body?.string()?.take(200)}
                    |  url=${webSocket.request().url}
                """.trimMargin(), t)
                _connectionState.value = false
                _isReconnecting.value = false  // ★ 清除重连状态

                if (!isIntentionalDisconnect) {
                    consecutiveFailures++
                    Log.w(TAG, "WS onFailure: consecutiveFailures=$consecutiveFailures/$maxConsecutiveFailures")

                    // ★ 修复：连续失败超过阈值时降级到 REST，不继续重连
                    if (consecutiveFailures >= maxConsecutiveFailures) {
                        Log.e(TAG, "WS onFailure: MAX_CONSECUTIVE_FAILURES reached, degrading to REST mode")
                        onPermanentFailure?.invoke()
                        return
                    }
                    scheduleReconnect()  // D-14: Exponential backoff
                }
            }
        })
        this.webSocket = newWebSocket
    }

    private fun scheduleReconnect() {
        // Pitfall 3: Cancel existing reconnect job to prevent duplicate connections
        reconnectJob?.cancel()
        reconnectJob = reconnectScope.launch {
            Log.d(TAG, "WS scheduleReconnect: delay=${currentDelayMs}ms, consecutiveFailures=$consecutiveFailures")
            _isReconnecting.value = true  // ★ 标记正在重连
            delay(currentDelayMs)
            currentDelayMs = (currentDelayMs * 2).coerceAtMost(maxDelayMs)  // D-14: Double delay, cap at 30s
            Log.d(TAG, "WS scheduleReconnect: attempting connect, nextDelay=${currentDelayMs}ms")
            connectInternal()
        }
    }

    // D-15: Register NetworkCallback for immediate reconnect on network restore
    private fun registerNetworkCallback() {
        if (isNetworkCallbackRegistered) return
        networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                // ★ 修复：仅在 WS 已断连时才触发重连
                // 原因：registerNetworkCallback() 注册后，onAvailable 会立即为当前活跃网络触发一次
                // 如果 WS 已经连接（onOpen 已触发），这会导致 connectInternal() 被错误地再次调用
                // 关闭刚建立的连接再重建，造成短暂断连闪烁
                if (_connectionState.value) return
                // Pitfall 3: Cancel pending backoff reconnect to prevent race
                reconnectJob?.cancel()
                currentDelayMs = 1000L  // Reset backoff
                connectInternal()
            }
        }
        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        try {
            connectivityManager.registerNetworkCallback(request, networkCallback!!)
            isNetworkCallbackRegistered = true
        } catch (_: Exception) { /* ConnectivityManager may not be available */ }
    }

    private fun unregisterNetworkCallback() {
        if (isNetworkCallbackRegistered) {
            try {
                networkCallback?.let { connectivityManager.unregisterNetworkCallback(it) }
            } catch (_: Exception) { /* Already unregistered */ }
            isNetworkCallbackRegistered = false
            networkCallback = null
        }
    }

    fun disconnect() {
        isIntentionalDisconnect = true
        reconnectJob?.cancel()
        reconnectJob = null
        currentDelayMs = 1000L
        consecutiveFailures = 0  // ★ 修复：断开时重置失败计数
        _connectionState.value = false
        _isReconnecting.value = false  // ★ 清除重连状态
        Log.d(TAG, "WS disconnect: intentional, resetting state")
        webSocket?.close(1000, "User disconnect")
        webSocket = null
        currentHost = ""
        currentPort = ""
        currentToken = null
        currentBaseUrl = null
        onReconnected = null
        onPermanentFailure = null
        unregisterNetworkCallback()
    }

    companion object {
        private const val TAG = "WebSocketManager"
    }
}
