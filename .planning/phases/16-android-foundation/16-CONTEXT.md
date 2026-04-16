# Phase 16: Android Foundation - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Android 项目搭建，MVVM + Hilt + Material Design 3 主题，服务器连接配置，导航骨架。不实现业务交互（戏剧 CRUD、命令输入等属于 Phase 17），仅搭建骨架让 Phase 17-18 有地可建。

</domain>

<decisions>
## Implementation Decisions

### 服务器连接体验
- **D-01:** 手动输入 IP:port + 历史记录下拉 — 无需后端改动，开发者/极客友好，历史记录降低重复输入成本
- **D-02:** 连接后自动检测 Token — 先连 IP:port 调 `GET /api/v1/auth/verify`，若返回 `mode: "bypass"` 则跳过 token 输入，若需 token 则弹出输入对话框。后端 `/auth/verify` 已就绪（Phase 15 D-08）
- **D-03:** 连接失败反馈 — Snackbar 提示 + 重试按钮，区分错误类型：网络不可达 / 401 认证失败 / 连接超时
- **D-04:** DataStore Preferences 持久化服务器配置 — 存储 IP、port、token（加密存储）、最后连接时间。下次启动自动尝试上次连接

### 项目架构与依赖
- **D-05:** Kotlin 2.0.x + Compose BOM 2024.12 — 最新稳定组合，Composable 生命周期与 Kotlin 2.0 协程优化
- **D-06:** Retrofit + OkHttp + kotlinx.serialization — 业界标准 REST 客户端，OkHttp 拦截器统一注入 Authorization header，kotlinx.serialization 性能优于 Gson
- **D-07:** 无 Room 数据库 — 纯在线模式，DataStore 仅存偏好/服务器配置。APP-01 定义 App 为纯 UI 客户端，无本地数据缓存需求
- **D-08:** Navigation Compose — 官方推荐导航方案，与 Compose 深度集成，type-safe 路由
- **D-09:** Hilt 依赖注入 — APP-14 已定。管理 Retrofit 实例、Repository、ViewModel、DataStore
- **D-10:** minSdk 26 (Android 8.0), targetSdk 35 — 覆盖 95%+ 设备，Dynamic Color 需 API 31 但有 fallback

### 导航与屏幕结构
- **D-11:** 底部导航栏 3 tab — 戏剧列表 (drama-list) / 创建 (drama-create) / 设置 (settings)。Material Design 3 NavigationBar 组件
- **D-12:** drama-detail 从列表项点击进入 — 非 tab 项，作为独立路由 `drama/{dramaId}`，带返回箭头
- **D-13:** 服务器连接配置在设置页面 — 不做独立连接屏幕，设置页顶部放置"服务器连接"section。APP-01 连接配置与 APP-16 设置归一
- **D-14:** 首次启动引导 — DataStore 无服务器历史时，自动弹出连接对话框（全屏 Dialog），连接成功后进入主界面。后续启动直接进入上次连接
- **D-15:** 导航图：`connection-guide (条件)` → `main (drama-list / create / settings)` → `drama-detail`

### 主题与视觉风格
- **D-16:** MD3 Dynamic Color 启用 (Android 12+, API 31+) — `dynamicColor = true`，API < 31 fallback 到自定义品牌色
- **D-17:** 暗色模式默认 — 戏剧 App 暗色更沉浸，`isSystemInDarkTheme()` 跟随系统，但首次启动默认暗色
- **D-18:** 品牌色深靛蓝 — `primary = Color(0xFF1A237E)` 系列（Material Blue 900），戏剧感、庄重感，暗色模式下自动调亮
- **D-19:** Typography 微调 — MD3 默认 + `titleLarge` 加粗 (`FontWeight.Bold`)，增强戏剧标题气势。其余沿用 MD3 默认
- **D-20:** 形状沿用 MD3 默认 rounded — 不做额外定制，保持一致性

### Claude's Discretion
- Gradle 模块结构（单模块 vs 多模块）— 单模块足够，项目体量小
- 具体包结构（data/domain/ui 层组织）
- Retrofit API interface 的具体方法签名
- DataStore 存储键名和加密策略
- 连接引导 Dialog 的动画和布局细节
- 首次启动检测逻辑的具体实现
- Compose preview 的组织方式

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目规划
- `.planning/ROADMAP.md` — Phase 16 定义、成功标准、依赖关系
- `.planning/REQUIREMENTS.md` — APP-01, APP-13, APP-14, APP-16 需求定义
- `.planning/STATE.md` — v2.0 已决定的架构选型和风险表
- `.planning/PROJECT.md` — 项目愿景、约束、"纯在线模式"定义

### Phase 13-15 上下文（后端 API 参考）
- `.planning/phases/13-api-foundation/13-CONTEXT.md` — 14 个 REST 端点定义、Pydantic 模型、返回值格式
- `.planning/phases/14-websocket-layer/14-CONTEXT.md` — WS 事件类型、replay buffer、心跳机制
- `.planning/phases/15-authentication/15-CONTEXT.md` — Token 认证、`/auth/verify` 端点、bypass 模式

### 核心源码（后端 API 契约）
- `app/api/models.py` — **关键**：Pydantic 请求/响应模型，Android Retrofit 接口必须对齐此文件
- `app/api/routers/commands.py` — 8 个命令端点的路径、请求体、响应格式
- `app/api/routers/queries.py` — 6 个查询端点的路径、请求体、响应格式
- `app/api/routers/auth.py` — `/auth/verify` 端点定义
- `app/api/routers/websocket.py` — WS endpoint 路径和握手参数

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- 后端 API 契约完整：14 个 REST 端点 + 1 个 WS 端点 + 1 个 auth 验证端点 — Android Retrofit interface 可直接映射
- Pydantic 模型 (`app/api/models.py`)：`CommandResponse`, `DramaStatusResponse`, `DramaListResponse`, `AuthVerifyResponse` 等 — Android data class 镜像此结构
- WS 事件模型 (`WsEvent`, `ReplayMessage`, `HeartbeatMessage`) — Android sealed class 映射
- `/auth/verify` 返回 `{"valid": bool, "mode": "token"|"bypass"}` — 连接检测逻辑的直接依据

### Established Patterns
- REST 返回值格式：`{"status": "success"|"error", "message": "...", ...领域字段}` — Android Response 统一处理
- Token 认证：`Authorization: Bearer <token>` (REST) + `?token=xxx` (WS) — OkHttp interceptor + WS URL 构造
- API 版本前缀：`/api/v1/` — Retrofit baseUrl 须包含
- CORS `allow_origins=["*"]` dev 模式 — Android 无跨域问题

### Integration Points
- `POST /api/v1/drama/start` — 创建戏剧（Phase 17 使用，Phase 16 仅搭建骨架）
- `GET /api/v1/drama/list` — 戏剧列表（Phase 17 使用）
- `GET /api/v1/drama/status` — 戏剧状态（Phase 17 使用）
- `GET /api/v1/auth/verify` — Phase 16 连接检测
- `ws://host:port/api/v1/ws?token=xxx` — Phase 16 搭建 WS 基础，Phase 17 使用

</code_context>

<specifics>
## Specific Ideas

- 暗色模式默认 — 戏剧 App 夜间使用居多，暗色沉浸感强
- 深靛蓝品牌色 — 庄重、神秘、戏剧感，区别于常见的蓝紫色 App
- 连接后自动检测 token — 零配置 dev 模式体验：无 token 时 App 直接进入，有 token 时才弹输入
- DataStore 存服务器配置 — 轻量偏好存储，无需数据库
- 首次启动全屏引导 — 降低首次使用门槛

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-android-foundation*
*Context gathered: 2026-04-16*
