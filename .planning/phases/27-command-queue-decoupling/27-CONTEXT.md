# Phase 27: 命令队列解耦 + 锁粒度细化

## 目标

解决 Android 客户端在面对流式输出和独立 A2A Actor Service 时，单一全局协程锁成为严重瓶颈的问题。

## 核心问题

`app/api/app.py` 中创建了一个全局 `asyncio.Lock`：

```python
app.state.runner_lock = asyncio.Lock()
```

所有导演模式命令端点（`/next`, `/action`, `/speak`, `/steer`, `/auto`, `/end`, `/storm`, `/chat`）都通过 `async with lock:` 串行执行。当导演执行一场 `/next`（涉及多个 A2A 演员调用，耗时 30~120 秒）时，其他命令完全被阻塞。

## 解决方案

### 架构变更

**从：全局阻塞锁 → 到：异步命令队列 + 单 Worker 串行消费**

```
Before (阻塞):
  Client A: POST /next ──→ async with lock: run(30s) ──→ Response
  Client B: POST /chat ──→ [等待30s] ──→ async with lock: run(...) ──→ Response

After (非阻塞):
  Client A: POST /next ──→ enqueue(cmd_1) ──→ Response (status=queued, <50ms)
  Client B: POST /chat ──→ enqueue(cmd_2) ──→ Response (status=queued, <50ms)
                              ↓
                    CommandQueue Worker (单协程)
                              ↓
              cmd_1: async with lock: run(30s) → WS events
              cmd_2: async with lock: run(...) → WS events
```

### 新增组件

- `app/api/command_queue.py` — `CommandQueue` 类
  - `asyncio.Queue` 存储待执行命令
  - 单 `Worker` 协程串行消费，持有 `runner_lock` 执行
  - 命令状态跟踪（pending → running → completed/failed）
  - 自动清理已完成命令，防止内存泄漏

### 改造端点

| 端点 | 变更 |
|------|------|
| `POST /drama/start` | 保持不变（初始化状态快，STORM 已是后台任务） |
| `POST /drama/next` | `async with lock` → `command_queue.enqueue()` |
| `POST /drama/action` | `async with lock` → `command_queue.enqueue()` |
| `POST /drama/speak` | `async with lock` → `command_queue.enqueue()` |
| `POST /drama/steer` | `async with lock` → `command_queue.enqueue()` |
| `POST /drama/auto` | `async with lock` → `command_queue.enqueue()` |
| `POST /drama/end` | `async with lock` → `command_queue.enqueue()` |
| `POST /drama/storm` | `async with lock` → `command_queue.enqueue()` |
| `POST /drama/chat` | 普通消息入队；`/cast` 仍直接执行（快操作） |
| `POST /drama/free_chat` | 保持不变（bypass 锁，直联 A2A） |
| `GET /drama/command/{id}` | **新增** — 轮询命令执行状态/结果 |

### 模型变更

- `CommandResponse` 新增 `command_id: str = ""` 字段
- 新增 `CommandStatusResponse` 模型

### 生命周期变更

- `app/api/app.py` lifespan startup: 创建并启动 `CommandQueue`
- `app/api/app.py` lifespan shutdown: 优雅停止 `CommandQueue`

## 关键保证

1. **ADK 状态安全**：Worker 串行执行，同一时刻只有一个命令持有 `runner_lock`
2. **API 非阻塞**：端点 < 50ms 返回 `status=queued`
3. **实时推送**：WS event_callback 随命令入队，执行期间事件正常推送
4. **REST 降级**：无 WS 客户端可通过 `GET /command/{id}` 轮询结果
5. **内存安全**：已完成命令 5 分钟后自动清理

## 兼容性

- Android 端无需修改：WS 事件流不变，REST 响应新增 `command_id` 字段不影响现有解析
- `free_chat` 完全不受影响
- 查询端点（`/drama/status`, `/drama/scenes` 等）不使用锁，不受影响
