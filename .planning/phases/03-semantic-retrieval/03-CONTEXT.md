# Phase 3: Semantic Retrieval - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

实现基于标签/关键词/角色名/事件类型的记忆检索，让演员和导演能回忆特定过往。核心交付：
1. 标签系统——场景压缩时自动生成标签集（角色名、地点、情感关键词、冲突类型），已有数据提供回填工具
2. 检索函数——`retrieve_relevant_scenes(tags, current_scene, tool_context)` 统一接口，搜索三层记忆（scene_summaries + working_memory + critical_memories），加权标签匹配排序
3. 集成——导演侧 Tool 手动调用，演员侧 context_builder 自动注入相关回忆段落
4. 性能——纯 Python 计算无 LLM 调用，检索延迟 < 100ms

不包含：向量数据库集成（v2 范围）、语义相似度模型、跨戏剧检索

</domain>

<decisions>
## Implementation Decisions

### 标签生成策略
- **D-01:** 场景压缩时自动生成标签集——在 `memory_manager.py` 的 LLM 压缩 prompt 中要求输出标签，解析后存入 `scene_summaries[].tags` 字段。标签类型：角色名、地点、情感关键词、冲突类型
- **D-02:** 提供 `backfill_tags(tool_context)` 一次性回填工具，对已有 scene_summaries 调用 LLM 批量生成标签。回填后标记 `state["drama"]["tags_backfilled"] = True` 避免重复执行
- **D-03:** 标签存储格式：`tags: ["角色:朱棣", "地点:皇宫", "情感:愤怒", "冲突:权力争夺", "秘密发现"]`——带前缀分类，便于加权匹配和调试
- **D-04:** working_memory 和 critical_memories 不生成标签（条目少、文本短，直接用关键词匹配即可）

### 检索范围与接口
- **D-05:** 统一接口 `retrieve_relevant_scenes(tags, current_scene, tool_context)`，导演和演员共用
- **D-06:** 搜索三层记忆：scene_summaries（主检索层，有 tags 字段）> working_memory（近期细节，关键词匹配）> critical_memories（关键事件，关键词匹配）
- **D-07:** 演员限定自身记忆（从 `state["drama"]["actors"][actor_name]` 检索），导演全局搜索（遍历所有演员的记忆）
- **D-08:** 返回 top-K 结果（默认 K=5），每条结果包含：来源层、场景范围、摘要/原文、匹配标签列表、相关度分数

### 相关度算法
- **D-09:** 加权标签匹配算法，纯 Python 计算无 LLM 调用：
  - 角色名标签权重 3.0（最关键——"谁"的回忆）
  - 冲突/事件类型标签权重 2.0（"什么事"）
  - 情感关键词标签权重 1.5（"什么感受"）
  - 地点标签权重 1.0（"在哪里"）
  - 无前缀标签权重 1.0（兜底）
- **D-10:** 匹配计算：`score = sum(tag_weight for query_tag in tags if tag matches entry_tag)`，支持前缀匹配（查询"角色:朱棣"匹配"角色:朱棣"）
- **D-11:** working_memory 和 critical_memories 的匹配：直接对 entry 文本做关键词包含检查（tag in entry_text），命中则赋固定权重 1.0
- **D-12:** 去重：同一场景的记忆只保留得分最高的条目，避免 scene_summaries 和 working_memory 返回同一场景的重复信息

### 调用时机与集成
- **D-13:** 导演侧：`retrieve_relevant_scenes` 注册为 Tool 函数，导演 agent instruction 中引导使用（"当你需要回忆特定过往时，调用 retrieve_relevant_scenes"）
- **D-14:** 演员侧：`build_actor_context_from_memory()` 末尾新增"【相关回忆】"段落，用当前场景编号和已有标签自动检索，注入 top-3 最相关记忆
- **D-15:** 演员自动检索的标签来源：当前 working_memory 中最新条目的文本 + 当前场景的关键词（从 state 中读取当前场景描述）
- **D-16:** 自动注入的相关回忆受 token 预算控制——如果 actor context 已接近预算，相关回忆段落最先被截断（优先级最低）

### Claude's Discretion
- 标签前缀的具体分类列表（可扩展）
- LLM 压缩 prompt 中标签生成的具体措辞和格式
- 回填工具的批处理大小
- 关键词匹配的模糊程度（是否支持部分匹配/同义词）
- 去重的具体阈值（场景编号相同即去重 vs 内容相似度去重）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 语义检索相关
- `.planning/ROADMAP.md` — Phase 3 成功标准：retrieve_relevant_scenes 函数、标签自动生成、相关度排序、<100ms 延迟、不依赖外部向量数据库
- `.planning/REQUIREMENTS.md` — MEMORY-05 需求定义：语义检索
- `.planning/PROJECT.md` — 项目愿景和约束（Core Value: 无限畅写，逻辑不断；Out of Scope: 向量数据库集成）

### Phase 1/2 已锁定决策
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 3 层记忆架构（D-01~D-13），关键记忆保护，异步压缩，scene_summaries 含 scenes_covered + key_events
- `.planning/phases/02-context-builder/02-CONTEXT.md` — context_builder 职责划分（D-03），token 预算控制（D-02），D-04 前向兼容预留

### 现有代码（必须读取理解）
- `app/memory_manager.py` — 记忆 CRUD + 压缩，`_build_compression_prompt_working()` 和 `_build_compression_prompt_arc()` 需修改以输出标签，`add_working_memory()` 需了解 tags 字段
- `app/context_builder.py` — `build_actor_context_from_memory()` 需新增"相关回忆"段落，`estimate_tokens()` 和 `_truncate_sections()` 需了解以控制新段落预算
- `app/state_manager.py` — state 数据结构，检索需遍历 actors 的 scene_summaries/working_memory/critical_memories
- `app/tools.py` — 注册 `retrieve_relevant_scenes` Tool 函数，导演 agent instruction 更新
- `app/agent.py` — 导演 agent instruction（引导使用检索工具）

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构，STORM 流水线数据流
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）
- `.planning/codebase/STRUCTURE.md` — 模块依赖图，新增代码位置指引

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `memory_manager.py` 的 `_build_compression_prompt_working()` — 已有 LLM 压缩 prompt，修改即可输出标签
- `memory_manager.py` 的 `_build_compression_prompt_arc()` — 场景→弧线压缩 prompt，标签信息可传递到弧线层
- `memory_manager.py` 的 `_compress_working_to_summary()` / `_compress_summaries_to_arc()` — 异步压缩流程，解析 LLM 结果的位置，需增加标签解析
- `context_builder.py` 的 `build_actor_context_from_memory()` — 已有完整演员上下文组装流程，末尾新增"相关回忆"段落
- `context_builder.py` 的 `_truncate_sections()` — 逐层截断机制，新增段落设置低优先级即可自动截断
- `context_builder.py` 的 `estimate_tokens()` — token 估算，用于检索结果的数量控制
- `tools.py` 的 Tool 函数注册模式 — 统一签名 `def tool_name(param, tool_context) -> dict`

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...}`
- State 路径：`tool_context.state["drama"]["actors"][name]`
- 中英双语 docstring（英文首行，中文细节）
- 异步 LLM 调用模式：`asyncio.create_task()` + `_pending_compressions` 追踪
- 压缩结果解析：JSON fallback + 正则提取

### Integration Points
- `app/memory_manager.py` — 修改 LLM 压缩 prompt 输出标签，解析标签存入 scene_summaries
- `app/context_builder.py` — 新增"相关回忆"段落，调用检索函数
- `app/tools.py` — 注册 `retrieve_relevant_scenes` 和 `backfill_tags` Tool 函数
- `app/agent.py` — 导演 agent instruction 增加检索引导
- 新模块 `app/semantic_retriever.py` — 检索核心逻辑（加权匹配、三层搜索、去重排序）

</code_context>

<specifics>
## Specific Ideas

- 标签前缀分类便于加权：`角色:` `地点:` `情感:` `冲突:` `事件:` `其他:`
- 回填工具可做成 CLI 命令 `/backfill-tags`，也可做成 Tool 函数由导演调用，两者兼有更灵活
- 演员自动注入的相关回忆应标注来源场景编号（如"第3-5场"），帮助演员定位时间线
- 检索结果应高亮匹配的标签，便于调试和用户理解

</specifics>

<deferred>
## Deferred Ideas

- 向量数据库集成（ChromaDB/FAISS）— v2 REQUIREMENTS Out of Scope，当前纯 JSON 标签匹配足够
- 语义相似度模型（embedding-based retrieval）— 同上，需要额外依赖和基础设施
- 跨戏剧检索（从其他戏剧中回忆类似场景）— 有趣但远超当前范围
- 自然语言查询接口（"朱棣上次生气是什么时候"→自动提取标签检索）— 可作为后续增强

</deferred>

---

*Phase: 03-semantic-retrieval*
*Context gathered: 2026-04-11*
