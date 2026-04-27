package com.drama.app.di

import android.content.Context
import com.drama.app.data.local.SecureStorage
import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.remote.api.AuthApiService
import com.drama.app.data.remote.api.DramaApiService
import com.drama.app.data.remote.interceptor.AuthInterceptor
import com.drama.app.data.remote.interceptor.BaseUrlInterceptor
import com.drama.app.data.remote.interceptor.NetworkExceptionInterceptor
import com.drama.app.data.remote.ws.WebSocketManager
import com.drama.app.BuildConfig
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.scopes.ActivityScoped
import dagger.hilt.components.SingletonComponent
import dagger.hilt.android.qualifiers.ApplicationContext
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
    fun provideBaseUrlInterceptor(serverPreferences: ServerPreferences): BaseUrlInterceptor {
        return BaseUrlInterceptor(serverPreferences)
    }

    @Provides
    @Singleton
    fun provideAuthInterceptor(secureStorage: SecureStorage): AuthInterceptor {
        return AuthInterceptor(secureStorage)
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        baseUrlInterceptor: BaseUrlInterceptor,
        authInterceptor: AuthInterceptor,
        networkExceptionInterceptor: NetworkExceptionInterceptor,
    ): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(baseUrlInterceptor)           // D-23-10: 动态 BaseUrl
            .addInterceptor(authInterceptor)
            .addInterceptor(networkExceptionInterceptor)
            .apply {
                // D-23-15: HttpLoggingInterceptor 仅在 DEBUG 时注入
                if (BuildConfig.DEBUG) {
                    val loggingInterceptor = HttpLoggingInterceptor().apply {
                        level = HttpLoggingInterceptor.Level.BODY
                        redactHeader("Authorization")
                    }
                    addInterceptor(loggingInterceptor)
                }
            }
            .connectTimeout(30, TimeUnit.SECONDS)  // Cloud servers may need cold-start time
            .readTimeout(300, TimeUnit.SECONDS)  // LLM calls can take minutes
            .writeTimeout(30, TimeUnit.SECONDS)
            .pingInterval(60, TimeUnit.SECONDS)  // TCP keepalive; app-level heartbeat at 15s is authoritative
            .build()
    }

    // D-23-10: BaseUrlInterceptor 动态替换 URL，Retrofit baseUrl 仅作初始占位
    @Provides
    @Singleton
    fun provideRetrofit(
        okHttpClient: OkHttpClient,
        json: Json,
        serverPreferences: ServerPreferences,
    ): Retrofit {
        val baseUrl = serverPreferences.currentApiBaseUrl()
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
}

/**
 * D-23-05: WebSocketModule — 独立 Module，@InstallIn(ActivityComponent::class)
 * WebSocketManager 从 @Singleton 降级为 @ActivityScoped，连接跟随页面生命周期。
 * D-23-06: 多 VM 通过 acquire/release 引用计数共享连接。
 */
@Module
@InstallIn(dagger.hilt.android.components.ActivityComponent::class)
object WebSocketModule {

    @ActivityScoped
    @Provides
    fun provideWebSocketManager(
        json: Json,
        @ApplicationContext context: Context,
        okHttpClient: OkHttpClient,
    ): WebSocketManager {
        return WebSocketManager(json, context, okHttpClient)
    }
}
