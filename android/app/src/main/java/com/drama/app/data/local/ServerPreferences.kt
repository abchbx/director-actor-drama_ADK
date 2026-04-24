package com.drama.app.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import com.drama.app.domain.model.ServerConfig
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject

class ServerPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>,
    private val secureStorage: SecureStorage,
) {
    companion object {
        val SERVER_IP = stringPreferencesKey("server_ip")
        val SERVER_PORT = stringPreferencesKey("server_port")
        val SERVER_BASE_URL = stringPreferencesKey("server_base_url")
        val LAST_CONNECTED = longPreferencesKey("last_connected")
    }

    val serverConfig: Flow<ServerConfig?> = dataStore.data.map { prefs ->
        val ip = prefs[SERVER_IP] ?: return@map null
        val port = prefs[SERVER_PORT] ?: return@map null
        val baseUrl = prefs[SERVER_BASE_URL]
        ServerConfig(
            ip = ip,
            port = port,
            token = secureStorage.getToken(),
            lastConnected = prefs[LAST_CONNECTED],
            baseUrl = baseUrl,
        )
    }

    suspend fun saveServerConfig(config: ServerConfig) {
        dataStore.edit { prefs ->
            prefs[SERVER_IP] = config.ip
            prefs[SERVER_PORT] = config.port
            prefs[LAST_CONNECTED] = System.currentTimeMillis()
            if (config.baseUrl.isNullOrBlank()) {
                prefs.remove(SERVER_BASE_URL)
            } else {
                prefs[SERVER_BASE_URL] = config.baseUrl
            }
        }
        // Token 加密存储委托给 SecureStorage
        secureStorage.saveToken(config.token)
    }

    suspend fun clearServerConfig() {
        dataStore.edit { prefs ->
            prefs.remove(SERVER_IP)
            prefs.remove(SERVER_PORT)
            prefs.remove(LAST_CONNECTED)
        }
        secureStorage.saveToken(null)
    }
}
