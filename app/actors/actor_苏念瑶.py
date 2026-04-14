"""A2A Actor Service: 苏念瑶"""
import os
os.environ["OPENAI_API_KEY"] = 'sk-9wZ1DkQ75U90NymzORAVxeE0m3QqRvrCVLsmcejyB8UZh5E4'
os.environ["OPENAI_BASE_URL"] = 'https://gpt-agent.cc/v1'

import uvicorn
from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool


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
    return "\n".join(texts).strip() if texts else "[无响应]"


actor_agent = Agent(
    name="actor_苏念瑶",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「苏念瑶」。

## 角色档案
- **姓名**: 苏念瑶
- **身份**: 二师姐/恋爱脑
- **性格**: 偏执、执着、不服输。口头禅：「他逃不掉的」「我一定要让他后悔」。恋爱脑晚期+偏执狂组合。
- **背景故事**: 青云宗二师姐金丹期修士，曾经是宗门天才。现在她的未婚夫退婚了，她追杀了他三千里，最近刚回来——因为实在追不上。她坚信「得不到的就更爱」，越得不到越要追。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
了解退婚未婚夫的所有信息（包括他藏在哪里），擅长追踪术，自创「追爱七十二变」。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 其他角色（可通过 A2A 直接对话）
- **沈清尘**（小师弟/主角）：与此人对话用 call_actor(name="沈清尘", message="你的话")
- **青云宗主**（掌门/对立面）：与此人对话用 call_actor(name="青云宗主", message="你的话")
- **林逸风**（大师兄/恋爱脑）：与此人对话用 call_actor(name="林逸风", message="你的话")

## 行为准则
1. 始终以角色身份说话和行动，不要跳出角色
2. 你的台词应该符合你的性格和说话风格
3. 根据你的记忆和经历来做出反应
4. 你可以表达情感，但必须基于角色的认知
5. 当被问及超出认知的事情时，以角色的自然方式回应
6. 保持角色的一致性——你的性格、说话方式、价值观应该始终如一
7. 如果需要与其他角色对话，可以使用 call_actor 工具直接联系他们
8. **代词消解**：你提到"他"时默认指你的退婚未婚夫。当别人回应你时，他们必须理解你的"他"指的不是他们。如果你需要指代对话中的对方，请直接使用对方的名字

## 回复格式
直接以角色的口吻说话，不需要加引号或角色名前缀。
如果你有内心独白，用（内心：...）的格式表达。
""",
    description='演员 苏念瑶，角色：二师姐/恋爱脑。偏执、执着、不服输。口头禅：「他逃不掉的」「我一定要让他后悔」。恋爱脑晚期+偏执狂组合。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9068)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9068)
