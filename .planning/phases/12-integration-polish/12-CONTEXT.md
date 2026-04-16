# Phase 12: Integration & Polish - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

端到端集成测试、CLI 优化、性能调优、已知 bug 修复、文档完善，确保系统可交付。

核心交付物：
1. 端到端测试：`/start` → setup → 30+ 场戏（含冲突注入 + Dynamic STORM）→ `/save` → `/load` → 继续 → `/end`，全流程无错误
2. 修复已知 bug：`actor_speak()` 算符优先级、`_conversation_log` 全局状态竞态
3. 性能优化：debounced state saving、场景归档、共享 httpx.AsyncClient
4. CLI 命令完整可用：`/next`、`/action`、`/steer`、`/storm`、`/end`、`/save`、`/load`、`/export`
5. 演员进程健康检查和崩溃恢复机制可用
6. 测试覆盖：每个新模块至少有单元测试，核心流程有集成测试

**不包含：** Web UI、多用户支持、向量数据库集成、`_current_drama_folder` 全局变量迁移（deferred）

</domain>

<decisions>
## Implementation Decisions

### 端到端测试策略
- **D-01:** 端到端测试使用真实 LLM 调用，非 Mock。验证完整交互路径，包括 LLM 生成内容的实际处理能力
- **D-02:** 30+ 场测试采用里程碑断言——仅在关键节点验证状态，不逐场写断言。关键里程碑：
  - 第 3 场后：actors 已创建、working_memory 有数据
  - 第 5 场后：张力评分存在、established_facts 非空
  - 第 8 场后：Dynamic STORM 应触发、新视角存在
  - 第 15 场后：coherence_check 应触发过、timeline 有多个 time_periods
  - save → load 后：state 完全一致
  - /end 后：完整剧本导出成功
- **D-03:** 集成测试覆盖关键路径——最重要的跨模块交互，不追求全路径覆盖。关键路径：
  - 冲突注入 → arc_tracker 更新 → context_builder 包含冲突信息
  - Dynamic STORM → 新视角 → 导演上下文包含新视角
  - 一致性检查 → 矛盾检测 → 修复旁白
  - 时间推进 → 跳跃检测 → 导演上下文包含时间线警告
  - save → load → 继续创作 → 状态完整
- **D-04:** E2E 测试文件为 `tests/integration/test_e2e_full_flow.py`，标记为 `@pytest.mark.e2e`，默认不运行（需 `pytest -m e2e` 显式触发），避免 CI 中产生不可控成本和延迟

### 已知 Bug 修复
- **D-05:** 渐进式修复策略——优先修 `actor_speak()` 算符优先级 bug + `_conversation_log` 全局状态迁移（影响最大的两个），`_current_drama_folder` 延后标记
- **D-06:** `_conversation_log` 迁移方向：从模块级全局变量移入 `ToolContext.state["drama"]["conversation_log"]`，与现有 state 持久化对齐，消除跨 drama 污染。迁移步骤：
  1. `state_manager.py` 中 `_conversation_log` 不再是模块级变量
  2. `add_conversation()` / `get_conversation_log()` / `export_conversations()` 改为通过 `tool_context.state["drama"]` 读写
  3. `init_drama_state()` 初始化 `conversation_log: []`
  4. `load_progress()` 兼容旧存档（conversation_log 在旧存档中是独立文件，需合并到 state）
  5. `start_drama()` 清空逻辑从 `global _conversation_log = []` 改为 state 操作
- **D-07:** `_current_drama_folder` 暂不迁移，加 `# TODO: Phase 12+ — migrate _current_drama_folder to ToolContext.state` 注释标记。单用户模式下风险可控
- **D-08:** `actor_speak()` 算符优先级 bug——需先精确定位 line 246 附近的具体问题（ROADMAP 描述可能过时，实际代码行号已偏移），确认后修复

### 性能优化
- **D-09:** Debounced State Saving——5 秒间隔 debounce，退出时强制 flush。实现方式：
  - `state_manager.py` 中引入 `_save_timer` 和 `_dirty_flag`
  - `_set_state()` 设置 `_dirty_flag = True`，不立即写盘
  - 异步/定时器每 5 秒检查 `_dirty_flag`，dirty 时才实际写盘
  - `save_drama()` 和 `atexit` 强制 flush
  - 崩溃最多丢 5 秒状态，可接受
- **D-10:** 场景归档——20 场阈值触发归档。实现方式：
  - `state_manager.py` 新增 `archive_old_scenes(state)` 函数
  - 当 `len(state["scenes"]) > 20` 时，将前 N-20 场场景数据移至 `scenes/scene_{num}.json`
  - `state["scenes"]` 中只保留索引元数据：`{"scene_number": 1, "title": "...", "time_label": "...", "archived": True}`
  - 归档场景的完整数据通过 `load_archived_scene(scene_num)` 按需读取
  - `context_builder.py` 中 `_extract_scene_transition()` 和 `_build_recent_scenes_section()` 需适配归档场景
- **D-11:** 共享 AsyncClient——Director 端 `tools.py` 创建模块级共享 `_shared_httpx_client: httpx.AsyncClient | None = None`，生命周期绑定到 drama session。actor 端暂不改动（独立进程隔离，改动收益小）
- **D-12:** 共享 AsyncClient 生命周期管理——`start_drama()` 时创建，`end_drama()` / `atexit` 时关闭。提供 `get_shared_client()` 懒初始化函数

### CLI 优化
- **D-13:** CLI 体验提升三项全上：
  1. **Spinner / "思考中..."提示** — LLM 调用期间显示旋转指示器，`cli.py` 中在 `runner.run_async()` 等待时启动 spinner 协程
  2. **每场摘要展示** — `write_scene()` 后自动打印 1-2 行摘要（场景号 + 标题 + 参与角色）
  3. **统一中文错误提示格式** — 所有 Tool 返回的 error message 统一为中文 + 常见错误附带修复建议
- **D-14:** Spinner 实现方式——使用 `rich.spinner` 或简单 `sys.stdout.write` 循环，不引入重量级依赖。回退方案：仅打印 "⏳ 思考中..." + 换行
- **D-15:** 场景摘要格式：
  ```
  ── 第5场：密室对峙 ── 参演：朱棣、苏念
  ```

### 演员健康检查与崩溃恢复
- **D-16:** 演员健康检查采用被动检测——`actor_speak()` 调用失败时检测崩溃，不搞主动心跳。理由：主动心跳复杂度高、资源消耗大，单用户模式下过度设计
- **D-17:** 崩溃恢复采用自动重启——检测到崩溃时：
  1. `actor_speak()` 捕获连接异常后调用 `_restart_actor(actor_name, tool_context)`
  2. `_restart_actor()` 从 `state["actors"][name]` 读取配置 + 从 `actor_card.json` 获取 A2A 连接信息
  3. 调用 `create_actor_service()` 重建子进程
  4. 记忆从 `state["actors"][name]` 重新注入（working_memory, emotions 等已在 state 中）
  5. 重启成功后自动重试 `actor_speak()`
- **D-18:** 连续崩溃 3 次后放弃自动重启——`state["actors"][name]["crash_count"]` 追踪连续崩溃次数，达到 3 后返回结构化错误，提示用户手动干预（如 `/cast` 查看状态 + 手动 `create_actor` 重建）。成功调用后重置 crash_count
- **D-19:** 崩溃恢复日志——每次自动重启记录到 `state["actors"][name]["restart_log"]`，包含时间戳和原因，便于调试

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 12 需求定义
- `.planning/ROADMAP.md` — Phase 12 成功标准：端到端测试全流程、已知 bug 修复、性能优化、CLI 命令完整、演员健康检查、测试覆盖
- `.planning/REQUIREMENTS.md` — 全部需求追踪，Phase 12 是集成阶段需确认所有需求达标
- `.planning/PROJECT.md` — 项目愿景（Core Value: 无限畅写，逻辑不断）、约束（单用户模式、A2A 进程隔离、200K token 上限）、已知问题清单

### 已锁定决策的前置 Phase
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 3 层记忆架构，is_critical 标记，working_memory 结构
- `.planning/phases/02-context-builder/02-CONTEXT.md` — context_builder 职责划分，token 预算控制
- `.planning/phases/03-semantic-retrieval/03-CONTEXT.md` — 语义检索，标签匹配
- `.planning/phases/04-infinite-loop-engine/04-CONTEXT.md` — DramaRouter 架构，场景衔接
- `.planning/phases/05-mixed-autonomy-mode/05-CONTEXT.md` — 混合推进，导演 prompt 段落结构
- `.planning/phases/06-tension-scoring-conflict-engine/06-CONTEXT.md` — 张力评分，冲突引擎，纯函数模式
- `.planning/phases/07-arc-tracking/07-CONTEXT.md` — 弧线追踪，plot_threads 结构
- `.planning/phases/08-dynamic-storm/08-CONTEXT.md` — Dynamic STORM，视角发现
- `.planning/phases/09-progressive-storm/09-CONTEXT.md` — 渐进式 STORM
- `.planning/phases/10-coherence-system/10-CONTEXT.md` — 一致性检查，established_facts，矛盾修复
- `.planning/phases/11-timeline-tracking/11-CONTEXT.md` — 时间线追踪，跳跃检测

### 代码库映射
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）
- `.planning/codebase/STRUCTURE.md` — 模块依赖图、文件位置、新增代码指南
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构

### 需修改的核心文件（必须读取理解）
- `app/state_manager.py` (1261 行) — conversation_log 迁移、debounce、场景归档的核心文件
- `app/tools.py` (2249 行) — actor_speak bug 修复、共享 AsyncClient、崩溃恢复、CLI 错误提示
- `app/agent.py` (468 行) — 导演 prompt 可能的微调
- `app/actor_service.py` (401 行) — 崩溃恢复重启逻辑
- `app/context_builder.py` (1328 行) — 场景归档适配
- `cli.py` — spinner、场景摘要展示

### 研究文档
- `.planning/research/ARCHITECTURE.md` — 架构演进设计
- `.planning/research/PITFALLS.md` — 已知陷阱

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `state_manager.py` 的 `_set_state()` — debounce 改造的目标函数
- `state_manager.py` 的 `_save_state_to_file()` — 实际写盘函数，debounce 后仍调用此函数
- `state_manager.py` 的 `init_drama_state()` — 新增 `conversation_log` 初始化 + debounce 状态初始化
- `state_manager.py` 的 `load_progress()` — 旧存档兼容（conversation_log 从独立文件迁移到 state）
- `tools.py` 的 `actor_speak()` (214 行) — bug 修复 + 崩溃恢复注入点
- `actor_service.py` 的 `create_actor_service()` — 崩溃重启复用此函数
- `actor_service.py` 的 `stop_actor_service()` — 重启前需先停止旧进程
- `cli.py` 的 `run_interactive()` — spinner 注入点
- 所有 Phase 1-11 的纯函数模块 — E2E 测试需调用这些模块验证跨模块交互
- `tests/unit/conftest.py` — 测试 fixture，E2E 测试可复用 `_make_state()` 等 helper

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "..."}`
- State 路径：`tool_context.state["drama"]["..."]`
- 导演上下文段落格式：【中文标签】+ 内容
- 测试模式：`_make_state(**overrides)` 构建测试用 state
- 导演建议模式：Prompt 引导而非代码强制
- 全局状态迁移模式：模块级变量 → `ToolContext.state`（与 Phase 1 memory 迁移模式一致）
- 旧存档兼容模式：`setdefault()` + 缺失字段初始化

### Integration Points
- `app/state_manager.py` — debounce 改造、conversation_log 迁移、场景归档
- `app/tools.py` — actor_speak bug 修复、崩溃恢复、共享 AsyncClient、错误提示统一
- `app/actor_service.py` — 崩溃重启逻辑
- `app/context_builder.py` — 场景归档适配（归档场景按需加载）
- `cli.py` — spinner、场景摘要
- `tests/integration/test_e2e_full_flow.py` — 新增 E2E 测试
- `tests/unit/test_state_manager.py` — debounce / 归档 / conversation_log 迁移的单元测试
- `tests/unit/test_tools_phase12.py` — 新增 Phase 12 工具的单元测试

</code_context>

<specifics>
## Specific Ideas

- E2E 测试里程碑断言的具体检查点：
  ```python
  # 第3场后
  assert len(state["actors"]) >= 2
  assert any(wm for actor in state["actors"].values() for wm in actor.get("working_memory", []))
  
  # 第5场后
  assert state.get("tension_scores") or state.get("conflict_engine", {}).get("last_tension_score") is not None
  assert len(state.get("established_facts", [])) > 0
  
  # 第8场后
  storm = state.get("dynamic_storm", {})
  assert len(storm.get("perspectives", [])) > 0 or len(storm.get("trigger_history", [])) > 0
  
  # 第15场后
  assert len(state.get("coherence_checks", {}).get("check_history", [])) > 0
  assert len(state.get("timeline", {}).get("time_periods", [])) >= 2
  
  # save → load
  saved_state = json.loads(json.dumps(state))  # deep copy
  loaded_state = load_progress(theme)
  assert loaded_state == saved_state
  
  # /end 后
  assert export_path exists and file size > 0
  ```

- conversation_log 迁移步骤：
  1. `init_drama_state()` 新增 `"conversation_log": []`
  2. `add_conversation()` 改为 `state["drama"]["conversation_log"].append(entry)` + 设置 dirty flag
  3. `get_conversation_log()` 改为从 `state["drama"]["conversation_log"]` 读取
  4. `load_progress()` 兼容：检查旧存档的 `conversations/conversation_log.json`，合并到 state 中
  5. 删除模块级 `_conversation_log` 变量

- Debounce 实现骨架：
  ```python
  _save_dirty = False
  _save_timer: threading.Timer | None = None
  DEBOUNCE_SECONDS = 5

  def _set_state(state, tool_context):
      global _save_dirty, _save_timer
      tool_context.state["drama"] = state
      _save_dirty = True
      if _save_timer is None or not _save_timer.is_alive():
          _save_timer = threading.Timer(DEBOUNCE_SECONDS, _flush_state, args=[tool_context])
          _save_timer.start()

  def _flush_state(tool_context):
      global _save_dirty, _save_timer
      if _save_dirty:
          _save_state_to_file(tool_context.state["drama"]["theme"], tool_context.state["drama"])
          _save_dirty = False
      _save_timer = None
  ```

- 场景归档实现骨架：
  ```python
  SCENE_ARCHIVE_THRESHOLD = 20

  def archive_old_scenes(state):
      scenes = state.get("scenes", [])
      if len(scenes) <= SCENE_ARCHIVE_THRESHOLD:
          return state
      to_archive = scenes[:-SCENE_ARCHIVE_THRESHOLD]
      for scene in to_archive:
          scene_num = scene.get("scene_number", 0)
          archive_path = os.path.join(_get_drama_folder(state["theme"]), "scenes", f"scene_{scene_num:04d}.json")
          with open(archive_path, "w", encoding="utf-8") as f:
              json.dump(scene, f, ensure_ascii=False, indent=2)
      # Replace archived scenes with index metadata
      state["scenes"] = [
          {"scene_number": s.get("scene_number"), "title": s.get("title", ""), "time_label": s.get("time_label", ""), "archived": True}
          for s in to_archive
      ] + scenes[-SCENE_ARCHIVE_THRESHOLD:]
      return state
  ```

- 崩溃恢复实现骨架：
  ```python
  MAX_CRASH_COUNT = 3

  async def _restart_actor(actor_name, tool_context):
      state = tool_context.state.get("drama", {})
      actor_data = state.get("actors", {}).get(actor_name, {})
      crash_count = actor_data.get("crash_count", 0) + 1
      
      if crash_count >= MAX_CRASH_COUNT:
          return {"status": "error", "message": f"角色「{actor_name}」连续崩溃 {crash_count} 次，请手动用 /cast 查看状态后重建"}
      
      # Stop old process if any
      stop_actor_service(actor_name)
      
      # Restart with original config
      result = create_actor_service(
          actor_name=actor_name,
          role=actor_data.get("role", ""),
          personality=actor_data.get("personality", ""),
          background=actor_data.get("background", ""),
          knowledge_scope=actor_data.get("knowledge_scope", ""),
          tool_context=tool_context,
      )
      
      # Update crash count
      state["actors"][actor_name]["crash_count"] = crash_count
      state["actors"][actor_name].setdefault("restart_log", []).append({
          "time": datetime.now().isoformat(),
          "reason": "auto_restart_after_crash",
      })
      
      return result
  ```

- 场景摘要展示格式：
  ```
  ── 第5场：密室对峙 ── 参演：朱棣、苏念
  ```

</specifics>

<deferred>
## Deferred Ideas

- `_current_drama_folder` 全局变量迁移到 `ToolContext.state` — 单用户模式下风险可控，延后处理
- 主动心跳健康检查 — 过度设计，被动检测足够
- 全路径集成测试覆盖 — ROI 太低，关键路径覆盖即可
- Mock LLM E2E 测试套件 — 当前选择真实 LLM，如后续需要快速 CI 回归可补充 Mock 版本
- 自适应 debounce 间隔 — 根据调用频率动态调整，当前固定 5 秒足够
- 场景归档压缩 — 归档文件用 gzip 压缩减小磁盘占用
- 并行 actor_speak — 多角色同时对话提高效率（当前串行调用）
- 会话恢复 — CLI 异常退出后会话自动恢复
- Web UI — 当前仅 CLI，Web 界面需额外基础设施
- 多用户支持 — 当前架构为单用户设计

</deferred>

---

*Phase: 12-integration-polish*
*Context gathered: 2026-04-14*
