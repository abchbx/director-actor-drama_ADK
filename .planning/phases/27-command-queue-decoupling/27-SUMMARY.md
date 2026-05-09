# Phase 27 总结：命令队列解耦 + 锁粒度细化

## 状态

✅ 已完成

## 交付物

### 新增文件
- `app/api/command_queue.py` — CommandQueue 核心组件（异步队列 + Worker）
- `.planning/phases/27-command-queue-decoupling/27-CONTEXT.md` — 设计文档

### 修改文件
- `app/api/models.py` — CommandResponse 新增 command_id；新增 CommandStatusResponse
- `app/api/deps.py` — 新增 get_command_queue 依赖注入
- `app/api/app.py` — lifespan 中启动/停止 CommandQueue
- `app/api/routers/commands.py` — 导演模式端点全面改为异步入队

## 核心变更

**Before**：所有导演命令通过 `async with lock:` 串行阻塞执行
**After**：端点入队后立即返回（<50ms），后台 Worker 串行消费执行

## 测试验证

- [x] Linter 通过（0 errors）
- [x] CommandQueue 单元测试：enqueue 立即返回、多命令不阻塞、Worker 串行执行、状态轮询、内存清理、错误处理
- [x] `/next` 入队后 `/chat` 可立即入队（enqueue < 50ms）
- [x] WS 事件推送正常（event_callback 随命令入队，Worker 执行期间推送）
- [x] GET `/command/{id}` 轮询可用（CommandStatusResponse 返回 status/queue_depth/elapsed_seconds）

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| Worker 单点故障 | Worker 异常会被捕获，记录日志后继续消费下一条 |
| 命令堆积 | 队列无上限（UNLIMITED），但 Worker 单线程保证顺序 |
| 内存泄漏 | 已完成命令 5 分钟后自动清理，>100 条时触发清理 |
| REST 降级客户端白屏 | 新增 `/command/{id}` 端点供轮询 |
