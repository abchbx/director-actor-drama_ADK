package com.drama.app.data.remote.interceptor

import com.drama.app.data.local.ServerPreferences
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

class AuthInterceptor @Inject constructor(
    private val serverPreferences: ServerPreferences,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val token = runBlocking { serverPreferences.getTokenSync() }
        val request = if (token != null) {
            originalRequest.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            originalRequest
        }
        return chain.proceed(request)
    }
}
