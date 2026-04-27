# Milestones — Director-Actor-Drama

## v2.5 技术债务治理 — COMPLETE

**Phases:** 1 (Phase 23) | **Plans:** 3/3 done

### Key Accomplishments

1. DramaDetailViewModel 拆分 — 1665行 God Object → 协调者 + 5 子组件 (ConnectionOrchestrator/BubbleMerger/CommandRouter/SaveLoadManager/ExportManager)
2. WS 生命周期统一 — @ActivityScoped + acquire/release 引用计数，无 VM 间泄露
3. R8 混淆启用 — isMinifyEnabled=true + ProGuard 保守 keep
4. UiState 子状态拆分 — Connection/Interaction/SaveLoad/ActorPanel 独立重组
5. ARCH-10 数据源策略 — WS 优先/REST 降级 (addFromRest)，消除 UI 闪烁
6. BaseUrlInterceptor + ServerPreferences 内存缓存 — 运行时切换服务器，零阻塞
7. network_security_config Debug/Release 分离 — Release 禁明文，Debug 允许 LAN
8. HttpLoggingInterceptor 仅 DEBUG 注入 — Release 零日志泄露
9. 57+ 单元测试 — BubbleMerger/CommandRouter/ConnectionOrchestrator/BaseUrlInterceptor
10. ConnectionOrchestrator isWsConnected 修复 — 独立 MutableStateFlow 替代每次创建

### All 17 ARCH Requirements Resolved

ARCH-01~ARCH-17 全部有对应测试或验证覆盖。

### Deferred to v3.0

- P2: RetryPolicy 可配置重试、Room 离线缓存
- P3: 图标库按需引入、CI/CD GitHub Actions

## v2.0 Android 移动端 — COMPLETE (incl. Gap Closure)

**Phases:** 6 (shipped) + 3 (gap closure) | **Plans:** 18 + 3 = 21 done

### Key Accomplishments

1. FastAPI REST API Server — 14 个 REST 端点 + WebSocket 实时推送 + 简单 Token 认证
2. Android App (Kotlin + Jetpack Compose) — Material Design 3 风格，MVVM + Hilt 架构
3. 戏剧交互主界面 — 创建/列表/详情/命令输入栏/场景历史/保存加载
4. 演员面板 + 状态概览 — 演员卡片/张力/弧线/时间线
5. 富文本渲染 + 剧本导出 — 角色名高亮/情绪标签/头像/Share Intent
6. WebSocket 自动重连 — 指数退避 + ConnectivityManager + 网络弹性
7. WS 心跳修复 — JSON 解析 + 服务端 heartbeat 兼容 + 8 个新测试
8. 命令接线补全 — STEER/AUTO/STORM 端点 + isProcessing 四路径重置 + 60s safety timeout
9. 事件与导出补全 — 3 缺失事件处理 + Export 端到端
10. 群聊模式 — ChatInputBar 清理 + sender_name + 删除旧组件

### Stats

- **Timeline:** 2 days (2026-04-15 → 2026-04-16) + gap closure (2026-04-25 → 2026-04-26)
- **LOC:** ~3,200 Python (api/) + ~5,500 Kotlin (android/)
- **Feat commits:** 18 + 5 (gap closure)

### Archives

- `.planning/milestones/v2.0-ROADMAP.md` (pending)

## v3.0 群聊模式 — COMPLETE

**Phases:** 1 (Phase 22) | **Plans:** 1/1 done

### Key Accomplishments

1. ChatInputBar 斜杠命令清理 — 从 12 个命令精简到 6 个功能性命令
2. 快捷芯片 — 下一场/落幕按钮，与 MentionChip 同级
3. 后端 sender_name 注入 — ChatRequest 接收发送者名称，非"导演"时注入 [名称] 前缀
4. 删除 CommandInputBar.kt 死代码

## v1.0 无限畅写版 — SHIPPED 2026-04-14

**Phases:** 12 | **Plans:** 29 | **Tests:** 517 passed

### Key Accomplishments

1. 3 层记忆架构 + 异步压缩 — 支撑 50+ 场戏不溢出上下文
2. 无限叙事循环 + 混合推进模式 — AI 自主推进 + 用户随时干预无缝切换
3. 张力评分 + 冲突引擎 + Dynamic STORM — 自动检测平淡并注入转折
4. 一致性检查 + 矛盾修复 + 时间线追踪 — 保障"逻辑不断"核心承诺
5. 端到端集成 + 517 测试通过 — 全流程验证可交付

### Stats

- **Timeline:** 3 days (2026-04-11 → 2026-04-14)
- **LOC:** ~9,560 Python
- **Feat commits:** 30
- **Files modified:** 217

### Archives

- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`
