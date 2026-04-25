"""Runner event stream extraction utility.

Iterates over ADK Runner event streams and extracts structured results:
- final_response: The director's final text response (deduplicated)
- tool_results: Structured results from tool calls (function_response)
- event_callback: Optional async callback for each event (Phase 14 WebSocket)

★ 核心修复：基于 invocation_id 去重，确保一次命令只返回一条 final_response。
ADK Runner 在自动推进等多步骤场景中，可能产生多次 is_final_response() 事件。
每次 _collect 调用只保留最后一次 final_response，丢弃中间的重复响应。
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from fastapi import HTTPException
from google.adk.events import Event
from google.adk.runners import Runner
from google.genai import types

logger = logging.getLogger(__name__)


async def run_command_and_collect(
    runner: Runner,
    message: str,
    user_id: str,
    session_id: str,
    timeout: float = 120.0,
    event_callback: Callable[[Event], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Run a command through the ADK Runner and collect structured results.

    Iterates over the Runner event stream, extracting:
    - final_response: Text from the FINAL response event only (deduplicated)
    - tool_results: List of dicts from function_response events (deduplicated)

    ★ Dedup strategy:
    - Each _collect call gets a unique invocation_id
    - Only the LAST is_final_response() event's text is kept
    - function_response events with identical (name, response_id) are deduped
    - This prevents duplicate bubbles in Android when ADK yields multiple
      final_response events during auto-advance or multi-step flows.

    Args:
        runner: The ADK Runner instance.
        message: The user message to send.
        user_id: User ID for the session.
        session_id: Session ID for the session.
        timeout: Maximum seconds to wait before raising 504.
        event_callback: Optional async callback invoked for each Runner event.
            When provided (WS scenario), receives every event for real-time push.
            When None (REST scenario), behavior unchanged.

    Returns:
        Dict with "final_response" (str) and "tool_results" (list[dict]).

    Raises:
        HTTPException: 504 if the command execution times out.
    """
    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )

    # ★ 核心修复：每次调用分配唯一 invocation_id，用于日志追踪和去重
    invocation_id = uuid.uuid4().hex[:8]

    async def _collect() -> dict[str, Any]:
        # ★ 核心修复：只保留最后一次 final_response，丢弃中间的重复
        # ADK 在多步执行中（如 auto_advance）会产生多次 is_final_response()，
        # 每次都是子 agent 的"最终"输出，但对用户而言只有最后一次是真正的最终结果
        final_text = ""
        final_response_count = 0
        tool_results: list[dict] = []
        # ★ 去重集合：跟踪已处理的 (tool_name, id) 对，防止同一工具结果重复
        seen_tool_results: set[tuple[str, str]] = set()
        event_count = 0
        start_time = time.monotonic()

        # DEBUG: Log command entry point
        cmd_label = message[:80] + ("..." if len(message) > 80 else "")
        logger.info(
            "[DIRECTOR-LOG] 🚀 命令启动 [%s]: %s (timeout=%.0fs)",
            invocation_id, cmd_label, timeout,
        )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            event_count += 1
            elapsed = time.monotonic() - start_time

            # DEBUG: Log each event type at INFO level (visible in server console)
            event_type = _describe_event(event)
            logger.info(
                "[DIRECTOR-LOG] ⏱️ [%s] #%d t=%.1fs | %s",
                invocation_id, event_count, elapsed, event_type,
            )

            # D-01: Event callback for WS real-time push
            if event_callback:
                try:
                    await event_callback(event)
                except Exception as exc:
                    logger.warning(
                        "[DIRECTOR-LOG] ⚠️ WS回调失败 [%s #%d]: %s",
                        invocation_id, event_count, exc,
                    )
                    pass  # Callback failure must NOT block Runner execution

            if event.is_final_response():
                # ★ 核心修复：每次 is_final_response() 都覆盖 final_text
                # 只保留最后一次的文本，确保 CommandResponse 只包含单次聚合响应
                final_response_count += 1
                if event.content and event.content.parts:
                    text_parts = []
                    for part in event.content.parts:
                        if part.text:
                            text_parts.append(part.text)
                    if text_parts:
                        # ★ 覆盖而非追加 — 只保留最新一次 final_response
                        final_text = "".join(text_parts)
                        logger.info(
                            "[DIRECTOR-LOG] ✅ [%s] final_response#%d (%d字符): %.50s...",
                            invocation_id, final_response_count, len(final_text),
                            final_text.strip(),
                        )
                        if final_response_count > 1:
                            logger.warning(
                                "[DIRECTOR-LOG] ⚠️ [%s] 去重: 丢弃前%d次final_response，保留最新",
                                invocation_id, final_response_count - 1,
                            )
            elif event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_response and part.function_response.response:
                        tool_name = part.function_response.name or "?"
                        resp = part.function_response.response

                        # ★ 核心修复：基于 (tool_name, id) 去重 tool_results
                        # ADK 有时会对同一个工具调用产生重复的 function_response 事件
                        # ★ 修复去重键冲突：actor_speak/director_narrate/create_actor 等工具
                        # 没有 "id" 或 "scene_number" 字段，导致所有同类结果被错误去重。
                        # 使用 ADK function_response 自带的 id（每次调用唯一）作为首选去重键。
                        resp_id = resp.get("id", resp.get("scene_number", ""))
                        # 如果返回值没有唯一标识，使用 ADK 分配的 function_response.id
                        # 该 id 在每次工具调用时由 ADK 自动生成，保证全局唯一
                        if not resp_id and part.function_response.id:
                            resp_id = part.function_response.id
                        # 最终兜底：用 actor_name + situation 哈希生成唯一键
                        if not resp_id:
                            actor = resp.get("actor_name", "")
                            msg = str(resp.get("message", resp.get("situation", "")))[:50]
                            resp_id = f"{actor}:{msg}"
                        dedup_key = (tool_name, str(resp_id))

                        if dedup_key in seen_tool_results:
                            logger.warning(
                                "[DIRECTOR-LOG] ⚠️ [%s] 去重: 跳过重复 tool_result %s",
                                invocation_id, dedup_key,
                            )
                            continue
                        seen_tool_results.add(dedup_key)

                        status_val = resp.get("status", "ok")
                        msg_preview = str(resp.get("message", ""))[:60]
                        logger.info(
                            "[DIRECTOR-LOG] 🔧 [%s] Tool完成 [%s] status=%s | %.60s",
                            invocation_id, tool_name, status_val, msg_preview,
                        )
                        tool_results.append(dict(resp))

        total_time = time.monotonic() - start_time
        logger.info(
            "[DIRECTOR-LOG] 🏁 [%s] 命令完成: %s (共%d事件, %.1f秒, %d工具调用, %d字符响应, final_count=%d)",
            invocation_id, cmd_label, event_count, total_time,
            len(tool_results), len(final_text), final_response_count,
        )
        return {"final_response": final_text, "tool_results": tool_results}

    try:
        return await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(
            "[DIRECTOR-LOG] 💥 [%s] 命令超时! '%s' 超过 %.1f 秒限制",
            invocation_id, message, timeout,
        )
        raise HTTPException(status_code=504, detail="Command execution timed out")


def _describe_event(event: Event) -> str:
    """Return a human-readable one-line description of an ADK Event."""
    parts_desc = []
    if not event.content or not event.content.parts:
        return f"[empty_event author={event.author}]"
    for part in event.content.parts:
        if part.function_call:
            fn = part.function_call
            args_preview = ""
            if fn.args:
                args_str = str(dict(fn.args))
                args_preview = f"({args_str[:80]})"
            parts_desc.append(f"CALL {fn.name}{args_preview}")
        elif part.function_response:
            fr = part.function_response
            resp = fr.response or {}
            status = resp.get("status", "")
            msg = str(resp.get("message", ""))[:40]
            parts_desc.append(f"RESP {fr.name} [{status}] {msg}")
        elif part.text:
            text_preview = part.text.strip().replace("\n", " ")[:60]
            parts_desc.append(f"TEXT({len(part.text)}ch): {text_preview}")
        else:
            parts_desc.append(f"[unknown_part]")
    return " | ".join(parts_desc) if parts_desc else "[no_parts]"
