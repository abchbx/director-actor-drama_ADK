# Phase 12: Integration & Polish - Research

**Researched:** 2026-04-14
**Domain:** 端到端集成测试 / 性能优化 / Bug 修复 / CLI 优化 / 崩溃恢复
**Confidence:** HIGH

## Summary

Phase 12 是整个项目的集成收尾阶段，需将 Phase 1-11 构建的 11 个子模块组装成一个可交付的系统。核心挑战不在于新功能开发，而在于：确保跨模块交互的正确性（E2E 测试）、消除全局状态竞态（`_conversation_log` 迁移）、优化高频 I/O 路径（debounce + 归档 + 共享 AsyncClient）、提升用户体验（CLI spinner + 场景摘要 + 错误提示）、增强系统韧性（演员崩溃恢复）。

代码库已具备成熟模式可直接复用：`_set_state()` 是所有状态变更的唯一入口、`mock_tool_context` fixture 提供标准测试状态、`load_progress()` 的 `setdefault()` 兼容模式已有 11 个 phase 的先例。E2E 测试需采用真实 LLM 调用 + 里程碑断言模式，以平衡验证深度和测试脆弱性。

**Primary recommendation:** 严格遵循 CONTEXT.md 锁定的 19 项决策（D-01 至 D-19），以 `_conversation_log` 迁移和 debounce 实现为突破口（两者耦合在 `state_manager.py`），E2E 测试用 `@pytest.mark.e2e` 隔离避免 CI 成本，CLI spinner 使用已安装的 `rich` 库而非手写。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 端到端测试使用真实 LLM 调用，非 Mock
- **D-02:** 30+ 场测试采用里程碑断言——仅在关键节点验证状态，不逐场写断言
- **D-03:** 集成测试覆盖关键路径——最重要的跨模块交互，不追求全路径覆盖
- **D-04:** E2E 测试文件为 `tests/integration/test_e2e_full_flow.py`，标记为 `@pytest.mark.e2e`，默认不运行
- **D-05:** 渐进式修复策略——优先修 `actor_speak()` 算符优先级 bug + `_conversation_log` 全局状态迁移
- **D-06:** `_conversation_log` 迁移方向：从模块级全局变量移入 `ToolContext.state["drama"]["conversation_log"]`
- **D-07:** `_current_drama_folder` 暂不迁移，加 `# TODO` 注释标记
- **D-08:** `actor_speak()` 算符优先级 bug——需先精确定位确认后修复
- **D-09:** Debounced State Saving——5 秒间隔 debounce，退出时强制 flush
- **D-10:** 场景归档——20 场阈值触发归档，归档场景保留索引元数据，完整数据按需加载
- **D-11:** 共享 AsyncClient——Director 端 `tools.py` 创建模块级共享 `_shared_httpx_client`
- **D-12:** 共享 AsyncClient 生命周期——`start_drama()` 时创建，`end_drama()` / `atexit` 时关闭
- **D-13:** CLI 体验提升三项全上：Spinner + 每场摘要展示 + 统一中文错误提示
- **D-14:** Spinner 使用 `rich.spinner` 或简单 `sys.stdout.write` 循环，不引入重量级依赖
- **D-15:** 场景摘要格式：`── 第5场：密室对峙 ── 参演：朱棣、苏念`
- **D-16:** 演员健康检查采用被动检测——`actor_speak()` 调用失败时检测崩溃
- **D-17:** 崩溃恢复采用自动重启——检测到崩溃时调用 `_restart_actor()`
- **D-18:** 连续崩溃 3 次后放弃自动重启
- **D-19:** 崩溃恢复日志记录到 `state["actors"][name]["restart_log"]`

### Claude's Discretion
- E2E 测试中 LLM 调用的 timeout 设置
- E2E 测试的 drama theme 选择（需稳定可复现）
- `_conversation_log` 迁移的具体实现细节（read/write 路径调整）
- `archive_old_scenes()` 的归档文件格式
- Spinner 的具体实现库选择（rich vs 手写）
- 场景摘要的精确格式
- `_restart_actor()` 的具体错误恢复流程
- 共享 AsyncClient 的连接池大小和 timeout 配置
- Debounce 实现是用 asyncio.Timer 还是 threading.Timer
- `actor_speak()` 算符优先级 bug 的精确修复方式（需先定位）

### Deferred Ideas (OUT OF SCOPE)
- `_current_drama_folder` 全局变量迁移到 `ToolContext.state`
- 主动心跳健康检查
- 全路径集成测试覆盖
- Mock LLM E2E 测试套件
- 自适应 debounce 间隔
- 场景归档压缩
- 并行 actor_speak
- 会话恢复
- Web UI / 多用户支持
</user_constraints>

<phase_requirements>
## Phase Requirements

Phase 12 没有独立的 REQ-ID，它是集成阶段，确保所有先前需求（MEMORY-01 至 COHERENCE-05）在端到端流程中完整兑现。

| ID | Description | Research Support |
|----|-------------|------------------|
| ALL-PRIOR | 确保所有 Phase 1-11 需求在端到端流程中工作 | E2E 里程碑断言在关键节点验证每个子系统的状态产出 |
| INTEG-01 | 端到端测试全流程无错误 | 真实 LLM + 里程碑断言模式（D-01/D-02/D-03） |
| INTEG-02 | 已知 bug 修复 | `actor_speak` 错误检测逻辑审查 + `_conversation_log` 迁移方案 |
| INTEG-03 | 性能优化三项 | debounce(5s) + 归档(20场) + 共享AsyncClient 的具体实现模式 |
| INTEG-04 | CLI 命令完整可用 | Spinner(rich) + 场景摘要 + 中文错误提示 |
| INTEG-05 | 演员崩溃恢复 | 被动检测 + 自动重启(3次上限) + restart_log |
| INTEG-06 | 测试覆盖 | 每个新模块单元测试 + 核心流程集成测试 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 8.4.2 | Test framework | 已在项目中使用，`pyproject.toml` 配置完毕 [VERIFIED: uv run] |
| pytest-asyncio | ~0.23.x | Async test support | 项目依赖，用于 `actor_speak` 等 async 函数测试 [VERIFIED: pyproject.toml] |
| httpx | 0.28.1 | Async HTTP client | A2A SDK 依赖，当前每次调用创建新实例 [VERIFIED: uv run] |
| rich | 14.3.2 | CLI spinner + formatting | 已安装但未在 CLI 中使用，无额外依赖 [VERIFIED: uv run] |
| a2a-sdk | 0.3.26 | A2A protocol client | ClientFactory 接受共享 httpx_client [VERIFIED: uv run + source] |
| threading.Timer | stdlib | Debounce timer | Python 标准库，无依赖，适合 `_set_state()` 同步写盘场景 [CITED: docs.python.org] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | stdlib | Mock ToolContext | 单元测试中替代 `ToolContext` |
| atexit | stdlib | Cleanup registration | debounce flush + AsyncClient 关闭 + actor services 停止 |
| json | stdlib | State serialization | 归档场景文件格式 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rich.spinner | 手写 sys.stdout 循环 | rich 更优雅但引入显示依赖；手写更轻量但需处理光标/换行 |
| threading.Timer | asyncio.Timer | asyncio 需要事件循环；threading.Timer 在 `_set_state()` 同步上下文中更简单 |
| 共享 AsyncClient (Director) | 每次新建 AsyncClient | 共享节省 TCP 连接开销；新建代码更简单但每次 `actor_speak` 有冷启动延迟 |

**Installation:**
无新依赖需要安装——所有库已存在于项目依赖中。

**Version verification:**
```
pytest==8.4.2 (2026-04-14 verified)
httpx==0.28.1 (2026-04-14 verified)
rich==14.3.2 (2026-04-14 verified)
a2a-sdk==0.3.26 (2026-04-14 verified)
Python==3.11.1 (2026-04-14 verified)
```

## Architecture Patterns

### Recommended Project Structure (新增/修改文件)
```
app/
├── state_manager.py     # 修改：debounce + conversation_log 迁移 + 场景归档
├── tools.py             # 修改：actor_speak bug fix + 崩溃恢复 + 共享 AsyncClient + 错误提示
├── actor_service.py     # 修改：崩溃重启逻辑
├── context_builder.py   # 修改：归档场景适配
├── agent.py             # 微调：导演 prompt 错误提示引导
cli.py                   # 修改：spinner + 场景摘要
tests/
├── unit/
│   ├── test_state_manager.py    # 新增：debounce + 归档 + conversation_log 单元测试
│   └── test_tools_phase12.py    # 新增：崩溃恢复 + AsyncClient + 错误提示
└── integration/
    └── test_e2e_full_flow.py    # 新增：E2E 全流程测试
```

### Pattern 1: Debounced State Saving
**What:** 将 `_set_state()` 从每次变更立即写盘改为 5 秒 debounce 批量写盘
**When to use:** 所有经过 `_set_state()` 的状态变更
**Why threading.Timer over asyncio:** `_set_state()` 是同步函数（line 1118），threading.Timer 无需事件循环，在同步上下文中更简单可靠 [CITED: docs.python.org/library/threading.html#timer-objects]

**Example:**
```python
# Source: CONTEXT.md D-09 + state_manager.py current implementation
import threading

_save_dirty: bool = False
_save_timer: threading.Timer | None = None
DEBOUNCE_SECONDS = 5

def _set_state(state: dict, tool_context):
    """Set drama state in tool context with debounced disk persistence."""
    global _save_dirty, _save_timer
    if tool_context is not None:
        tool_context.state["drama"] = state
        _save_dirty = True
        # Cancel existing timer if any, schedule new one
        if _save_timer is not None and _save_timer.is_alive():
            _save_timer.cancel()
        _save_timer = threading.Timer(DEBOUNCE_SECONDS, _flush_state)
        _save_timer.daemon = True  # Don't block process exit
        _save_timer.start()

def _flush_state():
    """Force-write dirty state to disk."""
    global _save_dirty, _save_timer
    if _save_dirty:
        # Need theme from somewhere — use module-level or thread-safe access
        _save_state_to_file(theme, state)
        _save_dirty = False
    _save_timer = None

def flush_state_sync(tool_context=None):
    """Synchronous flush for atexit / save_drama calls."""
    global _save_dirty, _save_timer
    if _save_timer is not None:
        _save_timer.cancel()
        _save_timer = None
    if _save_dirty and tool_context is not None:
        state = tool_context.state.get("drama", {})
        theme = state.get("theme", "")
        if theme:
            _save_state_to_file(theme, state)
            _save_dirty = False
```

**关键设计决策：**
- `_flush_state()` 需要访问当前 state 和 theme。由于 timer 在独立线程运行，需通过闭包或模块级变量传递。推荐闭包方式：`threading.Timer(DEBOUNCE_SECONDS, lambda: _flush_with_context(tool_context))`
- Timer 设为 `daemon=True`，避免进程退出时 timer 线程阻塞
- `save_progress()` 和 `atexit` 必须调用 `flush_state_sync()` 强制写盘

### Pattern 2: Shared AsyncClient Singleton
**What:** Director 端共享一个 `httpx.AsyncClient` 实例，所有 `actor_speak()` 调用复用
**When to use:** 每次 `_call_a2a_sdk()` 需要 httpx_client 时

**Example:**
```python
# Source: tools.py line 397 + a2a-sdk ClientConfig API
_shared_httpx_client: httpx.AsyncClient | None = None

def get_shared_client() -> httpx.AsyncClient:
    """Get or lazily create the shared httpx.AsyncClient."""
    global _shared_httpx_client
    if _shared_httpx_client is None or _shared_httpx_client.is_closed:
        _shared_httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=120.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _shared_httpx_client

async def close_shared_client():
    """Close the shared httpx.AsyncClient."""
    global _shared_httpx_client
    if _shared_httpx_client is not None and not _shared_httpx_client.is_closed:
        await _shared_httpx_client.aclose()
        _shared_httpx_client = None
```

**在 `_call_a2a_sdk()` 中的修改：**
```python
# Before: 创建新的 httpx_client，用后关闭
httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout=120))
# ... use ...
await httpx_client.aclose()

# After: 使用共享 client，不关闭
httpx_client = get_shared_client()
# ... use ...
# 不调用 aclose() — 生命周期由 start_drama/end_drama 管理
```

**生命周期绑定：**
- `start_drama()`: 调用 `get_shared_client()` 懒初始化
- `end_drama()`: 调用 `await close_shared_client()`
- `atexit`: 注册同步清理（需用 `asyncio.run()` 或设置 client 为 None）

### Pattern 3: Conversation Log Migration
**What:** 将 `_conversation_log` 从模块级全局变量移入 `ToolContext.state["drama"]["conversation_log"]`
**When to use:** 所有对话记录的读写操作

**迁移步骤（D-06 已锁定）：**
```python
# Before (state_manager.py line 18):
_conversation_log: list[dict] = []

# After:
# init_drama_state() 新增:
state["conversation_log"] = []

# add_conversation() 修改:
state = _get_state(tool_context)
state.setdefault("conversation_log", []).append(entry)
# 不再调用 _save_conversations() — 统一走 _set_state() debounce

# get_conversation_log() 修改:
state = _get_state(tool_context)
log = state.get("conversation_log", [])
# 不再从磁盘加载 conversation_log.json

# load_progress() 兼容旧存档:
# 检查旧 conversations/conversation_log.json，合并到 state["conversation_log"]
conv_file = os.path.join(_get_conversations_dir(theme), "conversation_log.json")
if os.path.exists(conv_file):
    with open(conv_file, "r", encoding="utf-8") as f:
        old_log = json.load(f)
    state.setdefault("conversation_log", old_log)
```

### Pattern 4: Actor Crash Recovery (Passive Detection)
**What:** `actor_speak()` 捕获连接异常时检测崩溃，自动重启
**When to use:** A2A 调用失败时

**Example:**
```python
# Source: CONTEXT.md D-16/D-17/D-18
async def actor_speak(actor_name, situation, tool_context):
    # ... existing code ...
    try:
        actor_dialogue = await _call_a2a_sdk(card_file, prompt, actor_name, port)
    except Exception as e:
        # Passive crash detection
        err_type = type(e).__name__
        msg = str(e).lower()
        if "connect" in err_type or "refused" in msg or "connection" in msg:
            # Attempt auto-restart
            restart_result = await _restart_actor(actor_name, tool_context)
            if restart_result["status"] == "success":
                # Retry once after restart
                actor_dialogue = await _call_a2a_sdk(card_file, prompt, actor_name, port)
            else:
                actor_dialogue = f"[{actor_name}重启失败: {restart_result['message']}]"
        # ... rest of error handling ...
```

### Pattern 5: E2E Milestone Assertions
**What:** 在 30+ 场戏剧的关键节点验证状态，不逐场断言
**When to use:** E2E 测试中，每 N 场后检查一次

**Example:**
```python
# Source: CONTEXT.md D-02
@pytest.mark.e2e
async def test_full_drama_flow():
    """E2E test: /start → 30+ scenes → /save → /load → continue → /end"""
    # Phase 1: Setup
    result = start_drama("简单的宫廷戏剧", tool_context)
    assert result["status"] == "success"
    # Create actors...
    
    # Phase 2: Run scenes (3 scenes)
    for i in range(3):
        next_scene(tool_context)
        # ... director creates scene with actor_speak ...
    
    # Milestone 1: After scene 3
    state = tool_context.state["drama"]
    assert len(state["actors"]) >= 2, "At least 2 actors should exist"
    assert any(wm for actor in state["actors"].values() 
               for wm in actor.get("working_memory", [])), "Working memory should have data"
    
    # ... more scenes + milestones ...
```

### Anti-Patterns to Avoid
- **在 `_flush_state()` 中直接访问 `tool_context`**：timer 在独立线程运行，`tool_context` 可能已被清理。应通过闭包捕获必要参数
- **E2E 测试逐场断言具体 LLM 输出内容**：LLM 输出不确定，应断言状态结构而非文本内容
- **`_conversation_log` 迁移后保留独立 `_save_conversations()`**：迁移后对话记录统一走 `_set_state()` debounce，独立的 `_save_conversations()` 应废弃
- **在 `actor_speak()` 的 try 块中同时处理业务错误和崩溃恢复**：两类错误应分离——崩溃检测在 except 块，业务逻辑在 try 块内

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI spinner | 手写 `while True: print("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")` | `rich.live.Live` + `rich.spinner.Spinner` | rich 已安装（14.3.2），手写需处理光标、终端兼容、信号中断 |
| Debounce timer | `asyncio.create_task(asyncio.sleep(5))` | `threading.Timer` | `_set_state()` 是同步函数，asyncio 需要运行中的事件循环，threading 无此限制 |
| HTTP 连接复用 | 每次创建新 `httpx.AsyncClient` | 共享单例 `get_shared_client()` | TCP 三次握手开销，keep-alive 连接池复用减少延迟 |
| 对话记录持久化 | 独立 `_save_conversations()` + `_conversation_log` 全局变量 | `state["conversation_log"]` + `_set_state()` debounce | 统一持久化路径，消除全局状态竞态 |

**Key insight:** Phase 12 的核心价值是"收敛而非扩展"——不引入新模式，而是将 Phase 1-11 的分散模式统一到 `ToolContext.state` + `_set_state()` 这一标准路径上。

## Runtime State Inventory

> 此阶段不是 rename/refactor/migration 为主的阶段，但 `_conversation_log` 迁移涉及运行时状态变更。

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `conversations/conversation_log.json` — 旧存档中的独立对话文件 | `load_progress()` 兼容：读取并合并到 `state["conversation_log"]` |
| Live service config | `_conversation_log` 模块级变量 — 跨 drama 污染源 | 代码迁移：移入 `state["drama"]["conversation_log"]` |
| OS-registered state | `atexit.register(lambda: stop_all_actor_services())` — cli.py line 29 | 新增：`atexit` 注册 `flush_state_sync()` + `close_shared_client()` |
| Secrets/env vars | 无变更 | — |
| Build artifacts | 无变更 | — |

**Nothing found in category:**
- Secrets/env vars: 无需变更 — 环境变量结构不变
- Build artifacts: 无需变更 — 不涉及编译/打包

## Common Pitfalls

### Pitfall 1: Debounce Timer 在 `_flush_state()` 中访问过期引用
**What goes wrong:** `threading.Timer` 的回调在独立线程执行，如果通过闭包捕获 `tool_context`，但 drama 已切换或进程即将退出，`tool_context` 中的 state 可能已失效
**Why it happens:** `_set_state(tool_context)` 设置 timer，但 timer 触发时 `tool_context` 可能指向旧 drama
**How to avoid:** `_flush_state()` 应从模块级变量读取最新 state（如 `_latest_state` 和 `_latest_theme`），而非依赖 timer 闭包中的 `tool_context`
**Warning signs:** 切换 drama 后保存了错误的 state；进程退出时数据丢失

### Pitfall 2: 共享 AsyncClient 在 Drama 切换时泄漏
**What goes wrong:** 用户执行 `/load` 切换 drama，共享的 `_shared_httpx_client` 仍然连接旧 actor 端口；新 drama 的 actor 在不同端口，导致所有 `actor_speak()` 连接失败
**Why it happens:** AsyncClient 的连接池缓存了旧端口的 keep-alive 连接
**How to avoid:** `load_drama()` 中调用 `await close_shared_client()` 关闭旧连接，下次 `actor_speak()` 自动重新创建
**Warning signs:** `/load` 后所有 actor_speak 返回连接错误

### Pitfall 3: `_conversation_log` 迁移破坏旧存档兼容性
**What goes wrong:** 迁移后 `get_conversation_log()` 从 `state["conversation_log"]` 读取，但旧存档没有这个字段，返回空列表，导致对话记录丢失
**Why it happens:** 旧存档的对话存储在 `conversations/conversation_log.json` 独立文件中，不在 `state.json` 中
**How to avoid:** `load_progress()` 中检测旧存档：如果 `state` 缺少 `conversation_log` 字段但存在 `conversations/conversation_log.json` 文件，读取文件内容填充到 `state["conversation_log"]`
**Warning signs:** 加载旧存档后 `export_conversations()` 返回空

### Pitfall 4: E2E 测试在 CI 中因 LLM API 限制而 flaky
**What goes wrong:** 30+ 场真实 LLM 测试需要 15-30 分钟，可能因 API rate limit、网络超时、模型负载高而间歇性失败
**Why it happens:** 真实 LLM 调用本质上是不可控的外部依赖
**How to avoid:** (1) `@pytest.mark.e2e` 默认不运行（D-04），只在手动 `pytest -m e2e` 时执行；(2) 设置合理的 timeout（单次 LLM 调用 120s，全场测试 60min）；(3) 选择简单的 drama theme 降低 LLM 生成复杂度
**Warning signs:** CI 中 E2E 测试超时或返回 429 rate limit

### Pitfall 5: 场景归档后 `context_builder` 访问归档场景失败
**What goes wrong:** 归档后 `state["scenes"]` 中只保留索引元数据（`archived: True`），`context_builder.py` 中的 `_build_recent_scenes_section()` 和 `_extract_scene_transition()` 尝试访问 `content`/`description` 字段但找不到
**Why it happens:** 归档场景的完整数据移到了独立文件，`state["scenes"]` 中只有 `scene_number`/`title`/`time_label`
**How to avoid:** (1) 只归档前 N-20 场，保留最近 20 场完整数据（确保 `_build_recent_scenes_section()` 展示的最近 10 场始终有完整数据）；(2) `_extract_scene_transition()` 只取 `scenes[-1]`，此场景始终在保留区内
**Warning signs:** 归档后 context_builder 构建的上下文中场景描述为空

### Pitfall 6: `_restart_actor()` 在 `create_actor_service()` 失败时无限重试
**What goes wrong:** 如果 actor 端口被占用或 API key 失效，自动重启每次都失败，消耗时间和 API 额度
**Why it happens:** 崩溃恢复逻辑未考虑非瞬态错误（如配置错误、端口冲突）
**How to avoid:** D-18 的 3 次上限限制；每次重启前增加短暂延迟（1s/2s/4s exponential backoff）；区分瞬态错误（连接超时 → 重试）和非瞬态错误（配置错误 → 直接放弃）
**Warning signs:** `restart_log` 中连续 3 次相同错误

## Code Examples

Verified patterns from official sources and codebase:

### Debounce Implementation with threading.Timer
```python
# Source: Python stdlib threading.Timer + CONTEXT.md D-09
import threading
from typing import Optional

# Module-level debounce state
_save_dirty: bool = False
_save_timer: Optional[threading.Timer] = None
DEBOUNCE_SECONDS = 5
_latest_theme: str = ""       # Track current theme for timer callback
_latest_state_ref: dict = {}  # Track current state for timer callback

def _set_state(state: dict, tool_context):
    """Set drama state with debounced disk persistence (D-09)."""
    global _save_dirty, _save_timer, _latest_theme, _latest_state_ref
    if tool_context is not None:
        tool_context.state["drama"] = state
        _latest_theme = state.get("theme", "")
        _latest_state_ref = state
        _save_dirty = True
        # Cancel pending timer
        if _save_timer is not None and _save_timer.is_alive():
            _save_timer.cancel()
        _save_timer = threading.Timer(DEBOUNCE_SECONDS, _flush_state)
        _save_timer.daemon = True
        _save_timer.start()

def _flush_state():
    """Write dirty state to disk (called from timer thread)."""
    global _save_dirty, _save_timer
    if _save_dirty and _latest_theme:
        _save_state_to_file(_latest_theme, _latest_state_ref)
        _save_dirty = False
    _save_timer = None

def flush_state_sync():
    """Force flush for save_progress/atexit."""
    global _save_dirty, _save_timer
    if _save_timer is not None:
        _save_timer.cancel()
        _save_timer = None
    if _save_dirty and _latest_theme:
        _save_state_to_file(_latest_theme, _latest_state_ref)
        _save_dirty = False
```

### Shared AsyncClient with Lifecycle Management
```python
# Source: httpx 0.28.1 docs + a2a-sdk ClientConfig API
import httpx
from typing import Optional

_shared_httpx_client: Optional[httpx.AsyncClient] = None

def get_shared_client() -> httpx.AsyncClient:
    """Get or lazily create the shared httpx.AsyncClient (D-11/D-12)."""
    global _shared_httpx_client
    if _shared_httpx_client is None or _shared_httpx_client.is_closed:
        _shared_httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=120.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _shared_httpx_client

async def close_shared_client():
    """Close the shared httpx.AsyncClient (D-12)."""
    global _shared_httpx_client
    if _shared_httpx_client is not None and not _shared_httpx_client.is_closed:
        await _shared_httpx_client.aclose()
        _shared_httpx_client = None
```

### Rich Spinner in CLI
```python
# Source: rich 14.3.2 — Spinner + Live context manager
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
import asyncio

async def _send_message_with_spinner(runner, message):
    """Send message with spinner while waiting for LLM."""
    console = Console()
    spinner = Spinner("dots", text=" 🤔 思考中...")
    response_parts = []
    
    async def _process_response():
        content = types.Content(role="user", parts=[types.Part.from_text(text=message)])
        async for event in runner.run_async(...):
            # ... existing event processing ...
            pass
    
    # Run spinner and response processing concurrently
    with Live(spinner, console=console, transient=True):
        await _process_response()
    
    return "\n".join(response_parts)
```

### Scene Archival
```python
# Source: CONTEXT.md D-10 + state_manager.py existing patterns
SCENE_ARCHIVE_THRESHOLD = 20

def archive_old_scenes(state: dict) -> dict:
    """Archive scenes beyond threshold to reduce state.json size (D-10)."""
    scenes = state.get("scenes", [])
    if len(scenes) <= SCENE_ARCHIVE_THRESHOLD:
        return state
    
    to_archive = scenes[:-SCENE_ARCHIVE_THRESHOLD]
    keep = scenes[-SCENE_ARCHIVE_THRESHOLD:]
    
    theme = state.get("theme", "")
    drama_folder = _get_drama_folder(theme) if theme else ""
    
    for scene in to_archive:
        scene_num = scene.get("scene_number", 0)
        if drama_folder:
            scenes_dir = os.path.join(drama_folder, "scenes")
            os.makedirs(scenes_dir, exist_ok=True)
            archive_path = os.path.join(scenes_dir, f"scene_{scene_num:04d}.json")
            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump(scene, f, ensure_ascii=False, indent=2)
    
    # Replace archived scenes with index metadata only
    archived_indices = [
        {
            "scene_number": s.get("scene_number"),
            "title": s.get("title", ""),
            "time_label": s.get("time_label", ""),
            "archived": True,
        }
        for s in to_archive
    ]
    
    state["scenes"] = archived_indices + keep
    return state

def load_archived_scene(theme: str, scene_num: int) -> dict | None:
    """Load a single archived scene from disk."""
    archive_path = os.path.join(
        _get_drama_folder(theme), "scenes", f"scene_{scene_num:04d}.json"
    )
    if os.path.exists(archive_path):
        with open(archive_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None
```

### Crash Recovery in actor_speak()
```python
# Source: CONTEXT.md D-16/D-17/D-18
MAX_CRASH_COUNT = 3

async def _restart_actor(actor_name: str, tool_context) -> dict:
    """Restart a crashed actor service (D-17)."""
    state = tool_context.state.get("drama", {})
    actor_data = state.get("actors", {}).get(actor_name, {})
    crash_count = actor_data.get("crash_count", 0) + 1
    
    if crash_count >= MAX_CRASH_COUNT:
        return {
            "status": "error",
            "message": f"角色「{actor_name}」连续崩溃 {crash_count} 次，请手动干预",
        }
    
    # Stop old process
    stop_actor_service(actor_name)
    
    # Extract memory for context restoration
    memory_entries = []
    working = actor_data.get("working_memory", [])
    if working:
        memory_entries = [e["entry"] for e in working]
    critical = actor_data.get("critical_memories", [])
    if critical:
        memory_entries = [f"[关键] {m['entry']}" for m in critical] + memory_entries
    
    # Restart with original config + memory
    svc_result = create_actor_service(
        actor_name=actor_name,
        role=actor_data.get("role", ""),
        personality=actor_data.get("personality", ""),
        background=actor_data.get("background", ""),
        knowledge_scope=actor_data.get("knowledge_scope", ""),
        memory_entries=memory_entries,
    )
    
    # Update state
    if "actors" not in state:
        state["actors"] = {}
    state["actors"][actor_name]["crash_count"] = crash_count
    state["actors"][actor_name].setdefault("restart_log", []).append({
        "time": datetime.now().isoformat(),
        "reason": "auto_restart_after_crash",
    })
    
    return svc_result
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 每次 `_set_state()` 立即写盘 | Debounced 5s 批量写盘 | Phase 12 (D-09) | 减少 I/O 次数，提升高频场景变更下的性能 |
| `_conversation_log` 全局变量 | `state["drama"]["conversation_log"]` | Phase 12 (D-06) | 消除跨 drama 污染，统一持久化路径 |
| 每次 `actor_speak()` 新建 httpx.AsyncClient | 共享单例 AsyncClient | Phase 12 (D-11) | TCP 连接复用，减少冷启动延迟 |
| 所有场景数据存 state.json | 旧场景归档到独立文件 | Phase 12 (D-10) | state.json 大小从 O(N) 降至 O(20)，加载更快 |
| CLI 等待 LLM 无反馈 | Spinner + 场景摘要 | Phase 12 (D-13/D-14) | 用户体验感知改善 |

**Deprecated/outdated:**
- `_save_conversations()` 独立写盘函数：迁移后对话记录走 `_set_state()` debounce，此函数应标记 deprecated 或删除
- `_conversation_log` 模块级变量：迁移后应删除
- `clear_conversation_log()` 中的 `global _conversation_log`：迁移后改为 `state["conversation_log"] = []`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `actor_speak()` 算符优先级 bug 在 line 297/307 的 `not (A and (B or C))` 模式 | 已知 Bug 修复 | 如实际 bug 在别处，需额外定位时间 |
| A2 | `threading.Timer` 适合 debounce 场景，`_set_state()` 总是在同步上下文调用 | Debounce | 如有 async 调用路径，需额外处理 |
| A3 | 归档场景不需要在 context_builder 中按需加载（最近 20 场始终完整） | 场景归档 | 如需要访问归档场景的完整内容，context_builder 需适配 |
| A4 | `rich.live.Live` 可以与 `runner.run_async()` 的 async generator 共存 | CLI Spinner | 如 Live 和 async generator 冲突，需降级为简单文字提示 |
| A5 | `ClientFactory.create()` 可以在不同时间多次调用但共享同一个 `ClientConfig` 中的 `httpx_client` | 共享 AsyncClient | 如 ClientFactory 内部复制了 httpx_client，共享可能无效 |

**关键说明：** A1 需要执行阶段精确定位。当前代码中 line 297 的 `not (actor_dialogue.startswith("[") and ("失败" in actor_dialogue or "超时" in actor_dialogue))` 逻辑与 line 315 的正面判断完全一致（De Morgan 对偶），看起来逻辑是正确的。ROADMAP 提到的"算符优先级 bug"可能指：
1. 原始版本中缺少括号导致 `not A and B or C` 而非 `not (A and (B or C))`
2. 检测条件不够全面——如 `[{actor_name}调用失败` 不含"失败"但含"调用失败"时，`"失败" in actor_dialogue` 为 True，但 `"连接失败"` 也匹配——看起来没问题
3. 可能是 line 246 附近的返回值中 `message` 格式问题

**建议：** 在执行阶段先运行现有 `actor_speak` 单元测试，然后构造边界测试用例验证各种错误消息格式的检测逻辑。

## Open Questions

1. **`actor_speak()` 算符优先级 bug 的精确定位**
   - What we know: ROADMAP 和 CONTEXT.md 都提到"line 246 附近"，但实际代码行号已偏移
   - What's unclear: 具体是哪一行、什么表达式
   - Recommendation: 在执行阶段 grep 搜索 `not.*and.*or` 模式，构造边界测试用例验证

2. **`_flush_state()` 中的线程安全问题**
   - What we know: `_set_state()` 可能从主线程和 timer 线程并发调用
   - What's unclear: `_latest_state_ref` 字典的读写是否需要加锁
   - Recommendation: Python GIL 保证字典操作原子性，单用户模式下风险极低，但 `flush_state_sync()` 中 cancel+write 应考虑加 `threading.Lock()`

3. **E2E 测试的 drama theme 选择**
   - What we know: 需要"稳定可复现"的主题
   - What's unclear: 哪种主题 LLM 生成最稳定
   - Recommendation: 选择简单、现代背景的 theme（如"两个朋友在咖啡店的对话"），避免历史/奇幻题材的复杂人名和世界观

4. **`rich.live.Live` 与 ADK Runner 的 async 交互**
   - What we know: `runner.run_async()` 是 async generator，`Live` 是同步上下文管理器
   - What's unclear: 两者是否能安全地嵌套使用
   - Recommendation: 测试 `Live` 的 `__aenter__`/`__aexit__` 异步版本是否存在；如不存在，用 `asyncio.create_task` 在后台运行 spinner

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.11.1 | — |
| pytest | Testing | ✓ | 8.4.2 | — |
| httpx | AsyncClient | ✓ | 0.28.1 | — |
| rich | CLI Spinner | ✓ | 14.3.2 | 手写 `sys.stdout.write` 循环 |
| a2a-sdk | A2A calls | ✓ | 0.3.26 | — |
| threading | Debounce | ✓ | stdlib | — |
| OPENAI_API_KEY | E2E tests | ✓ | .env | E2E 测试不可运行 |
| LLM API access | E2E tests | ? | — | Mock fallback (deferred) |

**Missing dependencies with no fallback:**
- 如 LLM API 不可用，E2E 测试无法运行。但这正是 `@pytest.mark.e2e` 默认不运行的原因（D-04）

**Missing dependencies with fallback:**
- 如 `rich` 与 async runner 不兼容，降级为简单 `"⏳ 思考中..."` 文字提示

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/unit -x -q` |
| Full suite command | `uv run pytest tests/unit tests/integration` |
| E2E command | `uv run pytest -m e2e` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INTEG-01 | E2E 全流程 30+ 场 | e2e | `pytest -m e2e tests/integration/test_e2e_full_flow.py` | ❌ Wave 0 |
| INTEG-02a | actor_speak 错误检测 | unit | `pytest tests/unit/test_tools_phase12.py::test_actor_speak_error_detection -x` | ❌ Wave 0 |
| INTEG-02b | conversation_log 迁移 | unit | `pytest tests/unit/test_state_manager.py::test_conversation_log_migration -x` | ❌ Wave 0 |
| INTEG-03a | Debounce 写盘 | unit | `pytest tests/unit/test_state_manager.py::test_debounced_save -x` | ❌ Wave 0 |
| INTEG-03b | 场景归档 | unit | `pytest tests/unit/test_state_manager.py::test_scene_archival -x` | ❌ Wave 0 |
| INTEG-03c | 共享 AsyncClient | unit | `pytest tests/unit/test_tools_phase12.py::test_shared_httpx_client -x` | ❌ Wave 0 |
| INTEG-04a | CLI spinner | unit | `pytest tests/unit/test_cli_phase12.py::test_spinner -x` | ❌ Wave 0 |
| INTEG-04b | 场景摘要格式 | unit | `pytest tests/unit/test_cli_phase12.py::test_scene_summary -x` | ❌ Wave 0 |
| INTEG-05a | 崩溃检测与重启 | unit | `pytest tests/unit/test_tools_phase12.py::test_crash_recovery -x` | ❌ Wave 0 |
| INTEG-05b | 3 次崩溃上限 | unit | `pytest tests/unit/test_tools_phase12.py::test_crash_count_limit -x` | ❌ Wave 0 |
| INTEG-06 | 集成测试关键路径 | integration | `pytest tests/integration/ -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit -x -q`
- **Per wave merge:** `uv run pytest tests/unit tests/integration`
- **Phase gate:** Full suite green + `uv run pytest -m e2e` (manual)

### Wave 0 Gaps
- [ ] `tests/integration/test_e2e_full_flow.py` — covers INTEG-01
- [ ] `tests/unit/test_state_manager.py` — covers INTEG-02b, INTEG-03a, INTEG-03b (extend existing)
- [ ] `tests/unit/test_tools_phase12.py` — covers INTEG-02a, INTEG-03c, INTEG-05a, INTEG-05b
- [ ] `tests/unit/test_cli_phase12.py` — covers INTEG-04a, INTEG-04b
- [ ] pytest markers: `@pytest.mark.e2e` registration in `pyproject.toml`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — 单用户模式，无认证需求 |
| V3 Session Management | no | N/A — ADK InMemorySessionService 管理 |
| V4 Access Control | no | N/A — 单用户模式 |
| V5 Input Validation | yes | Python 类型系统 + `dict` 返回值中的 status 字段 |
| V6 Cryptography | no | N/A — 无加密需求 |

### Known Threat Patterns for Python/LLM Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LLM API key exposure in actor generated code | Information Disclosure | `.gitignore` 排除 `app/actors/`；actor_service.py 生成代码时注入 env var |
| State file tampering | Tampering | `state.json` 存储 in `app/dramas/` (gitignored)；单用户模式下风险可控 |
| Debounce 期间崩溃丢数据 | Denial of Service | 最多丢 5 秒状态（D-09 已接受风险） |

## Sources

### Primary (HIGH confidence)
- 源代码直接阅读：`app/state_manager.py` (1262 行), `app/tools.py` (2249 行), `app/actor_service.py` (402 行), `cli.py` (194 行), `app/context_builder.py` (1330 行)
- `a2a-sdk` ClientConfig / ClientFactory API：`uv run python -c "import inspect; ..."` 直接验证 [VERIFIED]
- `rich` 14.3.2 Spinner API：`uv run python -c "from rich.spinner import Spinner; ..."` [VERIFIED]
- `httpx` 0.28.1 AsyncClient API：项目已使用 [VERIFIED]
- `threading.Timer` Python stdlib [CITED: docs.python.org]

### Secondary (MEDIUM confidence)
- pytest-asyncio fixture 配置：`pyproject.toml` asyncio_default_fixture_loop_scope = "function" [VERIFIED]
- `_conversation_log` 竞态条件：从代码分析推断（module-level list + 多处 `global` 声明）[ASSUMED from code review]

### Tertiary (LOW confidence)
- `rich.live.Live` 与 async generator 的兼容性：未实际测试 [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 所有库版本已验证，使用模式来自官方文档和代码
- Architecture: HIGH — 模式来自已有代码库惯例（_set_state, mock_tool_context, setdefault 兼容）
- Pitfalls: HIGH — 来自 PITFALLS.md 已有研究 + 源代码分析
- Bug 修复: MEDIUM — actor_speak 算符优先级 bug 尚需精确定位
- E2E 测试: MEDIUM — 真实 LLM 测试的稳定性有待执行阶段验证

**Research date:** 2026-04-14
**Valid until:** 2026-05-14（依赖库版本稳定期）
