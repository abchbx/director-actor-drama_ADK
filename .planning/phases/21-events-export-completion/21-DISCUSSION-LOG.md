# Phase 21: Events & Export Completion — Discussion Log

**Date:** 2026-04-26
**Status:** Discussion Complete → Ready for Planning

---

## 1. ROADMAP 事实纠正

ROADMAP 原文声称"补全5种被忽略的 WS 事件类型"，列出 `status/actor_status/actor_created/cast_update/progress`。

**实际代码审查结果：** 仅 3 种事件真正未处理。

| 事件类型 | ROADMAP 声称 | 实际状态 | 证据 |
|---------|-------------|---------|------|
| `status` | 未处理 | ✅ 确认未处理 | `handleWsEvent` when 块无此分支 |
| `actor_status` | 未处理 | ✅ 确认未处理 | `handleWsEvent` when 块无此分支 |
| `progress` | 未处理 | ✅ 确认未处理 | `handleWsEvent` when 块无此分支 |
| `actor_created` | 未处理 | ❌ 已处理 | ViewModel 627-632 行：清 stormPhase + preloadActorPanel() |
| `cast_update` | 未处理 | ❌ 已处理 | ViewModel 634-637 行：preloadActorPanel() |

**结论：** Phase 21 事件处理范围为 3 种缺失事件，非 5 种。

---

## 2. 三种缺失事件的后端数据分析

### 2.1 `status` 事件

**触发时机：** `start_drama` 工具调用时（每次开新戏必发）

**call 阶段数据：**
```json
{
  "tool": "start_drama",
  "sender_type": "director",
  "sender_name": "旁白"
}
```

**response 阶段数据：** 无专属 `_extract_response_data` 分支，走 `else` → 仅 `{tool}`

**与 `scene_start` 的时序关系：** 同一 `start_drama` 调用同时触发 `["scene_start", "status", "command_echo"]`，`scene_start` 先处理，`status` 后到。

**Android 已有覆盖：** `scene_start` 已清 `stormPhase`/`isTyping` 并刷新演员面板。`status` 事件到达时，所有状态已正确，静默丢弃无实质影响。

**建议处理方式：** 添加空处理分支 + Log.d，避免 when 块走 else 分支的静默丢弃。

### 2.2 `actor_status` 事件

**触发时机：** `update_emotion` 工具调用后（演员情绪变化时）

**response 阶段数据：**
```json
{
  "actor_name": "角色名",
  "emotion": "新情绪",
  "sender_type": "director",
  "sender_name": "旁白"
}
```

**影响：** 目前演员面板通过 `preloadActorPanel()` 全量刷新。当 `actor_status` 事件到达时，面板可能还显示旧情绪。

**建议处理方式：** 精确更新演员列表中对应角色的 emotion 字段（避免全量刷新），同时触发 `preloadActorPanel()` 作为兜底。

### 2.3 `progress` 事件

**触发时机：** `export_drama` 工具调用后

**response 阶段数据：**
```json
{
  "message": "📜 剧本已导出！\n📄 剧本文件: /path/to/file.md\n💬 对话记录: /path/to/conv.md",
  "export_path": "/path/to/file.md",
  "sender_type": "director",
  "sender_name": "旁白"
}
```

**影响：** 导出流程的进度反馈完全缺失。用户点导出后无任何确认。

**建议处理方式：** 在 export action 完成后由 WS `progress` 事件提供最终确认 snackbar。但由于 export 是 REST 调用触发的同步操作，REST 响应已包含结果，WS `progress` 事件仅作为冗余确认通道。

---

## 3. Export 功能 — 核心设计决策

### 3.1 问题：后端返回文件路径，Android 无法访问

当前后端 `/drama/export` 流程：
1. `export_script()` 在 Python 内存中生成 Markdown 字符串
2. 写入服务器本地文件系统
3. 返回 `{status, message, filepath, drama_folder, ...}`

Android 收到 `export_path: "/data/dramas/xxx/exports/xxx.md"` —— 此路径在手机上毫无意义。

### 3.2 方案对比

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 后端返回 content** | 在 ExportResponse 中添加 `content` 字段，包含完整 Markdown | 最简、一步到位 | 响应体大（完整剧本可能数十 KB） |
| **B: 新增下载端点** | `GET /drama/export/file` 返回文件流 | RESTful、支持大文件 | 多一个端点、两步操作 |
| **C: 仅 snackbar 提示** | 不做 Share Intent，只显示"已导出" snackbar | 零改动 | 用户体验极差——导出了但手机上拿不到 |

### 3.3 决策：方案 A — 后端返回 content

理由：
1. **大道至简** — 一个端点、一次请求、一步到位
2. 剧本 Markdown 通常 < 100KB，对 REST 响应完全可接受
3. Android 拿到 content 后可直接触发 `Intent.ACTION_SEND` Share Intent
4. 无需新增端点、无需文件下载逻辑
5. 后端 `export_script()` 已在内存中生成完整 Markdown，仅需额外一行 `content: markdown` 加入返回值

**后端改动量：**
- `app/api/models.py`：`ExportResponse` 添加 `content: str = ""`
- `app/state_manager.py`：`export_script()` 返回值添加 `content: markdown`
- `app/api/routers/queries.py`：无需改动（已 `ExportResponse(**result)` 自动映射）

**Android 改动量：**
- `ExportResponseDto.kt`：添加 `val content: String = ""`
- `DramaRepository.kt`：添加 `exportDrama()` 接口方法
- `DramaRepositoryImpl.kt`：实现 `exportDrama()`
- `DramaDetailViewModel.kt`：添加 export action + state
- `DramaDetailScreen.kt`：overflow menu 添加"导出"按钮

---

## 4. Export UI 流程设计

```
用户点击 overflow → "导出" → ViewModel.exportDrama()
                                    ↓
                              isExporting = true
                              dramaRepository.exportDrama("markdown")
                                    ↓
                         ┌──── 成功 ────┐──── 失败 ────┐
                         ↓              ↓              ↓
                   isExporting=false   isExporting=false
                   content 拿到       snackbar 显示错误
                         ↓
                   Intent.ACTION_SEND
                   type = "text/markdown"
                   extra = content
                   startActivity(shareIntent)
```

**Share Intent 效果：** 弹出 Android 系统分享面板，用户可选择：
- 发送到微信/Telegram
- 保存到 Google Drive
- 发送到邮件
- 复制到剪贴板
- 保存到文件管理器

**UI 状态：**
- `isExporting: Boolean = false` — 控制导出中状态
- 不需要额外的 Dialog，Share Intent 本身是系统 UI

---

## 5. 文件修改范围

### 后端 (3 文件)

| 文件 | 改动 |
|------|------|
| `app/api/models.py` | `ExportResponse` 添加 `content: str = ""` |
| `app/state_manager.py` | `export_script()` 返回值添加 `content: markdown` |
| — 无需改动 routers — | `ExportResponse(**result)` 自动映射 |

### Android (6 文件)

| 文件 | 改动 |
|------|------|
| `ExportResponseDto.kt` | 添加 `val content: String = ""` |
| `DramaRepository.kt` | 添加 `exportDrama()` 接口方法 |
| `DramaRepositoryImpl.kt` | 实现 `exportDrama()` |
| `DramaDetailViewModel.kt` | 3 事件处理 + export action + state |
| `DramaDetailScreen.kt` | overflow menu 添加"导出" |
| `DramaDetailUiState` (同 ViewModel 文件) | 添加 `isExporting` 字段 |

**总计：9 文件** (3 后端 + 6 Android)

---

## 6. 设计决策汇总

| # | 决策 | 选项 | 结论 | 理由 |
|---|------|------|------|------|
| D-21-01 | 未处理事件数量 | 5 vs 3 | **3** | actor_created/cast_update 已处理 |
| D-21-02 | `status` 事件处理 | 空分支 vs 状态更新 | **空分支 + Log.d** | scene_start 已覆盖其功能 |
| D-21-03 | `actor_status` 事件处理 | 精确更新 vs 全量刷新 | **精确更新 + preloadActorPanel 兜底** | 避免面板闪烁，保证数据一致 |
| D-21-04 | `progress` 事件处理 | snackbar vs 忽略 | **snackbar 确认** | export 完成后的 WS 确认通道 |
| D-21-05 | Export 内容获取 | 方案 A/B/C | **方案 A：后端返回 content** | 最简方案，一步到位 |
| D-21-06 | Export 分享方式 | Share Intent vs 保存文件 | **Share Intent** | 系统原生，无需权限，用户自由选择目标 |
| D-21-07 | Export UI 位置 | overflow menu vs 独立按钮 | **overflow menu "导出"项** | 低频操作，不占主界面空间 |

---

## 7. 风险与边界

| 风险 | 影响 | 缓解 |
|------|------|------|
| 大剧本 Markdown > 1MB | REST 响应慢 | 实际场景 unlikely；超过时可截断提示 |
| Share Intent 无可用应用 | 用户无法分享 | 提供 fallback：复制到剪贴板 |
| 后端 export_script 无活跃 drama | 返回 error | ViewModel 处理 error snackbar |

---

## 8. Success Criteria (修订)

基于事实纠正，修订 ROADMAP 中的 Success Criteria：

1. ~~Android ViewModel 正确处理 status/actor_status/actor_created/cast_update/progress 5种事件~~ → **Android ViewModel 正确处理 status/actor_status/progress 3种缺失事件**（actor_created/cast_update 已处理）
2. ~~DramaRepository.exportDramaContent() 调用后端 /export 端点并返回 Markdown 内容~~ → **后端 ExportResponse 包含 content 字段，DramaRepository.exportDrama() 返回含 Markdown 内容的响应**
3. DramaDetailViewModel 包含 export action + loading/success/error 状态管理 ✅
4. DramaDetailScreen overflow menu 包含 Export 按钮，触发 Android Share Intent 分享 ✅

---

*造化宗师审视完毕。删繁就简，3 事件 + 1 导出，至臻之境。*
