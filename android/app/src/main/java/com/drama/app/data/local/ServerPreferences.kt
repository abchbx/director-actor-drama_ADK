package com.drama.app.data.local

import android.content.SharedPreferences
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
    private val dataStore: DataStore<Preferences>,        // D-04
    private val encryptedPrefs: SharedPreferences,         // D-04: EncryptedSharedPreferences for token
) {
    companion object {
        val SERVER_IP = stringPreferencesKey("server_ip")
        val SERVER_PORT = stringPreferencesKey("server_port")
        private const val ENCRYPTED_KEY_TOKEN = "auth_token"  // D-04: token encrypted via EncryptedSharedPreferences
        val LAST_CONNECTED = longPreferencesKey("last_connected")
    }

    val serverConfig: Flow<ServerConfig?> = dataStore.data.map { prefs ->
        val ip = prefs[SERVER_IP] ?: return@map null
        val port = prefs[SERVER_PORT] ?: return@map null
        ServerConfig(
            ip = ip,
            port = port,
            token = encryptedPrefs.getString(ENCRYPTED_KEY_TOKEN, null),
            lastConnected = prefs[LAST_CONNECTED],
        )
    }

    suspend fun saveServerConfig(config: ServerConfig) {
        dataStore.edit { prefs ->
            prefs[SERVER_IP] = config.ip
            prefs[SERVER_PORT] = config.port
            prefs[LAST_CONNECTED] = System.currentTimeMillis()
        }
        // D-04: Token encrypted separately via EncryptedSharedPreferences
        config.token?.let { token ->
            encryptedPrefs.edit().putString(ENCRYPTED_KEY_TOKEN, token).apply()
        } ?: run {
            encryptedPrefs.edit().remove(ENCRYPTED_KEY_TOKEN).apply()
        }
    }

    suspend fun clearServerConfig() {
        dataStore.edit { prefs ->
            prefs.remove(SERVER_IP)
            prefs.remove(SERVER_PORT)
            prefs.remove(LAST_CONNECTED)
        }
        encryptedPrefs.edit().remove(ENCRYPTED_KEY_TOKEN).apply()
    }

    // Interceptor 需要同步读取 token
    suspend fun getTokenSync(): String? {
        return encryptedPrefs.getString(ENCRYPTED_KEY_TOKEN, null)
    }
}
