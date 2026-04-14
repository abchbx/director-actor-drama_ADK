"""Dynamic actor A2A service launcher.

Each actor runs as an independent A2A service on its own port,
with its own session, memory, and cognitive boundary.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logger = logging.getLogger(__name__)

# Base port for actor services; each new actor gets port+1
ACTOR_BASE_PORT = 9001

# Track running actor processes
_actor_processes: dict[str, subprocess.Popen] = {}


def _get_actor_dir() -> str:
    """Get the actors runtime directory."""
    actors_dir = os.path.join(os.path.dirname(__file__), "actors")
    os.makedirs(actors_dir, exist_ok=True)
    return actors_dir


def _get_actor_port(actor_name: str) -> int:
    """Get the port for a given actor (deterministic based on name hash).
    
    Uses hashlib-based stable hash instead of Python's built-in hash(),
    which is randomized across processes since Python 3.3 (PYTHONHASHSEED).
    """
    import hashlib
    stable_hash = int(hashlib.md5(actor_name.encode("utf-8")).hexdigest(), 16)
    port_hash = stable_hash % 100
    return ACTOR_BASE_PORT + port_hash


def generate_actor_agent_code(
    actor_name: str,
    role: str,
    personality: str,
    background: str,
    knowledge_scope: str,
    port: int,
    other_actors: list[dict] | None = None,
    memory_entries: list[str] | None = None,
) -> str:
    """Generate the Python code for an actor's A2A agent service.

    Args:
        actor_name: The character's name.
        role: The character's role.
        personality: Personality traits.
        background: Character's backstory.
        knowledge_scope: What this character knows (cognitive boundary).
        port: The port to run the A2A service on.
        other_actors: List of other actors' info for direct A2A communication.
        memory_entries: Prior memory strings to inject as historical context.

    Returns:
        Python source code string.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    model_name = os.environ.get("MODEL_NAME", "openai/claude-sonnet-4-6")

    # Build other actors info for direct A2A communication
    other_actors_section = ""
    if other_actors:
        actors_info = []
        for actor in other_actors:
            if actor.get("name") != actor_name:
                actors_info.append(
                    f"- **{actor['name']}**（{actor['role']}）："
                    f"与此人对话用 call_actor(name=\"{actor['name']}\", message=\"你的话\")"
                )
        if actors_info:
            other_actors_section = "\n\n## 其他角色（可通过 A2A 直接对话）\n" + "\n".join(actors_info)

    # Build memory section for historical context restoration
    memory_section = ""
    if memory_entries:
        memory_lines = [f"- {m}" for m in memory_entries]
        memory_section = (
            "\n\n## 你的历史记忆（从存档恢复）\n"
            "以下是你之前的经历和记忆，请在回应时参考这些信息：\n"
            + "\n".join(memory_lines)
        )
    
    # Build the call_actor tool code
    call_actor_tool = '''
# Tool: call_actor - 直接与其他演员进行 A2A 对话
# 注意：这个工具用于演员之间直接对话，导演场景中不需要使用
async def call_actor(actor_name: str, message: str, tool_context=None) -> str:
    """Call another actor via A2A protocol to get their response.
    
    Args:
        actor_name: Name of the actor to call
        message: Message to send to the actor
    
    Returns:
        The other actor's response as dialogue text.
    """
    import json
    import uuid
    import httpx
    from a2a.client import ClientFactory, ClientConfig
    from a2a.types import AgentCard, Message, Part
    
    # Find the actor's card file
    actors_dir = os.path.join(os.path.dirname(__file__), "actors")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in actor_name)
    card_file = os.path.join(actors_dir, f"actor_{safe_name}_card.json")
    
    if not os.path.exists(card_file):
        return f"[无法找到演员 {actor_name} 的信息]"
    
    with open(card_file, "r") as f:
        card_data = json.load(f)
    agent_card = AgentCard(**card_data)
    
    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    client_config = ClientConfig(httpx_client=httpx_client, streaming=False)
    client = ClientFactory(config=client_config).create(card=agent_card)
    
    a2a_msg = Message(messageId=str(uuid.uuid4()), parts=[Part(text=message)], role="user")
    
    texts = []
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
    
    await httpx_client.aclose()
    return "\\n".join(texts).strip() if texts else "[无响应]"
'''

    code = f'''"""A2A Actor Service: {actor_name}"""
import os
os.environ["OPENAI_API_KEY"] = {repr(api_key)}
os.environ["OPENAI_BASE_URL"] = {repr(base_url)}

import uvicorn
from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

{call_actor_tool}

actor_agent = Agent(
    name="actor_{actor_name}",
    model=LiteLlm(model={repr(model_name)}),
    instruction="""你是一位戏剧演员，正在扮演角色「{actor_name}」。

## 角色档案
- **姓名**: {actor_name}
- **身份**: {role}
- **性格**: {personality}
- **背景故事**: {background}

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
{knowledge_scope}

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）{other_actors_section}{memory_section}

## 行为准则
1. 始终以角色身份说话和行动，不要跳出角色
2. 你的台词应该符合你的性格和说话风格
3. 根据你的记忆和经历来做出反应
4. 你可以表达情感，但必须基于角色的认知
5. 当被问及超出认知的事情时，以角色的自然方式回应
6. 保持角色的一致性——你的性格、说话方式、价值观应该始终如一
7. 如果需要与其他角色对话，可以使用 call_actor 工具直接联系他们

## 指代消解规则（极其重要）
由于你是独立运行的演员，你只能看到导演发给你的情境信息。
当情境中出现代词时，请严格遵循以下规则：

1. **导演标注优先**：如果代词后有括号标注，如「他（李明）」或「他（李明，她的恋人）」，
   括号内的名字即为该代词的真实指代，你必须按此理解，绝对不可误解
2. **禁止自我代入**：当别人说「他/她/它」时，**绝对不要默认理解为指代你自己**，
   除非括号标注中明确写了你的名字。例如：A说「我再不去追他我会后悔的」，
   如果标注为「他（李明）」，则「他」=李明，不是你
3. **未标注时按角色自然回应**：如果代词没有标注且你无法确定指代对象，
   按角色性格自然回应（可以困惑、追问、或根据上下文推测，但不要对号入座）
4. **情境包说明**：导演发给你的每条情境都经过指代消解处理，
   你可以信任括号标注的准确性——这是导演为你提供的共享认知

## 回复格式
直接以角色的口吻说话，不需要加引号或角色名前缀。
""",
    description={repr(f"演员 {actor_name}，角色：{role}。{personality}")},
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port={port})

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port={port})
'''
    return code


def create_actor_service(
    actor_name: str,
    role: str,
    personality: str,
    background: str,
    knowledge_scope: str,
    other_actors: list[dict] | None = None,
    memory_entries: list[str] | None = None,
) -> dict:
    """Create and launch an actor as an A2A service.

    Args:
        actor_name: The character's name.
        role: The character's role.
        personality: Personality traits.
        background: Character's backstory.
        knowledge_scope: What this character knows.
        other_actors: List of other actors' info for direct A2A communication.
        memory_entries: List of prior memory strings to inject into the actor's
                        system prompt so historical context is preserved on reload.

    Returns:
        dict with creation status and connection info.
    """
    actors_dir = _get_actor_dir()
    port = _get_actor_port(actor_name)

    # Generate actor agent code with other actors info
    code = generate_actor_agent_code(
        actor_name, role, personality, background, knowledge_scope, port, other_actors,
        memory_entries=memory_entries,
    )

    # Write actor file
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in actor_name)
    actor_file = os.path.join(actors_dir, f"actor_{safe_name}.py")
    with open(actor_file, "w", encoding="utf-8") as f:
        f.write(code)

    # Write agent card JSON for RemoteA2aAgent discovery
    agent_card = {
        "name": f"actor_{actor_name}",
        "description": f"演员 {actor_name}，角色：{role}",
        "url": f"http://localhost:{port}/",
        "version": "1.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": f"act_{safe_name}",
                "name": f"扮演{actor_name}",
                "description": f"以{actor_name}的身份进行角色扮演",
                "tags": ["acting", "roleplay"],
            }
        ],
    }
    card_file = os.path.join(actors_dir, f"actor_{safe_name}_card.json")
    with open(card_file, "w", encoding="utf-8") as f:
        json.dump(agent_card, f, ensure_ascii=False, indent=2)

    # Launch the actor service as a subprocess
    if actor_name in _actor_processes:
        _stop_actor_process(actor_name)

    process = subprocess.Popen(
        [sys.executable, actor_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(__file__)),  # project root
    )
    _actor_processes[actor_name] = process

    # Give the service a moment to start
    import time
    time.sleep(2)

    # Check if process is still running
    if process.poll() is not None:
        stderr_output = process.stderr.read().decode() if process.stderr else ""
        return {
            "status": "error",
            "message": f"Actor service failed to start: {stderr_output[:200]}",
        }

    return {
        "status": "success",
        "message": f"Actor '{actor_name}' A2A service started on port {port}",
        "actor_name": actor_name,
        "port": port,
        "card_url": f"http://localhost:{port}/.well-known/agent.json",
        "card_file": card_file,
        "rpc_url": f"http://localhost:{port}/",
    }


def get_actor_remote_config(actor_name: str, saved_port: int | None = None) -> Optional[dict]:
    """Get the A2A connection config for an actor.

    Args:
        actor_name: The character's name.
        saved_port: Previously persisted port (from state.json). If provided and
                    matches the deterministic port, use it; otherwise recalculate.

    Returns:
        dict with connection info, or None if actor not found.
    """
    actors_dir = _get_actor_dir()
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in actor_name)
    card_file = os.path.join(actors_dir, f"actor_{safe_name}_card.json")

    if not os.path.exists(card_file):
        return None

    with open(card_file, "r", encoding="utf-8") as f:
        card_data = json.load(f)

    # Prefer the URL from the card file (written at service creation time) as
    # the single source of truth; fall back to deterministic calculation.
    card_url = card_data.get("url", "")
    if card_url:
        port = int(card_url.rstrip("/").split(":")[-1])
    else:
        port = saved_port if saved_port is not None else _get_actor_port(actor_name)

    return {
        "actor_name": actor_name,
        "card_file": card_file,
        "card_url": f"http://localhost:{port}/.well-known/agent.json",
        "rpc_url": f"http://localhost:{port}/",
        "port": port,
    }


def stop_actor_service(actor_name: str) -> dict:
    """Stop an actor's A2A service.

    Args:
        actor_name: The character's name.

    Returns:
        dict with status.
    """
    return _stop_actor_process(actor_name)


def stop_all_actor_services() -> dict:
    """Stop all running actor services.

    Returns:
        dict with status.
    """
    stopped = []
    for name in list(_actor_processes.keys()):
        result = _stop_actor_process(name)
        stopped.append(result)
    return {"status": "success", "stopped": stopped}


def _stop_actor_process(actor_name: str) -> dict:
    """Stop a single actor process."""
    if actor_name in _actor_processes:
        process = _actor_processes.pop(actor_name)
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        return {"status": "success", "message": f"Actor '{actor_name}' service stopped."}
    return {"status": "info", "message": f"Actor '{actor_name}' was not running."}


def list_running_actors() -> dict:
    """List all running actor services.

    Returns:
        dict with running actors info.
    """
    running = {}
    for name, process in _actor_processes.items():
        poll = process.poll()
        running[name] = {
            "pid": process.pid,
            "running": poll is None,
            "port": _get_actor_port(name),
        }
    return {"status": "success", "actors": running}
