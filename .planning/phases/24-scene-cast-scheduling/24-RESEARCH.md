# Phase 24: 场景级演员调度 — Research

**Researched:** 2026-04-29
**Domain:** Backend state/tool patterns + Android actor panel + WS event system
**Confidence:** HIGH

## Summary

Phase 24 引入 `scene_cast` 机制，让每场戏拥有独立的"上场演员"列表。后端需要新增 state 字段、改造 `next_scene()`/`actor_speak_batch()`、新增 `set_scene_cast` 工具和 `cast_change` WS 事件。Android 端需要扩展 `ActorInfo`、改造演员面板 UI、新增导演选角交互。

代码库审计确认了关键模式：(1) 工具模式为"轻量 wrapper + 委托 state_manager"，参考 `update_emotion`/`steer_drama`；(2) 状态迁移使用 `state.setdefault()` 惯例，在 `load_progress()` 中集中处理，已有 12+ 个迁移先例；(3) WS 事件通过 `TOOL_EVENT_MAP` + `_extract_call_data`/`_extract_response_data` 双阶段映射，新增事件类型只需扩展映射表；(4) Phase 23 已将 VM 拆为 5 个子组件（`@Inject constructor`），演员面板状态仍在主 `DramaDetailUiState` 中；(5) `ChatInputBar` 的 `MentionChip` 可复用于选角 UI。

**Primary recommendation:** 严格遵循现有模式：`set_scene_cast` 工具委托 `state_manager` 逻辑，`load_progress()` 添加 `scene_cast` 迁移，`TOOL_EVENT_MAP` 增加 `cast_change` 映射，Android `ActorInfo` 扩展 `onStage` 字段并在 `mergeCastWithStatus` 中填充。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- State 新增字段: `state["scene_cast"]` = List[str] — 当前场景上场演员名
- next_scene() 改造: 接受可选的 `cast` 参数，默认 = 所有 AI 演员
- actor_speak_batch() 改造: 只调用 `scene_cast` 中的演员
- 新增 set_scene_cast() 工具: 导演手动调整上场演员
- 新增 cast_change WS 事件: 上下场变更推送
- ActorInfo 扩展: 新增 `onStage: Boolean` 字段
- 演员面板改造: 在场演员高亮，待机演员灰显
- 导演选角交互: 支持手动切换演员上下场
- cast_change 事件处理: 实时更新演员状态
- 默认值 = 所有 AI 演员，set_scene_cast 校验非空
- 向后兼容：缺失时默认 = 所有 AI 演员名

### Claude's Discretion
- 演员面板 UI 具体实现方式（分组/标签/灰显程度）
- 导演选角交互的交互模式（底部 Sheet / 对话框 / 拖拽）
- cast_change 事件数据格式的具体字段

### Deferred Ideas (OUT OF SCOPE)
- 待机演员 A2A 服务暂停/恢复（待机演员 A2A 保持运行，仅不参与本场景对话）
- 演员调度历史记录
- 自动智能选角（基于场景内容自动推荐上场演员）
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAST-01 | 后端 scene_cast state 字段与迁移 | §State Management Patterns — state.setdefault() 惯例，12+ 迁移先例 |
| CAST-02 | set_scene_cast 导演工具 | §Tool Structure Patterns — update_emotion/steer_drama 范式 |
| CAST-03 | next_scene + actor_speak_batch 调度改造 | §next_scene/actor_speak_batch 现有逻辑分析 |
| CAST-04 | cast_change WS 事件 | §WS Event Patterns — TOOL_EVENT_MAP + 双阶段映射 |
| CAST-05 | Android ActorInfo.onStage + 演员面板 UI | §Android Patterns — ActorInfo/ActorDrawerContent/mergeCastWithStatus |
| CAST-06 | Android 导演手动选角交互 | §MentionChip 复用分析 + §选角 UI 建议 |
</phase_requirements>

## Standard Stack

### Core (Backend — 已锁定)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-adk | >=1.15.0,<2.0.0 | Agent framework + ToolContext | 项目核心 [VERIFIED: pyproject.toml] |
| FastAPI | (via adk) | REST API + WebSocket | 项目已使用 [VERIFIED: app/api/] |
| Pydantic v2 | (via fastapi) | Request/response models | 项目已使用 [VERIFIED: app/api/models.py] |
| pytest | >=8.3.4 | 后端测试 | 项目已锁定 [VERIFIED: pyproject.toml] |

### Core (Android — 已锁定)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Kotlin | 2.1.0 | 主语言 | [VERIFIED: gradle/libs.versions.toml] |
| Compose | BOM 2024.12.01 | UI 框架 | [VERIFIED: gradle/libs.versions.toml] |
| Hilt | 2.54 | 依赖注入 | [VERIFIED: gradle/libs.versions.toml] |
| kotlinx.serialization | 1.7.3 | JSON 解析 | [VERIFIED: WsEventDto.kt] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mockito-kotlin | (test) | Android 单元测试 mock | 测试 ViewModel/子组件 |
| turbine | (test) | Flow 测试 | 测试 SharedFlow 事件 |
| coroutines-test | (test) | 协程测试 | 测试 suspend 函数 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| state["scene_cast"] as List[str] | state["scene_cast"] as Dict[str,bool] | Dict 可 O(1) 查找但 List 更直观、与 actors_available 一致 |
| 独立 SceneCastViewModel | 扩展现有 VM | 子组件模式更符合 Phase 23 架构，但独立 VM 更隔离 |

**Installation:** 无新依赖 — 全部使用项目现有库。

## Architecture Patterns

### Recommended Project Structure (新增文件)
```
app/
├── tools.py                    # 新增 set_scene_cast() 工具函数
├── state_manager.py            # 新增 scene_cast 迁移 + 辅助函数
├── agent.py                    # tools 列表添加 set_scene_cast
├── api/
│   ├── event_mapper.py         # TOOL_EVENT_MAP 添加 set_scene_cast 映射
│   ├── models.py               # (可选) SetSceneCastRequest
│   └── routers/
│       └── commands.py          # (可选) POST /drama/cast/scene 接口

android/app/src/main/java/com/drama/app/
├── domain/model/ActorInfo.kt   # 新增 onStage 字段
├── data/repository/DramaRepositoryImpl.kt  # mergeCastWithStatus 填充 onStage
├── ui/screens/dramadetail/
│   ├── DramaDetailViewModel.kt # 处理 cast_change 事件
│   └── components/
│       ├── ActorDrawerContent.kt  # 在场/待机分组显示
│       └── ActorCard.kt           # onStage 视觉区分
```

### Pattern 1: Tool 结构 — "轻量 wrapper + 委托"
**What:** 所有工具函数遵循"参数校验 + 委托 state_manager + 返回 dict"三段式
**When to use:** 新增任何 ADK 工具
**Example:**
```python
# Source: app/tools.py:2403-2413 (update_emotion)
def update_emotion(actor_name: str, emotion: str, tool_context: ToolContext) -> dict:
    """Update an actor's emotional state after a scene event.

    Args:
        actor_name: The name of the actor.
        emotion: The new emotional state (e.g., "愤怒", "悲伤", "喜悦", "恐惧").

    Returns:
        dict with status.
    """
    return update_actor_emotion(actor_name, emotion, tool_context)
```

更完整的工具模式参考 `steer_drama` (tools.py:1574-1606):
```python
# Source: app/tools.py:1574-1606
def steer_drama(direction: str, tool_context: ToolContext) -> dict:
    """Set a directional guidance for the next scene."""
    state = _get_state(tool_context)
    # 1. 参数校验
    if not direction or not direction.strip():
        return {"status": "error", "message": "❌ 方向不能为空。"}
    # 2. 修改 state
    state["steer_direction"] = direction
    _set_state(state, tool_context)
    # 3. 返回确认
    return {"status": "success", "message": f"🧭 方向已设置：{direction}", "steer_direction": direction}
```

### Pattern 2: State 迁移 — `state.setdefault()` 惯例
**What:** 所有新 state 字段在 `load_progress()` 中使用 `setdefault()` 迁移
**When to use:** 添加任何新 state 字段
**Example:**
```python
# Source: app/state_manager.py:934-1001
# Phase 5: Ensure new fields exist for backward compatibility (D-28)
state.setdefault("remaining_auto_scenes", 0)
state.setdefault("steer_direction", None)
state.setdefault("storm", {"last_review": {}})
# Phase 6: Ensure conflict_engine exists for backward compatibility (D-18)
state.setdefault("conflict_engine", {...})
# Phase 7: Arc Tracking backward compatibility
state.setdefault("plot_threads", [])
# Phase 10: Coherence System backward compatibility
state.setdefault("established_facts", [])
state.setdefault("coherence_checks", {...})
# Phase 11: Timeline Tracking backward compatibility
state.setdefault("timeline", {...})
# SceneContext backward compatibility
state.setdefault("scene_context", {})
```

### Pattern 3: WS 事件映射 — TOOL_EVENT_MAP 双阶段
**What:** 新事件类型通过扩展 `TOOL_EVENT_MAP` + `_extract_call_data`/`_extract_response_data` 实现
**When to use:** 新增任何 WS 推送事件
**Example:**
```python
# Source: app/api/event_mapper.py:21-44
TOOL_EVENT_MAP: dict[str, list[str]] = {
    "start_drama": ["scene_start", "status", "command_echo"],
    "next_scene": ["scene_start", "command_echo"],
    "update_emotion": ["actor_status"],
    "create_actor": ["actor_created", "cast_update"],
    "steer_drama": ["command_echo"],
    # ...
}

# Response 阶段映射
TOOL_EVENT_MAP_RESPONSE: dict[str, list[str]] = {
    "director_narrate": ["narration"],
    "actor_speak": ["dialogue"],
    "actor_speak_batch": ["dialogue"],
    "end_drama": ["end_narration"],
}
```

### Pattern 4: Android 子组件 — `@Inject constructor` + SharedFlow 事件
**What:** Phase 23 确立的子组件组合模式
**When to use:** 新增任何 VM 职责
**Example:**
```kotlin
// Source: orchestrator/ConnectionOrchestrator.kt:28-49
class ConnectionOrchestrator @Inject constructor(
    private val webSocketManager: WebSocketManager,
    private val serverPreferences: ServerPreferences,
) {
    sealed class ConnectionEvent {
        data class Connected(val dramaId: String) : ConnectionEvent()
        data class EventReceived(val event: WsEventDto) : ConnectionEvent()
        // ...
    }
    private val _events = MutableSharedFlow<ConnectionEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<ConnectionEvent> = _events
}
```

### Pattern 5: Android Actor 数据流 — REST 合并
**What:** `getMergedCast()` 调用 `/drama/cast` + `/drama/cast/status` 两端点合并
**When to use:** 修改演员数据模型
**Example:**
```kotlin
// Source: DramaRepositoryImpl.kt:154-168, 358-396
override suspend fun getMergedCast(): Result<List<ActorInfo>> = runCatching {
    val cast = dramaApiService.getCast()
    val status = dramaApiService.getCastStatus()
    mergeCastWithStatus(cast, status)
}

private fun mergeCastWithStatus(
    cast: CastResponseDto,
    status: CastStatusResponseDto,
): List<ActorInfo> {
    val statusMap = status.actors
    for ((name, actorElement) in cast.actors) {
        val actorObj = (actorElement as? JsonObject)?.jsonObject ?: continue
        // ... 解析字段
        mergedActors.add(ActorInfo(
            name = name,
            role = role,
            // ...
            isA2ARunning = isRunning,
            a2aPort = port,
            thinkingProgress = thinkingSteps,
        ))
    }
}
```

### Anti-Patterns to Avoid
- **在 tool 函数中直接操作 state 字典而不通过 `_get_state`/`_set_state`**: 所有状态修改必须通过 state_manager 的辅助函数，确保磁盘持久化和防抖
- **在 `actor_speak_batch` 中硬编码过滤逻辑而不检查 `scene_cast`**: 应从 state 中读取 scene_cast 并在准备阶段过滤
- **在 Android ViewModel 的 WS 事件处理中直接更新 actors 列表**: 应通过 `mergeCastWithStatus` 或类似合并逻辑，保持数据源一致性
- **遗忘在 `init_drama_state` 中初始化新字段**: 新字段必须在 `init_drama_state()` 和 `load_progress()` 两处同步添加

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State 持久化 | 自写 JSON 保存逻辑 | `_set_state(state, tool_context)` | 已有防抖 + 立即 flush 机制 |
| WS 事件广播 | 自写 WS 推送代码 | `TOOL_EVENT_MAP` + `ConnectionManager.broadcast()` | 映射 + 重播缓冲区已处理 |
| Actor 数据合并 | 自写 DTO 转换 | `mergeCastWithStatus()` | 已处理 A2A 状态/端口/思考进度合并 |
| 后端状态迁移 | 自写版本号检测 | `state.setdefault()` | 12+ 迁移先例，零版本号惯例 |
| 线程安全 ID | 自写 AtomicInteger | `BubbleMerger.nextBubbleId()` | AtomicLong 已就位 |

**Key insight:** 后端状态迁移不使用版本号，而是用 `setdefault()` + per-field 兜底。这降低了实现复杂度，但要求每个新字段都在 `init_drama_state()` 和 `load_progress()` 两处同步添加。

## Runtime State Inventory

> 本阶段涉及 state 新增字段 + REST 端点修改，需检查运行时状态。

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `state.json` — 旧存档无 `scene_cast` 字段 | `load_progress()` 迁移：`state.setdefault("scene_cast", [])` |
| Live service config | `app/.adk/session.db` — ADK session 可能缓存旧 state 结构 | 代码层面通过 `setdefault()` 兜底，无需迁移 session.db |
| OS-registered state | None — 无系统级注册 | — |
| Secrets/env vars | None — scene_cast 不涉及密钥 | — |
| Build artifacts | None — 纯代码变更 | — |

**Nothing found in category:**
- OS-registered state: 无 — verified by 代码审计
- Secrets/env vars: 无 — verified by .env.example
- Build artifacts: 无 — 纯 Python/Kotlin 代码变更

## Common Pitfalls

### Pitfall 1: scene_cast 为空导致无人发言
**What goes wrong:** 导演清空 scene_cast 后，`actor_speak_batch` 无演员可调用，场景卡住
**Why it happens:** CONTEXT.md 已识别此风险（Severity: HIGH）
**How to avoid:** `set_scene_cast()` 工具必须校验非空；`next_scene()` 默认值 = 所有 AI 演员名；`actor_speak_batch()` 遇空 scene_cast 时返回友好错误而非静默失败
**Warning signs:** `actor_speak_batch` 返回 `results: []`，UI 无新对话

### Pitfall 2: 旧存档 scene_cast 缺失导致所有演员"待机"
**What goes wrong:** 加载旧存档时 `state.get("scene_cast")` 返回 None/空，如果代码将其理解为"无演员上场"则所有演员变待机
**Why it happens:** `None` vs `[]` 语义歧义 — `None` 表示"未设置（默认全员上场）"，`[]` 表示"明确设为空"
**How to avoid:** 迁移逻辑中 `scene_cast` 的默认值应为 `None`（而非 `[]`），读取时判断：`cast = state.get("scene_cast"); if cast is None: cast = all_ai_actors`
**Warning signs:** 加载旧存档后演员面板全部灰显

### Pitfall 3: next_scene 重置 scene_cast 导致导演手动选角丢失
**What goes wrong:** 导演手动调整 scene_cast 后，执行 `/next` 推进场景时 scene_cast 被重置为全部演员
**Why it happens:** `next_scene()` 调用 `advance_scene()` 后重建 scene_cast
**How to avoid:** `next_scene()` 添加可选 `cast` 参数；无参数时默认重置为全部 AI 演员（符合锁定决策），有参数时使用指定 cast；导演可在 `/next` 后立即 `/cast` 调整
**Warning signs:** 导演手动选角后在场景推进时被重置

### Pitfall 4: Android mergeCastWithStatus 未填充 onStage
**What goes wrong:** 新增 `ActorInfo.onStage` 字段后，REST API `/drama/cast` 响应中无 `scene_cast` 信息，导致 `onStage` 始终为默认值
**Why it happens:** `mergeCastWithStatus` 仅合并 `/drama/cast` + `/drama/cast/status`，scene_cast 信息在 state 而非 cast 端点
**How to avoid:** 方案 A：`/drama/cast/status` 响应中增加 `scene_cast` 字段；方案 B：新增 `/drama/cast/scene` 端点；方案 C：cast_change WS 事件驱动更新。推荐方案 A（最小变更）
**Warning signs:** 演员 onStage 状态在 app 重启后丢失

### Pitfall 5: event_mapper 遗漏 cast_change 的 response 数据提取
**What goes wrong:** `TOOL_EVENT_MAP` 添加了 `set_scene_cast` → `cast_change` 映射，但 `_extract_call_data`/`_extract_response_data` 未处理 `cast_change` 类型，导致客户端收到空 data
**Why it happens:** 新事件类型需要在 3 处同步：`TOOL_EVENT_MAP` + `_extract_call_data` + `_extract_response_data`
**How to avoid:** 添加 `cast_change` 时在 `_extract_response_data` 中提取 `scene_cast` 列表 + 变更详情
**Warning signs:** WS 事件 data 为空 dict `{}`

## Code Examples

### Example 1: set_scene_cast 工具（参考 steer_drama 模式）
```python
# 模式来源: app/tools.py:1574-1606 (steer_drama)
# 模式来源: app/tools.py:2403-2413 (update_emotion)

def set_scene_cast(
    cast: list[str],
    tool_context: ToolContext,
) -> dict:
    """Set the on-stage actors for the current scene. Use when director adjusts cast.

    Args:
        cast: List of actor names who are on-stage for this scene.
            Must not be empty. Actors not in this list will be on standby.

    Returns:
        dict with status and updated cast info.
    """
    state = _get_state(tool_context)

    # 参数校验
    if not cast:
        return {"status": "error", "message": "❌ 场景卡司不能为空。至少需要一名上场演员。"}

    # 校验演员存在性
    all_actors = state.get("actors", {})
    ai_actors = [n for n, d in all_actors.items() if not d.get("is_user_protagonist")]
    invalid = [n for n in cast if n not in all_actors]
    if invalid:
        return {"status": "error", "message": f"❌ 演员不存在：{'、'.join(invalid)}"}

    # 用户主角始终在场
    user_protagonists = [n for n, d in all_actors.items() if d.get("is_user_protagonist")]
    full_cast = list(dict.fromkeys(user_protagonists + cast))  # 去重保序

    state["scene_cast"] = full_cast
    _set_state(state, tool_context)

    standby = [n for n in ai_actors if n not in full_cast]
    return {
        "status": "success",
        "scene_cast": full_cast,
        "standby": standby,
        "message": f"🎭 场景卡司已更新\n上场：{'、'.join(full_cast)}\n待机：{'、'.join(standby) if standby else '无'}",
    }
```

### Example 2: next_scene 中 scene_cast 集成
```python
# 模式来源: app/tools.py:1295-1447 (next_scene)
# 关键修改点：在返回结果中包含 scene_cast 信息

def next_scene(tool_context: ToolContext) -> dict:
    # ... 现有逻辑 ...
    actors_data = state.get("actors", {})
    ai_actors = [n for n, d in actors_data.items() if not d.get("is_user_protagonist")]

    # ★ 新增：scene_cast 默认值逻辑
    scene_cast = state.get("scene_cast")
    if scene_cast is None:
        # 未设置 scene_cast（首次或旧存档）→ 默认全员上场
        scene_cast = list(actors_data.keys())
        state["scene_cast"] = scene_cast
        _set_state(state, tool_context)

    # 返回值包含 scene_cast
    return {
        "status": "success",
        "current_scene": scene_num,
        "actors_available": scene_cast,  # ★ 改为仅上场演员
        "scene_cast": scene_cast,        # ★ 新增
        "standby": [n for n in ai_actors if n not in scene_cast],  # ★ 新增
        # ... 其余现有字段 ...
    }
```

### Example 3: actor_speak_batch 中 scene_cast 过滤
```python
# 模式来源: app/tools.py:569-710 (actor_speak_batch)
# 关键修改点：在准备阶段检查 scene_cast

async def actor_speak_batch(actors: list[dict], tool_context: ToolContext) -> dict:
    state = tool_context.state.get("drama", {})
    scene_cast = state.get("scene_cast")  # ★ 新增
    # scene_cast 为 None 表示未设置（旧存档），不限制
    # scene_cast 为 list 则限制仅场内演员发言

    prep_list = []
    for entry in actors:
        actor_name = entry.get("actor_name", "")
        # ★ 新增：scene_cast 过滤
        if scene_cast is not None and actor_name not in scene_cast:
            prep_list.append({
                "actor_name": actor_name,
                "skip": True,
                "skip_reason": f"演员待机中（不在 scene_cast）",
            })
            continue
        # ... 原有逻辑 ...
```

### Example 4: event_mapper 添加 cast_change 映射
```python
# 模式来源: app/api/event_mapper.py:21-44, 78-126

# 1. TOOL_EVENT_MAP 添加映射
TOOL_EVENT_MAP: dict[str, list[str]] = {
    # ... 现有映射 ...
    "set_scene_cast": ["cast_change", "command_echo"],
}

# 2. _extract_call_data 添加 cast_change 处理
elif event_type == "cast_change":
    return {
        "tool": function_call.name,
        "cast": list(args.get("cast", [])),
        "sender_type": "director",
        "sender_name": "旁白",
    }

# 3. _extract_response_data 添加 cast_change 处理
elif event_type == "cast_change":
    return {
        "scene_cast": response.get("scene_cast", []),
        "standby": response.get("standby", []),
        "sender_type": "director",
        "sender_name": "旁白",
    }
```

### Example 5: ActorInfo 扩展 onStage 字段
```kotlin
// 来源: android/app/src/main/java/com/drama/app/domain/model/ActorInfo.kt
data class ActorInfo(
    val name: String,
    val role: String = "",
    val personality: String = "",
    val background: String = "",
    val emotions: String = "neutral",
    val memorySummary: String = "",
    val isA2ARunning: Boolean = false,
    val a2aPort: Int = 0,
    val thinkingProgress: Int = 0,
    val onStage: Boolean = true,  // ★ 新增，默认 true（向后兼容）
)
```

### Example 6: mergeCastWithStatus 填充 onStage
```kotlin
// 来源: DramaRepositoryImpl.kt:358-396
private fun mergeCastWithStatus(
    cast: CastResponseDto,
    status: CastStatusResponseDto,
    sceneCast: List<String>? = null,  // ★ 新增参数
): List<ActorInfo> {
    val onStageSet = sceneCast?.toSet()  // null = 全员上场
    for ((name, actorElement) in cast.actors) {
        // ... 现有解析逻辑 ...
        val isOnStage = onStageSet?.contains(name) ?: true  // ★ 新增
        mergedActors.add(ActorInfo(
            name = name,
            // ... 现有字段 ...
            onStage = isOnStage,  // ★ 新增
        ))
    }
}
```

### Example 7: Android cast_change WS 事件处理
```kotlin
// 模式来源: DramaDetailViewModel.kt:789-792 (cast_update 处理)
"cast_change" -> {
    // ★ 场景卡司变更 — 更新演员上场状态
    val sceneCast = event.data["scene_cast"]?.let { elem ->
        (elem as? kotlinx.serialization.json.JsonArray)?.mapNotNull {
            it.jsonPrimitive.contentOrNull
        }
    } ?: emptyList()
    // 直接更新现有 actors 列表的 onStage 状态
    _uiState.update { state ->
        state.copy(actors = state.actors.map { actor ->
            actor.copy(onStage = sceneCast.isEmpty() || actor.name in sceneCast)
        })
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 全局 actors dict 无场景级区分 | scene_cast List[str] 场景级过滤 | Phase 24 | 导演可控制每场戏的参与演员 |
| 演员面板平等展示 | 在场/待机分组 + 视觉区分 | Phase 24 | 用户可直观区分演员状态 |
| cast_update 全量刷新 | cast_change 增量推送 | Phase 24 | 更高效的 UI 更新 |

**Deprecated/outdated:**
- `actors_available = list(state["actors"].keys())` 全量返回：应改为 `scene_cast` 过滤

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | scene_cast 默认值 `None` 表示"全员上场"，`[]` 表示"明确为空" | Architecture Patterns | 如果代码某处将 `None` 和 `[]` 混用，可能导致全部待机 |
| A2 | `/drama/cast/status` API 可以安全扩展以包含 `scene_cast` 字段 | Common Pitfalls | 如果前端依赖固定 schema，可能需要版本协商 |
| A3 | `set_scene_cast` 工具只需在 `_improv_director` agent 注册，无需在 `_setup_agent` 注册 | Architecture Patterns | 如果 setup 阶段需要选角，则需要在两个 agent 都注册 |
| A4 | MentionChip 组件可复用于选角 UI，不需要新组件 | Android Patterns | 如果交互模式差异大（多选 vs 单选），可能需要新组件 |
| A5 | `cast_change` 事件不需要在 `NO_TYPING_TOOLS` 中排除 | Architecture Patterns | 如果 set_scene_cast 是瞬间操作，应排除 typing |

## Open Questions

1. **scene_cast 是否应持久化到 state.json 还是每次 next_scene 时重置？**
   - What we know: CONTEXT.md 决定 `next_scene()` 默认重置为全部 AI 演员
   - What's unclear: 导演手动调整的 scene_cast 是否应在 `/save` 后持久化？下次 `/load` 时恢复？
   - Recommendation: 持久化到 state.json。`load_progress()` 迁移时默认为 `None`（全员上场），导演调整后保存的 scene_cast 会被恢复

2. **`/drama/cast/status` API 扩展方案选择**
   - What we know: Android 当前通过 `getMergedCast()` 合并 cast + status
   - What's unclear: scene_cast 信息应放在 `/drama/cast/status` 响应中，还是新建端点，还是仅通过 WS 推送
   - Recommendation: 扩展 `/drama/cast/status` 响应添加 `scene_cast` 字段（最小变更，向后兼容）

3. **Android 选角交互的具体模式**
   - What we know: 锁定为 Claude's Discretion
   - What's unclear: 底部 Sheet / 对话框 / 演员面板内嵌 toggle
   - Recommendation: 演员面板内嵌 toggle 开关（最自然，复用现有面板，点击即切换上场/待机）

## Environment Availability

> 本阶段无新增外部依赖。仅涉及现有代码修改。

Step 2.6: SKIPPED (no new external dependencies — all changes are within existing Python/Android codebase)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (Backend) | pytest >=8.3.4 + pytest-asyncio |
| Config file | pyproject.toml (tool.ruff, tool.pytest) |
| Quick run command | `uv run pytest tests/unit/test_tools_phase5.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -x` |
| Framework (Android) | junit + mockito-kotlin + coroutines-test |
| Quick run command | `./gradlew :app:testDebugUnitTest --tests "*.BubbleMergerTest" -q` |
| Full suite command | `./gradlew :app:testDebugUnitTest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAST-01 | scene_cast state 字段初始化与迁移 | unit | `uv run pytest tests/unit/test_state_manager.py -x -q -k scene_cast` | ❌ Wave 0 |
| CAST-01 | init_drama_state 包含 scene_cast=None | unit | `uv run pytest tests/unit/test_state_manager.py -x -q -k init_drama` | ✅ (需扩展) |
| CAST-02 | set_scene_cast 工具正常工作 | unit | `uv run pytest tests/unit/test_tools_cast.py -x -q` | ❌ Wave 0 |
| CAST-02 | set_scene_cast 校验空列表 | unit | `uv run pytest tests/unit/test_tools_cast.py -x -q -k empty` | ❌ Wave 0 |
| CAST-02 | set_scene_cast 校验无效演员名 | unit | `uv run pytest tests/unit/test_tools_cast.py -x -q -k invalid` | ❌ Wave 0 |
| CAST-03 | next_scene 返回 scene_cast + standby | unit | `uv run pytest tests/unit/test_tools_cast.py -x -q -k next_scene` | ❌ Wave 0 |
| CAST-03 | actor_speak_batch 过滤待机演员 | unit | `uv run pytest tests/unit/test_tools_cast.py -x -q -k speak_batch` | ❌ Wave 0 |
| CAST-04 | cast_change WS 事件映射 | unit | `uv run pytest tests/unit/test_event_mapper.py -x -q -k cast_change` | ✅ (需扩展) |
| CAST-05 | ActorInfo.onStage 字段 + 默认值 | unit | `./gradlew :app:testDebugUnitTest --tests "*ActorInfo*"` | ❌ Wave 0 |
| CAST-06 | 导演选角 toggle 交互 | manual | — | — |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_tools_cast.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_tools_cast.py` — covers CAST-02, CAST-03
- [ ] `tests/unit/test_state_manager.py` — 扩展 scene_cast 迁移测试
- [ ] `tests/unit/test_event_mapper.py` — 扩展 cast_change 映射测试
- [ ] `android/app/src/test/.../ActorInfoTest.kt` — onStage 字段测试

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | 已有 auth middleware (Phase 15) |
| V3 Session Management | yes | ADK session + state.json |
| V4 Access Control | yes | require_auth + 导演角色校验 |
| V5 Input Validation | yes | set_scene_cast 参数校验 |
| V6 Cryptography | no | 无加密需求 |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 注入无效演员名到 set_scene_cast | Tampering | 参数校验：演员名必须存在于 state["actors"] |
| 清空 scene_cast 导致拒绝服务 | Denial of Service | 非空校验 + 用户主角自动包含 |
| WS 事件伪造（客户端冒充 cast_change） | Spoofing | 事件仅由后端 event_mapper 生成，客户端只读 |

## Sources

### Primary (HIGH confidence)
- `app/tools.py` — 工具结构模式，next_scene/actor_speak_batch/steer_drama/update_emotion 完整源码
- `app/state_manager.py` — 状态管理模式，init_drama_state/load_progress 迁移惯例
- `app/api/event_mapper.py` — WS 事件映射模式，TOOL_EVENT_MAP + 双阶段提取
- `android/app/src/main/java/com/drama/app/domain/model/ActorInfo.kt` — 当前数据模型
- `android/app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt` — mergeCastWithStatus 数据合并
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ActorDrawerContent.kt` — 演员面板 UI
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt` — MentionChip 可复用组件
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/orchestrator/` — Phase 23 子组件模式

### Secondary (MEDIUM confidence)
- Phase 23-01-SUMMARY.md — VM 拆分架构确认
- Phase 23-RESEARCH.md — 子组件组合模式详细说明

### Tertiary (LOW confidence)
- 无

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 全部基于项目现有代码审计，无外部依赖
- Architecture: HIGH — 工具/状态/事件模式均有多个代码先例可参考
- Pitfalls: HIGH — 基于代码审计发现的具体风险点

**Research date:** 2026-04-29
**Valid until:** 2026-05-29 (stable — 无外部依赖，项目代码变更频率低)
