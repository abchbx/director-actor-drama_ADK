"""Runner event stream extraction utility.

Iterates over ADK Runner event streams and extracts structured results:
- final_response: The director's final text response
- tool_results: Structured results from tool calls (function_response)
- event_callback: Optional async callback for each event (Phase 14 WebSocket)
"""

import asyncio
from typing import Any, Awaitable, Callable

from fastapi import HTTPException
from google.adk.events import Event
from google.adk.runners import Runner
from google.genai import types


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

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            # D-01: Event callback for WS real-time push
            # REST path: callback=None, behavior unchanged
            if event_callback:
                try:
                    await event_callback(event)
                except Exception:
                    pass  # Callback failure must NOT block Runner execution

            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            final_text += part.text
            elif event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_response and part.function_response.response:
                        tool_results.append(dict(part.function_response.response))

        return {"final_response": final_text, "tool_results": tool_results}

    try:
        return await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Command execution timed out")
