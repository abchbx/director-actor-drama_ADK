package com.drama.app.domain.repository

import com.drama.app.domain.model.AuthMode

interface AuthRepository {
    suspend fun verifyServer(ip: String, port: String): Result<AuthMode>
}
