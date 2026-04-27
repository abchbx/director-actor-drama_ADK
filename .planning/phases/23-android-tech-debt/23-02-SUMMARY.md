# Phase 23-02: P1 阵地战 — 质量与安全 — Summary

**Date:** 2026-04-26
**Status:** ✅ COMPLETED
**Wave:** 2

---

## Objective Achieved

动态 BaseUrl 切换 + 网络安全 Debug/Release 分离 + 条件日志注入 + BubbleMerger/CommandRouter 单元测试 + ConnectionOrchestrator isWsConnected 修复。

---

## Tasks Completed

### Task 1a: BaseUrlInterceptor + ServerPreferences + NetworkModule 集成

- **ServerPreferences.kt**: 添加 `currentApiBaseUrl()` 同步方法 + `cachedApiBaseUrl` 内存缓存 + `saveServerConfig()` 更新缓存 + `clearServerConfig()` 清除缓存 (per D-23-10)
- **BaseUrlInterceptor.kt** (~40行): OkHttp Interceptor 从 ServerPreferences 读取当前 BaseUrl，替换请求 URL 的 scheme/host/port (per D-23-10)
- **NetworkModule.kt**:
  - 添加 `provideBaseUrlInterceptor()` 方法
  - `provideOkHttpClient()` 注入 `baseUrlInterceptor` 作为第一个拦截器
  - HttpLoggingInjector 改为 `BuildConfig.DEBUG` 条件注入 (per D-23-15)
  - `provideRetrofit()` 使用 `serverPreferences.currentApiBaseUrl()` 替代 `runBlocking` 读取

### Task 1b: AuthRepository 复用 + 网络安全配置 (Debug/Release 分离)

- **AuthRepositoryImpl.kt**: 已复用注入的 OkHttpClient（23-01 已实现），验证请求使用 `okHttpClient.newBuilder()` 共享连接池 (per D-23-11)
- **network_security_config.xml**: Release 配置 — `cleartextTrafficPermitted="false"` + 白名单仅 localhost/10.0.2.2/127.0.0.1 (per D-23-14)
- **network_security_config_debug.xml**: Debug 配置 — `cleartextTrafficPermitted="true"`，允许 LAN 192.168.x.x
- **AndroidManifest.xml**: `usesCleartextTraffic="false"` + `networkSecurityConfig="${networkSecurityConfig}"` (per D-23-14)
- **build.gradle.kts**: `manifestPlaceholders["networkSecurityConfig"]` 区分 Debug/Release

### Task 2: BubbleMerger/CommandRouter 单元测试 + ConnectionOrchestrator WS 优先策略

- **BubbleMergerTest.kt** (~140行, 15 个 @Test): 覆盖 nextBubbleId、hasError/markErrorAdded、clear/cleanup、addFromRest 数据源策略（WS连接拒绝/WS断开接受/去重）、mergeAfterReconnect (per ARCH-10, ARCH-15)
- **CommandRouterTest.kt** (~130行, 20 个 @Test): 覆盖 route 所有 CommandType、isActionCommand、isPlotChanging、isLocalCommand、getDisplayText、extractMention (per D-23-13)
- **ConnectionOrchestrator.kt**: 修复 isWsConnected — 从每次访问创建新 MutableStateFlow 改为独立 `_isWsConnected` 字段，从 ConnectionState 收集同步更新 (per D-23-16)
- **build.gradle.kts**: 添加 testImplementation junit/mockito-kotlin/coroutines-test (per D-23-12)
- **proguard-rules.pro**: 添加 interceptor 包 keep 规则 (per D-23-09)

---

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `data/remote/interceptor/BaseUrlInterceptor.kt` | ~40 | 动态 BaseUrl 切换拦截器 |
| `res/xml/network_security_config.xml` | 17 | Release 网络安全配置 |
| `res/xml/network_security_config_debug.xml` | 10 | Debug 网络安全配置 |
| `src/test/.../BubbleMergerTest.kt` | ~140 | BubbleMerger 单元测试 |
| `src/test/.../CommandRouterTest.kt` | ~130 | CommandRouter 单元测试 |

## Files Modified

| File | Change |
|------|--------|
| `ServerPreferences.kt` | +currentApiBaseUrl() +cachedApiBaseUrl 内存缓存 +saveServerConfig/clear 更新缓存 |
| `NetworkModule.kt` | +BaseUrlInterceptor 注入 +BuildConfig.DEBUG 条件日志 +currentApiBaseUrl() 替代 runBlocking |
| `AndroidManifest.xml` | usesCleartextTraffic=false + networkSecurityConfig placeholder |
| `build.gradle.kts` | +manifestPlaceholders +testImplementation deps |
| `ConnectionOrchestrator.kt` | 修复 isWsConnected: 独立 _isWsConnected MutableStateFlow |
| `proguard-rules.pro` | +interceptor 包 keep 规则 |

---

## Design Decisions Applied

| ID | Decision | Status |
|----|----------|--------|
| D-23-10 | BaseUrlInterceptor 动态 BaseUrl + ServerPreferences 内存缓存 | ✅ |
| D-23-11 | AuthRepository 复用共享 OkHttpClient | ✅ (23-01 已实现，已验证) |
| D-23-12 | 测试依赖 junit + mockito-kotlin + coroutines-test | ✅ |
| D-23-13 | BubbleMerger/CommandRouter 单元测试覆盖 | ✅ |
| D-23-14 | network_security_config Debug/Release 分离 | ✅ |
| D-23-15 | HttpLoggingInterceptor 仅 DEBUG 注入 | ✅ |
| D-23-16 | ConnectionOrchestrator isWsConnected 独立 StateFlow | ✅ |

---

## Threat Model Mitigations

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-23-06: BaseUrlInterceptor 动态 URL | ServerPreferences.currentApiBaseUrl() 从 DataStore 读取，UI 限制输入 | ✅ |
| T-23-07: network_security_config 白名单 | Release 仅 localhost/10.0.2.2/127.0.0.1 | ✅ |
| T-23-08: HttpLoggingInterceptor in release | BuildConfig.DEBUG 条件注入 | ✅ |
| T-23-09: ServerPreferences runBlocking | 仅首次访问（缓存为空时），后续走内存 | ✅ |
| T-23-10: Debug LAN 明文 | 仅 Debug 构建，不分发 | ✅ |
| T-23-11: addFromRest isWsConnected 竞态 | MutableStateFlow 原子性保证 | ✅ |

---

## Key Code: BaseUrlInterceptor 动态切换流程

```
用户在设置中切换 IP:port → ServerPreferences.saveServerConfig()
  → cachedApiBaseUrl = newUrl + DataStore 持久化
  → 下一个 OkHttp 请求 → BaseUrlInterceptor.intercept()
    → serverPreferences.currentApiBaseUrl() → 返回 cachedBaseUrl
    → 替换 request URL 的 scheme/host/port
  → 无需重启应用
```

---

## Next Steps

Phase 23-03 (P2/P3 扫荡战): 线程安全 + 重试策略 + Room 缓存 + CI/CD + 体积优化
