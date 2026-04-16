# Phase 17: Android Interaction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 17-android-interaction
**Areas discussed:** 戏剧创建流程, 戏剧列表与卡片, 主戏剧屏幕与实时场景, 场景历史与导航

---

## 戏剧创建流程

|| Option | Description | Selected |
|--------|-------------|----------|
| 全屏创建表单 + STORM 进度 + 自动跳转 | 主题输入占满屏幕中央，STORM 事件实时更新进度，完成后自动跳转 DramaDetail | ✓ |
| 简洁表单 + Loading spinner | 主题输入后显示 spinner，等待 REST 返回后跳转 | |
| 分步引导 (Wizard) | 第一步输入主题，第二步展示 STORM 结果，第三步确认开始 | |

**User's choice:** Claude 代决 — 全屏创建表单 + STORM 进度 + 自动跳转
**Notes:** 沉浸式体验优先；STORM 进度让用户感知 AI 思考过程；完成后自动跳转减少操作步骤

---

## 戏剧列表与卡片

|| Option | Description | Selected |
|--------|-------------|----------|
| 紧凑卡片 + 三点菜单 | 两行信息（主题+状态/场数+时间），DropdownMenu 操作 | ✓ |
| 展开卡片 + 内联按钮 | 卡片内直接显示加载/删除按钮 | |
| 滑动操作 (Swipe) | 左滑删除，右滑加载 | |

**User's choice:** Claude 代决 — 紧凑卡片 + 三点菜单
**Notes:** 紧凑布局信息密度高；三点菜单不占卡片空间，MD3 规范；滑动操作与系统返回手势冲突

---

## 主戏剧屏幕与实时场景

|| Option | Description | Selected |
|--------|-------------|----------|
| 角色分段气泡 + 底部命令栏 + 快捷芯片 | 聊天气泡式渲染，底部固定输入栏，Chip 快捷命令 | ✓ |
| 纯文本滚动 + 底部命令栏 | 场景内容为纯文本段落，底部输入栏 | |
| 卡片时间线 + 底部命令栏 | 每个场景/对白为独立卡片，垂直时间线布局 | |

**User's choice:** Claude 代决 — 角色分段气泡 + 底部命令栏 + 快捷芯片
**Notes:** 气泡式最沉浸，与戏剧对白场景天然契合；快捷芯片降低命令输入门槛；纯文本太平淡，卡片太松散

---

## 场景历史与导航

|| Option | Description | Selected |
|--------|-------------|----------|
| 底部半屏 BottomSheet + 摘要列表 | 右上角历史按钮，BottomSheet 展示场景摘要，点击跳转 | ✓ |
| 侧边 NavigationDrawer | 左侧抽屉拉出场景列表 | |
| 独立历史页面 | 从主屏幕导航到独立的历史浏览页面 | |

**User's choice:** Claude 代决 — 底部半屏 BottomSheet + 摘要列表
**Notes:** 轻量即开即用；侧边 Drawer 与系统返回手势冲突；独立页面增加导航复杂度；BottomSheet 是最自然的"看一眼历史"交互

---

## Claude's Discretion

- `DramaItemDto` 具体字段设计和序列化策略
- 聊天气泡 Compose 组件拆分方式
- 命令输入文本解析逻辑
- WS 事件到 UI 状态的 Flow 转换架构
- BottomSheet peekHeight 和展开行为
- 场景历史数据获取方案细节
- 输入栏软键盘交互
- LazyColumn 自动滚动到底部策略

## Deferred Ideas

- 演员面板 — Phase 18 APP-07
- 富文本渲染增强 — Phase 18 APP-11
- WS 自动重连 + 指数退避 — Phase 18 APP-15
- 剧本导出 — Phase 18 APP-09
- 戏剧状态概览 — Phase 18 APP-08
- Typing 指示器增强 — Phase 18 APP-10
