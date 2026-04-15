"""Runner event stream extraction utility.

Iterates over ADK Runner event streams and extracts structured results:
- final_response: The director's final text response
- tool_results: Structured results from tool calls (function_response)
"""

import asyncio
from typing import Any

from fastapi import HTTPException
from google.adk.runners import Runner
from google.genai import types


async def run_command_and_collect(
    runner: Runner,
    message: str,
    user_id: str,
    session_id: str,
    timeout: float = 120.0,
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
