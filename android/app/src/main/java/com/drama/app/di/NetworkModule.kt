package com.drama.app.di

import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.remote.api.AuthApiService
import com.drama.app.data.remote.api.DramaApiService
import com.drama.app.data.remote.interceptor.AuthInterceptor
import com.drama.app.data.remote.ws.WebSocketManager
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true     // 后端可能新增字段，忽略不影响
        coerceInputValues = true     // null → default
        isLenient = true
    }

    @Provides
    @Singleton
    fun provideAuthInterceptor(serverPreferences: ServerPreferences): AuthInterceptor {
        return AuthInterceptor(serverPreferences)
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor,
    ): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BODY
            })
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    // Pitfall 1: Retrofit baseUrl 在构建时固定，无法运行时修改
    // 从 DataStore 读取上次连接的 IP:port 构建 baseUrl
    // 当用户切换服务器时，需要重启 Activity 让 Hilt 重建 DI graph
    @Provides
    @Singleton
    fun provideRetrofit(
        okHttpClient: OkHttpClient,
        json: Json,
        serverPreferences: ServerPreferences,
    ): Retrofit {
        val config = runBlocking { serverPreferences.serverConfig.first() }
        val baseUrl = if (config != null) {
            "http://${config.ip}:${config.port}/api/v1/"
        } else {
            "http://127.0.0.1:8000/api/v1/"  // 占位，首次启动未连接时
        }
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    @Provides
    @Singleton
    fun provideDramaApiService(retrofit: Retrofit): DramaApiService {
        return retrofit.create(DramaApiService::class.java)
    }

    // AuthApiService not provided as Singleton here — AuthRepositoryImpl
    // builds temporary Retrofit instances for verification before connection is established.
    // The Hilt-provided AuthApiService is available for post-connection use if needed.

    @Provides
    @Singleton
    fun provideWebSocketManager(
        okHttpClient: OkHttpClient,
        json: Json,
    ): WebSocketManager {
        return WebSocketManager(okHttpClient, json)
    }
}
