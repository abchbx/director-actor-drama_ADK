package com.drama.app.data.repository

import com.drama.app.data.remote.api.DramaApiService
import com.drama.app.data.remote.dto.ActionRequestDto
import com.drama.app.data.remote.dto.ChatRequestDto
import com.drama.app.data.remote.dto.CommandResponseDto
import com.drama.app.data.remote.dto.LoadRequestDto
import com.drama.app.data.remote.dto.SaveRequestDto
import com.drama.app.data.remote.dto.SpeakRequestDto
import com.drama.app.data.remote.dto.SteerRequestDto
import com.drama.app.data.remote.dto.AutoRequestDto
import com.drama.app.data.remote.dto.StormRequestDto
import com.drama.app.data.remote.dto.ExportRequestDto
import com.drama.app.data.remote.dto.ExportResponseDto
import com.drama.app.data.remote.dto.StartDramaRequestDto
import com.drama.app.domain.model.ActorInfo
import com.drama.app.domain.model.Drama
import com.drama.app.domain.model.SceneBubble
import com.drama.app.domain.repository.DramaRepository
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject

class DramaRepositoryImpl @Inject constructor(
    private val dramaApiService: DramaApiService,
) : DramaRepository {

    // ===== 原有 DTO 级方法 =====

    override suspend fun startDrama(theme: String): Result<CommandResponseDto> =
        runCatching {
            dramaApiService.startDrama(StartDramaRequestDto(theme))
        }

    override suspend fun listDramas(): Result<List<Drama>> = runCatching {
        dramaApiService.listDramas().dramas.map { dto -> dramaItemDtoToDrama(dto) }
    }

    override suspend fun deleteDrama(folder: String): Result<String> = runCatching {
        dramaApiService.deleteDrama(folder)
        folder
    }

    override suspend fun saveDrama(saveName: String): Result<com.drama.app.data.remote.dto.SaveLoadResponseDto> =
        runCatching {
            dramaApiService.saveDrama(SaveRequestDto(saveName))
        }

    override suspend fun loadDrama(saveName: String): Result<com.drama.app.data.remote.dto.SaveLoadResponseDto> =
        runCatching {
            dramaApiService.loadDrama(LoadRequestDto(saveName))
        }

    override suspend fun getDramaStatus(): Result<com.drama.app.data.remote.dto.DramaStatusResponseDto> =
        runCatching {
            dramaApiService.getDramaStatus()
        }

    override suspend fun nextScene(): Result<CommandResponseDto> =
        runCatching {
            dramaApiService.nextScene()
        }

    override suspend fun userAction(description: String): Result<CommandResponseDto> =
        runCatching {
            dramaApiService.userAction(ActionRequestDto(description))
        }

    override suspend fun actorSpeak(actorName: String, situation: String): Result<CommandResponseDto> =
        runCatching {
            dramaApiService.actorSpeak(SpeakRequestDto(actorName, situation))
        }

    override suspend fun endDrama(): Result<CommandResponseDto> =
        runCatching {
            dramaApiService.endDrama()
        }

    override suspend fun steerDrama(direction: String): Result<CommandResponseDto> =
        runCatching {
            dramaApiService.steerDrama(SteerRequestDto(direction))
        }

    override suspend fun autoAdvanceDrama(numScenes: Int): Result<CommandResponseDto> =
        runCatching {
            dramaApiService.autoAdvance(AutoRequestDto(numScenes))
        }

    override suspend fun stormDrama(focus: String?): Result<CommandResponseDto> =
        runCatching {
            dramaApiService.triggerStorm(StormRequestDto(focus))
        }

    override suspend fun exportDrama(format: String): Result<ExportResponseDto> =
        runCatching {
            dramaApiService.exportDrama(ExportRequestDto(format))
        }

    override suspend fun getScenes(): Result<com.drama.app.data.remote.dto.ScenesResponseDto> =
        runCatching {
            dramaApiService.getDramaScenes()
        }

    override suspend fun getSceneDetail(sceneNumber: Int): Result<com.drama.app.data.remote.dto.SceneDetailDto> {
        return runCatching {
            try {
                dramaApiService.getDramaSceneDetail(sceneNumber)
            } catch (e: retrofit2.HttpException) {
                // T-17-11: Retry on 404 for current scene (file may not be generated yet)
                if (e.code() == 404 && sceneNumber > 0) {
                    kotlinx.coroutines.delay(1000)
                    dramaApiService.getDramaSceneDetail(sceneNumber)
                } else {
                    throw e
                }
            }
        }
    }

    override suspend fun getCastStatus(): Result<com.drama.app.data.remote.dto.CastStatusResponseDto> =
        runCatching {
            dramaApiService.getCastStatus()
        }

    override suspend fun getCast(): Result<com.drama.app.data.remote.dto.CastResponseDto> =
        runCatching {
            dramaApiService.getCast()
        }

    override suspend fun sendChatMessage(message: String, mention: String?): Result<CommandResponseDto> =
        runCatching {
            dramaApiService.chatMessage(ChatRequestDto(message, mention))
        }

    // ===== 业务逻辑下沉：领域模型级方法 =====

    override suspend fun sendChatMessageAsBubbles(message: String, mention: String?, senderName: String): Result<List<SceneBubble>> =
        runCatching {
            val resp = dramaApiService.chatMessage(ChatRequestDto(message, mention, senderType = "user", senderName = senderName))
            extractBubblesFromCommandResponse(resp)
        }

    override suspend fun getSceneBubbles(sceneNumber: Int, prefix: String, includeDivider: Boolean): Result<List<SceneBubble>> =
        runCatching {
            val detail = dramaApiService.getDramaSceneDetail(sceneNumber)
            sceneDetailToBubbles(detail, sceneNumber, prefix, includeDivider)
        }

    override suspend fun getMergedCast(): Result<List<ActorInfo>> = runCatching {
        val cast = try {
            dramaApiService.getCast()
        } catch (e: Exception) {
            // /drama/cast 可能因 drama 未初始化而 404 — 返回空列表而非失败
            return Result.success(emptyList())
        }
        // 容错：cast/status 失败不影响 cast 数据展示
        val status = try {
            dramaApiService.getCastStatus()
        } catch (e: Exception) {
            com.drama.app.data.remote.dto.CastStatusResponseDto()
        }
        mergeCastWithStatus(cast, status)
    }

    // ===== 私有映射方法 =====

    private fun dramaItemDtoToDrama(dto: com.drama.app.data.remote.dto.DramaItemDto): Drama =
        Drama(
            folder = dto.folder,
            theme = dto.theme,
            status = dto.status,
            updatedAt = dto.updated_at,
            currentScene = dto.current_scene,
            snapshots = dto.snapshots,
        )

    /**
     * 将换行符转换为 Markdown 支持的格式
     * 单个 \n 转换为双 \n\n，以支持 Markdown 段落分隔
     */
    private fun normalizeLineBreaks(text: String): String {
        return text.replace("\\n", "\n\n")
    }

    /**
     * 从 CommandResponseDto 提取可渲染的 SceneBubble 列表
     */
    private fun extractBubblesFromCommandResponse(resp: CommandResponseDto): List<SceneBubble> {
        val bubbles = mutableListOf<SceneBubble>()
        var counter = 0

        if (resp.final_response.isNotBlank() && resp.final_response.length > 5) {
            bubbles.add(SceneBubble.Narration(
                id = "api_resp_n_${counter++}",
                text = normalizeLineBreaks(resp.final_response.trim()),
            ))
        }

        for (result in resp.tool_results) {
            val actorName = result["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
            val narrationText = result["narration"]?.jsonPrimitive?.contentOrNull
                ?: result["formatted_narration"]?.jsonPrimitive?.contentOrNull
            val dialogueText = result["text"]?.jsonPrimitive?.contentOrNull
            val emotion = result["emotion"]?.jsonPrimitive?.contentOrNull ?: ""

            if (!actorName.isNullOrBlank() && !dialogueText.isNullOrBlank()) {
                bubbles.add(SceneBubble.Dialogue(
                    id = "api_resp_d_${counter++}",
                    actorName = actorName,
                    text = normalizeLineBreaks(dialogueText),
                    emotion = emotion,
                ))
            } else if (!narrationText.isNullOrBlank() && narrationText.length > 3) {
                bubbles.add(SceneBubble.Narration(
                    id = "api_resp_tool_n_${counter++}",
                    text = normalizeLineBreaks(narrationText),
                ))
            }
        }

        return bubbles
    }

    /**
     * 将 SceneDetailDto 转换为 SceneBubble 列表
     */
    private fun sceneDetailToBubbles(
        detail: com.drama.app.data.remote.dto.SceneDetailDto,
        sceneNumber: Int,
        prefix: String,
        includeDivider: Boolean,
    ): List<SceneBubble> {
        val bubbles = mutableListOf<SceneBubble>()

        if (includeDivider) {
            bubbles.add(SceneBubble.SceneDivider(
                id = "${prefix}div_$sceneNumber",
                sceneNumber = sceneNumber,
                sceneTitle = detail.title,
            ))
        }

        if (detail.narration.isNotBlank()) {
            bubbles.add(SceneBubble.Narration(
                id = "${prefix}${sceneNumber}_n",
                text = detail.narration,
            ))
        }

        for ((idx, d) in detail.dialogue.withIndex()) {
            val actorName = d["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
            val text = d["text"]?.jsonPrimitive?.contentOrNull ?: ""
            val emotion = d["emotion"]?.jsonPrimitive?.contentOrNull ?: ""
            if (actorName.isNotBlank() && text.isNotBlank()) {
                bubbles.add(SceneBubble.Dialogue(
                    id = "${prefix}${sceneNumber}_d$idx",
                    actorName = actorName,
                    text = text,
                    emotion = emotion,
                ))
            }
        }

        return bubbles
    }

    /**
     * 合并 Cast 和 CastStatus 为 ActorInfo 列表
     */
    private fun mergeCastWithStatus(
        cast: com.drama.app.data.remote.dto.CastResponseDto,
        status: com.drama.app.data.remote.dto.CastStatusResponseDto,
    ): List<ActorInfo> {
        val statusMap = status.actors
        val mergedActors = mutableListOf<ActorInfo>()

        for ((name, actorElement) in cast.actors) {
            val actorObj = (actorElement as? JsonObject)?.jsonObject ?: continue
            val role = actorObj["role"]?.jsonPrimitive?.contentOrNull ?: ""
            val personality = actorObj["personality"]?.jsonPrimitive?.contentOrNull ?: ""
            val background = actorObj["background"]?.jsonPrimitive?.contentOrNull ?: ""
            val emotions = actorObj["emotions"]?.jsonPrimitive?.contentOrNull ?: "neutral"
            val memorySummary = buildMemorySummary(actorObj)

            val a2aData = statusMap[name]
            val a2aObj = a2aData as? JsonObject
            val isRunning = a2aObj?.get("running")?.jsonPrimitive?.booleanOrNull ?: false
            val port = a2aObj?.get("port")?.jsonPrimitive?.intOrNull ?: 0
            val thinkingSteps = a2aObj?.get("thinking_steps")?.jsonPrimitive?.intOrNull
                ?: a2aObj?.get("steps")?.jsonPrimitive?.intOrNull
                ?: a2aObj?.get("progress")?.jsonPrimitive?.intOrNull
                ?: 0

            mergedActors.add(ActorInfo(
                name = name,
                role = role,
                personality = personality,
                background = background,
                emotions = emotions,
                memorySummary = memorySummary,
                isA2ARunning = isRunning,
                a2aPort = port,
                thinkingProgress = thinkingSteps,
            ))
        }

        return mergedActors
    }

    private fun buildMemorySummary(actorObj: JsonObject): String {
        val memoryArray = actorObj["memory"]?.jsonArray ?: return ""
        return memoryArray.mapNotNull { it.jsonPrimitive.contentOrNull }.joinToString(" ").take(500)
    }
}
