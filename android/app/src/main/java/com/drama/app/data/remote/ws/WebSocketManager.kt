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
import kotlinx.coroutines.isActive
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

    // === 重连策略 ===
    private var currentDelayMs = INITIAL_DELAY_MS
    private val reconnectScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var reconnectJob: Job? = null
    private var isIntentionalDisconnect = false

    // 连接代数计数器，每次 connectInternal() 递增，回调中比对，忽略旧代数的回调
    @Volatile private var connectGeneration = 0L

    // === 重连计数 ===
    private var consecutiveFailures = 0
    private val maxConsecutiveFailures = MAX_RETRIES  // 重连耗尽时降级到 REST
    var onPermanentFailure: (() -> Unit)? = null

    // === 心跳 ===
    private var heartbeatJob: Job? = null
    private var useCustomHeartbeat = false  // 根据是否支持 Ping/Pong 帧自动切换

    // === ConnectivityManager NetworkCallback ===
    private val connectivityManager by lazy {
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    }
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var isNetworkCallbackRegistered = false

    // === 事件流 ===
    private val _events = MutableSharedFlow<WsEventDto>(extraBufferCapacity = 64)
    val events: Flow<WsEventDto> = _events.asSharedFlow()

    // === 连接状态（密封类，替代 Boolean + Boolean 双状态） ===
    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    // === 向后兼容的便捷属性 ===
    @Deprecated("Use connectionState instead", replaceWith = ReplaceWith("connectionState"))
    val isConnected: StateFlow<Boolean> get() {
        // 保留旧代码兼容：映射 ConnectionState → Boolean
        val mapped = MutableStateFlow(_connectionState.value == ConnectionState.Connected)
        reconnectScope.launch {
            _connectionState.collect { mapped.value = it == ConnectionState.Connected }
        }
        return mapped
    }

    @Deprecated("Use connectionState instead", replaceWith = ReplaceWith("connectionState"))
    val isReconnecting: StateFlow<Boolean> get() {
        val mapped = MutableStateFlow(_connectionState.value is ConnectionState.Reconnecting)
        reconnectScope.launch {
            _connectionState.collect { mapped.value = it is ConnectionState.Reconnecting }
        }
        return mapped
    }

    // 首次连接标志：onOpen 时 isFirstConnection=true → 不回调 onReconnected
    private var isFirstConnection = true

    // Callback for reconnect success
    var onReconnected: (() -> Unit)? = null

    fun connect(host: String, port: String, token: String?, baseUrl: String? = null): Flow<WsEventDto> {
        currentHost = host
        currentPort = port
        currentToken = token
        currentBaseUrl = baseUrl
        isIntentionalDisconnect = false
        currentDelayMs = INITIAL_DELAY_MS
        isFirstConnection = true
        consecutiveFailures = 0

        _connectionState.value = ConnectionState.Connecting
        Log.d(TAG, "WS connect: host=$host port=$port baseUrl=$baseUrl hasToken=${token != null}")
        registerNetworkCallback()
        connectInternal()

        return _events.asSharedFlow()
    }

    private fun connectInternal() {
        // Close existing connection before creating a new one
        webSocket?.close(1000, "Replacing with new connection")
        webSocket = null

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

        val newWebSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                if (thisGeneration != connectGeneration) {
                    Log.w(TAG, "WS onOpen: ignored stale callback, generation=$thisGeneration, current=$connectGeneration")
                    return
                }
                currentDelayMs = INITIAL_DELAY_MS
                consecutiveFailures = 0
                _connectionState.value = ConnectionState.Connected
                Log.i(TAG, "WS onOpen: CONNECTED, generation=$thisGeneration, isFirstConnection=$isFirstConnection")

                // 检测是否需要自定义心跳
                // OkHttp pingInterval 仅对 WS Ping/Pong 帧生效
                // 如果服务端不响应 Ping 帧，则启动自定义文本心跳
                startHeartbeat(webSocket)

                if (isFirstConnection) {
                    isFirstConnection = false
                    Log.d(TAG, "WS onOpen: first connection established")
                } else {
                    Log.d(TAG, "WS onOpen: reconnected, triggering onReconnected callback")
                    onReconnected?.invoke()
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                if (thisGeneration != connectGeneration) return

                // 响应服务端应用层 heartbeat ping
                if (text.contains("\"type\"") && text.contains("\"ping\"")) {
                    webSocket.send("""{"type":"pong"}""")
                    return
                }

                // 处理 replay 消息
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

                // 响应服务端 pong（确认自定义心跳收到回复）
                if (text.contains("\"type\"") && text.contains("\"pong\"")) {
                    // 服务端响应了我们的自定义心跳，标记为使用自定义心跳模式
                    useCustomHeartbeat = true
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
                    return
                }
                Log.d(TAG, "WS onClosing: code=$code reason=$reason, generation=$thisGeneration")
                webSocket.close(1000, "Ack closing")
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (thisGeneration != connectGeneration) {
                    Log.w(TAG, "WS onClosed: ignored stale callback, generation=$thisGeneration")
                    return
                }
                Log.w(TAG, "WS onClosed: code=$code reason=$reason, generation=$thisGeneration, isIntentional=$isIntentionalDisconnect")
                stopHeartbeat()

                if (!isIntentionalDisconnect) {
                    consecutiveFailures++
                    if (consecutiveFailures >= maxConsecutiveFailures) {
                        _connectionState.value = ConnectionState.Disconnected
                        Log.e(TAG, "WS onClosed: MAX_RETRIES reached, degrading to REST mode")
                        onPermanentFailure?.invoke()
                    } else {
                        scheduleReconnect()
                    }
                } else {
                    _connectionState.value = ConnectionState.Disconnected
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (thisGeneration != connectGeneration) {
                    Log.w(TAG, "WS onFailure: ignored stale callback, generation=$thisGeneration")
                    return
                }
                Log.e(TAG, """
                    |WS onFailure: ${t.message}
                    |  generation=$thisGeneration
                    |  responseCode=${response?.code}
                    |  responseBody=${response?.body?.string()?.take(200)}
                    |  url=${webSocket.request().url}
                """.trimMargin(), t)
                stopHeartbeat()

                if (!isIntentionalDisconnect) {
                    consecutiveFailures++
                    Log.w(TAG, "WS onFailure: consecutiveFailures=$consecutiveFailures/$maxConsecutiveFailures")

                    if (consecutiveFailures >= maxConsecutiveFailures) {
                        _connectionState.value = ConnectionState.Disconnected
                        Log.e(TAG, "WS onFailure: MAX_RETRIES reached, degrading to REST mode")
                        onPermanentFailure?.invoke()
                    } else {
                        scheduleReconnect()
                    }
                } else {
                    _connectionState.value = ConnectionState.Disconnected
                }
            }
        })
        this.webSocket = newWebSocket
    }

    // === 心跳管理 ===

    /**
     * 启动心跳保活。
     *
     * 策略：
     * - OkHttp 已配置 pingInterval（通过 NetworkModule），会自动发送 WS Ping 帧
     * - 如果服务端不支持 Ping/Pong 帧（onFailure 回调），则切换为自定义文本心跳
     * - 自定义心跳每 30 秒发送一条 {"type":"heartbeat"} 消息
     */
    private fun startHeartbeat(ws: WebSocket) {
        stopHeartbeat()
        heartbeatJob = reconnectScope.launch {
            while (isActive) {
                delay(HEARTBEAT_INTERVAL_MS)
                if (useCustomHeartbeat) {
                    // 服务端已确认支持自定义心跳，发送文本心跳
                    try {
                        val sent = ws.send("""{"type":"heartbeat"}""")
                        if (!sent) {
                            Log.w(TAG, "WS heartbeat: send failed, connection may be dead")
                        }
                    } catch (e: Exception) {
                        Log.w(TAG, "WS heartbeat: send threw exception", e)
                    }
                }
                // 如果 useCustomHeartbeat=false，说明依赖 OkHttp 的 pingInterval
                // 不需要发送自定义心跳
            }
        }
    }

    private fun stopHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = null
    }

    // === 重连策略（指数退避） ===

    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        val retryCount = consecutiveFailures
        _connectionState.value = ConnectionState.Reconnecting(
            retry = retryCount,
            maxRetry = maxConsecutiveFailures,
        )
        reconnectJob = reconnectScope.launch {
            Log.d(TAG, "WS scheduleReconnect: delay=${currentDelayMs}ms, retry=$retryCount/$maxConsecutiveFailures")
            delay(currentDelayMs)
            currentDelayMs = (currentDelayMs * 2).coerceAtMost(MAX_DELAY_MS)
            Log.d(TAG, "WS scheduleReconnect: attempting connect, nextDelay=${currentDelayMs}ms")
            connectInternal()
        }
    }

    // === 网络回调 ===

    private fun registerNetworkCallback() {
        if (isNetworkCallbackRegistered) return
        networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                if (_connectionState.value == ConnectionState.Connected) return
                // Cancel pending backoff reconnect to prevent race
                reconnectJob?.cancel()
                currentDelayMs = INITIAL_DELAY_MS
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

    // === 主动断开 ===

    fun disconnect() {
        isIntentionalDisconnect = true
        reconnectJob?.cancel()
        reconnectJob = null
        stopHeartbeat()
        currentDelayMs = INITIAL_DELAY_MS
        consecutiveFailures = 0
        _connectionState.value = ConnectionState.Disconnected
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

    /**
     * 主动发起重连（用户点击"重试"按钮时调用）。
     * 重置失败计数，从初始延迟重新开始。
     */
    fun retry() {
        consecutiveFailures = 0
        currentDelayMs = INITIAL_DELAY_MS
        isIntentionalDisconnect = false
        _connectionState.value = ConnectionState.Connecting
        connectInternal()
    }

    companion object {
        private const val TAG = "WebSocketManager"
        private const val INITIAL_DELAY_MS = 2000L       // 初始退避 2 秒
        private const val MAX_DELAY_MS = 30_000L         // 最大退避 30 秒
        private const val MAX_RETRIES = 10               // 最多重试 10 次
        private const val HEARTBEAT_INTERVAL_MS = 30_000L // 心跳间隔 30 秒
    }
}
