package com.drama.app.data.repository

import com.drama.app.data.remote.api.AuthApiService
import com.drama.app.domain.model.AuthMode
import com.drama.app.domain.repository.AuthRepository
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.net.ConnectException
import java.net.SocketTimeoutException
import javax.inject.Inject

class AuthRepositoryImpl @Inject constructor(
    private val json: Json,
    private val okHttpClient: OkHttpClient,
) : AuthRepository {

    override suspend fun verifyServer(ip: String, port: String, baseUrl: String?): Result<AuthMode> {
        return try {
            // 临时构建 Retrofit 实例用于验证（连接前不知道最终服务器）
            // 使用全局 OkHttpClient.newBuilder() 继承超时/日志/异常拦截器，
            // 但移除 BaseUrlInterceptor（index=0），避免其用缓存旧值覆盖验证 URL。
            val verifyClient = okHttpClient.newBuilder()
                .apply {
                    // 移除 BaseUrlInterceptor（动态替换 URL 的拦截器）
                    interceptors().removeIf { it is com.drama.app.data.remote.interceptor.BaseUrlInterceptor }
                }
                .build()
            val apiBaseUrl = if (!baseUrl.isNullOrBlank()) {
                val base = baseUrl.trimEnd('/')
                "$base/api/v1/"
            } else {
                "http://$ip:$port/api/v1/"
            }
            val retrofit = Retrofit.Builder()
                .baseUrl(apiBaseUrl)
                .client(verifyClient)
                .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
                .build()
            val authApi = retrofit.create(AuthApiService::class.java)
            val response = authApi.verifyToken()  // D-02
            if (response.mode == "bypass") {
                Result.success(AuthMode.Bypass)
            } else {
                Result.success(AuthMode.RequireToken)
            }
        } catch (e: SocketTimeoutException) {
            Result.failure(Exception("TIMEOUT"))
        } catch (e: ConnectException) {
            Result.failure(Exception("NETWORK_UNREACHABLE"))
        } catch (e: javax.net.ssl.SSLException) {
            Result.failure(Exception("SSL_ERROR:${e.message}"))
        } catch (e: java.net.UnknownHostException) {
            Result.failure(Exception("DNS_ERROR:${e.message}"))
        } catch (e: retrofit2.HttpException) {
            when (e.code()) {
                401 -> Result.failure(Exception("AUTH_FAILED"))
                504 -> Result.failure(Exception("TIMEOUT"))  // NetworkExceptionInterceptor 合成的 504
                503 -> Result.failure(Exception("NETWORK_UNREACHABLE"))  // NetworkExceptionInterceptor 合成的 503
                else -> Result.failure(Exception("UNKNOWN:${e.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(Exception("UNKNOWN:${e.message}"))
        }
    }
}
