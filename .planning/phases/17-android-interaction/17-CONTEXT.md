# Phase 17: Android Interaction - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

戏剧 CRUD 交互主界面，命令输入栏，场景历史浏览，保存/加载确认。在 Phase 16 骨架基础上填充业务逻辑：创建戏剧 → 列表管理 → 主屏幕实时渲染 → 历史导航。不实现演员面板、富文本增强、WS 自动重连（Phase 18 范畴）。

</domain>

<decisions>
## Implementation Decisions

### 戏剧创建流程
- **D-01:** 全屏创建表单 — 主题输入框占屏幕中央，大字体 placeholder "输入你的戏剧主题..."，沉浸式创作体验
- **D-02:** 点击创建后调用 `POST /drama/start`，进入加载态 — LinearProgressIndicator + "导演正在构思世界观..."
- **D-03:** STORM 进度通过 WS 事件实时展示 — 收到 `storm_discover`/`storm_research`/`storm_outline` 事件时更新进度文案（如"发现新视角..."、"深入研究..."、"综合构思大纲..."）
- **D-04:** 创建完成自动跳转 — 收到 `scene_start` 事件后导航到 `DramaDetail(dramaId)`，无需独立 STORM 结果页面
- **D-05:** 若当前已有活跃 drama，`/start` 先自动保存旧 drama（后端 D-06 已实现），前端无需额外处理

### 戏剧列表与卡片
- **D-06:** 紧凑卡片布局两行信息 — 第一行：主题（titleLarge 加粗）+ 状态 badge（Active/Saved）；第二行：场数 + 更新时间
- **D-07:** 三点菜单操作 — `IconButton` + `DropdownMenu` 包含：加载、恢复、删除。不占卡片空间，符合 MD3 规范
- **D-08:** 删除操作 AlertDialog 确认 — 防误删，标题"删除戏剧？"，内容"此操作不可恢复"，确认/取消按钮
- **D-09:** 空列表状态 — 居中插画 + "还没有戏剧，点击下方创建按钮开始创作" + FAB 跳转创建 tab
- **D-10:** `DramaListResponseDto` 细化为 typed data class — 当前 `List<Map<String, JsonElement>>` 不可用，需新增 `DramaItemDto(theme, status, numScenes, updatedAt, dramaFolder)` 映射后端 `dramas` 数组项

### 主戏剧屏幕与实时场景
- **D-11:** 角色分段气泡渲染 — 旁白用半透明灰色气泡左对齐，对白用角色色气泡右对齐。气泡上方显示角色名 + 小圆形首字母头像。比纯文本更沉浸，比卡片时间线更紧凑
- **D-12:** 底部固定命令输入栏 — `BottomAppBar` 包含文本输入框 + 发送按钮。输入框上方一排快捷芯片（Chip）：`/next` `/action` `/speak` `/end`，点击自动填入命令前缀
- **D-13:** 快捷芯片交互 — `/next` 和 `/end` 直接发送命令（无需输入参数）；`/action` 和 `/speak` 点击后填入命令前缀 + 空格，光标聚焦输入框等待用户补充
- **D-14:** Typing 指示器基础版 — 收到 WS `typing` 事件时，场景内容底部显示脉冲动画 + "导演正在构思..."。Phase 18 会增强
- **D-15:** WS 事件驱动 UI 更新 — `narration` 追加旁白气泡，`dialogue` 追加对白气泡，`scene_end` 显示分割线 + 场景号，`tension_update` 更新顶部张力指示，`typing` 显示/隐藏指示器，`error` 显示错误 Snackbar
- **D-16:** 顶部 TopAppBar — 戏剧主题 + 当前场景号 + 张力评分（小型 LinearProgressIndicator 或数值标签）
- **D-17:** 进入 DramaDetail 时自动连接 WS + 订阅事件流 — 利用 Phase 16 的 `WebSocketManager.connect()` 返回 Flow，ViewModel 收集并更新 UI state

### 场景历史与导航
- **D-18:** 底部半屏 BottomSheet 展示历史 — 主屏幕右上角历史按钮（clock IconButton），点击弹出 BottomSheet
- **D-19:** BottomSheet 内容为场景摘要列表 — 每项显示场景号 + 前几行文字摘要，可滚动浏览
- **D-20:** 点击历史场景跳转完整内容 — 替换主屏幕内容显示该场景，TopAppBar 出现返回按钮回到当前场景
- **D-21:** 场景数据获取 — 通过 `GET /drama/status` 获取 `num_scenes`，然后从 state 中的 `scenes` 列表读取。后端若无单场景查询 API，需新增或从现有 `/status` 扩展返回 scenes 摘要列表

### 保存/加载确认
- **D-22:** 保存/加载操作 Snackbar 确认 — 成功提示"已保存：{save_name}" / "已加载：{save_name}"，失败提示错误信息
- **D-23:** 保存操作入口 — 主屏幕 TopAppBar 溢出菜单中的"保存"选项，点击弹出简单 Dialog 输入保存名（可选，默认用主题名）
- **D-24:** 加载操作入口 — 戏剧列表卡片的三点菜单"加载"项

### Claude's Discretion
- `DramaItemDto` 的具体字段设计和序列化策略
- 聊天气泡的 Compose 组件拆分方式（Bubble Composable）
- 命令输入文本解析逻辑（区分 `/` 命令 vs 自由文本 → `/action` 前缀）
- WS 事件到 UI 状态的 Flow 转换架构（StateFlow vs SharedFlow）
- BottomSheet 的 peekHeight 和展开行为
- 场景历史数据获取方案细节（API 扩展 vs 从现有 state 读取）
- 输入栏软键盘交互（imePadding、焦点管理）
- LazyColumn 自动滚动到底部策略

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目规划
- `.planning/ROADMAP.md` — Phase 17 定义、成功标准、依赖关系、APP-02~06/12 需求映射
- `.planning/REQUIREMENTS.md` — APP-02, APP-03, APP-04, APP-05, APP-06, APP-12 需求定义
- `.planning/STATE.md` — v2.0 已决定的架构选型和风险表
- `.planning/PROJECT.md` — 项目愿景、约束、"纯在线模式"定义

### Phase 16 上下文（直接前置 — Android 骨架）
- `.planning/phases/16-android-foundation/16-CONTEXT.md` — MVVM 架构、Hilt、MD3 主题、导航骨架、服务器连接

### Phase 13-15 上下文（后端 API 契约）
- `.planning/phases/13-api-foundation/13-CONTEXT.md` — 14 个 REST 端点定义、Pydantic 模型、返回值格式
- `.planning/phases/14-websocket-layer/14-CONTEXT.md` — 18 种 WS 事件类型、replay buffer、心跳机制、EventBridge
- `.planning/phases/15-authentication/15-CONTEXT.md` — Token 认证、`/auth/verify` 端点、bypass 模式

### 核心源码 — 后端 API 契约
- `app/api/models.py` — **关键**：Pydantic 请求/响应模型，Android DTO 必须对齐此文件
- `app/api/routers/commands.py` — 8 个命令端点的路径、请求体、响应格式
- `app/api/routers/queries.py` — 6 个查询端点的路径、请求体、响应格式
- `app/api/routers/websocket.py` — WS endpoint 路径和握手参数
- `app/api/event_mapper.py` — 18 种事件映射规则，Android 端需理解事件结构

### 核心源码 — Android 骨架
- `android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt` — **关键**：Retrofit 接口，Phase 17 直接调用
- `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` — **关键**：WS 连接 + Flow 事件流，Phase 17 消费事件
- `android/app/src/main/java/com/drama/app/data/remote/dto/WsEventDto.kt` — WS 事件 DTO，需理解 type 字段分发
- `android/app/src/main/java/com/drama/app/data/remote/dto/CommandResponseDto.kt` — 命令响应 DTO
- `android/app/src/main/java/com/drama/app/data/remote/dto/DramaStatusResponseDto.kt` — 状态响应 DTO
- `android/app/src/main/java/com/drama/app/data/remote/dto/DramaListResponseDto.kt` — 列表响应 DTO（需细化）
- `android/app/src/main/java/com/drama/app/ui/navigation/Route.kt` — 导航路由定义
- `android/app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt` — 导航图

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DramaApiService` — Retrofit 接口已映射全部 14 个端点（start/next/action/speak/steer/auto/storm/end/status/cast/list/save/load/export），Phase 17 Repository 直接调用
- `WebSocketManager` — OkHttp WS 连接 + `callbackFlow<WsEventDto>`，Phase 17 ViewModel 订阅此 Flow 驱动 UI
- `WsEventDto(type, timestamp, data)` — 通用事件模型，`data` 字段包含事件负载（角色名、对白内容等）
- `ReplayMessageDto` — 重连时 replay buffer 消息，连接后首条消息
- `AuthInterceptor` — OkHttp 拦截器自动注入 Bearer token，REST 调用无需手动处理认证
- `ServerPreferences` — DataStore 存储服务器配置，WS URL 构造直接读取
- 导航骨架 — `DramaList`/`DramaCreate`/`DramaDetail`/`Settings` 路由已定义，`DramaNavHost` 已配置
- MVVM 架构 — 所有 ViewModel 已创建（占位），`hiltViewModel()` 注入已就绪
- MD3 主题 — 暗色模式 + 深靛蓝品牌色 + Dynamic Color，Phase 17 直接使用

### Established Patterns
- MVVM 分层: Repository → ViewModel → Composable — Phase 17 沿用
- Hilt 依赖注入: `@Inject constructor` + `@Module` — 新 Repository/ViewModel 同模式
- DTO → Domain Model 转换: Repository 层负责，ViewModel 只暴露 domain model — Phase 17 新增 domain model
- Compose UI: `collectAsStateWithLifecycle()` + `StateFlow<UiState>` — 所有屏幕同模式
- 导航: `navController.navigate(Route)` — 跳转到 DramaDetail
- OkHttp 拦截器: `AuthInterceptor` 统一注入 token — REST 无需手动处理
- WS URL 构造: `ws://$host:$port/api/v1/ws?token=$token` — Phase 16 已实现

### Integration Points
- `DramaApiService.startDrama()` — 创建戏剧（创建屏幕调用）
- `DramaApiService.listDramas()` — 戏剧列表（列表屏幕调用）
- `DramaApiService.getDramaStatus()` — 戏剧状态（主屏幕 + 历史导航调用）
- `DramaApiService.saveDrama()` / `loadDrama()` — 保存/加载操作
- `DramaApiService.nextScene()` / `userAction()` / `actorSpeak()` / `endDrama()` — 命令输入栏调用
- `WebSocketManager.connect()` — 进入主屏幕时连接 WS
- `WebSocketManager.disconnect()` — 离开主屏幕时断开 WS
- `WsEventDto.type` 事件分发 — "narration"/"dialogue"/"scene_end"/"typing"/"tension_update"/"error" 等

</code_context>

<specifics>
## Specific Ideas

- 聊天气泡渲染场景 — 旁白灰色左对齐，对白角色色右对齐，沉浸式戏剧体验
- 快捷芯片命令栏 — `/next` `/action` `/speak` `/end` 一键操作，降低输入门槛
- STORM 进度实时展示 — "发现新视角..."→"深入研究..."→"综合构思大纲..."，让用户感知 AI 思考过程
- 三点菜单操作卡片 — 紧凑不占空间，MD3 规范交互
- BottomSheet 场景历史 — 轻量即开即用，不增加导航复杂度

</specifics>

<deferred>
## Deferred Ideas

- 演员面板（角色列表 + A2A 状态 + 记忆摘要）— Phase 18 APP-07
- 富文本渲染增强（情绪标签 + 头像圆形标识）— Phase 18 APP-11
- WS 自动重连 + 指数退避 — Phase 18 APP-15
- 剧本导出为 Markdown + Share Intent — Phase 18 APP-09
- 戏剧状态概览（张力/弧线/时间段）— Phase 18 APP-08
- 更丰富的 Typing 指示器（脉冲动画增强）— Phase 18 APP-10

</deferred>

---

*Phase: 17-android-interaction*
*Context gathered: 2026-04-16*
