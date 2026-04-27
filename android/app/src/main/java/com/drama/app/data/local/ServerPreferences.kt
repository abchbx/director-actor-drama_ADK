package com.drama.app.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import com.drama.app.domain.model.ServerConfig
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking
import javax.inject.Inject
import javax.inject.Singleton

/**
 * BaseUrl 配置管理（per D-23-10）。
 * DataStore 持久化 + 内存缓存同步读取，支持运行时切换服务器。
 */
@Singleton
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

    /** D-23-10: 内存缓存，避免每次请求都读 DataStore */
    @Volatile
    private var cachedApiBaseUrl: String? = null

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

    /** D-23-10: 获取当前 REST API BaseUrl（内存缓存优先，同步调用，供 BaseUrlInterceptor 使用） */
    fun currentApiBaseUrl(): String {
        cachedApiBaseUrl?.let { return it }
        // 首次访问从 DataStore 加载（T-23-09: runBlocking 仅在缓存为空时调用）
        val config = runBlocking { serverConfig.first() }
        val url = config?.toApiBaseUrl() ?: "http://127.0.0.1:8000/api/v1/"
        cachedApiBaseUrl = url
        return url
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
        // 更新内存缓存
        cachedApiBaseUrl = config.toApiBaseUrl()
        // Token 加密存储委托给 SecureStorage
        secureStorage.saveToken(config.token)
    }

    suspend fun clearServerConfig() {
        dataStore.edit { prefs ->
            prefs.remove(SERVER_IP)
            prefs.remove(SERVER_PORT)
            prefs.remove(LAST_CONNECTED)
        }
        cachedApiBaseUrl = null
        secureStorage.saveToken(null)
    }
}
