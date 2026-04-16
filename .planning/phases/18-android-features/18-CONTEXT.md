# Phase 18: Android Features - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

在 Phase 17 交互基础上增强 Android 端体验：演员面板、戏剧状态概览、剧本导出、Typing 指示器增强、富文本渲染、WebSocket 自动重连。不新增核心业务功能（如语音输入、推送通知、离线模式），仅增强已有交互的视觉品质和网络韧性。

</domain>

<decisions>
## Implementation Decisions

### 演员面板 (APP-07)
- **D-01:** 主屏幕右侧 Drawer 入口 — 从右向左滑出，不遮挡场景内容，沉浸感好。TopAppBar 右侧加人物 Icon 触发
- **D-02:** 紧凑三行卡片 — 第一行：名字(titleMedium.bold) + 情绪 badge；第二行：身份(role)；第三行：A2A 状态圆点 + 端口号。点击卡片展开详情（性格/背景/记忆摘要）
- **D-03:** 后端新增 `GET /drama/cast/status` 端点 — 返回每个 actor 的 A2A 进程存活状态 `{actors: [{name, status: "running"|"stopped", port}]}`。Android 展示绿色(running)/红色(stopped)圆点
- **D-04:** 记忆摘要截取前 100 字 + "查看更多" — 默认折叠，点击展开完整 memory 文本。平衡信息量与空间

### 戏剧状态概览 (APP-08)
- **D-05:** TopAppBar 下拉展开卡片 — 点击 TopAppBar 区域展开 compact 信息卡片，再点收回。不占常驻空间，交互轻量
- **D-06:** 全面五指标 — 当前场景号 + 张力评分(LinearProgressIndicator) + 弧线进度 + 时间段描述 + 演员数。符合成功标准 APP-08 全部要求
- **D-07:** 扩展现有 `GET /drama/status` 响应 — 在 `DramaStatusResponse` 新增 `arc_progress: list[{name, progress: float}]`, `time_period: str` 字段。改动最小，复用已有端点

### Typing 指示器增强 (APP-10)
- **D-08:** 脉冲动画 + 上下文文案 — 根据 WS `typing.data.tool` 字段动态切换：`director_narrate`→"导演正在构思..."、`actor_speak`→"演员正在思考..."、`next_scene/write_scene`→"剧情推进中..."、其他→"处理中..."

### 富文本渲染 (APP-11)
- **D-09:** 角色名加粗 + 主题色 — 对白气泡上方角色名使用 `titleMedium.bold` + 基于角色名 hash 的专属颜色，与旁白形成强视觉区分
- **D-10:** 情绪标签小圆角 badge — 紧跟角色名后显示，如 "李明 😡愤怒"，badge 背景色半透明
- **D-11:** 首字母圆形头像基于角色名 hash 固定色 — 每个角色根据名字 `hashCode()` 生成固定颜色，多次出现颜色一致。圆形背景 + 白色首字母

### 剧本导出 (APP-09)
- **D-12:** 后端扩展 `POST /drama/export` 返回 Markdown 文本 — `ExportResponse` 新增 `content: str` 字段，Android 拿到文本后写入 `context.cacheDir` 临时文件 + `Intent.createChooser` 分享
- **D-13:** 导出入口 — 主屏幕 TopAppBar 溢出菜单"导出剧本"选项，点击后调用 export API → 写临时文件 → 弹出系统分享面板

### WebSocket 自动重连 (APP-15)
- **D-14:** 指数退避策略 — 1s → 2s → 4s → 8s → 16s → 30s 封顶。连接成功后重置退避计时器。最多连续重试无限次（30s 间隔可接受）
- **D-15:** ConnectivityManager 网络监听 — 注册 `NetworkCallback`，网络恢复时立即触发重连，不等待退避计时器到时
- **D-16:** 重连后自动请求 `GET /drama/status` 刷新 — 结合 WS replay buffer（Phase 14 已有 100-event 补发）补齐断线期间状态变化。不清空已有气泡，仅追加可能错过的增量

### Claude's Discretion
- 演员 Drawer 的具体 Compose 组件拆分（DrawerContent / ActorCard / ActorDetailSection）
- 状态概览下拉卡片的展开/收起动画参数
- 角色名 hash → 颜色的具体映射算法（HSL 色相分布）
- 情绪 badge 的圆角半径和内边距
- 导出临时文件命名和清理策略
- WS 重连在 ViewModel 中的协程管理（Job 取消/重启）
- ConnectivityManager 注册/注销的生命周期绑定
- 重连期间 UI 状态指示（TopAppBar 连接状态圆点）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目规划
- `.planning/ROADMAP.md` — Phase 18 定义、成功标准、依赖关系、APP-07~11/15 需求映射
- `.planning/REQUIREMENTS.md` — APP-07, APP-08, APP-09, APP-10, APP-11, APP-15 需求定义
- `.planning/STATE.md` — v2.0 已决定的架构选型和风险表
- `.planning/PROJECT.md` — 项目愿景、约束、"纯在线模式"定义

### Phase 16-17 上下文（直接前置）
- `.planning/phases/16-android-foundation/16-CONTEXT.md` — MVVM 架构、Hilt、MD3 主题、导航骨架、服务器连接
- `.planning/phases/17-android-interaction/17-CONTEXT.md` — 气泡渲染、命令输入栏、场景历史、WS 事件处理、Typing 基础版

### Phase 13-15 上下文（后端 API 契约）
- `.planning/phases/13-api-foundation/13-CONTEXT.md` — 14 个 REST 端点定义、Pydantic 模型、返回值格式
- `.planning/phases/14-websocket-layer/14-CONTEXT.md` — 18 种 WS 事件类型、replay buffer、心跳机制、EventBridge
- `.planning/phases/15-authentication/15-CONTEXT.md` — Token 认证、`/auth/verify` 端点、bypass 模式

### 核心源码 — 后端 API 契约
- `app/api/models.py` — **关键**：Pydantic 请求/响应模型，Phase 18 需扩展 `DramaStatusResponse`、`ExportResponse`、新增 `CastStatusResponse`
- `app/api/routers/commands.py` — 命令端点，export 端点需扩展返回 content
- `app/api/routers/queries.py` — 查询端点，`/drama/status` 需扩展字段，新增 `/drama/cast/status`
- `app/api/routers/websocket.py` — WS endpoint，重连机制需配合 replay buffer
- `app/api/event_mapper.py` — 18 种事件映射规则，Phase 18 需理解 typing 事件的 data.tool 字段

### 核心源码 — Android 现有组件
- `android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt` — **关键**：Retrofit 接口，Phase 18 需新增 cast/status + 扩展 DTO
- `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` — **关键**：WS 连接，Phase 18 需改写为支持自动重连
- `android/app/src/main/java/com/drama/app/data/remote/dto/WsEventDto.kt` — WS 事件 DTO
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` — **关键**：主屏幕 ViewModel，Phase 18 需扩展演员面板/状态概览/重连逻辑
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt` — **关键**：主屏幕 Composable，Phase 18 需添加 Drawer/概览卡片/富文本
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/DialogueBubble.kt` — 对白气泡，Phase 18 需增强为富文本
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/TypingIndicator.kt` — Typing 组件，Phase 18 需增强动态文案
- `android/app/src/main/java/com/drama/app/domain/model/SceneBubble.kt` — 场景气泡模型，Phase 18 可能需扩展情绪/颜色字段
- `android/app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt` — Repository，Phase 18 需新增 cast/status/export 调用
- `android/app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt` — Repository 接口

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DramaApiService.getCast()` — 已有 Retrofit 方法返回 `CastResponseDto`，Phase 18 直接使用 + 新增 `/cast/status`
- `DramaApiService.exportDrama()` — 已有导出 API，需扩展 DTO 加 content 字段
- `DramaApiService.getDramaStatus()` — 已有状态 API，需扩展 DTO 加 arc_progress/time_period
- `WebSocketManager.connect()` — OkHttp WS + `callbackFlow<WsEventDto>`，Phase 18 需包装重连逻辑
- `DramaDetailViewModel.handleWsEvent()` — WS 事件分发已完善，Phase 18 扩展 typing 处理 + 重连逻辑
- `DialogueBubble` — 已有对白气泡组件，Phase 18 在此基础上增强
- `TypingIndicator` — 已有基础版脉冲动画，Phase 18 增强动态文案
- `TensionIndicator` — 已有张力指示器组件
- `SceneHistorySheet` — 已有 BottomSheet 组件模式可参考
- MD3 主题 + 暗色模式 — 直接使用，新增组件遵循现有设计语言
- `AuthInterceptor` — OkHttp 拦截器自动注入 token

### Established Patterns
- MVVM 分层: Repository → ViewModel → Composable — Phase 18 沿用
- Hilt 依赖注入: `@Inject constructor` + `@Module` — 新增 Repository 方法/ViewModel 扩展同模式
- DTO → Domain Model 转换: Repository 层负责 — 新增 DTO 需新增 domain model
- Compose UI: `collectAsStateWithLifecycle()` + `StateFlow<UiState>` — 新屏幕/组件同模式
- WS 事件驱动 UI: `handleWsEvent()` 分发 — 扩展现有 when 分支
- OkHttp 拦截器: `AuthInterceptor` — 新 API 自动带认证
- Drawer/BottomSheet 交互: MD3 标准组件 — 演员 Drawer 参考现有模式

### Integration Points
- `GET /drama/cast` — 演员面板读取角色列表
- `GET /drama/cast/status` (新增) — 演员面板读取 A2A 进程状态
- `GET /drama/status` (扩展) — 状态概览读取弧线/时间段
- `POST /drama/export` (扩展) — 剧本导出获取 Markdown 文本
- `WebSocketManager` 重连 — 与 `DramaDetailViewModel` 生命周期绑定
- `ConnectivityManager` — 网络恢复监听，触发 WS 重连
- WS `typing` 事件 `data.tool` 字段 — 动态切换 Typing 文案
- WS `tension_update` 事件 — 状态概览卡片实时更新张力
- Android Share Intent — 导出文件分享

</code_context>

<specifics>
## Specific Ideas

- 演员 Drawer 从右侧滑出 — 戏剧感交互，像翻开角色档案
- 基于角色名 hash 的固定头像色 — 视觉一致性，不用维护颜色映射表
- TopAppBar 下拉展开状态概览 — 轻量不遮挡，点开即看
- 导出 + 系统分享面板 — 一键分享到微信/邮件/笔记，原生体验
- WS 重连 + 网络监听双重保障 — 断线无感知恢复，用户体验连续

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-android-features*
*Context gathered: 2026-04-16*
