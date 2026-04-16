# Phase 6: Tension Scoring & Conflict Engine - Research

**Researched:** 2026-04-12
**Domain:** Heuristic tension scoring + conflict injection engine for AI narrative systems
**Confidence:** HIGH

## Summary

Phase 6 实现张力评分（`evaluate_tension`）和冲突注入（`inject_conflict`）两个核心 Tool 函数，以及支撑它们的冲突模板库、状态追踪和导演 prompt 集成。这是防止"流水账"的关键模块——当剧情变得平淡时，系统自动建议注入转折事件。

核心技术方案已完全锁定：纯启发式规则（4 信号加权），7 种冲突模板（Python 常量字典），8 场去重窗口，"导演建议"模式（非强制注入）。所有决策已在 CONTEXT.md 中锁定（D-01 至 D-19）。

现有代码库已为 Phase 6 做好前向兼容准备：`_build_conflict_section()` 已存在并读取 `conflict_engine` 字段，`_DIRECTOR_SECTION_PRIORITIES` 已预留扩展位置，`state_manager.py` 的 `init_drama_state()` 和 `load_progress()` 有成熟的字段初始化和兼容模式。新模块 `conflict_engine.py` 与 `memory_manager.py` 同级，遵循已建立的模块职责单一模式。

**Primary recommendation:** 严格遵循 CONTEXT.md 的 19 条决策，新建 `app/conflict_engine.py` 作为纯计算模块（无 LLM 调用），通过 4 个集成点（tools.py、agent.py、context_builder.py、state_manager.py）接入现有系统。张力评分的 4 个信号均可从现有 state 结构中直接读取，无需额外数据源。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 纯启发式规则，不调用 LLM——4 个信号加权计算张力评分
- **D-02:** 张力评分范围 0-100，< 30 低张力，30-70 正常，> 70 高张力
- **D-03:** 评分由导演 prompt 触发调用，尊重 ADK turn-based 模型
- **D-04:** 评分结果写入 `state["conflict_engine"]["tension_history"]`，保留最近 20 场
- **D-05:** 冲突注入为"导演建议"模式——返回结构化建议，非强制执行
- **D-06:** 冲突模板库为 Python 常量字典，不使用 LLM 生成
- **D-07:** 7 种冲突类型定义
- **D-08:** 同类型 8 场内不重复
- **D-09:** 连续多场低张力的渐进升级（1场→建议，2场→高紧迫，3+场→强制指引）
- **D-10:** 活跃冲突上限 3-4 条
- **D-11:** `evaluate_tension()` 注册为 `_improv_director` 的 Tool
- **D-12:** `inject_conflict()` 注册为 `_improv_director` 的 Tool
- **D-13:** 导演 prompt 新增 §8 张力评估段落
- **D-14:** `build_director_context()` 新增【张力状态】段落
- **D-15:** `build_director_context()` 中已有的 `_build_conflict_section()` 开始生效
- **D-16:** 新增 `state["conflict_engine"]` 子对象，7 个字段
- **D-17:** `init_drama_state()` 初始化 `conflict_engine` 子对象
- **D-18:** `load_progress()` 兼容旧存档
- **D-19:** 新建 `app/conflict_engine.py` 模块

### Claude's Discretion
- 4 个评分信号的具体权重微调
- 对话重复度的具体计算方式（文本哈希 vs 关键词提取 vs 简单字符串匹配）
- 冲突模板中 `prompt_hint` 的具体措辞
- `inject_conflict()` 返回的结构化建议的精确字段
- 张力评分结果呈现给用户的格式
- `tension_history` 的保留条数（20 条为默认，可调整）
- 活跃冲突的 `id` 生成策略
- 导演 prompt §8 的具体措辞和长度

### Deferred Ideas (OUT OF SCOPE)
- LLM 辅助的张力评分
- 自适应权重调整
- 用户自定义冲突模板
- 高张力冷却机制（v2 CONFLICT-06）
- 冲突解决指引
- 张力曲线可视化
- 冲突模板的 LLM 生成
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONFLICT-01 | 张力评分——每场结束后自动评估当前剧情张力水平（0-100），基于：角色冲突强度、未决事件数量、情绪对立程度 | `evaluate_tension()` 实现 4 信号加权计算：情感方差(30%)、未决冲突密度(30%)、对话重复度(20%)、距上次注入场次数(20%)。所有信号从 state 直接读取 |
| CONFLICT-02 | 低张力自动注入——张力评分低于阈值时，自动生成转折事件并融入剧情 | `inject_conflict()` 实现"导演建议"模式，返回结构化冲突建议。D-09 渐进升级：连续低张力时 urgency 递增。D-10 活跃冲突上限 4 条 |
| CONFLICT-03 | 冲突模板库——预置多种冲突类型模板 | `CONFLICT_TEMPLATES` Python 常量字典，7 种类型（D-07），每种含 name/description/prompt_hint/suggested_emotions |
| CONFLICT-04 | 冲突去重——记录近期已使用的冲突类型，避免连续注入相同类型 | `used_conflict_types` 列表记录 `{type, scene_used}`，D-08 8 场去重窗口。注入前检查间隔 < 8 则跳过 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | 核心语言 | 项目要求 >=3.10 [VERIFIED: pyproject.toml] |
| google-adk | >=1.15.0 | ToolContext, Agent 框架 | 项目基础框架 [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.3.4 | 单元测试 | 所有新函数测试 [VERIFIED: pyproject.toml] |
| ruff | >=0.4.6 | 代码格式化和 lint | 每次提交前 [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 简单字符串前缀匹配(对话重复度) | difflib.SequenceMatcher | difflib 更精确但更慢；前 20 字匹配已足够检测明显重复 [ASSUMED] |
| Python 常量字典(冲突模板) | YAML/JSON 配置文件 | 常量字典零依赖、类型安全；文件配置更灵活但增加 I/O 和解析复杂度 [ASSUMED] |

**Installation:**
无新依赖需要安装——Phase 6 纯粹使用 Python stdlib + 已有项目依赖。

**Version verification:** 无需新增包。

## Architecture Patterns

### Recommended Project Structure
```
app/
├── conflict_engine.py    # 新增：张力评分 + 冲突注入核心逻辑
├── tools.py              # 修改：新增 evaluate_tension + inject_conflict 两个 Tool
├── agent.py              # 修改：tools 列表注册 + prompt §8
├── context_builder.py    # 修改：新增 _build_tension_section + 扩展 _build_conflict_section
├── state_manager.py      # 修改：init + load 兼容
└── memory_manager.py     # 只读参考：detect_importance 和 CRITICAL_REASONS 复用模式
tests/unit/
├── test_conflict_engine.py  # 新增：核心逻辑测试
└── conftest.py              # 修改：新增 conflict_engine 相关 fixture
```

### Pattern 1: 纯计算模块（无 LLM 调用）
**What:** `conflict_engine.py` 是纯启发式计算模块，所有函数都是确定性纯函数或简单 state 读写，不涉及 LLM 调用。
**When to use:** 张力评分、冲突选择、去重检查、冲突建议生成。
**Example:**
```python
# Source: 遵循 memory_manager.py 的 detect_importance() 模式
def evaluate_tension(state: dict) -> dict:
    """纯启发式张力评分，4 信号加权计算。"""
    signals = {
        "emotion_variance": _calc_emotion_variance(state),    # 30%
        "unresolved_density": _calc_unresolved_density(state), # 30%
        "dialogue_repetition": _calc_dialogue_repetition(state), # 20%
        "scenes_since_inject": _calc_scenes_since_inject(state), # 20%
    }
    score = (
        signals["emotion_variance"] * 0.30
        + signals["unresolved_density"] * 0.30
        + signals["dialogue_repetition"] * 0.20
        + signals["scenes_since_inject"] * 0.20
    )
    tension_score = int(score * 100)  # 0-100
    is_boring = tension_score < 30
    return {"tension_score": tension_score, "is_boring": is_boring, "signals": signals}
```

### Pattern 2: Tool 函数封装（薄代理）
**What:** `tools.py` 中的 `evaluate_tension()` 和 `inject_conflict()` 是薄代理，负责 state 读写和调用 `conflict_engine.py` 核心逻辑。
**When to use:** 所有导演可调用的 Tool 函数。
**Example:**
```python
# Source: 遵循 auto_advance() / steer_drama() 的签名和返回格式模式
def evaluate_tension(tool_context: ToolContext) -> dict:
    """Evaluate current drama tension level based on heuristic signals.

    基于启发式规则评估当前剧情张力，无需 LLM 调用。

    Args:
        tool_context: Tool context for state access.

    Returns:
        dict with tension_score (0-100), is_boring, suggested_action, signals.
    """
    from .conflict_engine import calculate_tension
    state = _get_state(tool_context)
    result = calculate_tension(state)
    # Update state
    state.setdefault("conflict_engine", {})
    state["conflict_engine"]["tension_score"] = result["tension_score"]
    state["conflict_engine"]["is_boring"] = result["is_boring"]
    _set_state(state, tool_context)
    return {"status": "success", **result}
```

### Pattern 3: 导演上下文段落（priority-based section）
**What:** `context_builder.py` 新增 `_build_tension_section()`，遵循已有的 `_build_*_section()` 模式。
**When to use:** 所有需要注入导演上下文的信息段落。
**Example:**
```python
# Source: 遵循 _build_steer_section() / _build_auto_advance_section() 模式
def _build_tension_section(state: dict) -> dict:
    conflict_engine = state.get("conflict_engine")
    if not conflict_engine:
        return {"key": "tension", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["tension"], "truncatable": False}
    score = conflict_engine.get("tension_score", 0)
    is_boring = conflict_engine.get("is_boring", False)
    active_count = len(conflict_engine.get("active_conflicts", []))
    consecutive_low = conflict_engine.get("consecutive_low_tension", 0)
    label = "低张力⚠️" if is_boring else ("高张力🔥" if score > 70 else "正常")
    text = f"【张力状态】\n当前张力：{score}/100（{label}） | 活跃冲突：{active_count} 条 | 连续低张力：{consecutive_low} 场"
    return {"key": "tension", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["tension"], "truncatable": False}
```

### Anti-Patterns to Avoid
- **在 `evaluate_tension()` 中调用 LLM：** CONTEXT.md D-01 明确禁止。所有评分必须基于可从 state 直接计算的启发式信号。
- **`inject_conflict()` 直接修改剧情内容：** D-05 明确为"导演建议"模式，只返回结构化建议，由导演 LLM 决定如何融入。
- **在 `conflict_engine.py` 中直接操作 `tool_context`：** 与 `memory_manager.py` 的设计一致，核心逻辑接收 `state: dict` 参数，`tool_context` 操作留给 `tools.py` 层。
- **硬编码情绪到权重映射在多处：** `_EMOTION_WEIGHTS` 应定义为模块级常量，与 `context_builder.py` 的 `_EMOTION_CN` 同级，避免散落。
- **忘记 `load_progress()` 的旧存档兼容：** D-18 要求缺少 `conflict_engine` 时自动初始化默认值。使用 `setdefault()` 模式（参考 Phase 5 D-28）。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 情绪→数值映射 | 自定义情绪解析器 | `_EMOTION_WEIGHTS` 常量字典 | 已有 `_EMOTION_CN` 映射，扩展即可；中文情绪词有限且确定 |
| 冲突模板 | LLM 动态生成模板 | `CONFLICT_TEMPLATES` 常量字典 | D-06 明确禁止 LLM 生成；7 种类型足够，硬编码更可控 |
| 未决事件统计 | 重新解析 working_memory | `critical_memories` 中 `reason="未决事件"` 的条目 + `arc_summary.structured.unresolved` | Phase 1 已实现关键记忆分类，复用已有数据 |
| 情绪枚举 | 自定义枚举类 | 字符串常量 + 映射字典 | 与现有 `emotions` 字段保持一致（纯字符串），无需引入 enum |

**Key insight:** Phase 6 的核心计算（张力评分、冲突选择）所需的所有输入数据已存在于 state 中：`actors[].emotions`、`actors[].critical_memories`、`actors[].arc_summary.structured.unresolved`、`actors[].working_memory`、`conflict_engine.last_inject_scene`。无需新增数据采集逻辑。

## Common Pitfalls

### Pitfall 1: 张力评分始终偏高或偏低（校准问题）
**What goes wrong:** 4 个信号的归一化范围不一致，导致加权后评分偏向某一极端。例如情感方差原始值可能 0-4，而对话重复度 0-1，加权后情感方差主导。
**Why it happens:** 每个信号的计算方式不同，输出范围不同，需要统一归一化到 0-1 再加权。
**How to avoid:** 每个信号函数必须返回 0-1 范围的 float。情感方差通过除以理论最大值归一化；未决冲突密度通过除以上限归一化；对话重复度天然 0-1；距上次注入通过衰减函数归一化。
**Warning signs:** 测试中张力评分始终 > 80 或 < 20；`is_boring` 从未/始终为 True。

### Pitfall 2: 对话重复度误判
**What goes wrong:** 短文本前 20 字匹配过于敏感，导致正常场景被判定为重复。例如两个角色在不同场景都说"我明白了"——前 20 字相同但语义完全不同。
**Why it happens:** 简单字符串前缀匹配无法区分上下文不同但措辞相似的对话。
**How to avoid:** CONTEXT.md specifics 中建议"前 20 字相同的条目占比"——这是对最近 3 场 working_memory 的统计，而非全局。占比阈值应设置保守（如 > 0.6 才判定为重复），避免误判。可考虑使用前 20 字 + 角色名的组合作为匹配键。
**Warning signs:** `dialogue_repetition` 信号值始终 > 0.5；在剧情明显有变化的场景中仍被判为重复。

### Pitfall 3: 冲突注入后 `used_conflict_types` 不更新
**What goes wrong:** `inject_conflict()` 返回建议但未更新 `used_conflict_types`，导致下次仍可能选择同一类型。
**Why it happens:** 忘记在 `inject_conflict()` 中追加 `{type, scene_used}` 记录。
**How to avoid:** 在 `inject_conflict()` 的成功路径中，始终追加 `used_conflict_types` 记录并持久化 state。添加测试用例验证去重生效。
**Warning signs:** 连续注入相同类型的冲突；`used_conflict_types` 列表为空。

### Pitfall 4: `tension_history` 无限增长
**What goes wrong:** 每场评分都追加到 `tension_history`，长时间运行后列表过长，state.json 膨胀。
**Why it happens:** D-04 指定保留最近 20 场，但未强制裁剪。
**How to avoid:** 在追加新记录后，检查长度并裁剪到 20 条：`state["conflict_engine"]["tension_history"] = state["conflict_engine"]["tension_history"][-20:]`。
**Warning signs:** state.json 中 `tension_history` 超过 20 条。

### Pitfall 5: 导演不调用 `evaluate_tension()`
**What goes wrong:** 虽然注册了工具并在 prompt 中引导，但 LLM 可能忽略 §8 指引，从不主动调用张力评分。
**Why it happens:** LLM 对 tool 的调用依赖于 prompt 的强调程度；如果 §8 在长 prompt 中不够突出，可能被忽略。
**How to avoid:** (1) §8 放在 prompt 前半部分，紧接 §1 核心循环协议；(2) 在 `write_scene()` 返回值中附加张力评分提醒："💡 建议调用 evaluate_tension() 检查张力水平"；(3) `_build_tension_section()` 在 is_boring=True 时使用醒目标记。
**Warning signs:** 多场后 `tension_history` 为空；导演从不调用 `evaluate_tension()`。

### Pitfall 6: 活跃冲突不解决导致上限阻塞
**What goes wrong:** 活跃冲突达到 4 条后，`inject_conflict()` 只返回"上限已满"建议，但导演不知道该解决哪条冲突，导致永久无法注入新冲突。
**Why it happens:** D-10 只说返回建议，但没有机制帮助导演选择解决哪条冲突。
**How to avoid:** 在返回"上限已满"建议时，附带最旧/最不活跃冲突的提示："建议优先解决：{conflict.description}（已持续 {scenes} 场）"。这是 Claude's Discretion 范围内的优化。
**Warning signs:** 连续多场无法注入新冲突；`active_conflicts` 始终为 4 条。

### Pitfall 7: `_build_conflict_section()` 与 `_build_tension_section()` 信息重复
**What goes wrong:** 张力段落包含活跃冲突列表，冲突段落也显示活跃冲突，导致导演上下文中信息重复浪费 token。
**Why it happens:** 两个 section 都读取 `conflict_engine.active_conflicts`。
**How to avoid:** 明确分工：`_build_tension_section()` 显示张力评分+统计摘要（"活跃冲突：2 条"），`_build_conflict_section()` 显示每条冲突的详细信息（类型、描述、涉及角色）。张力段落不展开冲突详情。
**Warning signs:** 导演上下文中活跃冲突信息出现两次。

## Code Examples

Verified patterns from existing codebase:

### 信号 1：情感方差计算
```python
# Source: 基于 context_builder.py 的 _EMOTION_CN 映射扩展
# 情绪 → 张力权重映射（CONTEXT.md specifics 中的建议值）
_EMOTION_WEIGHTS = {
    "neutral": 1,    # 平静
    "happy": 2,      # 喜悦
    "hopeful": 2,    # 充满希望
    "confused": 2,   # 困惑
    "anxious": 3,    # 焦虑
    "sad": 4,        # 悲伤
    "determined": 4, # 决绝
    "angry": 5,      # 愤怒
    "fearful": 5,    # 恐惧
}

def _calc_emotion_variance(state: dict) -> float:
    """计算所有演员情绪的方差，归一化到 0-1。"""
    actors = state.get("actors", {})
    if not actors:
        return 0.0  # 无演员时无法计算方差
    
    weights = []
    for name, data in actors.items():
        emotion = data.get("emotions", "neutral")
        weights.append(_EMOTION_WEIGHTS.get(emotion, 1))
    
    if len(weights) < 2:
        return 0.0
    
    mean = sum(weights) / len(weights)
    variance = sum((w - mean) ** 2 for w in weights) / len(weights)
    # 理论最大方差：所有人在极端情绪(5) vs 中性(1)，最大约 4.0
    # 归一化：variance / 4.0，clamp to [0, 1]
    return min(1.0, variance / 4.0)
```

### 信号 2：未决冲突密度
```python
# Source: 复用 _extract_scene_transition() 中未决事件提取逻辑
def _calc_unresolved_density(state: dict) -> float:
    """计算未决冲突密度，归一化到 0-1。"""
    unresolved_count = 0
    for name, data in state.get("actors", {}).items():
        # 未决事件：critical_memories 中 reason="未决事件"
        for m in data.get("critical_memories", []):
            if m.get("reason") == "未决事件":
                unresolved_count += 1
        # arc_summary 中的 unresolved 列表
        arc = data.get("arc_summary", {}).get("structured", {})
        unresolved_count += len(arc.get("unresolved", []))
    
    # 加上 conflict_engine 中的活跃冲突
    conflict_engine = state.get("conflict_engine", {})
    unresolved_count += len(conflict_engine.get("active_conflicts", []))
    
    # 归一化：5 个未决冲突视为"高密度"，超过 5 饱和
    return min(1.0, unresolved_count / 5.0)
```

### 信号 3：对话重复度
```python
# Source: CONTEXT.md specifics 建议"前 20 字相同的条目占比"
def _calc_dialogue_repetition(state: dict) -> float:
    """计算最近 3 场对话重复度，0=无重复，1=完全重复。"""
    current_scene = state.get("current_scene", 0)
    if current_scene < 2:
        return 0.0  # 场景太少无法判断
    
    # 收集最近 3 场的 working_memory 条目
    recent_entries = []
    for name, data in state.get("actors", {}).items():
        for e in data.get("working_memory", [])[-5:]:
            scene = e.get("scene", 0)
            if current_scene - scene <= 3:
                entry_text = e.get("entry", "")[:20]
                if entry_text:
                    recent_entries.append(entry_text)
    
    if len(recent_entries) < 2:
        return 0.0
    
    # 计算重复比例
    seen = set()
    duplicates = 0
    for entry in recent_entries:
        if entry in seen:
            duplicates += 1
        seen.add(entry)
    
    repetition_ratio = duplicates / len(recent_entries)
    # 反转：重复度越高 → 张力越低 → 返回 (1 - repetition_ratio)
    return 1.0 - repetition_ratio
```

### 信号 4：距上次注入场次数
```python
# Source: D-01 信号 4 和 D-16 的 last_inject_scene 字段
def _calc_scenes_since_inject(state: dict) -> float:
    """计算距上次冲突注入的场景衰减值，0=刚注入，1=很久没注入。"""
    conflict_engine = state.get("conflict_engine", {})
    last_inject = conflict_engine.get("last_inject_scene", 0)
    current_scene = state.get("current_scene", 0)
    
    gap = current_scene - last_inject
    
    # 衰减函数：gap=0 → 0, gap=8 → 0.5, gap=16+ → 1.0
    # 使用 sigmoid-like 衰减
    if gap <= 0:
        return 0.0
    return min(1.0, gap / 16.0)
```

### 冲突模板常量结构
```python
# Source: D-06, D-07 定义
CONFLICT_TEMPLATES = {
    "new_character": {
        "name": "新角色登场",
        "description": "引入新角色打破现有格局",
        "prompt_hint": "一个陌生的身影出现在故事中——他/她的到来将打破现有的平衡",
        "suggested_emotions": ["anxious", "confused", "determined"],
    },
    "secret_revealed": {
        "name": "秘密发现",
        "description": "隐藏信息被揭露，改变角色关系",
        "prompt_hint": "一个被深藏的秘密浮出水面——真相将重新定义所有人之间的关系",
        "suggested_emotions": ["fearful", "angry", "sad"],
    },
    # ... 其余 5 种类型
}
```

### inject_conflict 返回结构
```python
# Source: CONTEXT.md specifics 中的建议
{
    "conflict_id": "conflict_5_escalation_1",
    "type": "escalation",
    "type_cn": "矛盾升级",
    "description": "现有分歧已到临界点——一个小火星就可能引爆全面对抗",
    "prompt_hint": "矛盾已经无法调和，冲突即将全面爆发",
    "involved_actors": ["朱棣", "道衍"],  # 从 active conflicts 推断
    "urgency": "normal",  # normal / high / critical
    "suggested_emotions": ["angry", "determined"],
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM 张力评分 | 纯启发式规则 | Phase 6 设计决策 | 零延迟、零 token 成本、确定性输出 |
| 强制冲突注入 | "导演建议"模式 | Phase 6 D-05 | 保留创意灵活性，导演 LLM 自由发挥 |
| 固定冲突类型 | 7 种类型 + 8 场去重 | Phase 6 D-07/D-08 | 防止重复，保持新鲜感 |
| 无冲突追踪 | active_conflicts 列表 + 上限 4 | Phase 6 D-10 | 防止冲突过载，drama fatigue |

**Deprecated/outdated:**
- REQUIREMENTS.md 中 CONFLICT-01 提到"0-10 评分范围"：已被 CONTEXT.md D-02 更新为 0-100 范围，提供更细粒度。实现时以 D-02 为准。

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 情感方差理论最大值约 4.0（5 vs 1 的极端情况） | 信号 1 归一化 | 归一化范围不准确，评分偏高/偏低 |
| A2 | 5 个未决冲突视为"高密度"饱和点 | 信号 2 归一化 | 如果实际冲突数远大于 5，信号永远饱和 |
| A3 | 前 20 字匹配足以检测对话重复 | 信号 3 计算 | 可能误判（短句相同但语义不同）或漏判（换词但语义重复） |
| A4 | 16 场衰减周期是合理的（信号 4） | 信号 4 衰减函数 | 如果实际需要更快/更慢的衰减，评分响应不匹配 |
| A5 | 导演 LLM 会遵循 §8 指引主动调用 evaluate_tension() | Prompt 集成 | 如果 LLM 忽略指引，张力评分系统形同虚设 |
| A6 | 冲突建议的 `involved_actors` 可从 active_conflicts 和 arc_summary 推断 | inject_conflict 实现 | 如果推断不准，建议的角色不合适 |

**需要用户确认的关键假设：** A1-A4 的归一化参数（4.0, 5, 20字, 16场）均属于 Claude's Discretion 中的"权重微调"范畴，初始值可在实现后通过测试校准。

## Open Questions (RESOLVED)

1. **对话重复度计算的精确方案** — RESOLVED: 使用前 20 字 + 角色名作为匹配键
   - What we know: CONTEXT.md specifics 建议"前 20 字相同的条目占比"，属于 Claude's Discretion
   - Resolution: Plan 06-01 选用"前 20 字 + 角色名"组合匹配键，降低"我明白了"等短句误判

2. **`inject_conflict()` 的 `involved_actors` 选择策略** — RESOLVED: 选择情绪最强烈的 2 个角色
   - What we know: 返回结构需要包含涉及角色
   - Resolution: Plan 06-01 选择当前情绪权重最高的 2 个角色作为 involved_actors

3. **导演 prompt §8 的具体措辞** — RESOLVED: 简短 3-5 行指引，紧接 §1 之后
   - What we know: 需要引导导演每场 write_scene 后调用 evaluate_tension()
   - Resolution: Plan 06-02 提供完整 §8 措辞，参考 Phase 5 §2 自动推进协议风格

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies identified — Phase 6 uses only Python stdlib and existing project dependencies)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.3.4 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/test_conflict_engine.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONFLICT-01 | evaluate_tension 返回 0-100 评分 + is_boring + signals | unit | `pytest tests/unit/test_conflict_engine.py::TestEvaluateTension -x` | ❌ Wave 0 |
| CONFLICT-01 | 情感方差计算正确 | unit | `pytest tests/unit/test_conflict_engine.py::TestCalcEmotionVariance -x` | ❌ Wave 0 |
| CONFLICT-01 | 未决冲突密度计算正确 | unit | `pytest tests/unit/test_conflict_engine.py::TestCalcUnresolvedDensity -x` | ❌ Wave 0 |
| CONFLICT-01 | 对话重复度计算正确 | unit | `pytest tests/unit/test_conflict_engine.py::TestCalcDialogueRepetition -x` | ❌ Wave 0 |
| CONFLICT-01 | 距上次注入衰减计算正确 | unit | `pytest tests/unit/test_conflict_engine.py::TestCalcScenesSinceInject -x` | ❌ Wave 0 |
| CONFLICT-02 | is_boring=True 时 inject_conflict 返回建议 | unit | `pytest tests/unit/test_conflict_engine.py::TestInjectConflict -x` | ❌ Wave 0 |
| CONFLICT-02 | 连续低张力渐进升级 | unit | `pytest tests/unit/test_conflict_engine.py::TestConsecutiveLowTension -x` | ❌ Wave 0 |
| CONFLICT-02 | 活跃冲突上限 4 条 | unit | `pytest tests/unit/test_conflict_engine.py::TestActiveConflictLimit -x` | ❌ Wave 0 |
| CONFLICT-03 | 7 种冲突模板结构完整 | unit | `pytest tests/unit/test_conflict_engine.py::TestConflictTemplates -x` | ❌ Wave 0 |
| CONFLICT-04 | 同类型 8 场去重 | unit | `pytest tests/unit/test_conflict_engine.py::TestConflictDedup -x` | ❌ Wave 0 |
| CONFLICT-04 | used_conflict_types 正确更新 | unit | `pytest tests/unit/test_conflict_engine.py::TestUsedConflictTypesUpdate -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_conflict_engine.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_conflict_engine.py` — covers CONFLICT-01~04
- [ ] `tests/unit/conftest.py` — add conflict_engine fixtures (mock_tool_context with conflict_engine sub-dict)
- [ ] `tests/unit/test_context_builder.py` — add tests for _build_tension_section
- [ ] `tests/unit/test_tools_phase6.py` — test evaluate_tension + inject_conflict tool wrappers

## Security Domain

> Phase 6 无外部输入、无网络调用、无用户数据处理。张力评分和冲突注入均为纯内部计算。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Tool 参数类型检查（conflict_type 必须在 CONFLICT_TEMPLATES 中） |
| V6 Cryptography | no | — |

### Known Threat Patterns for Tension/Conflict Engine

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 注入非法 conflict_type | Tampering | `inject_conflict()` 验证 conflict_type 在 CONFLICT_TEMPLATES.keys() 中 |
| 超长 entry text 注入 | Tampering | working_memory entry 已有 ENTRY_TEXT_MAX_LENGTH=500 限制（Phase 1） |
| state 篡改导致评分异常 | Tampering | 评分函数对所有输入做防御性读取（`.get()` + 默认值） |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/06-tension-scoring-conflict-engine/06-CONTEXT.md` — 19 条锁定决策 (D-01~D-19)
- `.planning/REQUIREMENTS.md` — CONFLICT-01~04 需求定义
- `.planning/ROADMAP.md` — Phase 6 成功标准
- `app/context_builder.py` — 现有导演上下文构建模式
- `app/tools.py` — 现有 Tool 函数签名和返回格式
- `app/agent.py` — _improv_director prompt 和 tools 列表
- `app/state_manager.py` — init_drama_state + load_progress 兼容模式
- `app/memory_manager.py` — detect_importance 和 CRITICAL_REASONS 参考模式
- `.planning/codebase/CONVENTIONS.md` — 编码规范

### Secondary (MEDIUM confidence)
- `.planning/research/PITFALLS.md` — Pitfall 5/6/8/9 与冲突引擎相关
- `.planning/research/ARCHITECTURE.md` — 架构演进设计
- `tests/unit/conftest.py` — 测试 fixture 模式
- `tests/unit/test_tools_phase5.py` — Phase 5 测试模式参考

### Tertiary (LOW confidence)
- 归一化参数（4.0, 5, 20字, 16场）基于训练知识 [ASSUMED] — 需实测校准

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 无新依赖，纯 Python stdlib + 已有项目框架
- Architecture: HIGH — 所有模式均有现有代码参考，CONTEXT.md 决策完整
- Pitfalls: HIGH — 基于 PITFALLS.md 和代码分析，7 个常见陷阱已识别

**Research date:** 2026-04-12
**Valid until:** 2026-05-12（稳定领域，30 天有效）
