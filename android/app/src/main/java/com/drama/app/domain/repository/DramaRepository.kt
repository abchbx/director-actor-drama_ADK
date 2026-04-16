package com.drama.app.domain.repository

import com.drama.app.data.remote.dto.CommandResponseDto
import com.drama.app.data.remote.dto.DramaStatusResponseDto
import com.drama.app.data.remote.dto.SaveLoadResponseDto
import com.drama.app.data.remote.dto.SceneDetailDto
import com.drama.app.data.remote.dto.ScenesResponseDto
import com.drama.app.domain.model.Drama

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
}
