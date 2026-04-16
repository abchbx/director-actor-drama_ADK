# Phase 16: Android Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 16-android-foundation
**Areas discussed:** 服务器连接体验, 项目架构与依赖, 导航与屏幕结构, 主题与视觉风格

---

## 服务器连接体验

|| Option | Description | Selected |
||--------|-------------|----------|
|| A. 手动输入 IP:port | 最简单，两个文本框 + 连接按钮 | |
|| B. 手动输入 + 历史记录 | 输入一次后记住，下拉列表选历史 | ✓ |
|| C. mDNS 自动发现 | 后端广播 .local 服务，App 自动扫描 | |
|| D. 扫码连接 | 后端显示 QR，App 扫码自动填入 | |

**User's choice:** Claude's Discretion (全部由你决定)
**Selected:** B — 手动输入 + 历史记录，无需后端改动

|| Token 输入方式 | Description | Selected |
||----------------|-------------|----------|
|| A. 连接页面单独输入 | IP:port + Token 两个输入框 | |
|| B. 连接后自动检测 | 先连 IP:port，401 则弹 Token 输入 | ✓ |
|| C. 内嵌于 URL | 类似 http://token@ip:port | |

**User's choice:** Claude's Discretion
**Selected:** B — 连接后自动检测，bypass 模式零输入

**Additional decisions:**
- 连接失败：Snackbar + 重试按钮，区分错误类型
- 持久化：DataStore Preferences 存储服务器配置

---

## 项目架构与依赖

|| Option | Description | Selected |
||--------|-------------|----------|
|| Retrofit + OkHttp | 业界标准 REST 客户端 | ✓ |
|| Ktor Client | Kotlin 原生 HTTP 客户端 | |
|| Room 数据库 | 本地数据缓存 | (不选 — 纯在线) |
|| Navigation Compose | 官方推荐导航 | ✓ |
|| AppFlow | 第三方导航 | |

**User's choice:** Claude's Discretion
**Selected:**
- Kotlin 2.0.x + Compose BOM 2024.12
- Retrofit + OkHttp + kotlinx.serialization
- 无 Room（纯在线）
- Navigation Compose
- Hilt (APP-14 已定)
- minSdk 26, targetSdk 35

---

## 导航与屏幕结构

|| Option | Description | Selected |
||--------|-------------|----------|
|| 底部导航栏 | 3 tab: 戏剧列表/创建/设置 | ✓ |
|| 侧边导航抽屉 | Drawer + NavigationRail | |
|| 服务器连接独立屏幕 | 首屏为连接页 | |
|| 服务器连接在设置页 | 设置页顶部连接配置 | ✓ |

**User's choice:** Claude's Discretion
**Selected:**
- 底部导航栏 3 tab（drama-list / create / settings）
- drama-detail 从列表点击进入（非 tab）
- 服务器连接配置在设置页面
- 首次启动弹出连接引导 Dialog

---

## 主题与视觉风格

|| Option | Description | Selected |
||--------|-------------|----------|
|| Dynamic Color + 品牌色 fallback | API 31+ 动态色，低版本品牌色 | ✓ |
|| 仅品牌色 | 不用 Dynamic Color | |
|| 亮色模式默认 | 跟随系统 | |
|| 暗色模式默认 | 戏剧沉浸感 | ✓ |

**User's choice:** Claude's Discretion
**Selected:**
- MD3 Dynamic Color 启用 (API 31+)，fallback 深靛蓝品牌色
- 暗色模式默认
- 品牌色：深靛蓝 (#1A237E)
- Typography：MD3 默认 + titleLarge 加粗
- 形状：MD3 默认 rounded

---

## Claude's Discretion

All four areas were delegated to Claude's judgment by user request ("全部由你决定").

## Deferred Ideas

None — discussion stayed within phase scope
