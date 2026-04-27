package com.drama.app.ui.screens.dramadetail.orchestrator

import com.drama.app.domain.model.SceneBubble
import java.util.concurrent.atomic.AtomicLong
import javax.inject.Inject

/**
 * 气泡列表管理子组件（per D-23-01, D-23-03, ARCH-10）。
 * 管理气泡列表、去重、线程安全 ID 生成（AtomicLong 替代 Int）。
 * 实现 WS优先/REST降级数据源策略（addFromRest），消除双写 UI 闪烁。
 *
 * 架构选择：使用 @Inject constructor — 同 ConnectionOrchestrator 说明。
 */
class BubbleMerger @Inject constructor() {
    /** D-23-03: AtomicLong 替代 Int，线程安全 */
    private val bubbleIdCounter = AtomicLong(0L)

    /** 追踪已添加的错误气泡内容，避免重复 */
    private val addedErrorIds = mutableSetOf<String>()

    /** 生成线程安全的气泡 ID */
    fun nextBubbleId(): String = "b_${bubbleIdCounter.incrementAndGet()}"

    /** 生成指定前缀的气泡 ID */
    fun nextBubbleId(prefix: String): String = "${prefix}${bubbleIdCounter.incrementAndGet()}"

    /**
     * ARCH-10: WS优先/REST降级数据源策略。
     * 当 WS 连接时（isWsConnected=true），REST 更新被静默丢弃（WS 是唯一真相源）。
     * 当 WS 断开时（isWsConnected=false），REST 更新被接受（降级模式）。
     *
     * @param bubbles REST 返回的气泡列表
     * @param isWsConnected 当前 WS 是否连接
     * @param currentBubbles 当前已有气泡列表
     * @return 接受的新气泡（空列表表示被拒绝或已去重）
     */
    fun addFromRest(bubbles: List<SceneBubble>, isWsConnected: Boolean, currentBubbles: List<SceneBubble>): List<SceneBubble> {
        if (isWsConnected) return emptyList()  // WS 连接时拒绝 REST 气泡 — SingleSourceOfTruth

        // WS 断开降级模式：接受 REST 气泡，去重合并
        val existingFingerprints = currentBubbles.map { it.contentFingerprint }.toSet()
        val newBubbles = bubbles.filterNot { restBubble ->
            restBubble.contentFingerprint in existingFingerprints
        }
        return newBubbles
    }

    /**
     * 合并重连后的气泡列表（基于后端权威顺序的智能合并）。
     *
     * 核心原则：
     * - 后端列表为权威顺序来源，新气泡按后端时序插入
     * - 本地气泡保留 UI 状态（如动画、展开等），不丢弃
     * - 通过 contentFingerprint 判断同一消息
     */
    fun mergeAfterReconnect(
        localBubbles: List<SceneBubble>,
        serverBubbles: List<SceneBubble>,
    ): List<SceneBubble> {
        if (serverBubbles.isEmpty()) return localBubbles
        if (localBubbles.isEmpty()) return serverBubbles

        val localFingerprintSet = localBubbles.map { it.contentFingerprint }.toMutableSet()
        val localByFingerprint = localBubbles.associateBy { it.contentFingerprint }

        val merged = mutableListOf<SceneBubble>()
        val mergedFingerprints = mutableSetOf<String>()

        // 1. 按后端权威顺序遍历
        for (serverBubble in serverBubbles) {
            val fp = serverBubble.contentFingerprint
            if (fp in mergedFingerprints) continue

            if (fp in localFingerprintSet) {
                // 本地也有 → 保留本地版本（保留 UI 状态）
                merged.add(localByFingerprint[fp] ?: serverBubble)
            } else {
                // 仅后端有 → 断网期间丢失的新消息
                merged.add(serverBubble)
            }
            mergedFingerprints.add(fp)
        }

        // 2. 追加仅存在于本地的气泡
        for (localBubble in localBubbles) {
            val fp = localBubble.contentFingerprint
            if (fp !in mergedFingerprints) {
                merged.add(localBubble)
                mergedFingerprints.add(fp)
            }
        }

        return merged
    }

    /**
     * 检查错误气泡是否已添加（去重）。
     * @return true 如果该错误已存在，false 表示是新错误可添加
     */
    fun hasError(errorMessage: String): Boolean = addedErrorIds.contains(errorMessage)

    /** 记录已添加的错误 */
    fun markErrorAdded(errorMessage: String) {
        addedErrorIds.add(errorMessage)
    }

    /** 清空所有状态 */
    fun clear() {
        bubbleIdCounter.set(0L)
        addedErrorIds.clear()
    }

    /** D-23-04: 主 VM onCleared 时调用 */
    fun cleanup() {
        clear()
    }
}
