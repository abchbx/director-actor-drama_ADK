# Phase 3: Semantic Retrieval - Research

**Researched:** 2026-04-11
**Domain:** 记忆检索 / 标签匹配算法 / LLM 输出解析
**Confidence:** HIGH

## Summary

本阶段实现基于标签的记忆检索系统，让演员和导演能回忆特定过往。核心技术方案是：在场景压缩时让 LLM 同时输出标签集（角色名/地点/情感/冲突类型），存入 `scene_summaries[].tags` 字段；新建 `app/semantic_retriever.py` 模块实现加权标签匹配检索算法；在 `context_builder.py` 末尾新增"【相关回忆】"段落自动注入 top-3 记忆；在 `tools.py` 注册 `retrieve_relevant_scenes` 和 `backfill_tags` 两个 Tool 函数供导演调用。

纯 Python 实现无外部依赖——标签匹配算法使用带前缀分类的加权匹配，复杂度 O(N×M)（N=记忆条目数，M=查询标签数），在 <100 条记忆 × <10 标签的场景下轻松满足 <100ms 延迟要求。LLM 压缩 prompt 修改是关键集成点——需在现有 `_build_compression_prompt_working()` 的输出格式部分增加标签输出要求，并在 `compress_working_to_scene()` 中解析标签。回填工具对已有 scene_summaries 批量调用 LLM 生成标签，一次性操作后标记完成。

**Primary recommendation:** 新建 `app/semantic_retriever.py` 作为独立模块，实现全部检索逻辑（标签匹配+三层搜索+去重排序），通过函数接口被 `context_builder.py` 和 `tools.py` 调用。修改 `memory_manager.py` 的压缩 prompt 和解析逻辑以输出标签。在 `context_builder.py` 的 `_assemble_actor_sections()` 末尾新增低优先级 section。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 场景压缩时自动生成标签集——在 `memory_manager.py` 的 LLM 压缩 prompt 中要求输出标签，解析后存入 `scene_summaries[].tags` 字段。标签类型：角色名、地点、情感关键词、冲突类型
- **D-02:** 提供 `backfill_tags(tool_context)` 一次性回填工具，对已有 scene_summaries 调用 LLM 批量生成标签。回填后标记 `state["drama"]["tags_backfilled"] = True` 避免重复执行
- **D-03:** 标签存储格式：`tags: ["角色:朱棣", "地点:皇宫", "情感:愤怒", "冲突:权力争夺", "秘密发现"]`——带前缀分类，便于加权匹配和调试
- **D-04:** working_memory 和 critical_memories 不生成标签（条目少、文本短，直接用关键词匹配即可）
- **D-05:** 统一接口 `retrieve_relevant_scenes(tags, current_scene, tool_context)`，导演和演员共用
- **D-06:** 搜索三层记忆：scene_summaries（主检索层，有 tags 字段）> working_memory（近期细节，关键词匹配）> critical_memories（关键事件，关键词匹配）
- **D-07:** 演员限定自身记忆（从 `state["drama"]["actors"][actor_name]` 检索），导演全局搜索（遍历所有演员的记忆）
- **D-08:** 返回 top-K 结果（默认 K=5），每条结果包含：来源层、场景范围、摘要/原文、匹配标签列表、相关度分数
- **D-09:** 加权标签匹配算法，纯 Python 计算无 LLM 调用：角色名标签权重 3.0、冲突/事件类型标签权重 2.0、情感关键词标签权重 1.5、地点标签权重 1.0、无前缀标签权重 1.0
- **D-10:** 匹配计算：`score = sum(tag_weight for query_tag in tags if tag matches entry_tag)`，支持前缀匹配
- **D-11:** working_memory 和 critical_memories 的匹配：直接对 entry 文本做关键词包含检查（tag in entry_text），命中则赋固定权重 1.0
- **D-12:** 去重：同一场景的记忆只保留得分最高的条目
- **D-13:** 导演侧：`retrieve_relevant_scenes` 注册为 Tool 函数
- **D-14:** 演员侧：`build_actor_context_from_memory()` 末尾新增"【相关回忆】"段落
- **D-15:** 演员自动检索的标签来源：当前 working_memory 中最新条目的文本 + 当前场景的关键词
- **D-16:** 自动注入的相关回忆受 token 预算控制——如果 actor context 已接近预算，相关回忆段落最先被截断（优先级最低）

### Claude's Discretion
- 标签前缀的具体分类列表（可扩展）
- LLM 压缩 prompt 中标签生成的具体措辞和格式
- 回填工具的批处理大小
- 关键词匹配的模糊程度（是否支持部分匹配/同义词）
- 去重的具体阈值（场景编号相同即去重 vs 内容相似度去重）

### Deferred Ideas (OUT OF SCOPE)
- 向量数据库集成（ChromaDB/FAISS）— v2 REQUIREMENTS Out of Scope，当前纯 JSON 标签匹配足够
- 语义相似度模型（embedding-based retrieval）— 同上，需要额外依赖和基础设施
- 跨戏剧检索（从其他戏剧中回忆类似场景）— 有趣但远超当前范围
- 自然语言查询接口（"朱棣上次生气是什么时候"→自动提取标签检索）— 可作为后续增强
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEMORY-05 | 语义检索 — 按关键词/角色名/事件类型检索历史记忆 | 标签系统（D-01~D-04）+ 加权匹配算法（D-09~D-11）+ 三层搜索（D-06）+ 导演/演员双侧集成（D-07/D-13/D-14）|
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `json` | 3.11+ | LLM 输出标签解析 | 零依赖，项目已有 JSON 解析模式 `[VERIFIED: memory_manager.py L253-259]` |
| Python stdlib `re` | 3.11+ | 标签解析的正则回退 | 项目已有正则模式 `[VERIFIED: context_builder.py L34]` |
| Python stdlib `asyncio` | 3.11+ | 回填工具的异步 LLM 调用 | 项目已有异步模式 `[VERIFIED: memory_manager.py L539]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `google.adk.tools.ToolContext` | >=1.15.0 | State 访问 | 所有 Tool 函数签名 `[VERIFIED: tools.py L15]` |
| `LiteLlm` (via `memory_manager._call_llm`) | >=1.15.0 | 标签回填的 LLM 调用 | backfill_tags 工具复用现有 LLM 调用基础设施 `[VERIFIED: memory_manager.py L137-181]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 自定义加权匹配 | scikit-learn TF-IDF | 无需外部依赖，纯 Python 加权匹配足够（<100 条数据量）；TF-IDF 过度设计 `[ASSUMED]` |
| 自定义 JSON 解析 | Pydantic 模型验证 | 项目无 Pydantic 验证模式（typing.py 中有但未用于 LLM 输出）；简单 JSON 解析足够 `[VERIFIED: memory_manager.py L250-281]` |

**Installation:**
```bash
# 无新依赖安装——全部使用项目已有库
```

**Version verification:** 本阶段零新依赖，所有库已在 Phase 1/2 中验证。

## Architecture Patterns

### Recommended Project Structure
```
app/
├── semantic_retriever.py   # 新增：检索核心逻辑（加权匹配、三层搜索、去重排序）
├── memory_manager.py       # 修改：压缩 prompt 增加标签输出 + 解析标签
├── context_builder.py      # 修改：新增"相关回忆"段落
├── tools.py                # 修改：注册 retrieve_relevant_scenes + backfill_tags
├── agent.py                # 修改：导演 agent instruction 增加检索引导
└── state_manager.py        # 不修改（但需了解 state 数据结构）
```

### Pattern 1: 标签前缀分类加权匹配
**What:** 标签格式 `"前缀:值"`，前缀决定权重，精确匹配计算得分
**When to use:** `scene_summaries` 层的标签匹配
**Example:**
```python
# Source: CONTEXT.md D-09, D-10
TAG_WEIGHTS = {
    "角色": 3.0,
    "冲突": 2.0,
    "事件": 2.0,
    "情感": 1.5,
    "地点": 1.0,
}

def _get_tag_weight(tag: str) -> float:
    """Extract prefix from tag and return corresponding weight."""
    if ":" in tag:
        prefix = tag.split(":")[0]
        return TAG_WEIGHTS.get(prefix, 1.0)
    return 1.0  # 无前缀标签权重 1.0

def _compute_tag_score(query_tags: list[str], entry_tags: list[str]) -> float:
    """Compute weighted matching score between query and entry tags."""
    score = 0.0
    for qt in query_tags:
        for et in entry_tags:
            if qt == et or qt.split(":")[-1] == et.split(":")[-1]:
                # 精确匹配或值匹配（忽略前缀）
                score += max(_get_tag_weight(qt), _get_tag_weight(et))
                break
    return score
```

### Pattern 2: LLM 输出标签解析（JSON 优先 + 正则回退）
**What:** 修改压缩 prompt 要求 LLM 输出 JSON 格式标签，解析时先尝试 JSON，失败则正则提取
**When to use:** `compress_working_to_scene()` 返回结果解析
**Example:**
```python
# Source: 基于 memory_manager.py L250-281 的现有 JSON 解析模式
def _parse_tags_from_llm_output(text: str) -> list[str]:
    """Parse tags from LLM compression output.
    
    尝试从 LLM 输出中提取标签列表。
    1. 优先尝试 JSON 解析（如果 LLM 输出了结构化标签）
    2. 回退到正则提取（如果 LLM 未按格式输出）
    """
    # Try JSON extraction (prompt asks for tags in JSON array)
    try:
        json_text = text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()
        data = json.loads(json_text)
        if isinstance(data, dict) and "tags" in data:
            return data["tags"]
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    
    # Fallback: regex extraction for prefix:value pattern
    tag_pattern = re.findall(r'["\']?(角色|地点|情感|冲突|事件|其他):([^"\',\]]+)["\']?', text)
    if tag_pattern:
        return [f"{prefix}:{value.strip()}" for prefix, value in tag_pattern]
    
    return []  # No tags extracted — non-fatal
```

### Pattern 3: 三层记忆检索（标签层 → 关键词层）
**What:** scene_summaries 用标签匹配，working_memory/critical_memories 用关键词包含检查
**When to use:** `retrieve_relevant_scenes()` 函数
**Example:**
```python
# Source: CONTEXT.md D-06, D-11
def _search_scene_summaries(query_tags: list[str], summaries: list[dict]) -> list[dict]:
    """Search scene_summaries using weighted tag matching (D-06 primary layer)."""
    results = []
    for s in summaries:
        entry_tags = s.get("tags", [])
        score = _compute_tag_score(query_tags, entry_tags)
        if score > 0:
            results.append({
                "source": "scene_summaries",
                "scenes_covered": s.get("scenes_covered", "?"),
                "text": s.get("summary", ""),
                "matched_tags": [qt for qt in query_tags if any(qt == et for et in entry_tags)],
                "score": score,
            })
    return results

def _search_text_layer(query_tags: list[str], entries: list[dict], source_name: str) -> list[dict]:
    """Search working_memory/critical_memories using keyword containment (D-11)."""
    results = []
    for e in entries:
        entry_text = e.get("entry", "")
        matched = [qt for qt in query_tags if qt.split(":")[-1] in entry_text]
        if matched:
            results.append({
                "source": source_name,
                "scenes_covered": str(e.get("scene", "?")),
                "text": entry_text,
                "matched_tags": matched,
                "score": 1.0,  # 固定权重 D-11
            })
    return results
```

### Anti-Patterns to Avoid
- **不要对 working_memory/critical_memories 生成标签（D-04）**：这些层条目少、文本短，关键词匹配足够，生成标签反而增加 LLM 调用开销和复杂度
- **不要使用模糊匹配/同义词扩展**：在 <100 条数据规模下，精确匹配+前缀分类已足够，模糊匹配引入不确定性且违反 D-10 的计算公式
- **不要在每次 actor_speak 调用时都执行检索**：检索应在 `build_actor_context_from_memory()` 中执行，与上下文组装流程一致，而非在 `actor_speak()` 中额外调用

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM 调用 | 新建 LLM 客户端 | `memory_manager._call_llm(prompt)` | 已有 LiteLlm + httpx 回退机制 `[VERIFIED: memory_manager.py L137-181]` |
| JSON 解析 | 自定义文本解析器 | `json.loads()` + 正则回退 | 项目已有此模式 `[VERIFIED: memory_manager.py L250-281]` |
| Token 估算 | 新建 token 计数器 | `context_builder.estimate_tokens()` | 已有 CJK+English 混合估算 `[VERIFIED: context_builder.py L79-103]` |
| 上下文裁剪 | 新建截断逻辑 | `context_builder._truncate_sections()` | 已有优先级截断机制 `[VERIFIED: context_builder.py L111-181]` |

**Key insight:** 本阶段的核心新代码只有 `semantic_retriever.py` 模块和 prompt 修改，其余全部是集成已有基础设施。

## Common Pitfalls

### Pitfall 1: LLM 压缩输出格式不一致
**What goes wrong:** LLM 有时不按要求的 JSON 格式输出标签，而是以自由文本形式输出，导致解析失败
**Why it happens:** LLM 输出不确定性强，即使 prompt 明确要求格式，也可能被摘要内容带偏
**How to avoid:** 1) 在 prompt 中用 `{{{` 转义 JSON 括号（项目已有此模式 `[VERIFIED: memory_manager.py L121]`）；2) 实现两级解析：JSON 优先 + 正则回退；3) 标签提取失败不阻塞压缩流程——`tags` 字段默认空列表
**Warning signs:** `tags` 字段频繁为空列表；回退到正则提取比例过高

### Pitfall 2: 检索结果与常规上下文重复
**What goes wrong:** 相关回忆返回的场景摘要与 context_builder 已包含的近期场景摘要重复
**Why it happens:** `scene_summaries` 中最新 10 条已包含在演员上下文的"【近期场景摘要】"段落中
**How to avoid:** 在检索结果中排除 `scenes_covered` 与当前工作记忆场景编号重叠的条目（D-12 去重）；或在 `_assemble_actor_sections()` 中与已有 scene_summaries 条目交叉对比
**Warning signs:** 演员上下文中出现同一段场景描述两次

### Pitfall 3: 标签回填工具的 LLM 调用开销
**What goes wrong:** 对大量已有 scene_summaries 逐一调用 LLM 生成标签，耗时过长且成本高
**Why it happens:** 每条摘要需要一次 LLM 调用，20 条摘要可能需要 20 次调用
**How to avoid:** 1) 批处理——将多条摘要合并到一次 LLM prompt 中（每次 3-5 条）；2) 异步执行——回填不阻塞主流程；3) 一次性标记 `tags_backfilled = True` 防止重复执行 `[VERIFIED: CONTEXT.md D-02]`
**Warning signs:** 回填操作超过 60 秒；API 调用费用异常

### Pitfall 4: 演员"相关回忆"段落占用过多 token 预算
**What goes wrong:** 自动注入的 top-3 相关记忆条目过长，挤压其他更重要段落的 token 空间
**Why it happens:** 场景摘要可能每条 200 字，3 条 = 600 字 ≈ 900 token，占 8000 预算的 11%
**How to avoid:** 1) 设置优先级最低（`priority: 0`），让 `_truncate_sections()` 优先裁剪；2) 每条回忆截断至 100 字；3) 动态调整 K 值——如果剩余 token 预算 < 500，自动降为 top-1 `[VERIFIED: CONTEXT.md D-16]`
**Warning signs:** 角色锚点或关键记忆被截断但相关回忆仍在

### Pitfall 5: 场景编号去重逻辑跨层不一致
**What goes wrong:** scene_summaries 的 `scenes_covered` 格式为 `"3-5"`，working_memory 的 `scene` 格式为整数 `3`，去重比较时类型不匹配
**Why it happens:** 两层数据结构不同——`scenes_covered` 是范围字符串，`scene` 是整数
**How to avoid:** 实现统一的 `_normalize_scene_range()` 函数，将 `"3-5"` 转为 `{3,4,5}` 集合，整数 `3` 转为 `{3}`，集合交集判断重复
**Warning signs:** 同一场景出现两条不同来源的回忆

## Code Examples

Verified patterns from official sources and existing codebase:

### 修改压缩 prompt 以输出标签
```python
# Source: 基于 memory_manager.py _build_compression_prompt_working() 修改
def _build_compression_prompt_working(entries: list[dict], actor_name: str) -> str:
    """Build the LLM prompt for working→scene compression WITH tag generation."""
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

## 输出格式（严格 JSON）
{{{{
  "summary": "场景摘要文本...",
  "tags": ["角色:朱棣", "地点:皇宫", "情感:愤怒", "冲突:权力争夺", "秘密发现"]
}}}}

### 标签生成规则
- 从摘要中提取 3-8 个标签
- 标签格式：前缀:值，前缀包括：角色、地点、情感、冲突、事件
- 角色名必标（谁在场），冲突/事件类型必标（发生了什么）
- 情感和地点视情况标注
- 无前缀标签用于难以归类的重要关键词"""
```

### 解析标签并存入 scene_summaries
```python
# Source: 基于 memory_manager.py compress_working_to_scene() 修改
async def compress_working_to_scene(
    actor_name: str, entries: list[dict], tool_context: ToolContext,
) -> dict:
    """Async LLM compression of working memory → scene summary with tags."""
    prompt = _build_compression_prompt_working(entries, actor_name)
    response_text = await _call_llm(prompt)
    
    # 尝试解析 JSON（含标签）
    tags = []
    summary_text = response_text
    
    try:
        json_text = response_text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(json_text)
        summary_text = result.get("summary", response_text)
        tags = result.get("tags", [])
        # 验证 tags 格式
        if not isinstance(tags, list):
            tags = []
    except (json.JSONDecodeError, KeyError, IndexError):
        # JSON 解析失败——尝试正则提取标签
        tags = _extract_tags_fallback(response_text)
        logger.info(f"Tag JSON parse failed for {actor_name}, extracted {len(tags)} tags via regex")
    
    # ... scenes_covered 和 key_events 计算逻辑不变 ...
    
    return {
        "summary": summary_text,
        "scenes_covered": scenes_covered,
        "key_events": key_events,
        "tags": tags,  # 新增字段
    }
```

### context_builder 新增"相关回忆"段落
```python
# Source: 基于 context_builder.py _assemble_actor_sections() 末尾新增
# 在 _assemble_actor_sections() 返回前新增:

# Semantic recall section (priority 0, lowest — D-16)
from .semantic_retriever import retrieve_relevant_scenes, _extract_auto_tags

auto_tags = _extract_auto_tags(actor_data, tool_context)
if auto_tags:
    state = _get_state(tool_context)
    current_scene = state.get("current_scene", 0)
    recall_results = retrieve_relevant_scenes(
        tags=auto_tags,
        current_scene=current_scene,
        tool_context=tool_context,
        actor_name=actor_name,  # 限定自身记忆 (D-07)
        top_k=3,  # 演员侧 top-3 (D-14)
    )
    if recall_results:
        recall_lines = []
        for r in recall_results:
            recall_lines.append(
                f"- 第{r['scenes_covered']}场：{r['text'][:100]} "
                f"[匹配: {', '.join(r['matched_tags'])}]"
            )
        sections.append({
            "key": "semantic_recall",
            "text": "【相关回忆】\n" + "\n".join(recall_lines),
            "priority": 0,  # 最低优先级——最先被截断 (D-16)
            "truncatable": True,
        })
```

### tools.py 注册 retrieve_relevant_scenes Tool
```python
# Source: 遵循 CONVENTIONS.md Tool 函数签名模式
def retrieve_relevant_scenes_tool(
    tags: str,  # 逗号分隔的标签列表，如 "角色:朱棣,情感:愤怒"
    tool_context: ToolContext,
) -> dict:
    """Retrieve relevant scene memories by tags. Use when director needs to recall specific past events.

    按标签检索相关历史记忆，导演全局搜索所有演员的记忆。

    Args:
        tags: Comma-separated tags, e.g. "角色:朱棣,情感:愤怒,冲突:权力争夺"

    Returns:
        dict with top-K relevant memories, sorted by relevance score.
    """
    from .semantic_retriever import retrieve_relevant_scenes
    
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        return {"status": "error", "message": "请提供至少一个标签用于检索。"}
    
    state = tool_context.state.get("drama", {})
    current_scene = state.get("current_scene", 0)
    
    results = retrieve_relevant_scenes(
        tags=tag_list,
        current_scene=current_scene,
        tool_context=tool_context,
        actor_name=None,  # 导演全局搜索 (D-07)
        top_k=5,  # 导演侧 top-5 (D-08)
    )
    
    return {
        "status": "success",
        "message": f"找到 {len(results)} 条相关记忆。",
        "results": results,
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 扁平记忆关键词搜索 | 标签加权匹配检索 | Phase 3 | 检索精度和灵活性大幅提升，支持分类权重 |
| 无标签（纯文本匹配） | LLM 生成分类标签 | Phase 3 | 结构化标签比纯文本匹配更精准 |
| 无记忆检索能力 | 三层记忆统一检索接口 | Phase 3 | 演员和导演都能回忆特定过往 |

**Deprecated/outdated:**
- `actor.memory` 扁平列表：已在 Phase 1 迁移为三层架构，Phase 3 不再涉及

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 单次检索 <100 条记忆 × <10 标签的 O(N×M) 匹配在纯 Python 中 <100ms | Architecture Patterns | 如果数据量远超预期可能需要优化；但 50 场戏约产生 10 个 scene_summaries + 5 个 working_memory + 5 个 critical_memories = ~20 条/演员，10 个演员 = ~200 条，仍可接受 |
| A2 | LLM 在现有压缩 prompt 中增加标签输出不会显著降低摘要质量 | Code Examples | 标签输出可能"挤占"LLM 的注意力，导致摘要质量下降；需要通过测试验证 |
| A3 | 标签前缀列表 `{角色, 地点, 情感, 冲突, 事件, 其他}` 足够覆盖戏剧场景的所有关键维度 | Architecture Patterns | 如果遗漏重要分类（如"时间"、"关系"），检索可能遗漏相关记忆；可通过扩展前缀列表解决 |
| A4 | 回填工具批处理 3-5 条/次是合理的批次大小 | Common Pitfalls | 如果 LLM 上下文允许更大批次，可以减少调用次数；如果批次太大可能降低标签质量 |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions (RESOLVED)

1. **标签值匹配是否应忽略前缀？** — RESOLVED
   - What we know: D-10 提到"支持前缀匹配（查询'角色:朱棣'匹配'角色:朱棣'）"，但未明确查询"朱棣"是否匹配"角色:朱棣"
   - What's unclear: 查询标签无前缀时，是否应该匹配所有前缀下同值的标签？
   - Recommendation: 实现"值匹配"——`"朱棣"` 匹配 `"角色:朱棣"`，但权重取较小值（避免无前缀标签获得角色权重 3.0）
   - **Resolution:** Plan 01 Task 1 采用 Recommendation：值匹配时权重取 1.0（低于前缀匹配权重），避免无前缀标签获得角色权重 3.0。参见 `_compute_tag_score` 实现。

2. **演员自动检索的标签提取策略（D-15）具体实现** — RESOLVED
   - What we know: 标签来源是 working_memory 最新条目的文本 + 当前场景关键词
   - What's unclear: "当前场景关键词"从哪里获取？state 中没有直接的 current_scene_description
   - Recommendation: 从 `state["scenes"][-1]` 获取最新场景的 title + description 作为关键词来源；如果无场景信息则只从 working_memory 提取
   - **Resolution:** Plan 01 Task 1 `_extract_auto_tags` 采用 Recommendation：从 `state["scenes"][-1]` 获取场景信息，无场景信息时只从 working_memory 提取。

3. **回填工具是注册为 Tool 函数还是 CLI 命令？** — RESOLVED
   - What we know: CONTEXT.md 具体想法中提到"两者兼有更灵活"
   - What's unclear: 是否需要同时实现两种入口
   - Recommendation: 优先实现为 Tool 函数（导演可调用），CLI 入口可作为 Claude's Discretion 延后
   - **Resolution:** Plan 02 Task 1 注册 `backfill_tags_tool` 为 Tool 函数。CLI 入口延后至 Claude's Discretion。

## Environment Availability

> Step 2.6: 本阶段无外部依赖（纯 Python + 已有 LLM 调用基础设施），环境可用性检查如下：

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | 全部代码 | ✓ | 3.11.1 | — |
| pytest | 单元测试 | ✓ | 9.0.2 | — |
| LiteLlm | 标签生成+回填 | ✓ | via ADK | httpx 回退 |
| json (stdlib) | 标签解析 | ✓ | 3.11+ | — |
| re (stdlib) | 正则回退 | ✓ | 3.11+ | — |

**Missing dependencies with no fallback:**
- None

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `python -m pytest tests/unit/test_semantic_retriever.py -x -q` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEMORY-05 | `retrieve_relevant_scenes()` returns top-K by weighted tag match | unit | `pytest tests/unit/test_semantic_retriever.py::test_retrieve_relevant_scenes -x` | ❌ Wave 0 |
| MEMORY-05 | Tags auto-generated during compression | unit | `pytest tests/unit/test_semantic_retriever.py::test_tag_generation_in_compression -x` | ❌ Wave 0 |
| MEMORY-05 | Tag parsing from LLM output (JSON + regex fallback) | unit | `pytest tests/unit/test_semantic_retriever.py::test_parse_tags_from_llm -x` | ❌ Wave 0 |
| MEMORY-05 | Deduplication: same scene keeps highest score | unit | `pytest tests/unit/test_semantic_retriever.py::test_dedup_same_scene -x` | ❌ Wave 0 |
| MEMORY-05 | Actor-limited vs director-global search scope | unit | `pytest tests/unit/test_semantic_retriever.py::test_search_scope -x` | ❌ Wave 0 |
| MEMORY-05 | "相关回忆" section in actor context with lowest priority | unit | `pytest tests/unit/test_context_builder.py -x` | ✅ exists, extend |
| MEMORY-05 | `backfill_tags()` tool function | unit | `pytest tests/unit/test_semantic_retriever.py::test_backfill_tags -x` | ❌ Wave 0 |
| MEMORY-05 | Retrieval latency < 100ms | unit | `pytest tests/unit/test_semantic_retriever.py::test_retrieval_latency -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/unit/test_semantic_retriever.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_semantic_retriever.py` — covers all MEMORY-05 unit tests
- [ ] `tests/unit/test_context_builder.py` — extend with "相关回忆" section tests
- [ ] `tests/unit/test_memory_manager.py` — extend with tag generation tests

## Security Domain

> 本阶段无安全敏感操作：纯内存数据计算，无用户输入验证需求，无外部 API 暴露。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | partial | D-07 演员限定自身记忆 vs 导演全局搜索——逻辑隔离而非权限控制 |
| V5 Input Validation | yes | 标签输入验证——防止注入/超长标签 |
| V6 Cryptography | no | — |

### Known Threat Patterns for Tag-Based Retrieval

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 标签注入（恶意标签值导致匹配异常） | Tampering | 标签长度限制 + 前缀白名单验证 |
| 越权访问他人记忆（绕过 D-07） | Information Disclosure | `retrieve_relevant_scenes()` 内部强制 actor_name 过滤，不接受外部覆盖 |

## Sources

### Primary (HIGH confidence)
- 代码库实际代码：`app/memory_manager.py`, `app/context_builder.py`, `app/tools.py`, `app/agent.py`, `app/state_manager.py`
- CONTEXT.md D-01~D-16 锁定决策
- Phase 1/2 CONTEXT.md 已锁定决策

### Secondary (MEDIUM confidence)
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构验证
- `.planning/codebase/CONVENTIONS.md` — 编码规范验证

### Tertiary (LOW confidence)
- [ASSUMED] 性能估算 <100ms — 基于数据量推算，未实测验证

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 零新依赖，全部基于已有代码模式
- Architecture: HIGH — 遵循现有模块分层模式，新模块 `semantic_retriever.py` 独立且职责清晰
- Pitfalls: HIGH — 基于代码库实际模式分析，5 个坑点均有具体规避策略

**Research date:** 2026-04-11
**Valid until:** 2026-05-11（稳定领域，30 天有效期）
