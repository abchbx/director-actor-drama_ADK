"""Free chat service — direct A2A communication with actors (bypassing Director).

This module allows users to chat directly with actors without going through
the ADK Runner / Director agent. Messages are sent via A2A protocol to each
actor's independent service, and responses are collected and returned.

Used by: /drama/free_chat endpoint (Phase 25)
"""

import asyncio
import logging
import uuid
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


async def _call_actor_direct(
    actor_name: str,
    message: str,
    sender_name: str = "用户",
) -> dict:
    """Send a message to a single actor via A2A protocol and collect response.

    Args:
        actor_name: Name of the target actor.
        message: Message text to send.
        sender_name: Name of the sender (displayed to actor).

    Returns:
        dict with actor response, e.g. {"actor_name": str, "text": str, "status": str}
    """
    from app.actor_service import get_actor_remote_config

    config = get_actor_remote_config(actor_name)
    if not config:
        logger.warning("[FREE-CHAT] Actor config not found: %s", actor_name)
        return {
            "actor_name": actor_name,
            "text": f"[演员 {actor_name} 未找到]",
            "status": "error",
        }

    try:
        from a2a.client import ClientFactory, ClientConfig
        from a2a.types import AgentCard, Message, Part
    except ImportError as e:
        logger.error("[FREE-CHAT] a2a package not available: %s", e)
        return {
            "actor_name": actor_name,
            "text": f"[A2A客户端不可用: {e}]",
            "status": "error",
        }

    card_file = config["card_file"]
    try:
        import json
        with open(card_file, "r", encoding="utf-8") as f:
            card_data = json.load(f)
        agent_card = AgentCard(**card_data)
    except Exception as e:
        logger.error("[FREE-CHAT] Failed to load agent card for %s: %s", actor_name, e)
        return {
            "actor_name": actor_name,
            "text": f"[无法加载演员卡片: {e}]",
            "status": "error",
        }

    # Build message with sender identity prefix so actor knows who is talking
    full_message = f"[{sender_name}] {message}"

    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    client_config = ClientConfig(httpx_client=httpx_client, streaming=False)
    client = ClientFactory(config=client_config).create(card=agent_card)

    a2a_msg = Message(
        messageId=str(uuid.uuid4()),
        parts=[Part(text=full_message)],
        role="user",
    )

    texts = []
    try:
        async for event in client.send_message(a2a_msg):
            if isinstance(event, tuple):
                for item in event:
                    if hasattr(item, "artifacts") and item.artifacts:
                        for artifact in item.artifacts:
                            for part in getattr(artifact, "parts", []):
                                root = getattr(part, "root", None)
                                if root:
                                    t = getattr(root, "text", None)
                                    meta = getattr(root, "metadata", None)
                                    if t and not (meta and meta.get("adk_thought")):
                                        texts.append(t)
    except Exception as e:
        logger.error("[FREE-CHAT] A2A error for %s: %s", actor_name, e)
        await httpx_client.aclose()
        return {
            "actor_name": actor_name,
            "text": f"[通信错误: {e}]",
            "status": "error",
        }

    await httpx_client.aclose()
    response_text = "\n".join(texts).strip() if texts else "[无响应]"

    logger.info(
        "[FREE-CHAT] %s responded (%d chars): %.50s...",
        actor_name, len(response_text), response_text,
    )

    return {
        "actor_name": actor_name,
        "text": response_text,
        "status": "success",
    }


async def broadcast_free_chat(
    message: str,
    target_actors: list[str],
    sender_name: str = "用户",
    mention: Optional[str] = None,
) -> list[dict]:
    """Broadcast a free-chat message to one or more actors.

    Args:
        message: The user's message.
        target_actors: List of actor names currently on stage.
        sender_name: Display name of the sender.
        mention: If provided, only send to this actor; otherwise broadcast.

    Returns:
        List of response dicts from each actor.
    """
    if mention:
        # @mention mode: only talk to the mentioned actor
        if mention not in target_actors:
            logger.warning(
                "[FREE-CHAT] Mentioned actor %s not in target list %s",
                mention, target_actors,
            )
            return [{
                "actor_name": mention,
                "text": f"[演员 {mention} 不在当前场景中]",
                "status": "error",
            }]
        recipients = [mention]
    else:
        # Broadcast mode: talk to all actors on stage
        recipients = target_actors

    if not recipients:
        logger.warning("[FREE-CHAT] No recipients available")
        return []

    logger.info(
        "[FREE-CHAT] Broadcasting to %d actor(s): %s",
        len(recipients), recipients,
    )

    # Concurrent A2A calls to all recipients
    tasks = [
        _call_actor_direct(actor, message, sender_name)
        for actor in recipients
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Normalize exceptions into error dicts
    normalized = []
    for actor_name, result in zip(recipients, results):
        if isinstance(result, Exception):
            logger.error("[FREE-CHAT] Exception from %s: %s", actor_name, result)
            normalized.append({
                "actor_name": actor_name,
                "text": f"[调用异常: {result}]",
                "status": "error",
            })
        else:
            normalized.append(result)

    return normalized
