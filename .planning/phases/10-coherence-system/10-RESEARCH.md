# Phase 10: Coherence System - Research

**Researched:** 2026-04-13
**Domain:** 一致性检查与矛盾修复（LLM 语义检测 + 启发式预筛选 + Prompt 锚点）
**Confidence:** HIGH

## Summary

Phase 10 实现"逻辑不断"的核心承诺，包含四个需求：一致性检查（COHERENCE-01）、关键事实追踪（COHERENCE-02）、角色一致性（COHERENCE-03）、矛盾修复（COHERENCE-04）。技术方案已由 CONTEXT.md D-01 至 D-39 完整锁定——两阶段检查（启发式预筛选 + LLM 语义判断）、导演手动添加事实、Prompt 锚点角色约束、导演建议模式矛盾修复。

项目已有成熟的模式可直接复用：`conflict_engine.py` 的纯函数模式、`arc_tracker.py` 的手动 Tool 创建模式（`create_thread_logic` → `create_thread`）、`dynamic_storm.py` 的 LLM prompt + async 调用模式。`context_builder.py` 中 `_build_facts_section()` 已有前向兼容空壳，`_DIRECTOR_SECTION_PRIORITIES` 中 `"facts": 5` 已就绪，`build_actor_context_from_memory()` 中已有优先级段落组装模式。Phase 10 的实现本质上是将现有模式组装应用到新领域——事实追踪和一致性检查。

**Primary recommendation:** 严格遵循已锁定决策，按照 `conflict_engine.py` + `arc_tracker.py` + `dynamic_storm.py` 三者组合模式构建 `coherence_checker.py`，新增 3 个 Tool 函数走 `create_thread` 式薄代理模式，LLM 调用走 `dynamic_storm` 式 `async` + `_call_llm` 模式。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01~D-05:** 事实数据结构——结构化对象列表，5 种 category，3 级 importance，fact_{scene}_{keyword}_{index} ID 生成
- **D-06~D-11:** 事实创建方式——导演手动为主，`add_fact(fact, category, importance, tool_context)` Tool，LLM 不自动提取，前 20 字 80% 重叠去重，MAX_FACTS=50
- **D-12~D-17:** 一致性检查——LLM 驱动 + 启发式预筛选两阶段，不使用纯启发式，检查频率每 5 场，预筛选 3 条规则
- **D-18~D-22:** 矛盾修复——三级严重度（high/medium/low），补充式 + 修正式修复，导演建议模式不自动执行，`repair_contradiction(fact_id, repair_type, tool_context)` Tool
- **D-23~D-27:** 角色一致性——Prompt 注入方式，`build_actor_context_from_memory()` 新增角色锚点段落，锚点优先级 7
- **D-28~D-30:** 导演上下文集成——升级 `_build_facts_section()`，facts 优先级保持 5，新增 §11 一致性保障段落
- **D-31~D-35:** 状态持久化——`state["established_facts"]` + `state["coherence_checks"]`，`init_drama_state()` 初始化，`load_progress()` 兼容旧存档
- **D-36:** 新建 `app/coherence_checker.py` 模块
- **D-37~D-39:** 3 个 Tool 函数——`validate_consistency`、`add_fact`、`repair_contradiction`

### Claude's Discretion
- `validate_consistency()` 中 LLM prompt 的精确措辞和长度
- `generate_repair_narration_prompt()` 的精确措辞
- `_extract_actor_names()` 的实现方式（简单字符串匹配 vs 关键词提取）
- `_check_fact_overlap()` 的重叠度阈值和计算方式
- `_build_facts_section()` 的精确格式和排版
- 导演 prompt §11 的具体措辞和长度
- 角色锚点段落的精确格式
- `COHERENCE_CHECK_INTERVAL` 的精确值（默认 5，可调整）
- `MAX_FACTS` 的精确值（默认 50，可调整）
- `check_history` 的保留条数上限
- `validate_consistency()` LLM 调用的 model 选择（是否使用与主 Agent 不同的模型）

### Deferred Ideas (OUT OF SCOPE)
- LLM 自动提取事实
- 自适应检查频率
- 事实影响力追踪
- 事实过期机制
- 角色行为一致性自动检测
- 矛盾严重度自动评分
- 跨场景时间线验证（Phase 11）
- 事实的可视化
- 用户自定义一致性规则
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COHERENCE-01 | 一致性检查 — 新场景生成前检查与已确立事实的矛盾 | D-12~D-17 锁定两阶段策略；启发式预筛选纯函数可参考 `_filter_relevant_facts` 模式；LLM 语义检查参考 `discover_perspectives_prompt` + `_call_llm` async 模式 |
| COHERENCE-02 | 关键事实追踪 — 维护"已确立事实"清单 | D-01~D-11 锁定结构化对象 + 导演手动添加；参考 `create_thread_logic` 纯函数 + `create_thread` Tool 薄代理模式 |
| COHERENCE-03 | 角色一致性 — 确保演员行为符合性格定义和累积记忆 | D-23~D-27 锁定 Prompt 注入方式；参考 `_assemble_actor_sections` 优先级段落组装模式；锚点优先级 7（最高） |
| COHERENCE-04 | 矛盾修复 — 检测到逻辑矛盾时生成修复性旁白 | D-18~D-22 锁定三级严重度 + 导演建议模式；参考 `dynamic_storm` LLM prompt + async 调用模式；`generate_repair_narration_prompt` 纯函数 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-adk | >=1.15.0,<2.0.0 | Agent framework + ToolContext + Tool 定义 | 项目核心框架 [VERIFIED: pyproject.toml] |
| pytest | >=8.3.4,<9.0.0 | 单元测试 | 项目测试框架 [VERIFIED: pyproject.toml] |
| pytest-asyncio | >=0.23.8,<1.0.0 | 异步测试 | validate_consistency 是 async Tool [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re | stdlib | 关键词提取（中文 2-4 字匹配） | `_extract_actor_names` / fact_id 生成 |
| json | stdlib | LLM 响应解析 | `validate_consistency` 返回结构化矛盾 |
| datetime | stdlib | 时间戳 | fact.added_at |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 手动 `_call_llm` | ADK 内置 Agent LLM 调用 | `_call_llm` 已是项目标准模式，ADK Agent 调用在 Tool 内不可用 |
| 简单字符串匹配 `_extract_actor_names` | jieba 分词 | 分词引入依赖且对短句过度分析，字符串匹配对角色名匹配已足够 [CITED: CONTEXT.md D-09] |
| 前缀重叠 `_check_fact_overlap` | fuzzywuzzy 模糊匹配 | 模糊匹配引入依赖且可能误判中文短语，前 20 字字符重叠率已足够 [CITED: CONTEXT.md D-10] |

**Installation:** 无新依赖——Phase 10 仅使用 Python 标准库 + 项目已有依赖。

## Architecture Patterns

### Recommended Project Structure
```
app/
├── coherence_checker.py    # 新增——纯函数核心模块
├── tools.py                # 修改——新增 3 个 Tool 函数
├── agent.py                # 修改——tools 列表 + prompt §11
├── context_builder.py      # 修改——_build_facts_section + 角色锚点段落
├── state_manager.py        # 修改——init + load 兼容
├── conflict_engine.py      # 参考——纯函数模式
├── arc_tracker.py          # 参考——手动 Tool 创建模式
└── dynamic_storm.py        # 参考——LLM prompt + async 模式
tests/
└── unit/
    ├── test_coherence_checker.py   # 新增——纯函数测试
    └── test_tools_phase10.py       # 新增——Tool 函数测试
```

### Pattern 1: 纯函数核心 + Tool 薄代理
**What:** 核心逻辑在纯函数中（state: dict in, dict out），Tool 函数仅做状态读写代理
**When to use:** 所有需要 ToolContext 的功能
**Example:**
```python
# coherence_checker.py — 纯函数
def add_fact_logic(fact: str, category: str, importance: str, state: dict) -> dict:
    """Pure function — no ToolContext dependency."""
    established_facts = state.get("established_facts", [])
    # ... 去重、ID 生成、验证 ...
    established_facts.append(new_fact)
    state["established_facts"] = established_facts
    return {"status": "success", "fact_id": new_fact["id"], ...}

# tools.py — 薄代理
def add_fact(fact: str, category: str = "event", importance: str = "medium", tool_context: ToolContext) -> dict:
    """Tool function — thin proxy."""
    state = _get_state(tool_context)
    result = add_fact_logic(fact, category, importance, state)
    if result["status"] == "success":
        _set_state(state, tool_context)
    return result
```
Source: [VERIFIED: arc_tracker.py `create_thread_logic` → tools.py `create_thread` 模式]

### Pattern 2: LLM Prompt 纯函数 + Async Tool 调用
**What:** LLM prompt 构建为纯函数返回字符串，Tool 函数中 async 调用 `_call_llm`
**When to use:** 一致性检查、修复旁白生成等需要 LLM 的场景
**Example:**
```python
# coherence_checker.py — prompt 纯函数
def validate_consistency_prompt(facts: list[dict], recent_scenes: list[dict]) -> str:
    """Build LLM prompt for consistency check."""
    sections = []
    sections.append("对比以下已确立事实与近期场景内容...")
    # ... 构建事实列表 + 场景内容 ...
    return "\n\n".join(sections)

# tools.py — async Tool
async def validate_consistency(tool_context: ToolContext) -> dict:
    """Trigger consistency check with LLM."""
    state = _get_state(tool_context)
    relevant_facts = _filter_relevant_facts(state)
    if not relevant_facts:
        return {"status": "success", "message": "✅ 无需检查", ...}
    prompt = validate_consistency_prompt(relevant_facts, recent_scenes)
    response_text = await _call_llm(prompt)
    # ... 解析 + 更新状态 ...
```
Source: [VERIFIED: dynamic_storm.py `discover_perspectives_prompt` → tools.py `async def dynamic_storm`]

### Pattern 3: 导演上下文段落组装
**What:** 通过 `_build_*_section(state)` 函数返回 section dict，由 `_assemble_director_sections` 按优先级排序
**When to use:** 导演上下文中新增段落
**Example:**
```python
def _build_facts_section(state: dict) -> dict:
    """Build established facts section for director context."""
    # ... 构建文本 ...
    return {
        "key": "facts",
        "text": text,
        "priority": _DIRECTOR_SECTION_PRIORITIES["facts"],  # 5
        "truncatable": True,
    }
```
Source: [VERIFIED: context_builder.py L824-845 现有空壳 + L60-74 优先级定义]

### Pattern 4: 演员上下文段落组装
**What:** 通过 `_assemble_actor_sections` 中按优先级添加 section dict
**When to use:** 演员上下文中新增角色锚点段落
**Example:**
```python
# Phase 10 新增——在 _assemble_actor_sections 中
# 角色 DNA 锚点 (priority 7, never truncated — D-26)
actor_dna_text = _build_actor_dna_section(actor_name, actor_data, tool_context)
if actor_dna_text:
    sections.append({
        "key": "actor_dna",
        "text": actor_dna_text,
        "priority": 7,  # D-26: 最高优先级
        "truncatable": False,
    })
```
Source: [VERIFIED: context_builder.py L220-230 anchor 段落模式]

### Pattern 5: ID 生成策略对齐
**What:** `fact_{scene}_{keyword}_{index}` 格式，与 `thread_`、`conflict_`、`storm_` 模式一致
**When to use:** 事实 ID 生成
**Example:**
```python
import re
match = re.search(r'[\u4e00-\u9fff]{2,4}', fact)
keyword = match.group(0) if match else "fact"
prefix = f"fact_{current_scene}_{keyword}"
existing_count = sum(1 for f in established_facts if f.get("id", "").startswith(prefix))
index = existing_count + 1
fact_id = f"fact_{current_scene}_{keyword}_{index}"
```
Source: [VERIFIED: arc_tracker.py L78-87 create_thread_logic ID 生成]

### Anti-Patterns to Avoid
- **在纯函数中依赖 ToolContext:** 所有 `*_logic` 函数只接受 `state: dict`，不引用 `tool_context`。测试时无需 mock ToolContext。[VERIFIED: conflict_engine.py, arc_tracker.py, dynamic_storm.py 均遵循此模式]
- **自动执行矛盾修复:** 矛盾修复必须由导演决定，不自动执行。与全系统"导演建议模式"精神一致。[CITED: CONTEXT.md D-21]
- **LLM 自动提取事实:** 误提取比漏提取更有害，错误事实导致假阳性矛盾检测。[CITED: CONTEXT.md D-07]
- **纯启发式规则做矛盾检测:** "朱棣在南京" vs "朱棣已北上"是矛盾，"朱棣愤怒" vs "朱棣平静"可能是时间差。需要语义理解。[CITED: CONTEXT.md D-13]
- **在 validate_consistency 中同步调用 LLM:** `_call_llm` 是 async 函数，Tool 必须用 `async def`。[VERIFIED: memory_manager.py L147]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM API 调用 | 自建 httpx 调用 | `from .memory_manager import _call_llm` | 已有 LiteLlm + httpx 双层 fallback，项目标准 |
| 状态读写 | 直接操作 `tool_context.state` | `_get_state(tool_context)` / `_set_state(state, tool_context)` | 已有标准函数，自动持久化到磁盘 |
| JSON 解析 LLM 响应 | 自建 JSON 提取 | `dynamic_storm.py` 的 `parse_llm_perspectives` 模式（```json 块 + 纯 JSON 数组 fallback） | 已验证的解析模式 |
| 中文关键词提取 | jieba 分词 | `re.search(r'[\u4e00-\u9fff]{2,4}', text)` | 短文本分词引入不必要复杂度 |
| 事实去重 | 模糊匹配库 | 前 20 字字符重叠率 > 80% | 简单有效，与项目已有 overlap 检测模式对齐 |

**Key insight:** Phase 10 不引入任何新外部依赖，所有功能通过 Python 标准库 + 项目已有基础设施实现。

## Common Pitfalls

### Pitfall 1: LLM 一致性检查返回假阳性过多
**What goes wrong:** LLM 将合理的变化（角色情绪转变、时间推移）误判为矛盾，导致导演被大量虚假警告干扰
**Why it happens:** LLM prompt 没有明确区分"矛盾"和"合理变化"的边界
**How to avoid:** prompt 中明确矛盾定义："同一时间同一地点不可能同时为真"，且强调"仅报告确信的矛盾，忽略模糊或可解释的差异"（D-14 已锁定）
**Warning signs:** 导演频繁忽略 validate_consistency 结果；矛盾修复率极低；导演反馈"检查结果没用"

### Pitfall 2: 事实清单膨胀导致 token 超支
**What goes wrong:** 50 条事实 × 30 字/条 = 1500 字 ≈ 750 tokens，在导演上下文中占比可控，但如果 _build_facts_section 同时展示 low importance 事实，token 可能翻倍
**Why it happens:** 未按 importance 过滤展示
**How to avoid:** 仅展示 high/medium importance 事实（D-05/D-28 已锁定），MAX_FACTS=50 作为软上限
**Warning signs:** 导演上下文 token 预算超支；_build_facts_section 返回文本过长

### Pitfall 3: 启发式预筛选过度过滤导致漏检
**What goes wrong:** 预筛选条件太严格，将与当前场景相关但 actors 不交集的事实排除
**Why it happens:** 仅按 actors 交集 + category 关联度筛选，忽略了全局规则（如"魔法在满月时最强"可能影响任何场景）
**How to avoid:** D-16 已锁定：category="rule" 的事实始终检查，不受 actors 交集限制
**Warning signs:** 检查后仍然出现矛盾；导演发现事实检查"漏掉"了明显矛盾

### Pitfall 4: validate_consistency 在每场调用导致延迟
**What goes wrong:** 每场都做 LLM 一致性检查，每场增加 5-15 秒延迟
**Why it happens:** 检查频率过高或触发条件太宽松
**How to avoid:** D-17 已锁定每 5 场检查一次，通过 `_build_facts_section` 中的提醒行触发；导演也可主动调用
**Warning signs:** 场景推进延迟明显增加；用户抱怨系统变慢

### Pitfall 5: 角色 DNA 锚点段落被截断
**What goes wrong:** 演员上下文 token 超预算时，角色 DNA 段落被裁剪，失去角色一致性保障
**Why it happens:** 锚点段落 truncatable=True 或优先级不够高
**How to avoid:** D-26 已锁定：锚点段落优先级 7（最高），truncatable=False
**Warning signs:** 演员行为偏离性格定义；锚点段落不完整

### Pitfall 6: 旧存档加载时 established_facts/coherence_checks 缺失导致 KeyError
**What goes wrong:** 加载 Phase 10 之前保存的存档时，state 中没有 established_facts 和 coherence_checks 字段
**Why it happens:** 新增状态字段但未做向后兼容处理
**How to avoid:** D-33/D-34 已锁定：`init_drama_state()` 初始化 + `load_progress()` 中 `setdefault` 兜底
**Warning signs:** KeyError 崩溃；旧存档加载后功能异常

### Pitfall 7: repair_contradiction 后原始事实被修改/删除
**What goes wrong:** 修复矛盾时修改或删除了原始事实，失去审计轨迹
**Why it happens:** 修复逻辑直接修改 fact 字典
**How to avoid:** D-22 已锁定：不删除或修改原始事实，仅追加 `repair_note` 字段
**Warning signs:** 事实清单变短；修复历史无法追溯

### Pitfall 8: _check_fact_overlap 对中文短句误判
**What goes wrong:** "朱棣起兵" 和 "朱棣已起兵" 前 20 字重叠率 > 80% 被标记为重复，但它们确实可能是同一事实的两种表述
**Why it happens:** 前 20 字字符比较不考虑语义差异
**How to avoid:** D-10 已锁定：重叠仅产生提醒（返回提醒而非阻止），由导演决定是否仍然添加
**Warning signs:** 导演无法添加合法的相似事实；去重提醒过于频繁

## Code Examples

Verified patterns from project source:

### add_fact_logic 纯函数（参考 create_thread_logic）
```python
# Source: [VERIFIED: arc_tracker.py L52-106]
def add_fact_logic(fact: str, category: str, importance: str, state: dict) -> dict:
    """Add a new established fact. Pure function — state: dict in, dict out."""
    established_facts = state.get("established_facts", [])
    
    # Validate category
    if category not in FACT_CATEGORIES:
        return {"status": "error", "message": f"无效的事实类别: {category}"}
    
    # De-dup check (D-10)
    overlap = _check_fact_overlap(fact, established_facts)
    if overlap["is_duplicate"]:
        return {"status": "info", "message": f"⚠️ 可能重复：{overlap['overlapping_with']}", ...}
    
    # Extract actors from fact text (D-09)
    known_actors = list(state.get("actors", {}).keys())
    actors = _extract_actor_names(fact, known_actors)
    
    # Generate fact_id (D-04)
    current_scene = state.get("current_scene", 0)
    match = re.search(r'[\u4e00-\u9fff]{2,4}', fact)
    keyword = match.group(0) if match else "fact"
    prefix = f"fact_{current_scene}_{keyword}"
    existing_count = sum(1 for f in established_facts if f.get("id", "").startswith(prefix))
    index = existing_count + 1
    fact_id = f"fact_{current_scene}_{keyword}_{index}"
    
    # Check MAX_FACTS (D-11)
    if len(established_facts) >= MAX_FACTS:
        return {"status": "info", "message": f"⚠️ 事实已达上限 {MAX_FACTS} 条，建议清理低 importance 事实"}
    
    # Create fact object (D-01)
    new_fact = {
        "id": fact_id,
        "fact": fact,
        "category": category,
        "actors": actors,
        "scene": current_scene,
        "importance": importance,
        "added_at": datetime.now().isoformat(),
    }
    established_facts.append(new_fact)
    state["established_facts"] = established_facts
    
    return {"status": "success", "fact_id": fact_id, "fact": new_fact}
```

### LLM Prompt 构建（参考 discover_perspectives_prompt）
```python
# Source: [VERIFIED: dynamic_storm.py L44-145]
def validate_consistency_prompt(facts: list[dict], recent_scenes: list[dict]) -> str:
    """Build LLM prompt for consistency check (D-14)."""
    sections = []
    
    # Core instruction
    sections.append(
        "对比以下已确立事实与近期场景内容，判断是否存在逻辑矛盾。\n"
        "矛盾定义：与已确立事实直接冲突的陈述（同一时间同一地点不可能同时为真）\n"
        "非矛盾：时间推移导致的变化、角色视角差异、新信息的补充\n"
        "仅报告确信的矛盾，忽略模糊或可解释的差异"
    )
    
    # Facts list
    fact_lines = []
    for i, f in enumerate(facts, 1):
        fact_lines.append(f"{i}. [{f['category']}] {f['fact']}（涉及：{'、'.join(f['actors'])}）")
    sections.append("已确立事实：\n" + "\n".join(fact_lines))
    
    # Recent scenes
    scene_lines = [f"第{s.get('scene_number', '?')}场：{s.get('content', '')[:200]}" for s in recent_scenes]
    sections.append("近期场景内容：\n" + "\n".join(scene_lines))
    
    # Output format
    sections.append(
        "请返回 JSON 格式：\n"
        '{"contradictions": [{"fact_id": "...", "fact_text": "...", '
        '"scene_text": "...", "explanation": "..."}], '
        '"has_contradiction": true/false}'
    )
    
    return "\n\n".join(sections)
```

### Async Tool 函数（参考 dynamic_storm）
```python
# Source: [VERIFIED: tools.py L772-883]
async def validate_consistency(tool_context: ToolContext) -> dict:
    """Trigger consistency check. Async — calls LLM."""
    state = _get_state(tool_context)
    
    # Heuristic pre-filtering (D-16)
    relevant_facts = _filter_relevant_facts(state)
    if not relevant_facts:
        return {"status": "success", "message": "✅ 一致性检查通过，无需检查", ...}
    
    # Get recent 2 scenes
    scenes = state.get("scenes", [])
    recent_scenes = scenes[-2:] if len(scenes) >= 2 else scenes
    
    # Build prompt
    prompt = validate_consistency_prompt(relevant_facts, recent_scenes)
    
    # Call LLM
    try:
        from .memory_manager import _call_llm
        response_text = await _call_llm(prompt)
    except Exception as e:
        return {"status": "error", "message": f"❌ 一致性检查 LLM 调用失败：{e}"}
    
    # Parse response
    contradictions = _parse_contradictions(response_text, relevant_facts)
    
    # Update coherence_checks state (D-32)
    ...
```

### 演员上下文锚点段落（参考 _assemble_actor_sections）
```python
# Source: [VERIFIED: context_builder.py L220-230 anchor 段落模式]
# Phase 10 新增——在 _assemble_actor_sections 中
# 角色 DNA 锚点 (priority 7, never truncated — D-26)

# 1. 性格核心
personality = actor_data.get("personality", "")

# 2. 关键记忆 (is_critical=True)
critical = actor_data.get("critical_memories", [])
critical_lines = [f"[第{m['scene']}场] {m['entry']}" for m in critical if m.get("is_critical")]

# 3. 涉及该演员的 high importance 事实
state_ref = _get_state(tool_context)
established_facts = state_ref.get("established_facts", [])
actor_facts = [f for f in established_facts 
               if actor_name in f.get("actors", []) and f.get("importance") == "high"]
fact_lines = [f"{f['fact']}（第{f['scene']}场）" for f in actor_facts]

# 组装锚点文本
dna_lines = ["【角色锚点】（你必须遵守的约束）"]
if personality:
    dna_lines.append(f"性格核心：{personality}")
if critical_lines:
    dna_lines.append(f"关键记忆：{critical_lines[0]}")  # 只取最重要的一条
if fact_lines:
    dna_lines.append(f"已确立事实：{fact_lines[0]}")  # 只取最重要的

sections.append({
    "key": "actor_dna",
    "text": "\n".join(dna_lines),
    "priority": 7,  # D-26: 最高优先级
    "truncatable": False,
})
```

### _build_facts_section 升级
```python
# Source: [VERIFIED: context_builder.py L824-845 现有空壳]
def _build_facts_section(state: dict) -> dict:
    """Build established facts section with check reminders (D-28)."""
    facts = state.get("established_facts", [])
    coherence = state.get("coherence_checks", {})
    
    if not facts:
        # 仍然可能需要检查提醒
        current_scene = state.get("current_scene", 0)
        last_check = coherence.get("last_check_scene", 0)
        if current_scene - last_check >= COHERENCE_CHECK_INTERVAL:
            return {
                "key": "facts",
                "text": f"💡 距上次一致性检查已 {current_scene - last_check} 场，建议调用 validate_consistency()",
                "priority": _DIRECTOR_SECTION_PRIORITIES["facts"],
                "truncatable": True,
            }
        return {"key": "facts", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["facts"], "truncatable": True}
    
    # Filter: only high/medium importance (D-05/D-28)
    visible_facts = [f for f in facts if f.get("importance") in ("high", "medium")]
    
    # Category labels
    CATEGORY_LABELS = {
        "event": "事件", "identity": "身份", "location": "地点",
        "relationship": "关系", "rule": "规则",
    }
    IMPORTANCE_LABELS = {"high": "核心", "medium": ""}
    
    lines = []
    for f in visible_facts:
        imp_label = IMPORTANCE_LABELS.get(f["importance"], "")
        cat_label = CATEGORY_LABELS.get(f["category"], f["category"])
        actors_str = f"，涉及：{'、'.join(f['actors'])}" if f.get("actors") else ""
        if imp_label:
            lines.append(f"[{imp_label}] {f['fact']}（第{f['scene']}场确立{actors_str}）")
        else:
            lines.append(f"[{cat_label}] {f['fact']}（第{f['scene']}场确立{actors_str}）")
    
    # Header with stats and check reminder
    current_scene = state.get("current_scene", 0)
    last_check = coherence.get("last_check_scene", 0)
    last_result = coherence.get("last_result")
    
    header_parts = [f"事实总数：{len(facts)} 条"]
    if last_check > 0:
        result_str = "无矛盾" if last_result == "clean" else f"发现 {last_result} 处矛盾"
        header_parts.append(f"上次检查：第{last_check}场（{result_str}）")
    
    # Check reminder every 5 scenes
    scenes_since = current_scene - last_check
    if scenes_since >= COHERENCE_CHECK_INTERVAL:
        header_parts.append(f"💡 距上次检查已 {scenes_since} 场，建议调用 validate_consistency() 检查一致性")
    
    text = "【已确立事实】\n" + " | ".join(header_parts) + "\n" + "\n".join(lines)
    return {"key": "facts", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["facts"], "truncatable": True}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 纯字符串事实列表 | 结构化对象列表（dict with id/category/actors/importance） | Phase 10 D-01 | 支持按 actors 交叉比对、按 category 分类、按 importance 过滤 |
| LLM 自动提取事实 | 导演手动添加 | Phase 10 D-07 | 避免误提取，创意决策由人类控制 |
| 纯启发式矛盾检测 | 启发式预筛选 + LLM 语义判断 | Phase 10 D-12 | 语义矛盾检测精准，启发式预筛选减少 LLM 输入量 |
| 自动修复矛盾 | 导演建议模式 | Phase 10 D-21 | 与全系统"导演建议模式"一致，不自动打断叙事 |

**Deprecated/outdated:**
- `_build_facts_section()` 的现有空壳实现（L824-845）：仅支持纯字符串列表，Phase 10 升级为完整结构化展示
- 简单 `state.get("established_facts")` 空壳检测：Phase 10 后 `established_facts` 将始终初始化为 `[]`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_call_llm` 可用于一致性检查的 LLM 调用，不需要额外的 API 配置 | Standard Stack | 需要改用其他 LLM 调用方式 |
| A2 | LLM 一致性检查的 JSON 输出格式可以被可靠解析 | Architecture Patterns | 需要更强的 fallback 解析逻辑 |
| A3 | 50 条事实在导演上下文中不会显著影响 token 预算 | Common Pitfalls | 需要调整 MAX_FACTS 或展示策略 |
| A4 | 演员上下文锚点段落的 priority=7 不会与现有段落冲突 | Architecture Patterns | 需要调整优先级映射 |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions

1. **LLM 检查的 JSON 输出可靠性**
   - What we know: `dynamic_storm.py` 使用 ```json 块 + 纯 JSON fallback 解析，已验证可靠
   - What's unclear: 一致性检查的 JSON 结构更复杂（嵌套 contradictions 数组），LLM 是否稳定输出
   - Recommendation: 参考 `parse_llm_perspectives` 模式，先尝试 ```json 块提取，再 fallback 到正则匹配 JSON 对象

2. **validate_consistency 是否需要 model 参数**
   - What we know: CONTEXT.md Claude's Discretion 中提到"是否使用与主 Agent 不同的模型"
   - What's unclear: 一致性检查是否需要更便宜/更快的模型来降低延迟
   - Recommendation: 初始版本使用与 `_call_llm` 相同的模型（通过 MODEL_NAME 环境变量控制），后续如需优化再添加 model 参数

## Environment Availability

Step 2.6: SKIPPED (no external dependencies identified — Phase 10 仅使用项目已有代码和 Python 标准库)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/unit/test_coherence_checker.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COHERENCE-01 | 启发式预筛选筛选出相关事实 | unit | `pytest tests/unit/test_coherence_checker.py::TestFilterRelevantFacts -x` | ❌ Wave 0 |
| COHERENCE-01 | LLM 一致性检查 prompt 构建正确 | unit | `pytest tests/unit/test_coherence_checker.py::TestValidateConsistencyPrompt -x` | ❌ Wave 0 |
| COHERENCE-01 | LLM 响应解析返回结构化矛盾 | unit | `pytest tests/unit/test_coherence_checker.py::TestParseContradictions -x` | ❌ Wave 0 |
| COHERENCE-02 | add_fact_logic 创建结构化事实对象 | unit | `pytest tests/unit/test_coherence_checker.py::TestAddFactLogic -x` | ❌ Wave 0 |
| COHERENCE-02 | fact_id 生成遵循 fact_{scene}_{keyword}_{index} 格式 | unit | `pytest tests/unit/test_coherence_checker.py::TestFactIdGeneration -x` | ❌ Wave 0 |
| COHERENCE-02 | _check_fact_overlap 检测重复事实 | unit | `pytest tests/unit/test_coherence_checker.py::TestCheckFactOverlap -x` | ❌ Wave 0 |
| COHERENCE-02 | _extract_actor_names 从事实文本提取角色名 | unit | `pytest tests/unit/test_coherence_checker.py::TestExtractActorNames -x` | ❌ Wave 0 |
| COHERENCE-03 | 角色锚点段落包含性格+关键记忆+事实 | unit | `pytest tests/unit/test_context_builder.py::TestActorDnaSection -x` | ❌ Wave 0 |
| COHERENCE-03 | 锚点段落优先级 7 且不可截断 | unit | `pytest tests/unit/test_context_builder.py::TestActorDnaPriority -x` | ❌ Wave 0 |
| COHERENCE-04 | generate_repair_narration_prompt 构建正确 | unit | `pytest tests/unit/test_coherence_checker.py::TestGenerateRepairNarration -x` | ❌ Wave 0 |
| COHERENCE-04 | repair_contradiction_logic 追加 repair_note | unit | `pytest tests/unit/test_coherence_checker.py::TestRepairContradiction -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_coherence_checker.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_coherence_checker.py` — covers COHERENCE-01/02/04 纯函数测试
- [ ] `tests/unit/test_tools_phase10.py` — covers 3 个 Tool 函数集成测试
- [ ] `tests/unit/test_context_builder.py` — 需新增角色锚点段落测试（COHERENCE-03）

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | 单用户 CLI，无认证 |
| V3 Session Management | no | 单会话模式 |
| V4 Access Control | no | 无多用户访问 |
| V5 Input Validation | yes | fact/category/importance 参数验证 |
| V6 Cryptography | no | 无加密需求 |

### Known Threat Patterns for AI Narrative System

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via fact text | Tampering | fact 文本长度限制 + LLM prompt 中隔离事实文本 |
| State pollution via excessive facts | Denial of Service | MAX_FACTS=50 软上限 |
| LLM response parsing failure | Tampering | 多层 JSON 解析 fallback（```json 块 → 纯 JSON → 正则） |

## Sources

### Primary (HIGH confidence)
- 项目源码: `app/conflict_engine.py` — 纯函数模式参考
- 项目源码: `app/arc_tracker.py` — 手动 Tool 创建模式参考
- 项目源码: `app/dynamic_storm.py` — LLM prompt + async 模式参考
- 项目源码: `app/context_builder.py` — 上下文段落组装模式参考
- 项目源码: `app/tools.py` — Tool 函数薄代理模式参考
- 项目源码: `app/state_manager.py` — 状态初始化和兼容模式参考
- CONTEXT.md D-01~D-39 — 所有决策已锁定

### Secondary (MEDIUM confidence)
- `.planning/research/PITFALLS.md` — Pitfall 2（压缩丢失关键细节→逻辑矛盾）、Pitfall 7（Dynamic STORM 创建矛盾情节）、Pitfall 16（"恐怖谷"近一致但微妙错误的情节）均直接关联 Phase 10
- `.planning/codebase/CONVENTIONS.md` — 编码规范参考

### Tertiary (LOW confidence)
- None — 所有技术决策已由 CONTEXT.md 锁定，无需外部验证

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 无新依赖，全部使用项目已有技术栈
- Architecture: HIGH — 严格复用项目已有模式（conflict_engine/arc_tracker/dynamic_storm），无创新架构
- Pitfalls: HIGH — CONTEXT.md 已详细分析并锁定解决方案

**Research date:** 2026-04-13
**Valid until:** 2026-05-13（30 days — 稳定领域，CONTEXT.md 锁定决策不变）
