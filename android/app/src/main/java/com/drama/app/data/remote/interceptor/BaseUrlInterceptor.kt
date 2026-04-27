package com.drama.app.data.remote.interceptor

import com.drama.app.data.local.ServerPreferences
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

/**
 * 动态 BaseUrl 切换拦截器（per D-23-10）。
 * 从 ServerPreferences 读取当前 BaseUrl，替换请求 URL 的 scheme/host/port。
 * 支持运行时切换服务器地址，新请求立即指向新地址，无需重启应用。
 */
class BaseUrlInterceptor @Inject constructor(
    private val serverPreferences: ServerPreferences,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val currentBaseUrl = serverPreferences.currentApiBaseUrl()
        val newBaseUrl = currentBaseUrl.toHttpUrlOrNull() ?: return chain.proceed(originalRequest)

        val newUrl = originalRequest.url.newBuilder()
            .scheme(newBaseUrl.scheme)
            .host(newBaseUrl.host)
            .port(newBaseUrl.port)
            .build()

        val newRequest = originalRequest.newBuilder()
            .url(newUrl)
            .build()

        return chain.proceed(newRequest)
    }
}
