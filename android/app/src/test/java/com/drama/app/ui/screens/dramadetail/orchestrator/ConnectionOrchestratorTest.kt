package com.drama.app.ui.screens.dramadetail.orchestrator

import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.remote.ws.ConnectionState
import com.drama.app.data.remote.ws.WebSocketManager
import com.drama.app.domain.model.ServerConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever

/**
 * ConnectionOrchestrator 单元测试（per ARCH-02, D-23-13）。
 * 覆盖：初始状态、isWsConnected 同步、connect/disconnect/cleanup 生命周期。
 */
class ConnectionOrchestratorTest {

    private lateinit var orchestrator: ConnectionOrchestrator
    private val mockWebSocketManager: WebSocketManager = mock()
    private val mockServerPreferences: ServerPreferences = mock()

    @Before
    fun setup() {
        whenever(mockWebSocketManager.connectionState)
            .thenReturn(MutableStateFlow(ConnectionState.Disconnected))
        whenever(mockWebSocketManager.events).thenReturn(flowOf())
        whenever(mockServerPreferences.serverConfig).thenReturn(
            flowOf(ServerConfig(ip = "192.168.1.100", port = "8000", token = "test"))
        )
        orchestrator = ConnectionOrchestrator(mockWebSocketManager, mockServerPreferences)
    }

    // ===== 初始状态 =====

    @Test
    fun `initial isWsConnected is false`() {
        assertFalse(orchestrator.isWsConnected.value)
    }

    @Test
    fun `initial hasConnected is false`() {
        assertFalse(orchestrator.hasConnected())
    }

    @Test
    fun `initial connectionState is Disconnected`() {
        assertEquals(ConnectionState.Disconnected, orchestrator.connectionState.value)
    }

    // ===== connect 生命周期 =====

    @Test
    fun `connect sets hasConnected flag`() = runTest {
        orchestrator.connect("test-drama", "token", this)
        assertTrue(orchestrator.hasConnected())
    }

    @Test
    fun `connect acquires WebSocketManager reference`() = runTest {
        orchestrator.connect("test-drama", "token", this)
        verify(mockWebSocketManager).acquire()
    }

    @Test
    fun `connect with already connected WS sets isWsConnected true`() = runTest {
        whenever(mockWebSocketManager.connectionState)
            .thenReturn(MutableStateFlow(ConnectionState.Connected))

        orchestrator = ConnectionOrchestrator(mockWebSocketManager, mockServerPreferences)
        orchestrator.connect("test-drama", "token", this)

        assertTrue(orchestrator.isWsConnected.value)
    }

    @Test
    fun `connect with disconnected WS sets isWsConnected false initially`() = runTest {
        orchestrator.connect("test-drama", "token", this)
        // WS not yet connected, so isWsConnected should be false
        assertFalse(orchestrator.isWsConnected.value)
    }

    // ===== disconnect 生命周期 =====

    @Test
    fun `disconnect resets hasConnected to false`() = runTest {
        orchestrator.connect("test-drama", "token", this)
        orchestrator.disconnect()
        assertFalse(orchestrator.hasConnected())
    }

    @Test
    fun `disconnect sets isWsConnected to false`() = runTest {
        whenever(mockWebSocketManager.connectionState)
            .thenReturn(MutableStateFlow(ConnectionState.Connected))
        orchestrator = ConnectionOrchestrator(mockWebSocketManager, mockServerPreferences)

        orchestrator.connect("test-drama", "token", this)
        // Now disconnect
        orchestrator.disconnect()
        assertFalse(orchestrator.isWsConnected.value)
    }

    @Test
    fun `disconnect clears onReconnected callback`() = runTest {
        orchestrator.connect("test-drama", "token", this)
        orchestrator.disconnect()
        verify(mockWebSocketManager).onReconnected = null
    }

    @Test
    fun `disconnect clears onPermanentFailure callback`() = runTest {
        orchestrator.connect("test-drama", "token", this)
        orchestrator.disconnect()
        verify(mockWebSocketManager).onPermanentFailure = null
    }

    // ===== cleanup =====

    @Test
    fun `cleanup calls disconnect and releases WebSocketManager`() {
        orchestrator.cleanup()
        verify(mockWebSocketManager).release()
        assertFalse(orchestrator.hasConnected())
        assertFalse(orchestrator.isWsConnected.value)
    }

    // ===== hasConnected / markConnected / resetConnectedFlag =====

    @Test
    fun `markConnected sets hasConnected true`() {
        orchestrator.markConnected()
        assertTrue(orchestrator.hasConnected())
    }

    @Test
    fun `resetConnectedFlag sets hasConnected false`() {
        orchestrator.markConnected()
        orchestrator.resetConnectedFlag()
        assertFalse(orchestrator.hasConnected())
    }

    // ===== isWsConnected 同步 =====

    @Test
    fun `isWsConnected reflects Connected state from WebSocketManager`() = runTest {
        val connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
        whenever(mockWebSocketManager.connectionState).thenReturn(connectionState)

        orchestrator = ConnectionOrchestrator(mockWebSocketManager, mockServerPreferences)
        orchestrator.connect("test-drama", "token", this)

        // Simulate WS connected
        connectionState.value = ConnectionState.Connected

        // Allow coroutine collection
        advanceUntilIdle()
        assertTrue(orchestrator.isWsConnected.value)
    }

    @Test
    fun `isWsConnected reflects Reconnecting state as false`() = runTest {
        val connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Connected)
        whenever(mockWebSocketManager.connectionState).thenReturn(connectionState)

        orchestrator = ConnectionOrchestrator(mockWebSocketManager, mockServerPreferences)
        orchestrator.connect("test-drama", "token", this)

        // Simulate reconnecting
        connectionState.value = ConnectionState.Reconnecting(retry = 1, maxRetry = 10)
        advanceUntilIdle()
        assertFalse(orchestrator.isWsConnected.value)
    }
}
