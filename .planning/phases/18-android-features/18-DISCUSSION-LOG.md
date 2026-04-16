# Phase 18: Android Features - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 18-android-features
**Areas discussed:** 演员面板设计, 戏剧状态概览, Typing指示器增强+富文本渲染, 剧本导出+WS自动重连

---

## 演员面板设计

|| Option | Description | Selected |
|--------|-------------|----------|
| 主屏幕右侧 Drawer | 从右向左滑出，不遮挡场景内容，沉浸感好 | ✓ |
| 底部导航新增"演员"Tab | 固定入口，但增加导航层级 | |
| TopAppBar演员Icon→BottomSheet | 点击弹出BottomSheet，轻量快捷 | |

**Q2: 演员卡片展示信息**

|| Option | Description | Selected |
|--------|-------------|----------|
| 紧凑三行 | 名字(加粗)+身份+情绪badge，点击展开详情 | ✓ |
| 详细卡片 | 名字+身份+性格+情绪+A2A状态+记忆，一屏3-4张 | |
| 极简单行 | 名字+身份+情绪emoji，类似聊天列表 | |

**Q3: A2A服务状态展示**

|| Option | Description | Selected |
|--------|-------------|----------|
| 后端新增/cast/status端点 | 返回A2A进程存活状态，Android展示绿/红圆点 | ✓ |
| 前端仅展示静态角色信息 | 不展示A2A状态，避免后端改动 | |
| 前端推测状态 | 根据WS事件被动更新，不主动查询 | |

**Q4: 记忆摘要展示**

|| Option | Description | Selected |
|--------|-------------|----------|
| 截取前100字+"查看更多" | 默认折叠，点击展开完整记忆 | ✓ |
| 完全不展示记忆 | 面板只看角色档案 | |
| 仅展示关键词标签 | 从memory提取3-5个关键词 | |

**User's choice:** 全部由 Claude 决定（"由你决定"）

---

## 戏剧状态概览

**Q1: 展示形式**

|| Option | Description | Selected |
|--------|-------------|----------|
| TopAppBar下拉展开卡片 | 点击TopAppBar区域展开compact卡片，再点收回 | ✓ |
| 独立BottomSheet | 类似场景历史，从底部弹出 | |
| 主屏幕内嵌状态行 | TopAppBar下方常驻一行指标 | |

**Q2: 包含指标**

|| Option | Description | Selected |
|--------|-------------|----------|
| 全面五指标 | 场景号+张力+弧线进度+时间段+演员数 | ✓ |
| 核心三指标 | 场景号+张力+时间段 | |
| 仅场景+张力 | 最精简 | |

**Q3: API策略**

|| Option | Description | Selected |
|--------|-------------|----------|
| 扩展/drama/status响应 | 新增arc_progress和time_period字段 | ✓ |
| 新增独立/drama/overview端点 | 分离关注点 | |
| 前端仅展示WS推送数据 | 不新增API | |

**User's choice:** 全部由 Claude 决定

---

## Typing指示器增强 + 富文本渲染

**Q1: Typing增强程度**

|| Option | Description | Selected |
|--------|-------------|----------|
| 脉冲动画+上下文文案 | 根据typing.data.tool动态切换"导演正在构思..."/"演员正在思考..." | ✓ |
| 骨架屏占位气泡 | 灰色气泡占位暗示即将出现内容 | |
| 全屏遮罩+进度提示 | 更强烈等待反馈，但打断沉浸感 | |

**Q2: 角色名高亮样式**

|| Option | Description | Selected |
|--------|-------------|----------|
| 角色名加粗+主题色 | titleMedium.bold + 基于角色名hash的专属色 | ✓ |
| 角色名普通文本 | 同字号仅加粗不加色 | |
| 角色名标签芯片 | @mention风格芯片 | |

**Q3: 情绪标签视觉**

|| Option | Description | Selected |
|--------|-------------|----------|
| 小圆角badge紧跟角色名 | 如"李明😡愤怒"，紧凑直观 | ✓ |
| 独立一行情绪条 | 角色名下方单独一行 | |
| 不显示情绪标签 | 仅在演员面板查看 | |

**Q4: 首字母圆形头像配色**

|| Option | Description | Selected |
|--------|-------------|----------|
| 基于角色名hash固定色 | 每个角色固定颜色，辨识度高 | ✓ |
| 统一品牌色 | 所有角色同一颜色 | |
| 基于情绪动态变色 | 颜色随情绪变化 | |

**User's choice:** 全部由 Claude 决定

---

## 剧本导出 + WS自动重连

**Q1: 剧本导出交互流程**

|| Option | Description | Selected |
|--------|-------------|----------|
| 后端返回Markdown文本+前端Share | 扩展ExportResponse加content字段，写入临时文件+系统分享 | ✓ |
| 后端提供下载URL+前端下载 | 新增文件下载端点 | |
| 后端仅返回路径+前端展示 | 用户自行查看，体验差 | |

**Q2: WS重连指数退避**

|| Option | Description | Selected |
|--------|-------------|----------|
| 1s→2s→4s→8s→16s→30s封顶 | 业界标准，连接成功后重置 | ✓ |
| 1s→3s→5s→10s→30s | 更快初始退避但步进不均 | |
| 固定5s间隔 | 简单但不优雅 | |

**Q3: 网络切换检测**

|| Option | Description | Selected |
|--------|-------------|----------|
| onFailure+ConnectivityManager监听 | 网络恢复立即重连，不等待退避 | ✓ |
| 仅依赖onFailure退避重连 | 不监听网络变化 | |
| 定时轮询/auth/verify | 定期检查连通性，浪费资源 | |

**Q4: 重连后状态恢复**

|| Option | Description | Selected |
|--------|-------------|----------|
| 重连后请求/drama/status刷新 | 结合WS replay补齐状态 | ✓ |
| 仅依赖WS replay buffer | 可能遗漏非事件类状态 | |
| 重连后全量重建 | 清空气泡+重建，最安全但闪烁 | |

**User's choice:** 全部由 Claude 决定

---

## Claude's Discretion

- 演员 Drawer 的具体 Compose 组件拆分
- 状态概览下拉卡片展开/收起动画参数
- 角色名 hash → 颜色映射算法
- 情绪 badge 圆角半径和内边距
- 导出临时文件命名和清理策略
- WS 重连协程管理
- ConnectivityManager 生命周期绑定
- 重连期间 UI 状态指示

## Deferred Ideas

None — discussion stayed within phase scope
