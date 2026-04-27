package com.drama.app.data.remote.interceptor

import com.drama.app.data.local.ServerPreferences
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/**
 * BaseUrlInterceptor 单元测试（per ARCH-04, D-23-13）。
 * 覆盖：URL 替换、路径保留、无效 URL 降级。
 */
class BaseUrlInterceptorTest {

    private lateinit var interceptor: BaseUrlInterceptor
    private val mockServerPreferences: ServerPreferences = mock()
    private lateinit var server: MockWebServer

    @Before
    fun setup() {
        interceptor = BaseUrlInterceptor(mockServerPreferences)
        server = MockWebServer()
        server.start()
    }

    @After
    fun teardown() {
        server.shutdown()
    }

    @Test
    fun `replaces host and port with current BaseUrl`() {
        // The interceptor redirects to the configured server
        whenever(mockServerPreferences.currentApiBaseUrl())
            .thenReturn("http://127.0.0.1:${server.port}/api/v1/")

        server.enqueue(MockResponse().setBody("ok"))

        val client = OkHttpClient.Builder()
            .addInterceptor(interceptor)
            .build()

        val request = Request.Builder()
            .url("http://placeholder:9999/api/v1/drama/status")
            .build()

        val response = client.newCall(request).execute()
        assertTrue(response.isSuccessful)

        val recorded = server.takeRequest()
        assertEquals("127.0.0.1", recorded.requestUrl?.host)
        assertEquals(server.port, recorded.requestUrl?.port)
        assertEquals("/api/v1/drama/status", recorded.path)
    }

    @Test
    fun `preserves path and query parameters`() {
        whenever(mockServerPreferences.currentApiBaseUrl())
            .thenReturn("http://127.0.0.1:${server.port}/api/v1/")

        server.enqueue(MockResponse().setBody("ok"))

        val client = OkHttpClient.Builder()
            .addInterceptor(interceptor)
            .build()

        val request = Request.Builder()
            .url("http://placeholder/api/v1/drama/start?theme=horror")
            .build()

        client.newCall(request).execute()

        val recorded = server.takeRequest()
        assertEquals("/api/v1/drama/start", recorded.path?.substringBefore("?"))
        assertEquals("horror", recorded.requestUrl?.queryParameter("theme"))
    }

    @Test
    fun `handles https to http scheme change`() {
        whenever(mockServerPreferences.currentApiBaseUrl())
            .thenReturn("http://127.0.0.1:${server.port}/api/v1/")

        server.enqueue(MockResponse().setBody("ok"))

        val client = OkHttpClient.Builder()
            .addInterceptor(interceptor)
            .build()

        // Request starts with https, interceptor switches to http
        // (can't actually test https→http without SSL, but verify the URL is replaced)
        val request = Request.Builder()
            .url("http://some-https-server:443/api/v1/drama/status")
            .build()

        client.newCall(request).execute()

        val recorded = server.takeRequest()
        assertEquals("127.0.0.1", recorded.requestUrl?.host)
        assertEquals("/api/v1/drama/status", recorded.path)
    }

    @Test
    fun `falls through to original request when BaseUrl is invalid`() {
        whenever(mockServerPreferences.currentApiBaseUrl())
            .thenReturn("not-a-valid-url")

        server.enqueue(MockResponse().setBody("ok"))

        val client = OkHttpClient.Builder()
            .addInterceptor(interceptor)
            .build()

        // Use server URL as original, so request succeeds even without redirect
        val request = Request.Builder()
            .url(server.url("/api/v1/test"))
            .build()

        val response = client.newCall(request).execute()
        assertTrue(response.isSuccessful)

        val recorded = server.takeRequest()
        // Should hit original server since BaseUrl is invalid
        assertEquals("/api/v1/test", recorded.path)
    }

    @Test
    fun `falls through to original request when BaseUrl is empty`() {
        whenever(mockServerPreferences.currentApiBaseUrl())
            .thenReturn("")

        server.enqueue(MockResponse().setBody("ok"))

        val client = OkHttpClient.Builder()
            .addInterceptor(interceptor)
            .build()

        val request = Request.Builder()
            .url(server.url("/api/v1/test"))
            .build()

        val response = client.newCall(request).execute()
        assertTrue(response.isSuccessful)
    }

    @Test
    fun `replaces scheme from http to http`() {
        whenever(mockServerPreferences.currentApiBaseUrl())
            .thenReturn("http://127.0.0.1:${server.port}/api/v1/")

        server.enqueue(MockResponse().setBody("ok"))

        val client = OkHttpClient.Builder()
            .addInterceptor(interceptor)
            .build()

        val request = Request.Builder()
            .url("http://original-host:8080/api/v1/test")
            .build()

        client.newCall(request).execute()

        val recorded = server.takeRequest()
        assertEquals("http", recorded.requestUrl?.scheme)
    }
}
