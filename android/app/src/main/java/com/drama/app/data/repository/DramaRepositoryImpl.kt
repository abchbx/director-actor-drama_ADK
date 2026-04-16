package com.drama.app.data.repository

import com.drama.app.data.remote.api.DramaApiService
import com.drama.app.data.remote.dto.ActionRequestDto
import com.drama.app.data.remote.dto.LoadRequestDto
import com.drama.app.data.remote.dto.SaveRequestDto
import com.drama.app.data.remote.dto.SpeakRequestDto
import com.drama.app.data.remote.dto.StartDramaRequestDto
import com.drama.app.domain.model.Drama
import com.drama.app.domain.repository.DramaRepository
import javax.inject.Inject

class DramaRepositoryImpl @Inject constructor(
    private val dramaApiService: DramaApiService,
) : DramaRepository {

    override suspend fun startDrama(theme: String): Result<com.drama.app.data.remote.dto.CommandResponseDto> =
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

    override suspend fun nextScene(): Result<com.drama.app.data.remote.dto.CommandResponseDto> =
        runCatching {
            dramaApiService.nextScene()
        }

    override suspend fun userAction(description: String): Result<com.drama.app.data.remote.dto.CommandResponseDto> =
        runCatching {
            dramaApiService.userAction(ActionRequestDto(description))
        }

    override suspend fun actorSpeak(actorName: String, situation: String): Result<com.drama.app.data.remote.dto.CommandResponseDto> =
        runCatching {
            dramaApiService.actorSpeak(SpeakRequestDto(actorName, situation))
        }

    override suspend fun endDrama(): Result<com.drama.app.data.remote.dto.CommandResponseDto> =
        runCatching {
            dramaApiService.endDrama()
        }

    override suspend fun getScenes(): Result<com.drama.app.data.remote.dto.ScenesResponseDto> =
        runCatching {
            dramaApiService.getDramaScenes()
        }

    override suspend fun getSceneDetail(sceneNumber: Int): Result<com.drama.app.data.remote.dto.SceneDetailDto> =
        runCatching {
            dramaApiService.getDramaSceneDetail(sceneNumber)
        }

    override suspend fun getCastStatus(): Result<com.drama.app.data.remote.dto.CastStatusResponseDto> =
        runCatching {
            dramaApiService.getCastStatus()
        }

    override suspend fun getCast(): Result<com.drama.app.data.remote.dto.CastResponseDto> =
        runCatching {
            dramaApiService.getCast()
        }

    private fun dramaItemDtoToDrama(dto: com.drama.app.data.remote.dto.DramaItemDto): Drama =
        Drama(
            folder = dto.folder,
            theme = dto.theme,
            status = dto.status,
            updatedAt = dto.updated_at,
            currentScene = dto.current_scene,
            snapshots = dto.snapshots,
        )
}
