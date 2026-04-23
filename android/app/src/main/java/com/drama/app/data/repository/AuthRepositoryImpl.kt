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
    private val okHttpClient: OkHttpClient,
    private val json: Json,
) : AuthRepository {

    override suspend fun verifyServer(ip: String, port: String, baseUrl: String?): Result<AuthMode> {
        return try {
            // 临时构建 Retrofit 实例用于验证（连接前不知道最终服务器）
            // 验证请求不注入 token，使用无拦截器的 OkHttpClient
            val noAuthClient = okHttpClient.newBuilder()
                .addInterceptor { chain -> chain.proceed(chain.request()) }
                .build()
            val apiBaseUrl = if (!baseUrl.isNullOrBlank()) {
                val base = baseUrl.trimEnd('/')
                "$base/api/v1/"
            } else {
                "http://$ip:$port/api/v1/"
            }
            val retrofit = Retrofit.Builder()
                .baseUrl(apiBaseUrl)
                .client(noAuthClient)
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
        } catch (e: retrofit2.HttpException) {
            if (e.code() == 401) {
                Result.failure(Exception("AUTH_FAILED"))
            } else {
                Result.failure(Exception("UNKNOWN:${e.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(Exception("UNKNOWN:${e.message}"))
        }
    }
}
