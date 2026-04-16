# Phase 15: Authentication - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

简单 Token 认证覆盖 REST + WebSocket，局域网/单用户场景，FastAPI HTTPBearer 依赖注入。不添加 OAuth、注册、多用户、token 刷新等复杂能力。核心价值：一把钥匙开一扇门——谁可连我。

</domain>

<decisions>
## Implementation Decisions

### Token 生成与存储
- **D-01:** `.env` 固定配置 `API_TOKEN=xxx` — 运维者设定，服务端启动时读取，重启不变。与现有 `.env` 机制（OPENAI_API_KEY 等）一致
- **D-02:** Token 格式 `secrets.token_urlsafe(32)` — 约 43 字符，256 bit 熵。单用户局域网场景绰绰有余
- **D-03:** 内存持有 `app.state.api_token` — 启动时从 `.env` 读取存入 app.state，进程重启重读。单进程单用户无需持久化到数据库
- **D-04:** 单 Token 共享 — 所有客户端（手机、平板、浏览器）使用同一 token。单用户场景大道至简

### Auth 绕过模式（Dev 模式）
- **D-05:** `.env` 中无 `API_TOKEN` 或为空时认证禁用 — 零配置启动：`git clone` 后 `python -m uvicorn app.api.app` 即可用，开发体验友好
- **D-06:** 启动时控制台 WARNING + 请求级别 debug 日志 — `⚠️ AUTH DISABLED: No API_TOKEN configured. All requests accepted.` 启动打印一次；每次请求 debug 级别记录，不打扰正常日志
- **D-07:** CORS 与 auth 绕过不耦合 — CORS 独立控制（Phase 13 已定 `allow_origins=["*"]` dev 模式），auth 绕过不影响 CORS 策略

### 认证端点
- **D-08:** `GET /api/v1/auth/verify` 返回 token 有效性 — Android App 连接时可先验证 token 再进入主界面。返回 `{"valid": true, "mode": "token"|"bypass"}`。此端点本身也需要认证（有 token 时）或自动通过（bypass 模式）

### WebSocket Token 验证
- **D-09:** WS 通过 `?token=xxx` query parameter 传 token — AUTH-03 已定，浏览器 WebSocket API 不支持自定义 header，此乃协议限制
- **D-10:** 先验证再 accept — 在 `websocket_endpoint` 入口提取 query parameter 中的 token 验证，无效则 raise `WebSocketException(status_code=4001)`，不消耗 ConnectionManager 资源。比 accept 后 close 更安全
- **D-11:** Dev 模式下 WS 也免认证 — 与 REST 行为一致，无 `API_TOKEN` 时 WS 连接直接 accept

### Token 生命周期
- **D-12:** 静态 token，无过期/刷新机制 — Token 生命周期 = 服务进程生命周期。重启后 .env 重读 token 不变。单用户局域网不需要动态刷新

### 安全加固
- **D-13:** 不做速率限制 — 单用户局域网，Runner 本身有 `asyncio.Lock` 串行化不会并发过载。Token 256 bit 熵暴力猜到宇宙热寂也猜不完
- **D-14:** 不在此阶段处理 HTTPS — HTTPS 是部署层关注点（nginx/caddy 反代），不是应用层。FastAPI 本身不处理 TLS
- **D-15:** 接受明文传输，局域网风险可控 — 局域网内中间人攻击概率极低。WS `?token=` 在 URL 中可能被日志记录，但信任网络下可接受。记录为已知限制
- **D-16:** Auth 事件记录到 Python logger — 认证成功/失败/绕过模式均记录。与现有 logging 体系一致，运维者可追踪异常访问

### Claude's Discretion
- HTTPBearer 依赖注入的具体实现方式（全局依赖 vs 路由级依赖）
- `app.state.auth_enabled` 布尔标志的存储位置和检查方式
- WebSocket query parameter token 提取的实现细节
- `/auth/verify` 端点的具体响应模型字段
- `.env.example` 中 `API_TOKEN` 的注释和示例值
- auth 相关单元测试和集成测试的组织方式

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目规划
- `.planning/ROADMAP.md` — Phase 15 定义、成功标准、依赖关系
- `.planning/REQUIREMENTS.md` — AUTH-01~04 需求定义
- `.planning/STATE.md` — v2.0 已决定的架构选型和风险表
- `.planning/PROJECT.md` — 项目愿景、约束、"简单 Token 认证"和"Out of Scope: OAuth/注册系统"定义

### Phase 13-14 上下文（直接前置）
- `.planning/phases/13-api-foundation/13-CONTEXT.md` — API 层决策、依赖注入体系、CORS 策略
- `.planning/phases/14-websocket-layer/14-CONTEXT.md` — WS 连接管理、heartbeat、replay buffer、event_callback

### 核心源码
- `app/api/deps.py` — **关键**：现有依赖注入体系（get_runner, get_runner_lock, get_tool_context），auth 依赖需在此添加
- `app/api/app.py` — FastAPI app factory，lifespan 中需读取 API_TOKEN 并存入 app.state
- `app/api/routers/commands.py` — 8 个命令端点，需添加 auth 依赖
- `app/api/routers/queries.py` — 6 个查询端点，需添加 auth 依赖
- `app/api/routers/websocket.py` — WS endpoint，需在 accept 前验证 query parameter token
- `app/api/ws_manager.py` — ConnectionManager，connect() 方法需与 auth 配合
- `app/api/models.py` — Pydantic 模型，需添加 AuthVerifyResponse 等模型
- `app/.env` — 现有环境变量，需添加 API_TOKEN
- `app/.env.example` — 环境变量示例，需添加 API_TOKEN 注释

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Depends()` 模式 (`app/api/deps.py`): 现有依赖注入体系完整，auth 依赖可如法炮制——`get_current_token` 从 app.state 读取，`require_auth` 作为 FastAPI HTTPBearer dependency
- `app.state` 属性 (`app/api/app.py`): 已存储 runner, session_service, runner_lock, connection_manager 等。auth 状态（api_token, auth_enabled）自然加入此模式
- `lifespan` 上下文管理器 (`app/api/app.py`): 启动时读取 `.env` 的天然位置，可在此初始化 auth 配置
- `.env` 机制 (`app/.env`): 已有 3 个环境变量，加入 `API_TOKEN` 零摩擦
- Pydantic 模型体系 (`app/api/models.py`): 可直接扩展 AuthVerifyResponse

### Established Patterns
- 依赖注入: `Depends(get_runner)`, `Depends(get_runner_lock)` — auth 依赖 `Depends(require_auth)` 保持一致
- 返回值格式: `{"status": "success"|"error", "message": "..."}` — auth 端点沿用
- 错误处理: `HTTPException(status_code=401, detail="Invalid token")` — 无效 token 统一 401
- 路由组织: `APIRouter` + `include_router` — auth 路由可独立 router 文件或加入现有 router
- 请求参数: `Request` 对象用于获取 app.state — auth 依赖同样需要 Request

### Integration Points
- `app/api/deps.py`: 新增 `require_auth` 依赖函数，所有受保护端点添加 `auth=Depends(require_auth)`
- `app/api/app.py`: lifespan 中读取 `API_TOKEN` 环境变量，存入 `app.state.api_token` + `app.state.auth_enabled`
- `app/api/routers/commands.py`: 8 个端点函数签名添加 `auth=Depends(require_auth)` 参数
- `app/api/routers/queries.py`: 6 个端点函数签名添加 `auth=Depends(require_auth)` 参数
- `app/api/routers/websocket.py`: websocket_endpoint 入口添加 token 验证逻辑
- `app/api/routers/` 或新文件: 新增 `GET /api/v1/auth/verify` 端点
- `app/.env` + `app/.env.example`: 添加 `API_TOKEN` 配置项

</code_context>

<specifics>
## Specific Ideas

- Token 从 `.env` 读取，不在代码中硬编码——与 OPENAI_API_KEY 保持一致
- Dev 模式（无 API_TOKEN）下启动打印醒目警告——运维者不可忽视
- WS 验证在 accept 前完成——不浪费 ConnectionManager 资源
- `GET /api/v1/auth/verify` 端点让 Android App 能优雅处理认证——先验证再进入
- Auth 依赖作为 FastAPI HTTPBearer——统一验证，无重复校验代码（AUTH-04）
- 所有 14 个 REST 端点 + 1 个 WS 端点受保护——覆盖完整，无遗漏

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-authentication*
*Context gathered: 2026-04-16*
