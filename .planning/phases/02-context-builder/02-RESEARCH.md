# Phase 2: Context Builder - Research

**Researched:** 2026-04-11
**Domain:** 上下文组装与 token 预算控制（戏剧叙事 AI 系统）
**Confidence:** HIGH

## Summary

Phase 2 的核心任务是将 `build_actor_context()` 从 `memory_manager.py` 迁移至新建的 `app/context_builder.py`，并新增 `build_director_context()` 函数，同时实现基于字符近似的 token 预算控制和逐层裁剪机制。这是 Phase 1 记忆基础架构的自然延伸——Phase 1 解决了"如何存储和管理记忆"，Phase 2 解决"如何精准地为 LLM 组装上下文"。

现有 `build_actor_context()` 实现（`memory_manager.py:604-687`）已包含完整的优先级排序逻辑（角色锚点→关键记忆→弧线→场景摘要→工作记忆→待压缩记忆），但不具备 token 预算控制。导演侧则完全没有上下文构建机制——导演 agent 的 instruction（`agent.py:175-352`）硬编码了操作流程，没有动态上下文注入。

**Primary recommendation:** 采用"组装→估算→裁剪"三步流程：先按优先级组装全部可用内容，再估算总 token 数，超预算时从最低优先级层开始逐层截断条目数。新增 `estimate_tokens()` 工具函数用于字符→token 近似换算。`build_director_context()` 采用字段存在性检查（D-04）实现向前兼容。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Phase 2 即纳入所有当前可用信息：全局故事弧线（所有演员 arc_summary 合并）+ 近期场景标题/关键事件 + 当前场景编号/状态 + 演员情绪快照 + STORM 视角列表。后续 Phase 增量扩展：张力/冲突（Phase 6）、动态 STORM（Phase 8）、已确立事实（Phase 10）
- **D-02:** Token 估算采用字符数近似（1 中文字 ≈ 1.5 token，1 英文词 ≈ 1 token），零外部依赖。裁剪策略采用逐层截断：超预算时从最低优先级层开始减少条目数——全局摘要不截 → 场景摘要减至最近 N 条 → 工作记忆减至最近 M 条
- **D-03:** 新建 `app/context_builder.py`，将 `build_actor_context()` 从 `memory_manager.py` 迁移过去。职责划分：context_builder 负责所有上下文组装 + token 预算控制；memory_manager 只负责记忆 CRUD + 压缩。`tools.py` 的 import 从 `memory_manager` 改为 `context_builder`。`memory_manager.py` 中保留 `_merge_pending_compression()` 等内部函数，`build_actor_context()` 改为从 context_builder 导入重导出（兼容过渡期）
- **D-04:** 预留接口占位——`build_director_context()` 内部检查 state 中是否存在 `conflict_engine`、`dynamic_storm`、`established_facts` 等字段，存在则纳入，不存在则跳过。后续 Phase 添加新 state 字段后自动生效，无需修改 context_builder

### Claude's Discretion
- 字符数→token 的具体换算系数（可微调）
- 导演上下文各组件的格式和排版细节
- `build_actor_context_from_memory()` 与 `build_actor_context()` 的关系（是否为同一函数的别名或增强版）
- 逐层截断时每层减少的具体步长

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEMORY-04 | 上下文构建器 — 为每场戏组装传入 LLM 的上下文，包含：全局摘要 + 近期场景摘要 + 当前场景工作记忆 + 导演指令，总 token 控制在预算内 | 本研究的 §Architecture Patterns、§Code Examples 提供 `build_actor_context_from_memory()` 和 `build_director_context()` 的完整设计；§Don't Hand-Roll 中的 `estimate_tokens()` 实现；§Common Pitfalls 中的 token 裁剪和优先级策略 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11.1 | 运行时 | 项目已安装 [VERIFIED: python3 --version] |
| google-adk | (installed) | ToolContext 类型 | 项目核心依赖，tool 函数签名必需 [VERIFIED: codebase] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re | stdlib | 中文字符检测 | `estimate_tokens()` 中区分中英文文本 |
| logging | stdlib | 裁剪日志 | 记录 token 预算裁剪操作 |
| pytest | (installed) | 单元测试 | 验证 token 估算、裁剪逻辑、上下文组装 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 字符数近似 token 估算 | tiktoken / tokenizer 库 | tiktoken 需要额外依赖且仅适用于 OpenAI 模型；本项目使用 LiteLlm 兼容多种模型，字符近似更通用。D-02 已锁定字符近似方案 [CITED: CONTEXT.md D-02] |
| 字符数近似 token 估算 | LLM API token counting | 需要网络调用，增加延迟；字符近似在预算控制场景下足够精确 [ASSUMED] |

**Installation:**
```bash
# 无新依赖需要安装 — Phase 2 完全使用 Python 标准库
```

**Version verification:** 不适用——零新依赖。

## Architecture Patterns

### Recommended Project Structure
```
app/
├── context_builder.py     # 新增：上下文组装 + token 预算控制
├── memory_manager.py      # 修改：迁出 build_actor_context，保留 CRUD + 压缩
├── tools.py               # 修改：import 从 context_builder 导入
├── agent.py               # 修改：导演 agent instruction 引用 build_director_context
└── state_manager.py       # 不变：通过 _get_state/_set_state 提供 state 访问
```

### Pattern 1: 组装→估算→裁剪 三步流程

**What:** 所有上下文构建函数遵循相同的三步模式：先组装全部可用内容，再估算总 token 数，最后按优先级裁剪至预算内。

**When to use:** 每次 LLM 调用前构建上下文时。

**Example:**
```python
def build_actor_context_from_memory(
    actor_name: str,
    tool_context: ToolContext,
    token_budget: int = 8000,
) -> str:
    """Build actor context with token budget control.
    
    三步流程：组装 → 估算 → 裁剪。
    """
    state = _get_state(tool_context)
    actor_data = state.get("actors", {}).get(actor_name, {})
    
    # Step 1: Assemble all sections with priority metadata
    sections = _assemble_actor_sections(actor_name, actor_data, tool_context)
    
    # Step 2: Estimate total tokens
    full_text = "\n\n".join(s["content"] for s in sections)
    total_tokens = estimate_tokens(full_text)
    
    # Step 3: Truncate if over budget (lowest priority first)
    if total_tokens > token_budget:
        sections = _truncate_sections(sections, token_budget)
    
    return "\n\n".join(s["content"] for s in sections)
```

### Pattern 2: 字段存在性检查实现向前兼容

**What:** `build_director_context()` 通过 `dict.get()` 检查 state 字段是否存在，存在则纳入，不存在则跳过。后续 Phase 添加新字段后自动生效。

**When to use:** 导演上下文构建（D-04 锁定决策）。

**Example:**
```python
def build_director_context(tool_context: ToolContext, token_budget: int = 30000) -> str:
    state = _get_state(tool_context)
    sections = []
    
    # Always-available sections
    sections.append(_build_global_arc_section(state))
    sections.append(_build_recent_scenes_section(state))
    sections.append(_build_actor_emotions_section(state))
    sections.append(_build_storm_section(state))
    
    # D-04: Forward-compatible sections (check field existence)
    if state.get("conflict_engine"):          # Phase 6
        sections.append(_build_conflict_section(state))
    if state.get("dynamic_storm"):            # Phase 8
        sections.append(_build_dynamic_storm_section(state))
    if state.get("established_facts"):        # Phase 10
        sections.append(_build_facts_section(state))
    
    # Truncate to budget
    ...
```

### Pattern 3: 兼容过渡期重导出

**What:** `memory_manager.py` 中原有 `build_actor_context` 的调用方（如测试文件 `test_memory_manager.py`）通过重导出保持兼容。

**When to use:** 迁移函数时的过渡期。

**Example:**
```python
# memory_manager.py 末尾添加
from .context_builder import build_actor_context  # 重导出，保持兼容
```

### Anti-Patterns to Avoid
- **在 context_builder 中调用 LLM：** 上下文组装必须是纯函数操作，不能引入 LLM 调用（那是 memory_manager 的压缩职责）。违反会导致 actor_speak 延迟叠加 [CITED: PITFALLS.md #10]
- **硬编码 state 字段路径：** 不要假设 state 中一定存在某个字段。使用 `dict.get(key, default)` 和字段存在性检查 [CITED: CONTEXT.md D-04]
- **在裁剪时丢弃最高优先级层：** 全局摘要是故事的根基，永远不应截断。裁剪应从最低优先级（工作记忆细节）开始 [CITED: CONTEXT.md D-02]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token 估算 | 完整 tokenizer（tiktoken/sentencepiece） | `estimate_tokens()` 字符近似 | D-02 锁定零外部依赖；不同 LLM 使用不同 tokenizer，字符近似在预算控制场景下足够精确 |
| 上下文格式化 | 每次手工拼接字符串 | `_assemble_actor_sections()` / `_assemble_director_sections()` 返回结构化 section 列表 | 统一格式、便于裁剪、便于测试 |
| 优先级裁剪 | 随意截断字符串 | `_truncate_sections()` 按优先级逐层裁剪 | 确保重要信息保留，D-02 锁定裁剪策略 |

**Key insight:** Token 预算控制的关键不是精确计数，而是"宁可多留预算，不可超出预算"。字符近似在实际使用中偏保守（通常会略微高估 token 数），这正好符合预算控制的需求——我们宁可少传一点信息，也不要超出 LLM 的上下文窗口。

## Common Pitfalls

### Pitfall 1: 迁移后循环导入

**What goes wrong:** `context_builder.py` 需要 `from .state_manager import _get_state, _set_state`，而 `memory_manager.py` 的重导出 `from .context_builder import build_actor_context` 可能形成循环。
**Why it happens:** Python 模块间相互导入时，若 A 导入 B 且 B 导入 A，会导致 ImportError。
**How to avoid:** `context_builder.py` 只依赖 `state_manager`（单向依赖），`memory_manager.py` 的重导出放在文件末尾（确保 context_builder 先完全加载）。`tools.py` 直接从 `context_builder` 导入，不再从 `memory_manager` 导入 `build_actor_context`。
**Warning signs:** `ImportError: cannot import name 'build_actor_context' from partially initialized module`

### Pitfall 2: 裁剪后上下文不连贯

**What goes wrong:** 当场景摘要被裁剪至最近 3 条时，演员可能不知道 3 条之前发生的关键事件，导致对话中提及远期事件时不知所云。
**Why it happens:** 裁剪只考虑了条目数量，没有考虑内容的逻辑连贯性。
**How to avoid:** (1) 裁剪策略遵循 D-02 优先级：全局摘要（含未决冲突）不截 → 场景摘要减至最近 N 条 → 工作记忆减至最近 M 条。全局摘要中包含未决冲突和关键角色信息，是远期事件的兜底。(2) 关键记忆（critical_memories）永远不被裁剪，它们包含了跨场景的关键事件。(3) 裁剪日志记录被裁掉的信息摘要，方便调试。
**Warning signs:** 演员在对话中提到远期事件时回应"我不知道这件事"；对话中出现知识断层。

### Pitfall 3: 导演上下文超大导致 LLM 调用失败

**What goes wrong:** 导演上下文预算为 30000 tokens，但如果演员数量多（最多 10 个）且每个演员都有完整的 arc_summary，合并后的全局弧线部分可能就超过预算。
**Why it happens:** 导演的"全局故事弧线"需要合并所有演员的 arc_summary，10 个演员 × ~500 tokens/人 = ~5000 tokens 仅仅弧线部分，加上 10 人的情绪快照、近期场景、STORM 视角，轻松达到 20000+ tokens。
**How to avoid:** (1) 导演的全局弧线不是简单拼接所有 arc_summary，而是取每个 arc 的结构化字段（theme/key_characters/unresolved）+ 精简的 narrative（可截断至 N 字符）。(2) 演员情绪快照只取一行摘要（如"朱棣: 焦虑"），不展开完整情绪上下文。(3) 近期场景只取标题和关键事件，不包含完整对话内容。(4) 30000 tokens 预算分配：全局弧线 ~6000 + 近期场景 ~8000 + 情绪快照 ~2000 + STORM 视角 ~4000 + 预留冲突/事实 ~5000 + 缓冲 ~5000。
**Warning signs:** 导演 LLM 调用返回截断响应；导演旁白变得泛泛而谈。

### Pitfall 4: 忽略 _merge_pending_compression 的数据一致性

**What goes wrong:** 迁移 `build_actor_context` 到 context_builder 时，忘记在新实现中调用 `_merge_pending_compression()`，导致异步压缩结果无法被合并到上下文中。
**Why it happens:** `_merge_pending_compression()` 是 Phase 1 新增的关键函数，在 `build_actor_context()` 开头被调用。如果迁移时遗漏，压缩结果将无法生效。
**How to avoid:** (1) 迁移 `build_actor_context` 时保留对 `_merge_pending_compression()` 的调用。(2) 新的 `build_actor_context_from_memory()` 必须在开头调用 `_merge_pending_compression()`（从 memory_manager 导入）。(3) 添加测试验证压缩结果在上下文中可见。
**Warning signs:** 演员上下文中出现"待压缩记忆"段落但永远不被替换为正式摘要；场景摘要列表不增长。

### Pitfall 5: Token 估算偏差导致实际超出预算

**What goes wrong:** 字符近似估算在某些情况下显著低估实际 token 数（如大量专业术语、混合语言文本），导致组装的上下文实际超出 LLM 窗口限制。
**Why it happens:** 1 中文字 ≈ 1.5 token 是平均值，某些生僻字或专业术语可能 1 字 ≈ 2-3 tokens。混合中英文的文本估算更不准确。
**How to avoid:** (1) 在估算系数中加入 10-15% 的安全裕度（如实际使用 1 中文字 ≈ 1.7 token 而非 1.5）。(2) `estimate_tokens()` 返回值应向上取整。(3) token_budget 参数应设为 LLM 实际窗口的 90% 以内（如 8000 token 预算对应 ~12000 实际窗口）。
**Warning signs:** LLM 返回截断响应；偶尔出现 "context length exceeded" 错误。

## Code Examples

### estimate_tokens — 字符近似 token 估算

```python
import re

# D-02: 1 中文字 ≈ 1.5 token, 1 英文词 ≈ 1 token
# 安全系数 1.1，向上取整
_CHAR_TOKEN_RATIO = 1.5   # CJK character → tokens
_WORD_TOKEN_RATIO = 1.0   # English word → tokens
_SAFETY_MARGIN = 1.1      # 10% safety margin

_CJK_PATTERN = re.compile(
    r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff'  # CJK Unified + Ext-A + Compatibility
    r'\U00020000-\U0002a6df\U0002a700-\U0002b73f'  # CJK Ext B+C
    r'\u3000-\u303f\uff00-\uffef]'                  # CJK Symbols + Halfwidth
)

def estimate_tokens(text: str) -> int:
    """Estimate token count from text using character-based approximation.

    字符数近似 token 估算（D-02）。
    中文字 ≈ 1.5 token，英文词 ≈ 1 token，含 10% 安全裕度。
    
    Args:
        text: The text to estimate tokens for.
    
    Returns:
        Estimated token count (ceiling, with safety margin).
    """
    if not text:
        return 0
    
    # Count CJK characters
    cjk_count = len(_CJK_PATTERN.findall(text))
    
    # Remove CJK characters, count remaining "words" (split by whitespace)
    non_cjk_text = _CJK_PATTERN.sub(' ', text)
    word_count = len(non_cjk_text.split())
    
    raw_tokens = cjk_count * _CHAR_TOKEN_RATIO + word_count * _WORD_TOKEN_RATIO
    return int(raw_tokens * _SAFETY_MARGIN) + 1  # +1 for ceiling
```

### build_actor_context_from_memory — 带 token 预算控制的演员上下文

```python
from .memory_manager import _merge_pending_compression
from .state_manager import _get_state, _set_state

# Priority levels for truncation (lower = truncated first)
_ACTOR_SECTION_PRIORITIES = {
    "working_memory": 1,      # Lowest priority — truncated first
    "scene_summaries": 2,     # Medium priority
    "arc_summary": 3,         # High priority — rarely truncated
    "critical_memories": 4,   # Very high — almost never truncated
    "emotion": 5,             # Never truncated
    "anchor": 6,              # Never truncated — identity anchor
}

def _assemble_actor_sections(
    actor_name: str,
    actor_data: dict,
    tool_context: ToolContext,
) -> list[dict]:
    """Assemble actor context sections with priority metadata.
    
    返回结构化 section 列表，每个 section 包含 content、priority、max_items。
    """
    # Merge async compression results first (Phase 1 integration)
    _merge_pending_compression(actor_name, actor_data, tool_context)
    
    sections = []
    
    # Tier 0: Character anchor (highest priority — Pitfall #3 in PITFALLS.md)
    role = actor_data.get("role", "")
    personality = actor_data.get("personality", "")
    sections.append({
        "key": "anchor",
        "priority": _ACTOR_SECTION_PRIORITIES["anchor"],
        "content": f"【角色锚点】你是{actor_name}，{role}。{personality}",
        "truncatable": False,
    })
    
    # Current emotion
    emotion = actor_data.get("emotions", "neutral")
    emotion_cn = {
        "neutral": "平静", "angry": "愤怒", "sad": "悲伤", "happy": "喜悦",
        "fearful": "恐惧", "confused": "困惑", "determined": "决绝",
        "anxious": "焦虑", "hopeful": "充满希望",
    }.get(emotion, emotion)
    sections.append({
        "key": "emotion",
        "priority": _ACTOR_SECTION_PRIORITIES["emotion"],
        "content": f"【当前情绪】{emotion_cn}",
        "truncatable": False,
    })
    
    # Critical memories (D-07: always included, never compressed)
    critical = actor_data.get("critical_memories", [])
    if critical:
        lines = [f"- [第{m['scene']}场] {m['entry']} [{m['reason']}]" for m in critical]
        sections.append({
            "key": "critical_memories",
            "priority": _ACTOR_SECTION_PRIORITIES["critical_memories"],
            "content": "【关键记忆（永久保留）】\n" + "\n".join(lines),
            "truncatable": False,  # Never truncate critical memories
        })
    
    # Tier 3: Arc summary
    arc = actor_data.get("arc_summary", {})
    if arc.get("narrative"):
        structured = arc.get("structured", {})
        theme = structured.get("theme", "")
        unresolved = "；".join(structured.get("unresolved", []))
        resolved = "；".join(structured.get("resolved", []))
        header = f"主题：{theme}" if theme else ""
        if unresolved:
            header += f" | 未决：{unresolved}"
        if resolved:
            header += f" | 已解决：{resolved}"
        arc_text = arc["narrative"]
        if header:
            content = f"【你的故事弧线】\n{header}\n{arc_text}"
        else:
            content = f"【你的故事弧线】\n{arc_text}"
        sections.append({
            "key": "arc_summary",
            "priority": _ACTOR_SECTION_PRIORITIES["arc_summary"],
            "content": content,
            "truncatable": True,
            "max_chars": 500,  # Arc narrative capped at ~500 chars
        })
    
    # Tier 2: Scene summaries (truncatable by count)
    summaries = actor_data.get("scene_summaries", [])
    if summaries:
        lines = [f"- 第{s['scenes_covered']}场：{s['summary']}" for s in summaries[-10:]]
        sections.append({
            "key": "scene_summaries",
            "priority": _ACTOR_SECTION_PRIORITIES["scene_summaries"],
            "content": "【近期场景摘要】\n" + "\n".join(lines),
            "truncatable": True,
            "items": summaries,
            "item_formatter": lambda s: f"- 第{s['scenes_covered']}场：{s['summary']}",
            "header": "【近期场景摘要】",
        })
    
    # Tier 1: Working memory (truncatable by count)
    working = actor_data.get("working_memory", [])
    if working:
        lines = [f"  第{e.get('scene', '?')}场: {e['entry']}" for e in working[-5:]]
        sections.append({
            "key": "working_memory",
            "priority": _ACTOR_SECTION_PRIORITIES["working_memory"],
            "content": "【最近的经历（详细）】\n" + "\n".join(lines),
            "truncatable": True,
            "items": working,
            "item_formatter": lambda e: f"  第{e.get('scene', '?')}场: {e['entry']}",
            "header": "【最近的经历（详细）】",
        })
    
    # Fallback: pending compression entries (D-09)
    pending = actor_data.get("_pending_compression", {})
    if pending.get("pending_entries"):
        pending_lines = [
            f"  第{e.get('scene', '?')}场（待压缩）: {e['entry']}"
            for e in pending["pending_entries"]
        ]
        sections.append({
            "key": "pending_memory",
            "priority": _ACTOR_SECTION_PRIORITIES["working_memory"],
            "content": "【待压缩记忆】\n" + "\n".join(pending_lines),
            "truncatable": True,
        })
    
    return sections


def _truncate_sections(
    sections: list[dict],
    token_budget: int,
) -> list[dict]:
    """Truncate sections to fit within token budget.
    
    逐层截断策略（D-02）：从最低优先级的可截断层开始减少条目数。
    """
    # First pass: calculate total tokens
    total_tokens = sum(estimate_tokens(s["content"]) for s in sections)
    if total_tokens <= token_budget:
        return sections
    
    logger.info(f"Context over budget: {total_tokens} > {token_budget}, truncating...")
    
    # Sort truncatable sections by priority (ascending = truncate first)
    truncatable = [(i, s) for i, s in enumerate(sections) if s.get("truncatable")]
    truncatable.sort(key=lambda x: x[1]["priority"])
    
    # Phase 1: Reduce item counts in sections with "items" field
    for idx, section in truncatable:
        if total_tokens <= token_budget:
            break
        items = section.get("items", [])
        if not items:
            continue
        
        formatter = section.get("item_formatter", str)
        header = section.get("header", "")
        
        # Progressively reduce items from the oldest (front)
        while len(items) > 1 and total_tokens > token_budget:
            removed_item = items.pop(0)  # Remove oldest
            new_lines = [formatter(item) for item in items]
            new_content = header + "\n" + "\n".join(new_lines) if header else "\n".join(new_lines)
            old_tokens = estimate_tokens(section["content"])
            new_tokens = estimate_tokens(new_content)
            total_tokens = total_tokens - old_tokens + new_tokens
            section["content"] = new_content
            section["items"] = items
            logger.debug(f"  Truncated {section['key']}: {len(items)} items remaining")
    
    # Phase 2: If still over budget, remove entire low-priority sections
    if total_tokens > token_budget:
        for idx, section in truncatable:
            if total_tokens <= token_budget:
                break
            if not section.get("truncatable"):
                continue
            removed_tokens = estimate_tokens(section["content"])
            sections[idx] = {**section, "content": ""}  # Empty but keep structure
            total_tokens -= removed_tokens
            logger.info(f"  Removed section: {section['key']} (saved ~{removed_tokens} tokens)")
    
    # Filter out empty sections
    return [s for s in sections if s.get("content")]
```

### build_director_context — 导演上下文

```python
def build_director_context(
    tool_context: ToolContext,
    token_budget: int = 30000,
) -> str:
    """Build context for the Director agent.
    
    导演上下文包含：全局故事弧线 + 近期场景 + 演员情绪快照 + STORM 视角。
    通过字段存在性检查（D-04）实现向前兼容：后续 Phase 添加的新 state 字段自动生效。
    
    Args:
        tool_context: Tool context for state access.
        token_budget: Maximum token budget (default: 30000).
    
    Returns:
        Formatted context string for the Director prompt.
    """
    state = _get_state(tool_context)
    if not state.get("theme"):
        return "暂无戏剧上下文"
    
    sections = []
    
    # === Always-available sections ===
    
    # 1. Global story arc (all actors' arc_summary merged)
    sections.append(_build_global_arc_section(state))
    
    # 2. Current scene & status
    current_scene = state.get("current_scene", 0)
    status = state.get("status", "")
    sections.append({
        "key": "current_status",
        "priority": 10,
        "content": f"【当前状态】第{current_scene}场 | 状态：{status}",
        "truncatable": False,
    })
    
    # 3. Recent scene titles + key events
    sections.append(_build_recent_scenes_section(state))
    
    # 4. Actor emotion snapshot (one-line per actor)
    sections.append(_build_actor_emotions_section(state))
    
    # 5. STORM perspectives (D-01: always included when available)
    sections.append(_build_storm_section(state))
    
    # === D-04: Forward-compatible sections ===
    
    if state.get("conflict_engine"):          # Phase 6
        sections.append(_build_conflict_section(state))
    
    if state.get("dynamic_storm"):            # Phase 8
        sections.append(_build_dynamic_storm_section(state))
    
    if state.get("established_facts"):        # Phase 10
        sections.append(_build_facts_section(state))
    
    # Truncate to budget
    total_tokens = sum(estimate_tokens(s["content"]) for s in sections)
    if total_tokens > token_budget:
        sections = _truncate_sections(sections, token_budget)
    
    return "\n\n".join(s["content"] for s in sections if s.get("content"))


def _build_global_arc_section(state: dict) -> dict:
    """Build the global story arc section from all actors' arc_summaries."""
    actors = state.get("actors", {})
    arc_parts = []
    
    for name, data in actors.items():
        arc = data.get("arc_summary", {})
        if arc.get("narrative"):
            structured = arc.get("structured", {})
            theme = structured.get("theme", "")
            unresolved = structured.get("unresolved", [])
            resolved = structured.get("resolved", [])
            
            part = f"**{name}**"
            if theme:
                part += f"（主题：{theme}）"
            part += f"：{arc['narrative'][:300]}"  # Cap narrative per actor
            
            if unresolved:
                part += f"\n  未决：{'；'.join(unresolved[:5])}"
            if resolved:
                part += f"\n  已解决：{'；'.join(resolved[:3])}"
            
            arc_parts.append(part)
    
    content = "【全局故事弧线】\n" + "\n\n".join(arc_parts) if arc_parts else "【全局故事弧线】暂无弧线数据"
    return {
        "key": "global_arc",
        "priority": 5,
        "content": content,
        "truncatable": True,
        "max_chars": 6000,  # ~6000 tokens for all arcs
    }


def _build_recent_scenes_section(state: dict) -> dict:
    """Build recent scenes section with titles and key events only."""
    scenes = state.get("scenes", [])
    recent = scenes[-10:] if len(scenes) > 10 else scenes
    
    if not recent:
        return {"key": "recent_scenes", "priority": 4, "content": "", "truncatable": True}
    
    lines = []
    for scene in recent:
        num = scene.get("scene_number", "?")
        title = scene.get("title", "无标题")
        desc = scene.get("description", "")[:100]  # Truncate description
        lines.append(f"- 第{num}场「{title}」：{desc}")
    
    return {
        "key": "recent_scenes",
        "priority": 4,
        "content": "【近期场景】\n" + "\n".join(lines),
        "truncatable": True,
        "items": recent,
        "item_formatter": lambda s: f"- 第{s.get('scene_number', '?')}场「{s.get('title', '无标题')}」：{s.get('description', '')[:100]}",
        "header": "【近期场景】",
    }


def _build_actor_emotions_section(state: dict) -> dict:
    """Build actor emotion snapshot (one-line per actor)."""
    actors = state.get("actors", {})
    lines = []
    emotion_cn = {
        "neutral": "平静", "angry": "愤怒", "sad": "悲伤", "happy": "喜悦",
        "fearful": "恐惧", "confused": "困惑", "determined": "决绝",
        "anxious": "焦虑", "hopeful": "充满希望",
    }
    
    for name, data in actors.items():
        role = data.get("role", "")
        emotion = data.get("emotions", "neutral")
        emotion_label = emotion_cn.get(emotion, emotion)
        lines.append(f"- {name}（{role}）：{emotion_label}")
    
    content = "【演员情绪快照】\n" + "\n".join(lines) if lines else ""
    return {
        "key": "actor_emotions",
        "priority": 6,
        "content": content,
        "truncatable": False,  # Always show emotion snapshot (it's tiny)
    }


def _build_storm_section(state: dict) -> dict:
    """Build STORM perspectives section."""
    storm = state.get("storm", {})
    perspectives = storm.get("perspectives", [])
    
    if not perspectives:
        return {"key": "storm", "priority": 3, "content": "", "truncatable": True}
    
    lines = []
    for p in perspectives:
        name = p.get("name", "未命名视角")
        desc = p.get("description", "")[:200]
        lines.append(f"- **{name}**：{desc}")
    
    content = "【STORM视角】\n" + "\n".join(lines)
    return {
        "key": "storm",
        "priority": 3,
        "content": content,
        "truncatable": True,
    }


# D-04: Placeholder sections for future phases
def _build_conflict_section(state: dict) -> dict:
    """Build active conflicts section. Populated by Phase 6."""
    conflict_engine = state.get("conflict_engine", {})
    active = conflict_engine.get("active_conflicts", [])
    if not active:
        return {"key": "conflicts", "priority": 4, "content": "", "truncatable": True}
    
    lines = [f"- {c.get('description', c)}" for c in active]
    return {
        "key": "conflicts",
        "priority": 4,
        "content": "【活跃冲突】\n" + "\n".join(lines),
        "truncatable": True,
    }


def _build_dynamic_storm_section(state: dict) -> dict:
    """Build dynamic STORM section. Populated by Phase 8."""
    ds = state.get("dynamic_storm", {})
    history = ds.get("trigger_history", [])
    if not history:
        return {"key": "dynamic_storm", "priority": 3, "content": "", "truncatable": True}
    
    latest = history[-1] if history else {}
    new_perspectives = latest.get("new_perspectives", [])
    lines = [f"- {p}" for p in new_perspectives]
    return {
        "key": "dynamic_storm",
        "priority": 3,
        "content": "【最新STORM发现】\n" + "\n".join(lines) if lines else "",
        "truncatable": True,
    }


def _build_facts_section(state: dict) -> dict:
    """Build established facts section. Populated by Phase 10."""
    facts = state.get("established_facts", [])
    if not facts:
        return {"key": "facts", "priority": 5, "content": "", "truncatable": True}
    
    lines = [f"- {f}" if isinstance(f, str) else f"- {f.get('fact', f)}" for f in facts[:20]]
    return {
        "key": "facts",
        "priority": 5,
        "content": "【已确立事实】\n" + "\n".join(lines),
        "truncatable": True,
    }
```

### 导入迁移 — tools.py 的改动

```python
# tools.py — 修改前
from .memory_manager import (
    add_working_memory,
    build_actor_context,     # ← 需要改
    detect_importance,
    mark_critical_memory,
)

# tools.py — 修改后
from .context_builder import build_actor_context  # 新位置
from .memory_manager import (
    add_working_memory,
    detect_importance,
    mark_critical_memory,
)
```

### memory_manager.py 的重导出

```python
# memory_manager.py — 在文件末尾添加
# Phase 2: Re-export for backward compatibility
# build_actor_context has been migrated to context_builder.py
from .context_builder import build_actor_context  # noqa: F401
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 扁平 memory 列表 | 3 层记忆 + critical_memories | Phase 1 (2026-04-11) | 上下文构建有了优先级排序的基础 |
| 无 token 预算控制 | estimate_tokens + 逐层裁剪 | Phase 2 (本阶段) | 演员上下文 ≤ 8000 tokens，导演 ≤ 30000 tokens |
| 导演无动态上下文 | build_director_context() | Phase 2 (本阶段) | 导演获得完整状态感知能力 |
| memory_manager 同时负责 CRUD 和组装 | 职责分离：CRUD→memory_manager, 组装→context_builder | Phase 2 (本阶段) | 单一职责，减少模块耦合 |

**Deprecated/outdated:**
- `memory_manager.build_actor_context()`: 迁移至 `context_builder.build_actor_context()`，原位置仅重导出

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 1 中文字 ≈ 1.5 token 在 Claude/GPT 模型上的平均偏差 < 20% | Standard Stack | 实际 token 数可能超出预算，导致 LLM 调用失败。通过 10% 安全裕度缓解 |
| A2 | 导演上下文 30000 tokens 预算足够容纳 10 个演员的全局弧线 + 近期场景 + STORM 视角 | Architecture Patterns | 如果不足，导演上下文被过度裁剪，丢失关键信息。通过 per-actor narrative 截断至 300 字符缓解 |
| A3 | 重导出方式不会导致测试或运行时问题 | Architecture Patterns | 如果有代码在 `memory_manager.build_actor_context` 上做 monkey-patch，重导出会失效。但本项目测试使用 mock，不依赖 monkey-patch |
| A4 | `_merge_pending_compression` 可以从 `memory_manager` 安全导入到 `context_builder` | Code Examples | 如果形成循环导入，需要改为延迟导入。单向依赖分析表明不会循环 |

## Open Questions (RESOLVED)

1. **`build_actor_context_from_memory()` vs `build_actor_context()` 的关系** — RESOLVED
   - What we know: CONTEXT.md 的 Claude's Discretion 允许我们决定这两者的关系
   - What's unclear: 是创建一个全新的 `build_actor_context_from_memory()` 作为增强版，还是直接修改 `build_actor_context()` 增加 token_budget 参数
   - Recommendation: 保持 `build_actor_context()` 的原始签名不变（向后兼容），新增 `build_actor_context_from_memory()` 带有 `token_budget` 参数。`build_actor_context()` 内部调用 `build_actor_context_from_memory()` 并使用默认预算。这样既满足 D-03 的迁移要求，又提供了预算控制能力。
   - **Resolution:** Plan 01 Task 1 按 Recommendation 实施：`build_actor_context()` 保持原签名并委托给 `build_actor_context_from_memory(token_budget=8000)`

2. **导演上下文如何注入到导演 agent** — RESOLVED
   - What we know: 导演 agent 的 instruction 是静态字符串（agent.py:175-352），不包含动态上下文
   - What's unclear: `build_director_context()` 应该作为 Tool 注册（导演可主动调用），还是内部调用（自动注入 prompt），还是两者兼有
   - Recommendation: 两者兼有。作为 Tool 注册让导演可以主动获取上下文摘要；同时在 `director_narrate()` 或 `next_scene()` 工具中自动注入，确保每次场景操作都有完整上下文。具体注入方式在 Plan 阶段确定。
   - **Resolution:** Plan 02 Task 1 按 Recommendation 实施：注册 `get_director_context` 为 Tool + 在 `director_narrate`/`next_scene` 中自动注入

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | 运行时 | ✓ | 3.11.1 | — |
| uv | 包管理 | ✓ | 0.10.0 | — |
| pytest | 测试 | ✓ | (installed) | — |
| google-adk | ToolContext | ✓ | (installed) | — |
| re (stdlib) | estimate_tokens | ✓ | stdlib | — |
| logging (stdlib) | 裁剪日志 | ✓ | stdlib | — |

**Missing dependencies with no fallback:**
- None

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml ([tool.pytest.ini_options]) |
| Quick run command | `uv run pytest tests/unit/test_context_builder.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEMORY-04 | estimate_tokens 准确性 | unit | `uv run pytest tests/unit/test_context_builder.py::test_estimate_tokens -x` | ❌ Wave 0 |
| MEMORY-04 | build_actor_context_from_memory 优先级排序 | unit | `uv run pytest tests/unit/test_context_builder.py::test_actor_context_priority -x` | ❌ Wave 0 |
| MEMORY-04 | build_actor_context_from_memory token 裁剪 | unit | `uv run pytest tests/unit/test_context_builder.py::test_actor_context_truncation -x` | ❌ Wave 0 |
| MEMORY-04 | build_director_context 包含所有 D-01 组件 | unit | `uv run pytest tests/unit/test_context_builder.py::test_director_context_components -x` | ❌ Wave 0 |
| MEMORY-04 | build_director_context D-04 前向兼容 | unit | `uv run pytest tests/unit/test_context_builder.py::test_director_context_forward_compat -x` | ❌ Wave 0 |
| MEMORY-04 | build_director_context token 裁剪 | unit | `uv run pytest tests/unit/test_context_builder.py::test_director_context_truncation -x` | ❌ Wave 0 |
| MEMORY-04 | 迁移后 tools.py 导入正确 | integration | `uv run pytest tests/unit/test_integration.py -x` | ✅ Existing |
| MEMORY-04 | memory_manager 重导出兼容 | unit | `uv run pytest tests/unit/test_memory_manager.py -x` | ✅ Existing |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_context_builder.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_context_builder.py` — covers MEMORY-04 (all unit tests above)
- [ ] Framework config: 已存在于 `pyproject.toml`，无需新增

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — 单用户 CLI，无认证 |
| V3 Session Management | no | N/A — ADK 管理会话 |
| V4 Access Control | no | N/A — 单用户模式 |
| V5 Input Validation | yes | `ENTRY_TEXT_MAX_LENGTH`（Phase 1 已实现），`estimate_tokens()` 拒绝空/null 输入 |
| V6 Cryptography | no | N/A — 无加密需求 |

### Known Threat Patterns for Python/ADK Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| State injection via actor_name | Tampering | `actor_data` 查找失败时返回默认值，不抛异常 |
| Token budget bypass | Denial of Service | `estimate_tokens()` 有上限检查，`_truncate_sections()` 强制裁剪 |
| Path traversal in state access | Tampering | `state_manager._sanitize_name()` 已处理（Phase 1） |

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `app/memory_manager.py` (build_actor_context 实现，604-687 行) [VERIFIED]
- Codebase analysis: `app/tools.py` (actor_speak 导入和调用，53-56/208 行) [VERIFIED]
- Codebase analysis: `app/agent.py` (导演 instruction，175-352 行) [VERIFIED]
- Codebase analysis: `app/state_manager.py` (state 结构、_get_state/_set_state) [VERIFIED]
- Phase 1 CONTEXT.md: D-01~D-13 锁定决策 [VERIFIED]

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` — Context Builder 集成方案、token 预算分配表 [CITED: project research]
- `.planning/research/PITFALLS.md` — 上下文耗尽、摘要失真等陷阱 [CITED: project research]
- `.planning/codebase/CONVENTIONS.md` — 编码规范 [CITED: project analysis]

### Tertiary (LOW confidence)
- Token 估算系数：1 中文字 ≈ 1.5 token 基于 Claude/GPT 的已知 tokenizer 行为 [ASSUMED — 未经官方 API 验证，但根据 LLM tokenizer 设计原理（BPE 对 CJK 使用 multi-byte 编码），该近似在预算控制场景下合理]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 零新依赖，纯 Python 标准库
- Architecture: HIGH — 基于现有代码结构分析，迁移路径清晰
- Pitfalls: HIGH — 基于 PITFALLS.md 和 Phase 1 实现经验

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (stable — 无外部依赖变化风险)
