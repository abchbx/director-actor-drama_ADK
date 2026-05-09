"""Command Queue — asynchronous command execution decoupling.

Replaces the global asyncio.Lock blocking pattern with a single-worker
asyncio.Queue: API endpoints enqueue commands and return immediately;
a background worker consumes the queue serially, holding the runner_lock
only during actual execution.

Phase 27: 锁粒度细化 — 全局阻塞锁 → 队列串行化
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from google.adk.runners import Runner

from app.api.runner_utils import run_command_and_collect

logger = logging.getLogger(__name__)

USER_ID = "drama_user"
SESSION_ID = "drama_session"


@dataclass
class QueuedCommand:
    """A single command waiting in the queue."""

    id: str
    command_text: str
    user_id: str
    session_id: str
    event_callback: Callable[..., Awaitable[None]] | None
    created_at: float = field(default_factory=time.monotonic)
    status: str = "pending"  # pending → running → completed | failed
    result: dict | None = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None


class CommandQueue:
    """Serial command queue with a single async worker.

    Guarantees:
    - Commands are executed strictly one-at-a-time (ADK state safety)
    - API endpoints return in < 50 ms (just enqueue)
    - Results are delivered via event_callback (WebSocket) or polled later
    """

    def __init__(self, runner: Runner, lock: asyncio.Lock):
        self._runner = runner
        self._lock = lock
        self._queue: asyncio.Queue[QueuedCommand] = asyncio.Queue()
        self._commands: dict[str, QueuedCommand] = {}
        self._worker_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background worker coroutine."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("[CommandQueue] Worker started")

    async def stop(self) -> None:
        """Signal the worker to stop and wait for graceful shutdown."""
        if not self._running:
            return
        self._running = False
        # Inject a sentinel to wake the worker if it's blocked on get()
        sentinel = QueuedCommand(
            id="__sentinel__",
            command_text="",
            user_id="",
            session_id="",
            event_callback=None,
        )
        await self._queue.put(sentinel)
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("[CommandQueue] Worker did not stop gracefully, cancelling")
                self._worker_task.cancel()
            except asyncio.CancelledError:
                pass
        logger.info("[CommandQueue] Worker stopped")

    async def enqueue(
        self,
        command_text: str,
        event_callback: Callable[..., Awaitable[None]] | None = None,
    ) -> str:
        """Enqueue a command and return its tracking ID immediately.

        Args:
            command_text: The CLI-formatted command string (e.g., "/next").
            event_callback: Optional async callback for WS real-time push.

        Returns:
            command_id: UUID for status polling.
        """
        cmd_id = f"cmd_{uuid.uuid4().hex[:12]}"
        cmd = QueuedCommand(
            id=cmd_id,
            command_text=command_text,
            user_id=USER_ID,
            session_id=SESSION_ID,
            event_callback=event_callback,
        )
        self._commands[cmd_id] = cmd
        await self._queue.put(cmd)
        logger.info("[CommandQueue] Enqueued [%s]: %s", cmd_id, command_text[:80])
        return cmd_id

    def get_command(self, command_id: str) -> QueuedCommand | None:
        """Get the status/result of a previously enqueued command."""
        return self._commands.get(command_id)

    @property
    def queue_depth(self) -> int:
        """Current number of pending commands in the queue."""
        return self._queue.qsize()

    def _cleanup_old_commands(self, max_age_seconds: float = 300.0) -> None:
        """Remove completed commands older than max_age to prevent memory leak."""
        now = time.monotonic()
        expired = [
            cid for cid, cmd in self._commands.items()
            if cmd.status in ("completed", "failed")
            and cmd.completed_at is not None
            and (now - cmd.completed_at) > max_age_seconds
        ]
        for cid in expired:
            del self._commands[cid]
        if expired:
            logger.debug("[CommandQueue] Cleaned up %d old commands", len(expired))

    async def _worker_loop(self) -> None:
        """Main worker: consume queue, hold lock, execute, repeat."""
        while self._running:
            try:
                cmd: QueuedCommand = await self._queue.get()
            except asyncio.CancelledError:
                break

            # Sentinel check for shutdown
            if cmd.id == "__sentinel__":
                self._queue.task_done()
                break

            cmd.status = "running"
            cmd.started_at = time.monotonic()
            logger.info(
                "[CommandQueue] Executing [%s]: %s (queue_depth=%d)",
                cmd.id, cmd.command_text[:80], self._queue.qsize(),
            )

            try:
                # ★ 核心：此处持有全局 runner_lock，但 API 端点不再阻塞
                async with self._lock:
                    result = await run_command_and_collect(
                        self._runner,
                        cmd.command_text,
                        cmd.user_id,
                        cmd.session_id,
                        event_callback=cmd.event_callback,
                    )
                cmd.status = "completed"
                cmd.result = result
                cmd.completed_at = time.monotonic()
                elapsed = cmd.completed_at - cmd.started_at
                logger.info(
                    "[CommandQueue] Completed [%s] in %.2fs (tools=%d)",
                    cmd.id, elapsed, len(result.get("tool_results", [])),
                )
            except Exception as e:
                cmd.status = "failed"
                cmd.error = str(e)
                cmd.completed_at = time.monotonic()
                logger.exception("[CommandQueue] Failed [%s]: %s", cmd.id, e)
                # Push error via callback so Android can display it
                if cmd.event_callback:
                    try:
                        await cmd.event_callback({
                            "type": "error",
                            "data": {"message": f"命令执行失败: {e}"},
                        })
                    except Exception:
                        pass
            finally:
                self._queue.task_done()
                # Periodic cleanup
                if len(self._commands) > 100:
                    self._cleanup_old_commands()
