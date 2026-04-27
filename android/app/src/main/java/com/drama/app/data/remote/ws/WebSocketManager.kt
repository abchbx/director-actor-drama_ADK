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
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import javax.inject.Inject

class WebSocketManager @Inject constructor(
    private val json: Json,
    @ApplicationContext private val context: Context,
    private val okHttpClient: OkHttpClient,
) {
    private val wsClient: OkHttpClient by lazy {
        // 使用全局 OkHttpClient.newBuilder() 继承超时/日志/异常拦截器，
        // 但排除 BaseUrlInterceptor（动态替换 URL 的拦截器），
        // 避免其用 ServerPreferences 缓存的旧值覆盖 WebSocket 目标 URL。
        // ⚠️ 注意：newBuilder().interceptors() 返回的是原列表的不可变视图，
        // 必须通过重新 addInterceptor 来构建新列表，不能调用 removeIf。
        val originalInterceptors = okHttpClient.interceptors
        okHttpClient.newBuilder()
            .apply {
                interceptors().clear()
                originalInterceptors.forEach {
                    if (it !is com.drama.app.data.remote.interceptor.BaseUrlInterceptor) {
                        addInterceptor(it)
                    }
                }
            }
            .readTimeout(0, java.util.concurrent.TimeUnit.SECONDS)  // WS: 无读取超时（覆盖全局 300s）
            .build()
    }

    private var webSocket: WebSocket? = null
    private var currentHost: String = ""
    private var currentPort: String = ""
    private var currentToken: String? = null
    private var currentBaseUrl: String? = null

    // D-23-06: 引用计数 — 多 VM 共享 WS 连接
    private val refCount = java.util.concurrent.atomic.AtomicInteger(0)

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

    // === 前后台感知：后台时暂停重连，避免无意义退避耗尽重试次数 ===
    @Volatile private var appInForeground = true
    private var pendingReconnectOnForeground = false

    // === 诊断信息：最近一次断连原因 ===
    private var lastFailureCode: Int = 0
    private var lastFailureReason: String = ""
    private var lastFailureIsAuthError: Boolean = false
    private var lastFailureIsConnectionRefused: Boolean = false

    // === 心跳已移除 ===
    // 服务端驱动应用层心跳：服务端每15s发ping，客户端回复pong
    // OkHttp pingInterval(60s) 仅作 TCP keepalive

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

    // D-23-07: deprecated 属性已删除，改用 connectionState StateFlow

    // 首次连接标志：onOpen 时 isFirstConnection=true → 不回调 onReconnected
    private var isFirstConnection = true

    // Callback for reconnect success
    var onReconnected: (() -> Unit)? = null

    /**
     * D-23-06: 多 VM 共享 WS 时引用计数。
     * acquire() 增加引用，release() 减少引用。
     * 引用归零时自动断开连接。
     */
    fun acquire() {
        val count = refCount.incrementAndGet()
        Log.d(TAG, "WebSocketManager acquired, refCount=$count")
    }

    fun release() {
        val count = refCount.decrementAndGet()
        Log.d(TAG, "WebSocketManager released, refCount=$count")
        if (count <= 0) {
            disconnect()
            refCount.set(0)
        }
    }

    /**
     * ★ 前后台切换通知：后台时暂停重连，前台时立即恢复。
     *
     * 后台暂停重连的原因：
     * - Android Doze/App Standby 会限制后台网络，重连几乎必然失败
     * - 无意义的后台重连会快速耗尽 maxConsecutiveFailures，导致切回前台时直接降级
     * - 切回前台后由前台逻辑主动触发重连，重置失败计数
     */
    fun setAppForeground(isForeground: Boolean) {
        val wasBackground = !appInForeground && isForeground
        appInForeground = isForeground
        Log.d(TAG, "App foreground=$isForeground")

        if (wasBackground && pendingReconnectOnForeground) {
            pendingReconnectOnForeground = false
            if (_connectionState.value != ConnectionState.Connected) {
                Log.i(TAG, "App returned to foreground, triggering immediate reconnect")
                consecutiveFailures = 0
                currentDelayMs = INITIAL_DELAY_MS
                isIntentionalDisconnect = false
                reconnectJob?.cancel()
                connectInternal()
            }
        }

        if (!isForeground) {
            // 切后台：取消当前 pending 的重连任务，避免后台无意义重试
            reconnectJob?.cancel()
            Log.d(TAG, "Background: cancelled pending reconnect")
        }
    }

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
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", "DramaApp-Android/2.0")
            .build()

        val newWebSocket = wsClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                if (thisGeneration != connectGeneration) {
                    Log.w(TAG, "WS onOpen: ignored stale callback, generation=$thisGeneration, current=$connectGeneration")
                    return
                }
                currentDelayMs = INITIAL_DELAY_MS
                consecutiveFailures = 0
                _connectionState.value = ConnectionState.Connected
                Log.i(TAG, "WS onOpen: CONNECTED, generation=$thisGeneration, isFirstConnection=$isFirstConnection")

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

                try {
                    val jsonObject = json.parseToJsonElement(text).jsonObject
                    val type = jsonObject["type"]?.jsonPrimitive?.content ?: ""

                    when (type) {
                        "ping" -> {
                            // D-01/D-02: 服务端应用层心跳 — 立即回复 pong
                            webSocket.send("""{"type":"pong"}""")
                            return
                        }
                        "pong" -> {
                            // 服务端对客户端 pong 的回显，或心跳确认 — 忽略
                            return
                        }
                        "replay" -> {
                            // D-09/D-10: replay buffer 补发
                            val replayMsg = json.decodeFromString<ReplayMessageDto>(text)
                            replayMsg.events.forEach { event ->
                                _events.tryEmit(event)
                            }
                            return
                        }
                    }

                    // 常规事件
                    val event = json.decodeFromString<WsEventDto>(text)
                    _events.tryEmit(event)
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to process WS message: $text", e)
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

                // 记录诊断信息
                lastFailureCode = code
                lastFailureReason = reason
                lastFailureIsAuthError = code == 4001
                lastFailureIsConnectionRefused = false

                if (!isIntentionalDisconnect) {
                    consecutiveFailures++
                    // 4001 = auth error: 不重试，直接降级
                    if (code == 4001) {
                        _connectionState.value = ConnectionState.Failed(
                            code = code, reason = reason,
                            isAuthError = true, isConnectionRefused = false,
                        )
                        Log.e(TAG, "WS onClosed: AUTH ERROR (code=4001), stopping reconnect. reason=$reason")
                        onPermanentFailure?.invoke()
                    } else if (consecutiveFailures >= maxConsecutiveFailures) {
                        _connectionState.value = ConnectionState.Failed(
                            code = code, reason = reason,
                            isAuthError = false, isConnectionRefused = false,
                        )
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
                val responseCode = response?.code ?: 0
                val responseBody = try { response?.body?.string()?.take(200) } catch (_: Exception) { null }
                val isConnRefused = t is java.net.ConnectException
                        || t.message?.contains("Connection refused", ignoreCase = true) == true
                        || t.message?.contains("Failed to connect", ignoreCase = true) == true
                        || t.message?.contains("ECONNREFUSED", ignoreCase = true) == true

                Log.e(TAG, """
                    |WS onFailure: ${t.message}
                    |  generation=$thisGeneration
                    |  responseCode=$responseCode
                    |  responseBody=$responseBody
                    |  url=${webSocket.request().url}
                    |  isConnectionRefused=$isConnRefused
                    |  exceptionType=${t.javaClass.simpleName}
                """.trimMargin(), t)

                // 记录诊断信息
                lastFailureCode = responseCode
                lastFailureReason = t.message ?: "Unknown error"
                lastFailureIsAuthError = responseCode == 401 || responseCode == 4001
                lastFailureIsConnectionRefused = isConnRefused

                if (!isIntentionalDisconnect) {
                    consecutiveFailures++
                    Log.w(TAG, "WS onFailure: consecutiveFailures=$consecutiveFailures/$maxConsecutiveFailures")

                    // 连接被拒/认证错误：不重试，直接降级
                    if (isConnRefused || lastFailureIsAuthError) {
                        _connectionState.value = ConnectionState.Failed(
                            code = responseCode, reason = lastFailureReason,
                            isAuthError = lastFailureIsAuthError, isConnectionRefused = isConnRefused,
                        )
                        Log.e(TAG, "WS onFailure: ${if (isConnRefused) "CONNECTION REFUSED" else "AUTH ERROR"}, stopping reconnect")
                        onPermanentFailure?.invoke()
                    } else if (consecutiveFailures >= maxConsecutiveFailures) {
                        _connectionState.value = ConnectionState.Failed(
                            code = responseCode, reason = lastFailureReason,
                            isAuthError = false, isConnectionRefused = isConnRefused,
                        )
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

    // === 重连策略（指数退避） ===

    private fun scheduleReconnect() {
        reconnectJob?.cancel()

        // ★ 后台时暂停重连，标记待恢复，避免无意义退避耗尽重试次数
        if (!appInForeground) {
            pendingReconnectOnForeground = true
            _connectionState.value = ConnectionState.Reconnecting(
                retry = consecutiveFailures,
                maxRetry = maxConsecutiveFailures,
            )
            Log.d(TAG, "WS scheduleReconnect: paused (app in background), will resume on foreground")
            return
        }

        val retryCount = consecutiveFailures
        _connectionState.value = ConnectionState.Reconnecting(
            retry = retryCount,
            maxRetry = maxConsecutiveFailures,
        )
        reconnectJob = reconnectScope.launch {
            Log.d(TAG, "WS scheduleReconnect: delay=${currentDelayMs}ms, retry=$retryCount/$maxConsecutiveFailures")
            delay(currentDelayMs)
            if (!isActive) return@launch
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
    }
}
