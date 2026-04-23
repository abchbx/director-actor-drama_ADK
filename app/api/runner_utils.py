"""Runner event stream extraction utility.

Iterates over ADK Runner event streams and extracts structured results:
|- final_response: The director's final text response
|- tool_results: Structured results from tool calls (function_response)
|- event_callback: Optional async callback for each event (Phase 14 WebSocket)

DEBUG: All lifecycle events are logged via logging module (server console)
     and optionally pushed as 'director_log' WS events for Android visibility.
"""

import asyncio
import logging
import time
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
    - final_response: Text from the final response event
    - tool_results: List of dicts from function_response events

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

    async def _collect() -> dict[str, Any]:
        final_text = ""
        tool_results: list[dict] = []
        event_count = 0
        start_time = time.monotonic()

        # DEBUG: Log command entry point
        cmd_label = message[:80] + ("..." if len(message) > 80 else "")
        logger.info("[DIRECTOR-LOG] 🚀 命令启动: %s (timeout=%.0fs)", cmd_label, timeout)

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
                "[DIRECTOR-LOG] ⏱️ [#%d] t=%.1fs | %s",
                event_count, elapsed, event_type,
            )

            # D-01: Event callback for WS real-time push
            if event_callback:
                try:
                    await event_callback(event)
                except Exception as exc:
                    logger.warning(
                        "[DIRECTOR-LOG] ⚠️ WS回调失败 [#%d]: %s", event_count, exc
                    )
                    pass  # Callback failure must NOT block Runner execution

            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            final_text += part.text
                            logger.info(
                                "[DIRECTOR-LOG] ✅ 最终响应片段 (%d字符): %.50s...",
                                len(part.text), part.text.strip(),
                            )
            elif event.content and event.parts:
                for part in event.parts:
                    if part.function_response and part.function_response.response:
                        tool_name = part.function_response.name or "?"
                        resp = part.function_response.response
                        status_val = resp.get("status", "ok")
                        msg_preview = str(resp.get("message", ""))[:60]
                        logger.info(
                            "[DIRECTOR-LOG] 🔧 Tool完成 [%s] status=%s | %.60s",
                            tool_name, status_val, msg_preview,
                        )
                        tool_results.append(dict(resp))

        total_time = time.monotonic() - start_time
        logger.info(
            "[DIRECTOR-LOG] 🏁 命令完成: %s (共%d事件, %.1f秒, %d工具调用, %d字符响应)",
            cmd_label, event_count, total_time,
            len(tool_results), len(final_text),
        )
        return {"final_response": final_text, "tool_results": tool_results}

    try:
        return await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(
            "[DIRECTOR-LOG] 💥 命令超时! '%s' 超过 %.1f 秒限制",
            message, timeout,
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
