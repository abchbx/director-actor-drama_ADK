package com.drama.app.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 安全存储层：使用 EncryptedSharedPreferences + AES256_GCM MasterKey 加密敏感数据。
 * 所有 token 读写必须通过此入口，禁止明文落盘或日志打印。
 */
@Singleton
class SecureStorage @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val masterKey: MasterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val encryptedPrefs: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        FILE_NAME,
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    // ---- Token ----

    /** 读取加密存储的 auth token，无 token 时返回 null。 */
    fun getToken(): String? = encryptedPrefs.getString(KEY_AUTH_TOKEN, null)

    /** 将 auth token 加密写入存储；传入 null 则清除。 */
    fun saveToken(token: String?) {
        val editor = encryptedPrefs.edit()
        if (token != null) {
            editor.putString(KEY_AUTH_TOKEN, token)
        } else {
            editor.remove(KEY_AUTH_TOKEN)
        }
        editor.apply()
    }

    /** 清除所有安全存储数据（如用户登出时调用）。 */
    fun clearAll() {
        encryptedPrefs.edit().clear().apply()
    }

    companion object {
        private const val FILE_NAME = "drama_secure_prefs"
        private const val KEY_AUTH_TOKEN = "auth_token"
    }
}
