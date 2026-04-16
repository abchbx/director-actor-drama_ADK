package com.drama.app.di

import android.content.Context
import android.content.SharedPreferences
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStore
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.repository.AuthRepositoryImpl
import com.drama.app.data.repository.ServerRepositoryImpl
import com.drama.app.domain.repository.AuthRepository
import com.drama.app.domain.repository.ServerRepository
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "drama_settings")

@Module
@InstallIn(SingletonComponent::class)
object DataStoreModule {

    @Provides
    @Singleton
    fun provideDataStore(@ApplicationContext context: Context): DataStore<Preferences> {
        return context.dataStore
    }

    // D-04: EncryptedSharedPreferences for token storage
    @Provides
    @Singleton
    fun provideEncryptedSharedPreferences(@ApplicationContext context: Context): SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        return EncryptedSharedPreferences.create(
            context,
            "drama_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    @Provides
    @Singleton
    fun provideServerPreferences(
        dataStore: DataStore<Preferences>,
        encryptedPrefs: SharedPreferences,
    ): ServerPreferences {
        return ServerPreferences(dataStore, encryptedPrefs)
    }

    @Provides
    @Singleton
    fun provideServerRepository(serverPreferences: ServerPreferences): ServerRepository {
        return ServerRepositoryImpl(serverPreferences)
    }

    @Provides
    @Singleton
    fun provideAuthRepository(
        okHttpClient: okhttp3.OkHttpClient,
        json: kotlinx.serialization.json.Json,
    ): AuthRepository {
        return AuthRepositoryImpl(okHttpClient, json)
    }
}
