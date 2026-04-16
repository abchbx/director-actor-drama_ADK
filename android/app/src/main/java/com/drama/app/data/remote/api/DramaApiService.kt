package com.drama.app.data.remote.api

import com.drama.app.data.remote.dto.*
import retrofit2.http.*

interface DramaApiService {
    // === Commands ===
    @POST("drama/start")
    suspend fun startDrama(@Body request: StartDramaRequestDto): CommandResponseDto

    @POST("drama/next")
    suspend fun nextScene(): CommandResponseDto

    @POST("drama/action")
    suspend fun userAction(@Body request: ActionRequestDto): CommandResponseDto

    @POST("drama/speak")
    suspend fun actorSpeak(@Body request: SpeakRequestDto): CommandResponseDto

    @POST("drama/steer")
    suspend fun steerDrama(@Body request: SteerRequestDto): CommandResponseDto

    @POST("drama/auto")
    suspend fun autoAdvance(@Body request: AutoRequestDto): CommandResponseDto

    @POST("drama/storm")
    suspend fun triggerStorm(@Body request: StormRequestDto): CommandResponseDto

    @POST("drama/end")
    suspend fun endDrama(): CommandResponseDto

    // === Queries ===
    @GET("drama/status")
    suspend fun getDramaStatus(): DramaStatusResponseDto

    @GET("drama/cast")
    suspend fun getCast(): CastResponseDto

    @GET("drama/list")
    suspend fun listDramas(): DramaListResponseDto

    @DELETE("drama/{folder}")
    suspend fun deleteDrama(@Path("folder") folder: String): DeleteDramaResponseDto

    @POST("drama/save")
    suspend fun saveDrama(@Body request: SaveRequestDto): SaveLoadResponseDto

    @POST("drama/load")
    suspend fun loadDrama(@Body request: LoadRequestDto): SaveLoadResponseDto

    @POST("drama/export")
    suspend fun exportDrama(@Body request: ExportRequestDto): ExportResponseDto
}
