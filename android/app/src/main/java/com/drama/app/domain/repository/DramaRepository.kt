package com.drama.app.domain.repository

import com.drama.app.data.remote.dto.CastResponseDto
import com.drama.app.data.remote.dto.CastStatusResponseDto
import com.drama.app.data.remote.dto.CommandResponseDto
import com.drama.app.data.remote.dto.DramaStatusResponseDto
import com.drama.app.data.remote.dto.SaveLoadResponseDto
import com.drama.app.data.remote.dto.SceneDetailDto
import com.drama.app.data.remote.dto.ScenesResponseDto
import com.drama.app.domain.model.ActorInfo
import com.drama.app.domain.model.Drama
import com.drama.app.domain.model.SceneBubble

interface DramaRepository {
    suspend fun startDrama(theme: String): Result<CommandResponseDto>
    suspend fun listDramas(): Result<List<Drama>>
    suspend fun deleteDrama(folder: String): Result<String>
    suspend fun saveDrama(saveName: String = ""): Result<SaveLoadResponseDto>
    suspend fun loadDrama(saveName: String): Result<SaveLoadResponseDto>
    suspend fun getDramaStatus(): Result<DramaStatusResponseDto>
    suspend fun nextScene(): Result<CommandResponseDto>
    suspend fun userAction(description: String): Result<CommandResponseDto>
    suspend fun actorSpeak(actorName: String, situation: String): Result<CommandResponseDto>
    suspend fun endDrama(): Result<CommandResponseDto>
    suspend fun getScenes(): Result<ScenesResponseDto>
    suspend fun getSceneDetail(sceneNumber: Int): Result<SceneDetailDto>
    suspend fun getCastStatus(): Result<CastStatusResponseDto>
    suspend fun getCast(): Result<CastResponseDto>
    suspend fun sendChatMessage(message: String, mention: String? = null): Result<CommandResponseDto>

    // ===== 业务逻辑下沉：返回领域模型而非 DTO =====

    /**
     * 发送群聊消息并直接返回可渲染的 SceneBubble 列表。
     * 将 CommandResponseDto → SceneBubble 的转换逻辑封装在 Repository 层。
     */
    suspend fun sendChatMessageAsBubbles(message: String, mention: String? = null): Result<List<SceneBubble>>

    /**
     * 获取场景详情并转换为可渲染的 SceneBubble 列表。
     * @param prefix 气泡 id 前缀（如 "init_", "poll_", "hist_"）
     * @param includeDivider 是否包含场景分隔线
     */
    suspend fun getSceneBubbles(sceneNumber: Int, prefix: String = "init_", includeDivider: Boolean = true): Result<List<SceneBubble>>

    /**
     * 获取合并后的演员列表（Cast + CastStatus → ActorInfo）。
     * 将两个 API 的数据合并逻辑封装在 Repository 层。
     */
    suspend fun getMergedCast(): Result<List<ActorInfo>>
}
