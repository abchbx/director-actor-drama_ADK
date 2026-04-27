package com.drama.app.ui.screens.dramadetail.orchestrator

import com.drama.app.domain.model.CommandType
import com.drama.app.domain.model.SceneBubble
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/**
 * BubbleMerger 单元测试（per D-23-12, D-23-13, ARCH-10, ARCH-15）。
 * 覆盖：气泡 ID 生成、addFromRest 数据源策略、mergeAfterReconnect、去重。
 */
class BubbleMergerTest {

    private lateinit var bubbleMerger: BubbleMerger

    @Before
    fun setup() {
        bubbleMerger = BubbleMerger()
    }

    // ===== 基础功能 =====

    @Test
    fun `nextBubbleId returns monotonically increasing String IDs`() {
        // D-23-03: AtomicLong 线程安全 ID
        val id1 = bubbleMerger.nextBubbleId()
        val id2 = bubbleMerger.nextBubbleId()
        assertTrue(id2 > id1)
        assertTrue(id1.startsWith("b_"))
    }

    @Test
    fun `nextBubbleId with prefix uses specified prefix`() {
        val id = bubbleMerger.nextBubbleId("cmd_")
        assertTrue(id.startsWith("cmd_"))
    }

    @Test
    fun `hasError returns false for new error`() {
        assertFalse(bubbleMerger.hasError("Something went wrong"))
    }

    @Test
    fun `hasError returns true after markErrorAdded`() {
        bubbleMerger.markErrorAdded("Something went wrong")
        assertTrue(bubbleMerger.hasError("Something went wrong"))
    }

    @Test
    fun `hasError deduplicates same error message`() {
        bubbleMerger.markErrorAdded("Error A")
        assertTrue(bubbleMerger.hasError("Error A"))
        assertFalse(bubbleMerger.hasError("Error B"))
    }

    @Test
    fun `clear resets counter and error tracking`() {
        bubbleMerger.nextBubbleId()
        bubbleMerger.markErrorAdded("Error")
        bubbleMerger.clear()
        assertFalse(bubbleMerger.hasError("Error"))
        // Counter reset — next ID should start from 1 again
        val id = bubbleMerger.nextBubbleId()
        assertEquals("b_1", id)
    }

    @Test
    fun `cleanup delegates to clear`() {
        bubbleMerger.nextBubbleId()
        bubbleMerger.markErrorAdded("Error")
        bubbleMerger.cleanup()
        assertFalse(bubbleMerger.hasError("Error"))
    }

    // ===== ARCH-10: addFromRest 数据源策略测试 =====

    @Test
    fun `addFromRest rejects REST bubbles when WS connected`() {
        // ARCH-10: WS 连接时 REST 更新被静默丢弃
        val restBubbles = listOf(
            SceneBubble.Narration(id = "r_1", text = "REST narration")
        )
        val currentBubbles = emptyList<SceneBubble>()
        val result = bubbleMerger.addFromRest(restBubbles, isWsConnected = true, currentBubbles = currentBubbles)
        assertTrue(result.isEmpty())
    }

    @Test
    fun `addFromRest accepts REST bubbles when WS disconnected`() {
        // ARCH-10: WS 断开时接受 REST 气泡（降级模式）
        val restBubbles = listOf(
            SceneBubble.Narration(id = "r_1", text = "REST narration")
        )
        val currentBubbles = emptyList<SceneBubble>()
        val result = bubbleMerger.addFromRest(restBubbles, isWsConnected = false, currentBubbles = currentBubbles)
        assertEquals(1, result.size)
        assertEquals("REST narration", (result[0] as SceneBubble.Narration).text)
    }

    @Test
    fun `addFromRest deduplicates REST bubbles against existing by contentFingerprint`() {
        // ARCH-15: 去重安全网 — WS 已有相同内容的气泡时，REST 版本被过滤
        val existingBubble = SceneBubble.Narration(id = "ws_1", text = "WS message")
        val restBubbles = listOf(
            SceneBubble.Narration(id = "r_1", text = "WS message")  // same fingerprint
        )
        val result = bubbleMerger.addFromRest(restBubbles, isWsConnected = false, currentBubbles = listOf(existingBubble))
        assertTrue(result.isEmpty())  // 重复的被过滤
    }

    @Test
    fun `addFromRest accepts multiple distinct REST bubbles in degraded mode`() {
        val restBubbles = listOf(
            SceneBubble.Narration(id = "r_1", text = "REST narration 1"),
            SceneBubble.Dialogue(id = "r_2", actorName = "Alice", text = "Hello")
        )
        val currentBubbles = emptyList<SceneBubble>()
        val result = bubbleMerger.addFromRest(restBubbles, isWsConnected = false, currentBubbles = currentBubbles)
        assertEquals(2, result.size)
    }

    @Test
    fun `addFromRest returns empty for empty input`() {
        val result = bubbleMerger.addFromRest(emptyList(), isWsConnected = false, currentBubbles = emptyList())
        assertTrue(result.isEmpty())
    }

    // ===== mergeAfterReconnect 测试 =====

    @Test
    fun `mergeAfterReconnect returns server bubbles when local is empty`() {
        val serverBubbles = listOf(
            SceneBubble.Narration(id = "s_1", text = "Server text")
        )
        val result = bubbleMerger.mergeAfterReconnect(localBubbles = emptyList(), serverBubbles = serverBubbles)
        assertEquals(1, result.size)
    }

    @Test
    fun `mergeAfterReconnect returns local bubbles when server is empty`() {
        val localBubbles = listOf(
            SceneBubble.Narration(id = "l_1", text = "Local text")
        )
        val result = bubbleMerger.mergeAfterReconnect(localBubbles = localBubbles, serverBubbles = emptyList())
        assertEquals(1, result.size)
    }

    @Test
    fun `mergeAfterReconnect prefers local version for duplicate content`() {
        // Same content fingerprint — keep local (preserves UI state)
        val localBubble = SceneBubble.Narration(id = "l_1", text = "Shared text")
        val serverBubble = SceneBubble.Narration(id = "s_1", text = "Shared text")
        val result = bubbleMerger.mergeAfterReconnect(
            localBubbles = listOf(localBubble),
            serverBubbles = listOf(serverBubble)
        )
        assertEquals(1, result.size)
        assertEquals("l_1", result[0].id)  // Local version preserved
    }

    @Test
    fun `mergeAfterReconnect adds server-only bubbles`() {
        val localBubble = SceneBubble.Narration(id = "l_1", text = "Local only")
        val serverBubble = SceneBubble.Narration(id = "s_1", text = "Server only")
        val result = bubbleMerger.mergeAfterReconnect(
            localBubbles = listOf(localBubble),
            serverBubbles = listOf(serverBubble)
        )
        assertEquals(2, result.size)
    }
}
