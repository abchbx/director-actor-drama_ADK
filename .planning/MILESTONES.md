# Milestones — Director-Actor-Drama

## v2.0 Android 移动端 — GAP CLOSURE IN PROGRESS

**Phases:** 6 (shipped) + 3 (gap closure) | **Plans:** 18 (done) + 3 (pending)

### Key Accomplishments

1. FastAPI REST API Server — 14 个 REST 端点 + WebSocket 实时推送 + 简单 Token 认证
2. Android App (Kotlin + Jetpack Compose) — Material Design 3 风格，MVVM + Hilt 架构
3. 戏剧交互主界面 — 创建/列表/详情/命令输入栏/场景历史/保存加载
4. 演员面板 + 状态概览 — 演员卡片/张力/弧线/时间线
5. 富文本渲染 + 剧本导出 — 角色名高亮/情绪标签/头像/Share Intent
6. WebSocket 自动重连 — 指数退避 + ConnectivityManager + 网络弹性

### Stats

- **Timeline:** 2 days (2026-04-15 → 2026-04-16)
- **LOC:** ~3,200 Python (api/) + ~5,000 Kotlin (android/)
- **Feat commits:** 18

### Archives

- `.planning/milestones/v2.0-ROADMAP.md` (pending)

## v1.0 无限畅写版 — SHIPPED 2026-04-14

**Phases:** 12 | **Plans:** 29 | **Tests:** 517 passed

### Key Accomplishments

1. 3 层记忆架构 + 异步压缩 — 支撑 50+ 场戏不溢出上下文
2. 无限叙事循环 + 混合推进模式 — AI 自主推进 + 用户随时干预无缝切换
3. 张力评分 + 冲突引擎 + Dynamic STORM — 自动检测平淡并注入转折
4. 一致性检查 + 矛盾修复 + 时间线追踪 — 保障"逻辑不断"核心承诺
5. 端到端集成 + 517 测试通过 — 全流程验证可交付

### Stats

- **Timeline:** 3 days (2026-04-11 → 2026-04-14)
- **LOC:** ~9,560 Python
- **Feat commits:** 30
- **Files modified:** 217

### Archives

- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`
