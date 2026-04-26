---
phase: 23
slug: android-tech-debt
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-26
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

|| Property | Value |
||----------|-------|
|| **Framework** | JUnit 4 + kotlinx-coroutines-test 1.10.2 + Turbine 1.2.0 + mockito-kotlin 5.4.0 |
|| **Config file** | none — Wave 0 installs |
|| **Quick run command** | `./gradlew :app:testDebugUnitTest --tests "com.drama.app.*"` |
|| **Full suite command** | `./gradlew :app:testDebugUnitTest` |
|| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./gradlew :app:testDebugUnitTest --tests "com.drama.app.ui.screens.dramadetail.orchestrator.*"`
- **After every plan wave:** Run `./gradlew :app:testDebugUnitTest`
- **Before `/gsd-verify-work`:** Full suite must be green + Release APK 验证混淆生效
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

|| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
||---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
|| 23-01-1a | 01 | 1 | ARCH-01, ARCH-09, ARCH-16, ARCH-17 | — | N/A | unit | `./gradlew :app:testDebugUnitTest --tests "*.BubbleMergerTest"` | ❌ W0 | ⬜ pending |
|| 23-01-1a | 01 | 1 | ARCH-01, ARCH-02, ARCH-17 | — | N/A | unit | `./gradlew :app:testDebugUnitTest --tests "*.ConnectionOrchestratorTest"` | ❌ W0 | ⬜ pending |
|| 23-01-1b | 01 | 1 | ARCH-01 | — | N/A | unit | `./gradlew :app:testDebugUnitTest --tests "*.CommandRouterTest"` | ❌ W0 | ⬜ pending |
|| 23-01-2 | 01 | 1 | ARCH-01, ARCH-07, ARCH-12, ARCH-14 | — | N/A | manual | VM line count: `wc -l DramaDetailViewModel.kt` < 400 | ✅ | ⬜ pending |
|| 23-01-3 | 01 | 1 | ARCH-02 | — | WS 生命周期按 Activity 作用域管理 | unit | `./gradlew :app:testDebugUnitTest --tests "*.WebSocketManagerTest"` | ❌ W0 | ⬜ pending |
|| 23-01-4 | 01 | 1 | ARCH-03 | T-23-01 | R8 混淆 + shrinkResources | manual | `./gradlew assembleRelease && unzip -l app/build/outputs/apk/release/*.apk \| grep com.drama` | ✅ | ⬜ pending |
|| 23-02-1a | 02 | 2 | ARCH-04 | T-23-05 | BaseUrlInterceptor 零阻塞切换 | unit | `./gradlew :app:testDebugUnitTest --tests "*.BaseUrlInterceptorTest"` | ❌ W0 | ⬜ pending |
|| 23-02-1a | 02 | 2 | ARCH-11 | T-23-04 | Release 构建零日志泄露 | manual | 检查 NetworkModule.kt 不含无条件 HttpLoggingInterceptor | ✅ | ⬜ pending |
|| 23-02-1b | 02 | 2 | ARCH-06 | T-23-02 | network_security_config 禁明文 | manual | 检查 AndroidManifest.xml usesCleartextTraffic=false | ✅ | ⬜ pending |
|| 23-02-1b | 02 | 2 | ARCH-08 | — | AuthRepository 复用 OkHttpClient | unit | 代码检查 AuthRepositoryImpl.kt 不含 Retrofit.Builder | ✅ | ⬜ pending |
|| 23-02-2 | 02 | 2 | ARCH-05, ARCH-10, ARCH-13, ARCH-15 | — | N/A | unit | `./gradlew :app:testDebugUnitTest` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/test/java/com/drama/app/` — 测试目录不存在，需创建
- [ ] `libs.versions.toml` — 需添加 junit 4.13.2, mockito-kotlin 5.4.0, kotlinx-coroutines-test 1.10.2, turbine 1.2.0 版本和库声明
- [ ] `build.gradle.kts` — 需添加 testImplementation 依赖
- [ ] `src/test/java/com/drama/app/ui/screens/dramadetail/orchestrator/BubbleMergerTest.kt` — BubbleMerger 去重/排序测试
- [ ] `src/test/java/com/drama/app/ui/screens/dramadetail/orchestrator/CommandRouterTest.kt` — CommandRouter 路由测试
- [ ] `src/test/java/com/drama/app/ui/screens/dramadetail/orchestrator/ConnectionOrchestratorTest.kt` — ConnectionOrchestrator 状态机测试
- [ ] `src/test/java/com/drama/app/MainDispatcherRule.kt` — 共享的协程测试 Rule

---

## Manual-Only Verifications

|| Behavior | Requirement | Why Manual | Test Instructions |
||----------|-------------|------------|-------------------|
|| R8 混淆 Release 构建 | ARCH-03 | 需要 Release 构建产物验证 | `./gradlew assembleRelease && unzip -l app/build/outputs/apk/release/*.apk \| grep com.drama` — 类名/方法名应不可读 |
|| network_security_config | ARCH-06 | 需要网络行为验证 | Release 构建连接局域网 IP 应拒绝明文 HTTP |
|| Release 构建零日志 | ARCH-11 | 需要构建变体验证 | 检查 NetworkModule.kt 中 HttpLoggingInterceptor 仅在 BuildConfig.DEBUG 时注入 |
|| VM 拆分行数 < 400 | ARCH-01 | 行数统计 | `wc -l DramaDetailViewModel.kt` 应 < 400 |
|| usesCleartextTraffic=false | ARCH-06 | Manifest 属性检查 | 检查 AndroidManifest.xml 中 usesCleartextTraffic="false" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
