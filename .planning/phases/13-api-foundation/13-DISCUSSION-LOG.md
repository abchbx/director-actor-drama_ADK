# Phase 13: API Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 13-api-foundation
**Areas discussed:** Runner 集成策略, 端点设计细节, 会话与互斥管理, 状态迁移方案

---

## Runner 集成策略

|| Option | Description | Selected |
|--------|-------------|----------|
| 共享 Runner + 单 Session | 与 CLI 行为一致，单用户模式最简单，互斥天然保证 | ✓ |
| 每请求新 Session | 理论上支持多 session，但当前需求是单用户模式，过度设计 | |
| 共享 Runner + Session 池 | 为未来多用户预留，但当前 scope 外 | |

|| Option | Description | Selected |
|--------|-------------|----------|
| 同步等待完整结果 | Phase 13 只做 REST，120s 超时，Phase 14 加 WS 后升级 | ✓ |
| 202 Accepted + 轮询 | 先返回 task_id，前端轮询 status，增加轮询逻辑 | |
| 202 Accepted + WS 推 | REST 发命令，结果通过 WS 推，依赖 WS 先就绪 | |

**User's choice:** Claude 决断 — 共享 Runner + 单 Session，同步等待完整结果
**Notes:** 与 CLI 行为一致，Phase 14 WebSocket 自然升级为流式体验

---

## 端点设计细节

|| Option | Description | Selected |
|--------|-------------|----------|
| final_response + 结构化 tool 结果 | 提取 scene_number, formatted_scene, actors_in_scene 等，前端有丰富数据 | ✓ |
| 只返回 final_response 文本 | 最简单，但丢失 tool 中间过程 | |
| 返回全部事件列表 | 最完整但冗余，前端用不到 | |

|| Option | Description | Selected |
|--------|-------------|----------|
| 混合模式 | 端点级错误 HTTP 4xx，tool 业务错误 200 + status: error | ✓ |
| HTTP 200 + 业务 status | 所有错误包在 200 里，前端判断 | |
| HTTP 语义全覆盖 | 所有错误映射为 HTTP 4xx/5xx | |

|| Option | Description | Selected |
|--------|-------------|----------|
| 直接调 state_manager | 更快，不触发 LLM，与查询式定位一致 | ✓ |
| 走 Runner | 与 CLI 行为一致，但 save/load 不需要 LLM | |

**User's choice:** Claude 决断 — D-03/D-04/D-05
**Notes:** save/load 直接调 state_manager，数据操作不需要 LLM

---

## 会话与互斥管理

|| Option | Description | Selected |
|--------|-------------|----------|
| 先自动保存旧 drama 再覆盖 | 安全优先，不丢数据，与 CLI quit-auto-save 精神一致 | ✓ |
| 自动覆盖 | 与 CLI 行为一致，最简单 | |
| 拒绝（409 Conflict） | 必须先 /end 或 /save，防止意外丢失 | |

|| Option | Description | Selected |
|--------|-------------|----------|
| Lock file | PID 写入 app/.api.lock，CLI/API 互检，可检测 stale | ✓ |
| 端口检测 | CLI 和 API 监听不同端口，无需显式互斥 | |
| 进程检测 | 检查其他进程持有 _actor_processes | |

|| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI startup 创建 | 与进程生命周期一致，Actor 服务 shutdown 时也清理 | ✓ |
| 首次请求懒创建 | 避免启动开销，但首次请求更慢 | |

**User's choice:** Claude 决断 — D-06/D-07/D-08
**Notes:** Lock file 是最可靠的互斥机制，stale lock 可通过 PID 存活检查处理

---

## 状态迁移方案

|| Option | Description | Selected |
|--------|-------------|----------|
| 直接用 state["drama"]["theme"] | 已存在且冗余，CONCERNS.md 确认 dead code | ✓ |
| 引入 SessionContext 对象 | 新建 dataclass 封装 theme + runner + session | |

|| Option | Description | Selected |
|--------|-------------|----------|
| 删全局变量，强制 tool_context | _get_current_theme(tool_context) 必须传参 | ✓ |
| 保留函数移除 fallback | 无参报错，有参正常 | |

|| Option | Description | Selected |
|--------|-------------|----------|
| CLI 自然兼容 | 走 Runner，tool_context 自动注入 | ✓ |
| CLI 需要额外适配 | 某些非 Runner 路径需手动传 theme | |

**User's choice:** Claude 决断 — D-09/D-10/D-11
**Notes:** CONCERNS.md 已确认 _current_drama_folder 是 dead code，彻底删除

---

## Claude's Discretion

- Pydantic 模型具体字段设计
- FastAPI 路由组织方式（单文件 vs 多文件 router）
- Lock file 的 stale 检测策略
- 命令式端点从 Runner 事件流提取结构化结果的实现方式
- CORS 具体允许的 origin 列表

## Deferred Ideas

None — discussion stayed within phase scope
