package com.drama.app.data.repository

import com.drama.app.data.local.SecureStorage
import com.drama.app.data.local.ServerPreferences
import com.drama.app.domain.model.ServerConfig
import com.drama.app.domain.repository.ServerRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject

class ServerRepositoryImpl @Inject constructor(
    private val serverPreferences: ServerPreferences,
    private val secureStorage: SecureStorage,
) : ServerRepository {
    override val serverConfig: Flow<ServerConfig?> = serverPreferences.serverConfig

    override suspend fun saveServerConfig(config: ServerConfig) {
        serverPreferences.saveServerConfig(config)
    }

    override suspend fun clearServerConfig() {
        serverPreferences.clearServerConfig()
    }
}
