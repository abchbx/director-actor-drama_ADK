# Phase 15: Authentication - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 15-authentication
**Areas discussed:** Token 生成与存储, Auth 绕过模式, WebSocket Token 验证, 安全加固

---

## Token 生成与存储

| Option | Description | Selected |
|--------|-------------|----------|
| .env 固定配置 | `API_TOKEN=xxx` 写入 .env，运维者设定，重启不变 | ✓ |
| 启动时随机生成 | `secrets.token_urlsafe(32)` 生成新 token，打印到控制台 | |
| 首次请求动态生成 | App 首连时服务端生成 token 返回 | |

**User's choice:** Claude 代定 → .env 固定配置
**Notes:** 与现有 `.env` 机制一致，运维者完全掌控

| Option | Description | Selected |
|--------|-------------|----------|
| URL-safe 32 字节 | `secrets.token_urlsafe(32)`，约 43 字符，256 bit 熵 | ✓ |
| UUID v4 | 36 字符，122 bit 熵 | |
| 自定义可读格式 | 如 `dad-xxxx-xxxx-xxxx` | |

**User's choice:** Claude 代定 → URL-safe 32 字节

| Option | Description | Selected |
|--------|-------------|----------|
| 内存持有 | `app.state.api_token`，进程重启重读 .env | ✓ |
| 配置文件 + 内存 | 额外写入 `app/.api_token` 文件 | |
| 仅 .env 文件 | 每次验证时重新读 .env | |

**User's choice:** Claude 代定 → 内存持有

| Option | Description | Selected |
|--------|-------------|----------|
| 单 Token | 所有客户端共享同一 token | ✓ |
| 多 Token 白名单 | `.env` 支持 `API_TOKENS=tok1,tok2,tok3` | |

**User's choice:** Claude 代定 → 单 Token

---

## Auth 绕过模式

| Option | Description | Selected |
|--------|-------------|----------|
| .env 无 API_TOKEN 即绕过 | 零配置启动，开发体验最友好 | ✓ |
| 显式 AUTH_ENABLED=false | 独立开关，多一个配置项 | |
| 绕过仅限 localhost | 局域网 Android 连接也会被拦截 | |

**User's choice:** Claude 代定 → .env 无 API_TOKEN 即绕过

| Option | Description | Selected |
|--------|-------------|----------|
| 启动 WARNING + 请求 debug | 运维者知情，不打扰正常日志 | ✓ |
| 仅启动时警告 | 出问题无审计 | |
| 无警告 | 安静到危险 | |

**User's choice:** Claude 代定 → 启动 WARNING + 请求 debug

| Option | Description | Selected |
|--------|-------------|----------|
| CORS 独立控制 | 不与 auth 绕过耦合 | ✓ |
| 绕过时放宽 CORS | 耦合两个安全维度 | |

**User's choice:** Claude 代定 → CORS 独立控制

| Option | Description | Selected |
|--------|-------------|----------|
| GET /api/v1/auth/verify | App 可先验证 token 再进入主界面 | ✓ |
| 不提供验证端点 | App 无法区分 token 错误和服务器不可达 | |

**User's choice:** Claude 代定 → 提供验证端点

---

## WebSocket Token 验证

| Option | Description | Selected |
|--------|-------------|----------|
| ?token=xxx query parameter | 浏览器 WS API 不支持自定义 header，此乃协议限制 | ✓ |
| 连接后首条消息发送 token | 先 accept 再验证，泄露资源 | |

**User's choice:** Claude 代定 → query parameter（AUTH-03 已定）

| Option | Description | Selected |
|--------|-------------|----------|
| 握手前拒绝: WebSocketException(4001) | 不消耗 ConnectionManager 资源 | ✓ |
| Accept 后 close code=4001 | ROADMAP 方案，短暂 accept 可能泄露资源 | |
| 混合: 先验证再 accept | 最安全，需调整代码结构 | |

**User's choice:** Claude 代定 → 握手前拒绝 WebSocketException(4001)

| Option | Description | Selected |
|--------|-------------|----------|
| Dev 模式下 WS 免认证 | 与 REST 行为一致 | ✓ |
| WS 必须带特殊标记 | 多此一举 | |

**User's choice:** Claude 代定 → Dev 模式 WS 免认证

| Option | Description | Selected |
|--------|-------------|----------|
| 无过期，静态 token | Token 生命周期 = 进程生命周期 | ✓ |
| 定期刷新 | 过度工程 | |
| 手动刷新端点 | 当前不需要 | |

**User's choice:** Claude 代定 → 无过期静态 token

---

## 安全加固

| Option | Description | Selected |
|--------|-------------|----------|
| 不做速率限制 | Runner Lock 已串行化，256 bit 熵不可暴力猜 | ✓ |
| 基础速率限制 | 增加依赖和配置 | |
| 仅 auth 端点限速 | Token 熵已足够防暴力 | |

**User's choice:** Claude 代定 → 不做速率限制

| Option | Description | Selected |
|--------|-------------|----------|
| 不在此阶段处理 HTTPS | 部署层关注点（nginx/caddy 反代） | ✓ |
| FastAPI 内置 HTTPS | 增加运维复杂度 | |
| 记录为已知风险 | 承认但不行动 | |

**User's choice:** Claude 代定 → 不在此阶段处理

| Option | Description | Selected |
|--------|-------------|----------|
| 接受明文，局域网可控 | 记录为已知限制 | ✓ |
| WS 改用首条消息传 token | 与 D-10 先验后 accept 矛盾 | |

**User's choice:** Claude 代定 → 接受明文

| Option | Description | Selected |
|--------|-------------|----------|
| Python logger 记录 auth 事件 | 与现有 logging 一致 | ✓ |
| 专门 auth 审计文件 | 过度工程 | |
| 不记录 | 安全盲区 | |

**User's choice:** Claude 代定 → Python logger

---

## Claude's Discretion

- HTTPBearer 依赖注入的具体实现方式
- auth_enabled 布尔标志的存储和检查方式
- WS query parameter token 提取实现
- /auth/verify 响应模型字段
- .env.example 中 API_TOKEN 注释
- auth 测试组织方式

## Deferred Ideas

None — discussion stayed within phase scope
