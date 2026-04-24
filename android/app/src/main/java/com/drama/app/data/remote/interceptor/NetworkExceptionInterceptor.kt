package com.drama.app.data.remote.interceptor

import android.util.Log
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import javax.inject.Inject

/**
 * 全局网络异常拦截器
 *
 * 捕获 OkHttp 层的网络异常（超时、DNS 解析失败等），
 * 将其转换为带有友好错误信息的 HTTP 响应，而非抛出未捕获异常。
 * 这样 Repository 层的 Retrofit 调用会收到 onFailure 回调而非 crash。
 */
class NetworkExceptionInterceptor @Inject constructor() : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request: Request = chain.request()
        return try {
            chain.proceed(request)
        } catch (e: SocketTimeoutException) {
            Log.w(TAG, "Network timeout: ${request.url}", e)
            buildErrorResponse(
                request = request,
                code = 504,
                message = "网络连接超时，请检查网络后重试",
            )
        } catch (e: UnknownHostException) {
            Log.w(TAG, "DNS resolution failed: ${request.url}", e)
            buildErrorResponse(
                request = request,
                code = 503,
                message = "无法连接到服务器，请检查网络或服务器地址",
            )
        } catch (e: java.net.ConnectException) {
            Log.w(TAG, "Connection refused: ${request.url}", e)
            buildErrorResponse(
                request = request,
                code = 503,
                message = "服务器连接被拒绝，请检查服务器是否运行",
            )
        } catch (e: javax.net.ssl.SSLException) {
            Log.w(TAG, "SSL error: ${request.url}", e)
            buildErrorResponse(
                request = request,
                code = 503,
                message = "安全连接失败，请检查服务器证书配置",
            )
        } catch (e: java.io.IOException) {
            Log.w(TAG, "Network IO error: ${request.url}", e)
            buildErrorResponse(
                request = request,
                code = 503,
                message = "网络异常：${e.message ?: "未知错误"}",
            )
        }
    }

    private fun buildErrorResponse(request: Request, code: Int, message: String): Response {
        val errorBody = """{"detail":"$message"}"""
            .toResponseBody("application/json".toMediaType())
        return Response.Builder()
            .request(request)
            .protocol(Protocol.HTTP_1_1)
            .code(code)
            .message(message)
            .body(errorBody)
            .build()
    }

    companion object {
        private const val TAG = "NetworkException"
    }
}
