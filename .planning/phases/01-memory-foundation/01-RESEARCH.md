# Phase 1: Memory Foundation - Research

**Researched:** 2026-04-11
**Domain:** 3 层记忆架构（工作记忆/场景摘要/全局摘要）+ LLM 异步压缩 + 旧格式迁移
**Confidence:** HIGH

## Summary

当前系统的演员记忆存储为 `actor.memory` 扁平列表，每条记忆仅有 `{entry, timestamp}` 结构，无容量限制、无压缩、无重要性区分。`actor_speak()` 在构建 prompt 时直接将全部记忆拼接为字符串，当戏剧推进到 50+ 场时（每场 3-5 条记忆 → 150-250 条），单次 actor 调用的记忆部分就超过 7500-12500 tokens，导致上下文窗口溢出。

本阶段需要构建 3 层记忆架构：工作记忆（5 条）、场景摘要（10 条）、全局摘要（结构化+自由文本），加上独立的 `critical_memories` 存储。核心挑战在于 LLM 压缩的异步实现——场景结束后后台启动压缩，下次使用时读取结果；以及旧格式到新格式的自动迁移逻辑。

**Primary recommendation:** 新建 `app/memory_manager.py` 模块，遵循现有 `state_manager.py` 的函数签名风格（`def func(params, tool_context) -> dict`），替换 `actor_speak()` 中的扁平 `memory_str` 构建，在 `load_progress()` 中插入迁移逻辑。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 工作记忆容量 = 5 条（覆盖当前+2个近期场景的详情）
- **D-02:** 场景摘要容量 = 10 条（约覆盖 20-30 场的压缩信息）
- **D-03:** 全局摘要 = 结构化字段（主题/关键角色/未决冲突/已解决冲突）+ 自由文本概述，两者兼有
- **D-04:** 工作记忆超过 5 条时触发压缩（最旧条目压缩为场景摘要）
- **D-05:** 场景摘要超过 10 条时触发压缩（最旧摘要压缩入全局摘要）
- **D-06:** 6 类事件自动标记为关键记忆：1.角色首次登场/关系确立 2.重大转折事件 3.情感高峰/低谷 4.未决事件/悬念 5.用户明确标记的事件（/mark 命令）6.系统检测的其他高重要性事件
- **D-07:** 关键记忆独立存储于 `actor.critical_memories`，不占用工作记忆的 5 条槽位，压缩时不会被丢弃
- **D-08:** 使用 LLM 生成摘要（自然语言摘要，质量高）
- **D-09:** 异步后台压缩——场景结束后后台启动压缩，下次场景使用时读取结果，用户无感
- **D-10:** 全局摘要更新策略：每次场景摘要被压缩时，用 LLM 重写整个全局摘要（保持精炼一致）
- **D-11:** 自动迁移——`load_progress()` 时检测旧格式 `actor.memory`（扁平列表），自动将全部条目倒入 `actor.working_memory`，用户无感
- **D-12:** 3 层记忆数据结构嵌套在 actor 对象内（详细结构见 CONTEXT.md）
- **D-13:** 旧版 `actor.memory` 字段保留为只读（不删除），新代码统一使用新字段

### Claude's Discretion
- LLM 调用使用的具体模型和 prompt 模板
- 异步压缩的具体实现方式（后台线程/协程/延迟任务）
- 场景摘要的格式细节
- `/mark` 命令的 CLI 交互设计

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEMORY-01 | 3 层记忆架构 — 工作记忆（当前场景详情）、场景摘要（近期场景压缩）、全局摘要（远期整体浓缩），三层逐级压缩 | §Architecture Patterns 详述数据结构设计；§Code Examples 提供完整函数签名 |
| MEMORY-02 | 自动记忆压缩 — 场景数超过阈值时自动将最早的工作记忆压缩为场景摘要，场景摘要超过阈值时压缩为全局摘要 | §LLM Compression Design 详述压缩触发逻辑、prompt 设计、异步实现 |
| MEMORY-03 | 重要性权重摘要 — 压缩时根据事件重要性保留关键细节（角色首次登场、重大转折、情感高峰），次要事件仅保留一句概述 | §Implementation Approach 详述 critical_memories 机制和 6 类判定逻辑 |
</phase_requirements>

## Current State Analysis

### 1. 记忆存储位置

记忆存储在 `tool_context.state["drama"]["actors"][name]` dict 中，键名为 `"memory"`：

```python
# state_manager.py:601-609 register_actor()
actor_data = {
    "role": role,
    "personality": personality,
    "background": background,
    "knowledge_scope": knowledge_scope,
    "memory": [],           # ← 扁平列表，仅此一个字段
    "emotions": "neutral",
    "created_at": datetime.now().isoformat(),
}
```

每条记忆条目结构为：
```python
{
    "entry": "面对情境: 导演描述了...",   # 文本内容
    "timestamp": "2026-04-11T10:30:00.123456"  # ISO 时间戳
}
```

**问题：** 无场景编号、无重要性标记、无压缩标记，纯追加列表。

### 2. 记忆更新方式

唯一入口：`state_manager.py:620-642 update_actor_memory()`

```python
def update_actor_memory(actor_name: str, memory_entry: str, tool_context=None) -> dict:
    actors[actor_name]["memory"].append({
        "entry": memory_entry,
        "timestamp": datetime.now().isoformat(),
    })
    state["actors"] = actors
    _set_state(state, tool_context)
```

调用方（`tools.py:205`）：
```python
update_actor_memory(actor_name, f"面对情境: {situation}", tool_context)
```

**问题：**
- 只记录了 "面对情境"，没有记录演员的对话回复（记忆不完整）
- 没有场景编号关联
- 无容量控制——纯 append，永不删除

### 3. 记忆消费方式

`tools.py:201-213` 中 `actor_speak()` 构建记忆字符串：

```python
memory_entries = [m["entry"] for m in actor_data.get("memory", [])]
memory_str = "\n".join(f"- {m}" for m in memory_entries) if memory_entries else "暂无记忆"

prompt = (
    f"【当前情境】{situation}\n\n"
    f"【你的记忆】\n{memory_str}\n\n"
    f"请以「{actor_name}」的身份回应上述情境。"
    f"保持角色一致性，不要跳出角色。"
    f"如有内心独白，用（内心：...）格式。"
)
```

**问题：**
- `memory_entries` 取出所有记忆，无过滤、无截断
- 记忆是纯文本列表，无层次感
- 缺少角色锚点（PITFALLS.md #3：演员遗忘背景设定）
- 缺少情绪状态注入

### 4. 记忆持久化流程

```
update_actor_memory() → _set_state() → tool_context.state["drama"] = state → _save_state_to_file()
```

`_set_state()` 每次调用都会序列化整个 state dict 到 `state.json`。`load_progress()` 从 `state.json` 反序列化后执行 `state.update(save_data)`。

**load_drama（tools.py:552-631）中的记忆消费：**

```python
memory_entries = [m["entry"] for m in actor_info.get("memory", [])]
svc_result = create_actor_service(
    actor_name=actor_name, ...,
    memory_entries=memory_entries,  # 注入到 A2A agent 的 system prompt
)
```

**问题：** `load_drama` 将全部记忆注入到 A2A agent 的 system prompt（`memory_section` in `generate_actor_agent_code:91-98`），这会随着记忆增长变得不可控。

### 5. 完整数据流

```
actor_speak()
  ├── get_actor_info() → 读取 actor_data["memory"]
  ├── 构建 memory_str（全部记忆拼接）
  ├── update_actor_memory() → 追加 "面对情境: {situation}"
  ├── 构建 prompt → 发送到 A2A agent
  └── 返回 dialogue

load_drama()
  ├── load_progress() → 从 state.json 加载
  ├── 提取 memory_entries → 注入 A2A agent system prompt
  └── 重启 A2A 服务
```

## Implementation Approach

### 新模块: `app/memory_manager.py`

#### 常量定义

```python
# Capacity limits (from D-01, D-02)
WORKING_MEMORY_LIMIT = 5      # 工作记忆最大条数
SCENE_SUMMARY_LIMIT = 10      # 场景摘要最大条数

# Critical memory reason types (from D-06)
CRITICAL_REASONS = [
    "首次登场",      # Character first appearance / relationship established
    "重大转折",      # Major plot turning point
    "情感高峰",      # Emotional peak
    "情感低谷",      # Emotional valley
    "未决事件",      # Unresolved event / suspense
    "用户标记",      # User explicitly marked via /mark
    "系统检测",      # System-detected high importance
]
```

#### 核心函数签名

```python
def add_working_memory(
    actor_name: str,
    entry: str,
    importance: str,  # "normal" | "critical"
    critical_reason: str | None,  # from CRITICAL_REASONS, only when importance="critical"
    tool_context: ToolContext,
) -> dict:
    """Add a memory entry to an actor's working memory.

    If importance is "critical", also add to critical_memories.
    After adding, check if compression is needed.

    Args:
        actor_name: The actor's name.
        entry: The memory text.
        importance: "normal" or "critical".
        critical_reason: Reason tag (required when importance="critical").
        tool_context: Tool context for state access.

    Returns:
        dict with status and compression info.
    """


def check_and_compress(actor_name: str, tool_context: ToolContext) -> dict:
    """Check memory tier sizes and trigger async compression if limits exceeded.

    This is the main compression orchestrator. Called after each memory addition.
    - If working_memory > WORKING_MEMORY_LIMIT: trigger _compress_working_to_scene()
    - If scene_summaries > SCENE_SUMMARY_LIMIT: trigger _compress_scene_to_arc()

    Args:
        actor_name: The actor whose memory to check.
        tool_context: Tool context for state access.

    Returns:
        dict with compression status (what was triggered, if anything).
    """


def build_actor_context(actor_name: str, tool_context: ToolContext) -> str:
    """Build the complete memory context string for an actor_speak() call.

    Replaces the old flat memory_str construction in tools.py:201-213.
    Assembles: character anchor + critical memories + arc summary + scene summaries + working memory.

    Args:
        actor_name: The actor whose context to build.
        tool_context: Tool context for state access.

    Returns:
        Formatted context string for the actor prompt.
    """


def mark_critical_memory(
    actor_name: str,
    memory_index: int,  # Index in working_memory list to promote
    reason: str,  # One of CRITICAL_REASONS
    tool_context: ToolContext,
) -> dict:
    """Mark an existing working memory entry as critical.

    Moves it to critical_memories and removes from working_memory.
    Used by /mark command.

    Args:
        actor_name: The actor's name.
        memory_index: 0-based index in working_memory.
        reason: Why this memory is critical.
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """


def migrate_legacy_memory(actor_name: str, tool_context: ToolContext) -> dict:
    """Migrate old flat actor.memory to new 3-tier structure.

    Called from load_progress() when old format detected.
    Per D-11: all old entries go to working_memory.
    Per D-13: old memory field preserved as read-only.

    Args:
        actor_name: The actor whose memory to migrate.
        tool_context: Tool context for state access.

    Returns:
        dict with migration status.
    """


async def compress_working_to_scene(
    actor_name: str,
    entries_to_compress: list[dict],
    tool_context: ToolContext,
) -> dict:
    """Compress working memory entries into a scene summary using LLM.

    Called by check_and_compress() when working_memory exceeds limit.
    Per D-08: uses LLM for natural language summary.
    Per D-09: runs asynchronously — stores result, next call picks it up.

    Args:
        actor_name: The actor whose memory to compress.
        entries_to_compress: Working memory entries to compress.
        tool_context: Tool context for state access.

    Returns:
        dict with the generated scene summary.
    """


async def compress_scene_to_arc(
    actor_name: str,
    summaries_to_compress: list[dict],
    tool_context: ToolContext,
) -> dict:
    """Compress scene summaries into arc summary using LLM.

    Called by check_and_compress() when scene_summaries exceeds limit.
    Per D-10: rewrites entire arc summary each time.

    Args:
        actor_name: The actor whose memory to compress.
        summaries_to_compress: Scene summaries to compress.
        tool_context: Tool context for state access.

    Returns:
        dict with the updated arc summary.
    """
```

#### 辅助函数（私有）

```python
def _get_actor_state(actor_name: str, tool_context: ToolContext) -> dict:
    """Get actor data dict from state. Returns empty dict if not found."""

def _is_critical_entry(entry_text: str) -> tuple[bool, str | None]:
    """Heuristic check: does this entry match any critical pattern?

    Returns (is_critical, reason_or_none).
    Used when importance="normal" to auto-detect critical events.
    """

def _detect_critical_event(entry_text: str, situation: str) -> str | None:
    """Use keyword patterns to detect D-06 critical event types.

    Checks for:
    - 首次登场: "第一次" "初见" "登场"
    - 重大转折: "转折" "突变" "发现" "揭露"
    - 情感高峰/低谷: emotion words in context
    - 未决事件: "悬念" "未知" "谜"
    Returns reason string or None.
    """

def _build_compression_prompt_working(entries: list[dict], actor_name: str) -> str:
    """Build the LLM prompt for working→scene compression."""

def _build_compression_prompt_arc(
    summaries: list[dict],
    existing_arc: dict,
    actor_name: str,
) -> str:
    """Build the LLM prompt for scene→arc compression."""
```

### state_manager.py 修改

#### 1. `register_actor()` — 新增默认字段

```python
# 当前（state_manager.py:601-609）
actor_data = {
    "role": role,
    "personality": personality,
    "background": background,
    "knowledge_scope": knowledge_scope,
    "memory": [],
    "emotions": "neutral",
    "created_at": datetime.now().isoformat(),
}

# 修改后
actor_data = {
    "role": role,
    "personality": personality,
    "background": background,
    "knowledge_scope": knowledge_scope,
    "memory": [],               # D-13: 保留旧字段（只读）
    "working_memory": [],       # D-12: 新 Tier 1
    "scene_summaries": [],      # D-12: 新 Tier 2
    "arc_summary": {            # D-12: 新 Tier 3
        "structured": {
            "theme": "",
            "key_characters": [],
            "unresolved": [],
            "resolved": [],
        },
        "narrative": "",
    },
    "critical_memories": [],    # D-07: 独立存储
    "emotions": "neutral",
    "created_at": datetime.now().isoformat(),
}
```

#### 2. `load_progress()` — 插入迁移逻辑

在 `load_progress()` 的 `_set_state(state, tool_context)` 调用之前（约 line 441），插入迁移检查：

```python
# 在 load_progress() 中，state.update(save_data) 之后
for actor_name, actor_data in state.get("actors", {}).items():
    if "working_memory" not in actor_data:
        # 旧格式检测 → 触发迁移
        from .memory_manager import migrate_legacy_memory
        migrate_legacy_memory(actor_name, tool_context)
```

#### 3. `update_actor_memory()` — 标记为弃用但保留

```python
def update_actor_memory(actor_name: str, memory_entry: str, tool_context=None) -> dict:
    """Add a memory entry for an actor. [DEPRECATED: use memory_manager.add_working_memory()]

    Kept for backward compatibility. Internally delegates to the new memory system.
    """
    from .memory_manager import add_working_memory
    return add_working_memory(
        actor_name=actor_name,
        entry=memory_entry,
        importance="normal",
        critical_reason=None,
        tool_context=tool_context,
    )
```

#### 4. `get_all_actors()` — 更新摘要字段

```python
# 当前（state_manager.py:694-704）
summary[name] = {
    "role": info.get("role", ""),
    "personality": info.get("personality", ""),
    "background": info.get("background", ""),
    "emotions": info.get("emotions", "neutral"),
    "memory_count": len(info.get("memory", [])),
}

# 修改后
summary[name] = {
    "role": info.get("role", ""),
    "personality": info.get("personality", ""),
    "background": info.get("background", ""),
    "emotions": info.get("emotions", "neutral"),
    "memory_count": len(info.get("memory", [])),  # 旧字段保留
    "working_memory_count": len(info.get("working_memory", [])),
    "scene_summaries_count": len(info.get("scene_summaries", [])),
    "critical_memories_count": len(info.get("critical_memories", [])),
    "has_arc_summary": bool(info.get("arc_summary", {}).get("narrative", "")),
}
```

### tools.py 修改

#### 1. `actor_speak()` — 替换 memory_str 构建

```python
# 当前（tools.py:201-213）
memory_entries = [m["entry"] for m in actor_data.get("memory", [])]
memory_str = "\n".join(f"- {m}" for m in memory_entries) if memory_entries else "暂无记忆"
update_actor_memory(actor_name, f"面对情境: {situation}", tool_context)
prompt = (
    f"【当前情境】{situation}\n\n"
    f"【你的记忆】\n{memory_str}\n\n"
    f"请以「{actor_name}」的身份回应上述情境。"
    f"保持角色一致性，不要跳出角色。"
    f"如有内心独白，用（内心：...）格式。"
)

# 修改后
from .memory_manager import add_working_memory, build_actor_context, check_and_compress

# 1. 先构建上下文（读取当前记忆状态）
memory_context = build_actor_context(actor_name, tool_context)

# 2. 将当前情境添加到工作记忆
importance = _assess_importance(situation, actor_data)  # 辅助函数
add_working_memory(
    actor_name=actor_name,
    entry=f"面对情境: {situation}",
    importance=importance["importance"],
    critical_reason=importance.get("reason"),
    tool_context=tool_context,
)

# 3. 触发异步压缩检查（不阻塞）
check_and_compress(actor_name, tool_context)

# 4. 构建增强 prompt
emotion_label = actor_data.get("emotions", "neutral")
emotion_cn = {"neutral": "平静", ...}.get(emotion_label, emotion_label)
prompt = (
    f"【角色锚点】你是{actor_name}，{actor_data.get('role', '')}。"
    f"{actor_data.get('personality', '')}\n\n"
    f"【当前情绪】{emotion_cn}\n\n"
    f"【当前情境】{situation}\n\n"
    f"{memory_context}\n\n"
    f"请以「{actor_name}」的身份回应上述情境。"
    f"保持角色一致性，不要跳出角色。"
    f"如有内心独白，用（内心：...）格式。"
)
```

#### 2. `actor_speak()` — 对话后更新记忆

在获取 actor_dialogue 后，将对话也记入记忆（当前系统只记录情境不记录回复）：

```python
# 在获取 actor_dialogue 后添加
add_working_memory(
    actor_name=actor_name,
    entry=f"我说：{actor_dialogue[:200]}",  # 截断避免过长
    importance="normal",
    critical_reason=None,
    tool_context=tool_context,
)
```

#### 3. `load_drama()` — 更新记忆提取逻辑

```python
# 当前（tools.py:586）
memory_entries = [m["entry"] for m in actor_info.get("memory", [])]

# 修改后：优先使用新的记忆层构建上下文
from .memory_manager import build_actor_context
# 但 load_drama 需要的是 memory_entries 列表（注入 A2A system prompt），
# 所以需要从新结构中提取摘要文本
memory_entries = _extract_memory_for_a2a(actor_info)
```

#### 4. 新增 `/mark` 工具函数

```python
def mark_memory(
    actor_name: str,
    reason: str,  # 简短说明，如 "这段很重要"
    tool_context: ToolContext,
) -> dict:
    """Mark the most recent working memory of an actor as critical.

    User-facing /mark command implementation.
    Per D-06 type 5: user explicitly marked events.

    Args:
        actor_name: The actor whose memory to mark.
        reason: User's explanation of why this is important.

    Returns:
        dict with status.
    """
    from .memory_manager import mark_critical_memory
    # Mark the last working memory entry
    state = tool_context.state.get("drama", {})
    working = state.get("actors", {}).get(actor_name, {}).get("working_memory", [])
    if not working:
        return {"status": "error", "message": f"演员「{actor_name}」没有工作记忆可标记。"}
    return mark_critical_memory(
        actor_name=actor_name,
        memory_index=len(working) - 1,
        reason="用户标记",
        tool_context=tool_context,
    )
```

### 迁移逻辑详细算法

```python
def migrate_legacy_memory(actor_name: str, tool_context: ToolContext) -> dict:
    """Migrate old flat actor.memory to new 3-tier structure.

    Algorithm:
    1. Check if working_memory already exists → skip if so
    2. Read old memory list: actor_data.get("memory", [])
    3. Convert each old entry {entry, timestamp} → {entry, importance: "normal", scene: 0}
       - scene=0 because we don't know which scene it was from
    4. If old memory count > WORKING_MEMORY_LIMIT:
       - First WORKING_MEMORY_LIMIT entries → scene_summaries (as-is, no compression)
       - Actually: put all in working_memory, let next check_and_compress() handle it
       - But that could trigger many async compressions at once...
       - Better: put all in working_memory with a flag, let natural compression handle it
    5. Initialize empty scene_summaries, arc_summary, critical_memories
    6. Keep old memory field (D-13: read-only preservation)

    Edge cases:
    - Empty memory list → just initialize new fields
    - Very large memory list (100+ entries) → put all in working_memory,
      compress gradually over next few scenes rather than all at once
    - Corrupted entries (missing "entry" key) → skip with warning
    """
    state = tool_context.state.get("drama", {})
    actors = state.get("actors", {})
    actor_data = actors.get(actor_name, {})

    if "working_memory" in actor_data:
        return {"status": "info", "message": f"演员「{actor_name}」已是新格式，无需迁移。"}

    old_memories = actor_data.get("memory", [])

    # Convert old format to new working_memory format
    new_working = []
    for m in old_memories:
        entry_text = m.get("entry", "")
        if not entry_text:
            continue
        new_working.append({
            "entry": entry_text,
            "importance": "normal",
            "scene": 0,  # Unknown scene
        })

    # Apply new fields
    actor_data["working_memory"] = new_working
    actor_data["scene_summaries"] = []
    actor_data["arc_summary"] = {
        "structured": {
            "theme": "",
            "key_characters": [],
            "unresolved": [],
            "resolved": [],
        },
        "narrative": "",
    }
    actor_data["critical_memories"] = []
    # Keep old "memory" field (D-13)

    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": f"演员「{actor_name}」记忆已迁移: {len(old_memories)} 条旧记忆 → working_memory",
        "migrated_count": len(old_memories),
    }
```

## LLM Compression Design

### 压缩触发机制

```
add_working_memory()
  └── check_and_compress()
        ├── if len(working_memory) > 5:
        │     overflow = working_memory[:-5]
        │     asyncio.create_task(compress_working_to_scene(actor, overflow, tc))
        │     working_memory = working_memory[-5:]  # 保留最新5条
        │
        └── if len(scene_summaries) > 10:
              overflow = scene_summaries[:-10]
              asyncio.create_task(compress_scene_to_arc(actor, overflow, tc))
              scene_summaries = scene_summaries[-10:]  # 保留最新10条
```

### 异步实现方案

**推荐方案：asyncio.create_task() + state 中的 pending_compression 字段**

```python
# 在 actor_data 中新增
actor_data["_pending_compression"] = {
    "working_to_scene": None,  # asyncio.Task 或 None
    "scene_to_arc": None,      # asyncio.Task 或 None
}
```

**流程：**

1. `check_and_compress()` 检测到溢出时，将 overflow 条目临时存入 `actor_data["_pending_compression"]["pending_entries"]`
2. 启动 `asyncio.create_task(compress_working_to_scene(...))` 
3. 压缩任务完成后，将结果写入 `actor_data["_pending_compression"]["result"]`
4. 下次 `build_actor_context()` 时，检查是否有待写入的压缩结果
5. 如果有，将结果合并到 `scene_summaries`，清除 pending 状态

**关键：压缩结果不直接修改 state，而是通过 pending 字段延迟合并。** 这避免了异步写入的竞态条件。

```python
async def compress_working_to_scene(
    actor_name: str,
    entries: list[dict],
    tool_context: ToolContext,
) -> dict:
    """Async LLM compression of working memory → scene summary."""
    from google.adk.models.lite_llm import LiteLlm

    prompt = _build_compression_prompt_working(entries, actor_name)

    # Use the same LiteLlm model as the main agent
    model = LiteLlm(model=os.environ.get("MODEL_NAME", "openai/claude-sonnet-4-6"))
    response = await model.generate_content_async([prompt])

    summary_text = response.text.strip()

    # Determine scenes covered
    scenes = sorted(set(e.get("scene", 0) for e in entries))
    scenes_covered = f"{scenes[0]}-{scenes[-1]}" if len(scenes) > 1 else str(scenes[0])

    # Extract key events (simple heuristic: first sentence of each entry)
    key_events = []
    for e in entries:
        first_sentence = e["entry"].split("。")[0] + "。"
        key_events.append(first_sentence)

    return {
        "summary": summary_text,
        "scenes_covered": scenes_covered,
        "key_events": key_events,
    }
```

### 压缩结果未就绪时的处理

```python
def build_actor_context(actor_name: str, tool_context: ToolContext) -> str:
    # ... 构建上下文 ...
    # 检查 pending compression
    pending = actor_data.get("_pending_compression", {})
    if pending.get("result"):
        # 合并压缩结果到正式字段
        result = pending["result"]
        if result.get("type") == "working_to_scene":
            actor_data["scene_summaries"].append(result["data"])
        elif result.get("type") == "scene_to_arc":
            actor_data["arc_summary"] = result["data"]
        actor_data["_pending_compression"] = {"working_to_scene": None, "scene_to_arc": None}
        _set_state(state, tool_context)

    # 如果压缩任务还在进行中，使用 overflow 中的原始条目作为 fallback
    if pending.get("pending_entries"):
        # 将未压缩的条目临时包含在上下文中（保证不丢信息）
        for entry in pending["pending_entries"]:
            parts.append(f"  第{entry.get('scene', '?')}场（待压缩）: {entry['entry']}")
```

### LLM Prompt 设计

#### Working → Scene Summary 压缩 Prompt

```python
def _build_compression_prompt_working(entries: list[dict], actor_name: str) -> str:
    entries_text = "\n".join(
        f"- [第{e.get('scene', '?')}场] {e['entry']}" for e in entries
    )
    return f"""你是一位戏剧记忆压缩助手。请将以下演员「{actor_name}」的工作记忆压缩为一段场景摘要。

## 输入（{len(entries)} 条工作记忆）
{entries_text}

## 压缩规则
1. 保留所有关键事件：角色首次登场、重大转折、情感变化、未决事件
2. 次要事件仅保留一句概述
3. 保持时间顺序
4. 使用第三人称叙述
5. 摘要长度控制在 150-200 字
6. 特别标注涉及{actor_name}的情感变化和决策

## 输出格式
直接输出摘要文本，不要加前缀或标题。"""


def _build_compression_prompt_arc(
    summaries: list[dict],
    existing_arc: dict,
    actor_name: str,
) -> str:
    summaries_text = "\n\n".join(
        f"### 场景 {s.get('scenes_covered', '?')}\n{s['summary']}" for s in summaries
    )
    existing_narrative = existing_arc.get("narrative", "暂无")
    existing_structured = existing_arc.get("structured", {})

    return f"""你是一位戏剧故事弧线压缩助手。请将以下场景摘要融入演员「{actor_name}」的全局故事弧线摘要。

## 新增场景摘要
{summaries_text}

## 现有全局摘要
### 结构化信息
- 主题: {existing_structured.get('theme', '未确定')}
- 关键角色: {', '.join(existing_structured.get('key_characters', []))}
- 未决冲突: {'; '.join(existing_structured.get('unresolved', []))}
- 已解决冲突: {'; '.join(existing_structured.get('resolved', []))}

### 叙事概述
{existing_narrative}

## 压缩规则
1. 将新增摘要融入现有全局摘要，重写整个概述
2. 更新结构化字段：添加新角色、更新冲突状态（未决→已解决）
3. 叙事概述控制在 200-300 字
4. 保持故事连贯性，不要遗漏重要转折
5. 如有新主题浮现，更新主题字段

## 输出格式（严格 JSON）
{{
  "structured": {{
    "theme": "故事核心主题",
    "key_characters": ["角色1", "角色2"],
    "unresolved": ["未决冲突1", "未决冲突2"],
    "resolved": ["已解决冲突1"]
  }},
  "narrative": "完整的故事弧线概述..."
}}"""
```

## Architecture Patterns

### 推荐项目结构（变更后）

```
app/
├── memory_manager.py       # 新增：3 层记忆核心模块
├── state_manager.py        # 修改：添加新字段、迁移逻辑
├── tools.py                # 修改：actor_speak 使用新记忆、新增 mark_memory
├── actor_service.py        # 修改：load_drama 中提取新记忆格式
├── agent.py                # 修改：_storm_director tools 列表添加 mark_memory
├── actors/                 # 运行时生成（无变更）
├── dramas/                 # 持久化数据（无变更）
└── app_utils/              # 工具模块（无变更）
```

### 新数据结构

```python
# actor 对象完整结构（新格式）
{
    "role": str,
    "personality": str,
    "background": str,
    "knowledge_scope": str,
    "memory": [...],                    # D-13: 旧字段保留（只读）
    "working_memory": [                 # D-12: Tier 1
        {
            "entry": "面对情境: 导演描述了...",
            "importance": "normal",     # "normal" | "critical"
            "scene": 3,                 # 场景编号
        },
        # ... 最多 5 条
    ],
    "scene_summaries": [                # D-12: Tier 2
        {
            "summary": "第3-5场：角色经历了...",
            "scenes_covered": "3-5",
            "key_events": ["首次登场", "情感转折"],
        },
        # ... 最多 10 条
    ],
    "arc_summary": {                    # D-12: Tier 3
        "structured": {
            "theme": "权力与忠诚的抉择",
            "key_characters": ["朱棣", "道衍"],
            "unresolved": ["朱棣是否起兵"],
            "resolved": ["密信被发现"],
        },
        "narrative": "从燕王府的密信发现开始...",
    },
    "critical_memories": [              # D-07: 独立存储
        {
            "entry": "第一次遇见道衍",
            "reason": "首次登场",
            "scene": 1,
        },
    ],
    "_pending_compression": {           # 内部状态（不对外暴露）
        "working_to_scene": None,       # asyncio.Task 引用
        "scene_to_arc": None,
        "pending_entries": [],          # 等待压缩的条目
        "result": None,                 # 压缩完成的结果
    },
    "emotions": "neutral",
    "port": 9042,
    "created_at": "...",
}
```

### Pattern: build_actor_context 输出格式

```
【角色锚点】你是朱棣，燕王。沉稳冷静，说话简短有力

【当前情绪】焦虑

【关键记忆（永久保留）】
- [第1场] 第一次遇见道衍 [首次登场]
- [第5场] 发现削藩密信 [重大转折]

【你的故事弧线】
从燕王府的密信发现开始，朱棣在忠诚与自保之间挣扎...
主题：权力与忠诚的抉择 | 未决：是否起兵 | 已解决：密信被发现

【近期场景摘要】
- 第8-10场：与道衍密谋起兵，情绪从犹豫转为决绝
- 第11-13场：与朝廷使者周旋，内心紧张但表面镇定

【最近的经历（详细）】
  第14场: 面对情境: 朝廷传来圣旨...
  第14场: 我说：臣不敢抗旨，但...
  第15场: 面对情境: 道衍建议立即行动...
```

### Anti-Patterns to Avoid

- **在 actor_speak 中同步调用 LLM 压缩** — 会增加 5-15 秒延迟，违反 D-09 的"用户无感"要求
- **直接在异步任务中修改 tool_context.state** — 竞态条件风险，必须通过 pending 字段延迟合并
- **删除旧 memory 字段** — 违反 D-13，必须保留为只读
- **一次性压缩所有旧记忆** — 迁移时如果旧记忆有 100+ 条，不要一次性全部压缩，应逐步处理

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM 调用 | 自己封装 HTTP 请求 | `LiteLlm` (via ADK) | 已有模型配置、错误处理、重试逻辑 |
| JSON 解析压缩结果 | 手动正则提取 | `json.loads()` + prompt 中要求 JSON 输出 | 结构化输出比正则更可靠 |
| 状态持久化 | 自定义文件写入 | `state_manager._set_state()` | 已有自动保存机制 |
| 异步任务管理 | 自定义线程池 | `asyncio.create_task()` | Python 原生协程，与 ADK 异步模型兼容 |

## Common Pitfalls

### Pitfall 1: LLM 压缩质量问题 — 关键细节丢失

**What goes wrong:** LLM 压缩摘要时遗漏了关键情节细节（谁死了、谁背叛了），导致后续场景产生逻辑矛盾。
**Why it happens:** LLM 倾向于生成泛化摘要，忽略具体事实。
**How to avoid:**
1. 压缩 prompt 明确要求"保留所有关键事件"
2. `critical_memories` 机制保证关键记忆永不压缩（D-07）
3. 场景摘要中包含 `key_events` 字段，列出关键事件标题
4. 可选：压缩后进行简单 NER 验证——检查摘要是否包含原始条目中的实体名
**Warning signs:** 演员在后续场景中提及已被压缩掉的事实，或与已压缩事实矛盾。

### Pitfall 2: 异步压缩竞态条件

**What goes wrong:** 压缩任务在后台运行时，`build_actor_context()` 读取了尚未更新的 state，导致上下文不完整。
**Why it happens:** `asyncio.create_task()` 创建的任务与主流程并发执行。
**How to avoid:**
1. 压缩结果通过 `_pending_compression` 字段传递，不在异步任务中直接修改 state
2. `build_actor_context()` 在构建前检查 pending 结果并合并
3. 压缩进行中的 overflow 条目作为 fallback 保留在上下文中
4. `_set_state()` 保持原子性——所有变更在一次调用中完成
**Warning signs:** 记忆条目突然消失；场景摘要列表长度不正确。

### Pitfall 3: Token 预算溢出

**What goes wrong:** 即使使用 3 层记忆，如果 critical_memories 积累过多或 arc_summary 过长，总 token 仍可能超预算。
**Why it happens:** critical_memories 没有容量限制（D-07 只说"不占工作记忆槽位"），可能无限增长。
**How to avoid:**
1. `build_actor_context()` 中添加 token 估算逻辑，总输出控制在 ~4000 tokens
2. 如果 critical_memories 超过 15 条，仅保留最近 10 条 + 最重要 5 条
3. arc_summary.narrative 硬限制 300 字（约 200 tokens）
4. scene_summaries 每条限制 200 字
**Warning signs:** `build_actor_context()` 输出超过 5000 字符。

### Pitfall 4: 迁移边界情况

**What goes wrong:** 旧 state.json 中 memory 条目格式不一致（缺少 entry 键、entry 为空、非标准 timestamp）。
**Why it happens:** 早期版本的 bug 或手动编辑 state.json。
**How to avoid:**
1. `migrate_legacy_memory()` 中对每条旧记忆做格式验证
2. 跳过 `entry` 缺失或为空的条目
3. 对 `timestamp` 缺失的条目使用默认值
4. 迁移后保留旧 memory 字段（D-13），允许回滚
**Warning signs:** 迁移后 working_memory 条目数少于旧 memory 条目数（应该相等或略少，因为跳过了空条目）。

### Pitfall 5: 演员对自身对话无记忆

**What goes wrong:** 当前系统只在 `actor_speak()` 中记录 "面对情境"，不记录演员的对话回复。压缩后演员不记得自己说过什么。
**Why it happens:** `tools.py:205` 只调用 `update_actor_memory(actor_name, f"面对情境: {situation}")`。
**How to avoid:**
1. 在获取 `actor_dialogue` 后，额外添加一条 `add_working_memory(actor_name, f"我说：{actor_dialogue[:200]}")`
2. 这意味着每场每位演员会产生 2 条工作记忆（1 条情境 + 1 条对话），5 条限制约覆盖 2.5 场
3. 如果感觉 5 条太少，可考虑将情境和对话合并为 1 条
**Warning signs:** 演员在后续场景中重复自己之前的立场，或与自己的历史发言矛盾。

## Code Examples

### Example 1: build_actor_context 完整实现

```python
def build_actor_context(actor_name: str, tool_context: ToolContext) -> str:
    """Build the complete memory context string for an actor_speak() call."""
    state = tool_context.state.get("drama", {})
    actor_data = state.get("actors", {}).get(actor_name, {})

    # Check and merge pending compression results
    _merge_pending_compression(actor_name, actor_data, tool_context)

    parts = []

    # Tier 0: Character anchor (prevents backstory forgetting — PITFALLS.md #3)
    role = actor_data.get("role", "")
    personality = actor_data.get("personality", "")
    parts.append(f"【角色锚点】你是{actor_name}，{role}。{personality}")

    # Current emotion
    emotion = actor_data.get("emotions", "neutral")
    emotion_cn = {"neutral": "平静", "angry": "愤怒", ...}.get(emotion, emotion)
    parts.append(f"【当前情绪】{emotion_cn}")

    # Critical memories (always included, never compressed — D-07)
    critical = actor_data.get("critical_memories", [])
    if critical:
        lines = [f"- [第{m['scene']}场] {m['entry']} [{m['reason']}]" for m in critical]
        parts.append("【关键记忆（永久保留）】\n" + "\n".join(lines))

    # Tier 3: Arc summary (always included — it's small)
    arc = actor_data.get("arc_summary", {})
    if arc.get("narrative"):
        structured = arc.get("structured", {})
        theme = structured.get("theme", "")
        unresolved = "；".join(structured.get("unresolved", []))
        resolved = "；".join(structured.get("resolved", []))
        arc_text = arc["narrative"]
        header = f"主题：{theme}"
        if unresolved:
            header += f" | 未决：{unresolved}"
        if resolved:
            header += f" | 已解决：{resolved}"
        parts.append(f"【你的故事弧线】\n{header}\n{arc_text}")

    # Tier 2: Scene summaries (compressed but informative)
    summaries = actor_data.get("scene_summaries", [])
    if summaries:
        lines = [f"- 第{s['scenes_covered']}场：{s['summary']}" for s in summaries[-10:]]
        parts.append("【近期场景摘要】\n" + "\n".join(lines))

    # Tier 1: Working memory (full detail, last 5 entries)
    working = actor_data.get("working_memory", [])
    if working:
        lines = [f"  第{e.get('scene', '?')}场: {e['entry']}" for e in working[-5:]]
        parts.append("【最近的经历（详细）】\n" + "\n".join(lines))

    # Fallback: pending entries not yet compressed
    pending = actor_data.get("_pending_compression", {})
    if pending.get("pending_entries"):
        lines = [f"  第{e.get('scene', '?')}场（待压缩）: {e['entry']}" 
                 for e in pending["pending_entries"]]
        parts.append("【待压缩记忆】\n" + "\n".join(lines))

    return "\n\n".join(parts) if parts else "暂无记忆"
```

### Example 2: check_and_compress 实现

```python
def check_and_compress(actor_name: str, tool_context: ToolContext) -> dict:
    """Check memory tier sizes and trigger async compression if needed."""
    import asyncio

    state = tool_context.state.get("drama", {})
    actor_data = state.get("actors", {}).get(actor_name, {})
    compressed = []

    # Check working_memory overflow
    working = actor_data.get("working_memory", [])
    if len(working) > WORKING_MEMORY_LIMIT:
        overflow = working[:-WORKING_MEMORY_LIMIT]
        actor_data["working_memory"] = working[-WORKING_MEMORY_LIMIT:]

        # Store overflow in pending for async compression
        pending = actor_data.setdefault("_pending_compression", {})
        pending["pending_entries"] = pending.get("pending_entries", []) + overflow

        # Launch async compression task
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.create_task(
                    compress_working_to_scene(actor_name, overflow, tool_context)
                )
                pending["working_to_scene"] = task
            else:
                # Fallback: synchronous compression (e.g., in tests)
                import asyncio
                result = asyncio.run(compress_working_to_scene(actor_name, overflow, tool_context))
                # Immediately add to scene_summaries
                actor_data["scene_summaries"].append(result)
                pending["pending_entries"] = [
                    e for e in pending.get("pending_entries", [])
                    if e not in overflow
                ]
        except RuntimeError:
            # No event loop — skip async, will be compressed next time
            pass

        compressed.append(f"working→scene: {len(overflow)} 条")

    # Check scene_summaries overflow
    summaries = actor_data.get("scene_summaries", [])
    if len(summaries) > SCENE_SUMMARY_LIMIT:
        overflow = summaries[:-SCENE_SUMMARY_LIMIT]
        actor_data["scene_summaries"] = summaries[-SCENE_SUMMARY_LIMIT:]

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.create_task(
                    compress_scene_to_arc(actor_name, overflow, tool_context)
                )
                actor_data.setdefault("_pending_compression", {})["scene_to_arc"] = task
            else:
                result = asyncio.run(compress_scene_to_arc(actor_name, overflow, tool_context))
                actor_data["arc_summary"] = result
        except RuntimeError:
            pass

        compressed.append(f"scene→arc: {len(overflow)} 条")

    # Save state if anything changed
    if compressed:
        state["actors"][actor_name] = actor_data
        _set_state(state, tool_context)

    return {
        "status": "success",
        "compressed": compressed,
        "message": f"压缩检查完成: {', '.join(compressed)}" if compressed else "无需压缩",
    }
```

### Example 3: _merge_pending_compression 实现

```python
def _merge_pending_compression(actor_name: str, actor_data: dict, tool_context) -> None:
    """Merge any completed compression results into the actor's state.

    Called at the start of build_actor_context() to ensure latest data.
    """
    pending = actor_data.get("_pending_compression", {})
    if not pending:
        return

    merged = False

    # Check working→scene result
    task_w2s = pending.get("working_to_scene")
    if task_w2s and task_w2s.done():
        try:
            result = task_w2s.result()
            actor_data["scene_summaries"].append(result)
            # Remove compressed entries from pending
            pending["pending_entries"] = []
            pending["working_to_scene"] = None
            merged = True
        except Exception:
            # Compression failed — keep entries in pending as fallback
            pending["working_to_scene"] = None

    # Check scene→arc result
    task_s2a = pending.get("scene_to_arc")
    if task_s2a and task_s2a.done():
        try:
            result = task_s2a.result()
            actor_data["arc_summary"] = result
            pending["scene_to_arc"] = None
            merged = True
        except Exception:
            pending["scene_to_arc"] = None

    if merged:
        from .state_manager import _set_state, _get_state
        state = _get_state(tool_context)
        state["actors"][actor_name] = actor_data
        _set_state(state, tool_context)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 扁平 memory 列表 | 3 层 tiered memory | Phase 1 (this) | 支持 50+ 场戏剧 |
| 同步全量记忆拼接 | 异步压缩 + 分层上下文构建 | Phase 1 (this) | 单次 actor 调用 token 控制在 ~4000 |
| 无重要性区分 | critical_memories + importance 标记 | Phase 1 (this) | 关键事件永不丢失 |
| update_actor_memory 直接 append | add_working_memory + check_and_compress | Phase 1 (this) | 自动容量管理 |

**Deprecated/outdated:**
- `update_actor_memory()`: 保留但内部委托给 `add_working_memory()`
- `actor_data["memory"]`: 保留为只读（D-13），新代码不读取

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `asyncio.create_task()` 在 ADK 工具调用上下文中可用 | LLM Compression Design | 如果 ADK 工具函数不在 async 上下文中运行，需要改用 threading 或其他机制 |
| A2 | `LiteLlm` 可直接用于独立的 LLM 调用（不在 Agent 上下文中） | LLM Compression Design | 如果 LiteLlm 需要 Agent 上下文，需要使用 httpx 直接调用 API |
| A3 | Python 的 `json.loads()` 能可靠解析 LLM 输出的 JSON | LLM Compression Design | LLM 可能输出格式不完美的 JSON，需要添加容错解析 |
| A4 | 5 条工作记忆（含情境+对话各 1 条）约覆盖 2.5 场足够 | Implementation Approach | 如果 1 场产生 3+ 条记忆（多人对话），5 条可能只覆盖 1-2 场，可能需要调整到 7-8 条 |
| A5 | 每场每位演员平均产生 2 条工作记忆 | Implementation Approach | 如果对话特别长或有多轮交互，可能产生更多条目 |

## Open Questions

1. **每场产生的工作记忆条数**
   - What we know: 当前只记录 "面对情境"，新设计额外记录对话回复，预计 2 条/场/演员
   - What's unclear: 如果 1 场中同一演员被多次调用 actor_speak，可能产生 4+ 条
   - Recommendation: 考虑将同一场景的多条记忆合并为 1 条（按场景编号聚合），或增大工作记忆限制到 7 条

2. **LiteLlm 独立调用的可行性**
   - What we know: LiteLlm 在 ADK Agent 内部使用正常
   - What's unclear: 在非 Agent 上下文（memory_manager.py 的压缩函数中）能否直接实例化并调用
   - Recommendation: 实现时先测试 `LiteLlm(model=...).generate_content_async()` 是否可用；如果不行，回退到 httpx 直接调用 OpenAI 兼容 API

3. **_pending_compression 字段是否持久化到 state.json**
   - What we know: `_set_state()` 会序列化整个 state dict
   - What's unclear: asyncio.Task 对象不可 JSON 序列化
   - Recommendation: `_pending_compression` 中的 task 引用不应持久化；持久化时只保存 `pending_entries`（原始数据），重启后重新触发压缩

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | 全部 | ✓ | 3.10-3.13 | — |
| google-adk | LiteLlm 压缩调用 | ✓ | >=1.15.0 | — |
| asyncio | 异步压缩 | ✓ | stdlib | 同步回退 |
| pytest | 测试 | ✓ | >=8.3.4 | — |

**Missing dependencies with no fallback:**
- None

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.3.4 |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `pytest tests/unit/test_memory_manager.py -x -q` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEMORY-01 | 3 层记忆数据结构正确初始化 | unit | `pytest tests/unit/test_memory_manager.py::test_register_actor_has_new_fields -x` | ❌ Wave 0 |
| MEMORY-01 | working_memory/scene_summaries/arc_summary/critical_memories 读写 | unit | `pytest tests/unit/test_memory_manager.py::test_add_working_memory -x` | ❌ Wave 0 |
| MEMORY-01 | build_actor_context 输出格式正确 | unit | `pytest tests/unit/test_memory_manager.py::test_build_actor_context -x` | ❌ Wave 0 |
| MEMORY-02 | 工作记忆超 5 条触发压缩 | unit | `pytest tests/unit/test_memory_manager.py::test_compress_working_to_scene -x` | ❌ Wave 0 |
| MEMORY-02 | 场景摘要超 10 条触发压缩 | unit | `pytest tests/unit/test_memory_manager.py::test_compress_scene_to_arc -x` | ❌ Wave 0 |
| MEMORY-02 | 异步压缩结果正确合并 | unit | `pytest tests/unit/test_memory_manager.py::test_pending_compression_merge -x` | ❌ Wave 0 |
| MEMORY-03 | 关键记忆判定逻辑 | unit | `pytest tests/unit/test_memory_manager.py::test_critical_memory_detection -x` | ❌ Wave 0 |
| MEMORY-03 | 关键记忆不被压缩 | unit | `pytest tests/unit/test_memory_manager.py::test_critical_memories_preserved -x` | ❌ Wave 0 |
| MEMORY-03 | /mark 命令标记关键记忆 | unit | `pytest tests/unit/test_memory_manager.py::test_mark_critical -x` | ❌ Wave 0 |
| MIGRATION | 旧格式自动迁移 | unit | `pytest tests/unit/test_memory_manager.py::test_migrate_legacy_memory -x` | ❌ Wave 0 |
| MIGRATION | 迁移后旧字段保留 | unit | `pytest tests/unit/test_memory_manager.py::test_legacy_field_preserved -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/test_memory_manager.py -x -q`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_memory_manager.py` — covers MEMORY-01/02/03 + migration
- [ ] `tests/unit/conftest.py` — shared fixtures (mock tool_context, sample actor state)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | 单用户 CLI 系统，无认证需求 |
| V3 Session Management | no | 无多用户会话 |
| V4 Access Control | no | 单用户，无权限分离 |
| V5 Input Validation | yes | memory entry 文本需要长度限制、注入防护 |
| V6 Cryptography | no | 无加密需求 |

### Known Threat Patterns for Python/LLM Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via memory entry | Tampering | 截断超长条目、不执行 entry 中的指令格式 |
| LLM output injection into state | Tampering | 验证 LLM JSON 输出格式、sanitize 特殊字符 |
| state.json 篡改 | Tampering | 文件系统权限；本阶段不额外处理 |

## Sources

### Primary (HIGH confidence)
- 代码库直接分析: `app/state_manager.py`, `app/tools.py`, `app/actor_service.py`, `app/agent.py`
- `.planning/research/ARCHITECTURE.md` — memory_manager.py 模块设计
- `.planning/research/STACK.md` — 零新依赖方案确认
- `.planning/research/PITFALLS.md` — 上下文耗尽、摘要失真等陷阱
- `.planning/codebase/CONVENTIONS.md` — 编码规范

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — MEMORY-01/02/03 需求定义
- CONTEXT.md 用户决策 — D-01 至 D-13 锁定决策

### Tertiary (LOW confidence)
- A1-A5 假设项 — 需要在实现阶段验证

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 零新依赖，全部基于现有代码库
- Architecture: HIGH — 数据结构、函数签名、数据流均从实际代码分析得出
- Pitfalls: HIGH — 从 PITFALLS.md 和代码分析交叉验证
- LLM compression design: MEDIUM — asyncio.create_task 方案需在 ADK 上下文中验证
- Migration: HIGH — 算法简单，边界情况已列举

**Research date:** 2026-04-11
**Valid until:** 2026-05-11（稳定，无外部依赖变化风险）
