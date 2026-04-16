package com.drama.app.data.remote.ws

import com.drama.app.data.remote.dto.WsEventDto
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
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
) {
    private var webSocket: WebSocket? = null

    fun connect(host: String, port: String, token: String?): Flow<WsEventDto> = callbackFlow {
        val url = if (token != null) {
            "ws://$host:$port/api/v1/ws?token=$token"
        } else {
            "ws://$host:$port/api/v1/ws"
        }
        val request = Request.Builder().url(url).build()
        webSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val event = json.decodeFromString<WsEventDto>(text)
                    trySend(event)
                } catch (_: Exception) { /* 忽略非事件消息如心跳 */ }
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                close()
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                close(t)
            }
        })
        awaitClose { webSocket?.close(1000, "Client disconnect") }
    }

    fun disconnect() {
        webSocket?.close(1000, "User disconnect")
        webSocket = null
    }
}
