package com.drama.app.data.remote.api

import com.drama.app.data.remote.dto.AuthVerifyResponseDto
import retrofit2.http.GET

interface AuthApiService {
    @GET("auth/verify")
    suspend fun verifyToken(): AuthVerifyResponseDto
}
