package com.drama.app.data.remote.ws

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import com.drama.app.data.remote.dto.WsEventDto
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
    private val context: Context,  // Application context for ConnectivityManager
) {
    private var webSocket: WebSocket? = null
    private var currentHost: String = ""
    private var currentPort: String = ""
    private var currentToken: String? = null

    // D-14: Exponential backoff state
    private var currentDelayMs = 1000L  // Initial 1s
    private val maxDelayMs = 30_000L    // Cap at 30s
    private val reconnectScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var reconnectJob: Job? = null
    private var isIntentionalDisconnect = false

    // D-15: ConnectivityManager NetworkCallback
    private val connectivityManager by lazy {
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    }
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var isNetworkCallbackRegistered = false

    // Event flow for reconnection-aware consumption
    private val _events = MutableSharedFlow<WsEventDto>(extraBufferCapacity = 64)
    val events: Flow<WsEventDto> = _events.asSharedFlow()

    // Connection state tracking for UI indicator
    private val _connectionState = MutableStateFlow(false)
    val connectionState: StateFlow<Boolean> = _connectionState.asStateFlow()

    // Callback for reconnect success
    var onReconnected: (() -> Unit)? = null

    fun connect(host: String, port: String, token: String?): Flow<WsEventDto> {
        currentHost = host
        currentPort = port
        currentToken = token
        isIntentionalDisconnect = false
        currentDelayMs = 1000L  // D-14: Reset on new connect

        registerNetworkCallback()  // D-15
        connectInternal()

        return _events.asSharedFlow()
    }

    private fun connectInternal() {
        val url = if (currentToken != null) {
            "ws://$currentHost:$currentPort/api/v1/ws?token=$currentToken"
        } else {
            "ws://$currentHost:$currentPort/api/v1/ws"
        }
        val request = Request.Builder().url(url).build()
        webSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                currentDelayMs = 1000L  // D-14: Reset backoff on successful connect
                _connectionState.value = true
                // Notify reconnect callback if this was a reconnect
                onReconnected?.invoke()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val event = json.decodeFromString<WsEventDto>(text)
                    _events.tryEmit(event)
                } catch (_: Exception) { /* Ignore non-event messages like heartbeats */ }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, "Ack closing")
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                _connectionState.value = false
                if (!isIntentionalDisconnect) {
                    scheduleReconnect()  // D-14: Exponential backoff
                }
            }
        })
    }

    private fun scheduleReconnect() {
        // Pitfall 3: Cancel existing reconnect job to prevent duplicate connections
        reconnectJob?.cancel()
        reconnectJob = reconnectScope.launch {
            delay(currentDelayMs)
            currentDelayMs = (currentDelayMs * 2).coerceAtMost(maxDelayMs)  // D-14: Double delay, cap at 30s
            connectInternal()
        }
    }

    // D-15: Register NetworkCallback for immediate reconnect on network restore
    private fun registerNetworkCallback() {
        if (isNetworkCallbackRegistered) return
        networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
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
        _connectionState.value = false
        webSocket?.close(1000, "User disconnect")
        webSocket = null
        unregisterNetworkCallback()
    }
}
