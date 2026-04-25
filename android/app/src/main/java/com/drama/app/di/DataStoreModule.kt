package com.drama.app.di

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStore
import com.drama.app.data.local.DramaSaveRepository
import com.drama.app.data.local.SecureStorage
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

private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(name = "drama_settings")
private val Context.savesDataStore: DataStore<Preferences> by preferencesDataStore(name = "drama_saves")

@Module
@InstallIn(SingletonComponent::class)
object DataStoreModule {

    @Provides
    @Singleton
    fun provideSettingsDataStore(@ApplicationContext context: Context): DataStore<Preferences> {
        return context.settingsDataStore
    }

    @Provides
    @Singleton
    @SavesDataStore
    fun provideSavesDataStore(@ApplicationContext context: Context): DataStore<Preferences> {
        return context.savesDataStore
    }

    @Provides
    @Singleton
    fun provideServerPreferences(
        dataStore: DataStore<Preferences>,
        secureStorage: SecureStorage,
    ): ServerPreferences {
        return ServerPreferences(dataStore, secureStorage)
    }

    @Provides
    @Singleton
    fun provideDramaSaveRepository(
        @SavesDataStore savesDataStore: DataStore<Preferences>,
    ): DramaSaveRepository {
        return DramaSaveRepository(savesDataStore)
    }

    @Provides
    @Singleton
    fun provideServerRepository(
        serverPreferences: ServerPreferences,
        secureStorage: SecureStorage,
    ): ServerRepository {
        return ServerRepositoryImpl(serverPreferences, secureStorage)
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
