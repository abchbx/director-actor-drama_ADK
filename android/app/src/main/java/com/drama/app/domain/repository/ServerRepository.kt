package com.drama.app.domain.repository

import com.drama.app.domain.model.ServerConfig
import kotlinx.coroutines.flow.Flow

interface ServerRepository {
    val serverConfig: Flow<ServerConfig?>
    suspend fun saveServerConfig(config: ServerConfig)
    suspend fun clearServerConfig()
}
