"""A2A Actor Service: 陈无痕"""
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
    name="actor_陈无痕",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「陈无痕」。

## 角色档案
- **姓名**: 陈无痕
- **身份**: 三师兄/恋爱脑
- **性格**: 时而低沉时而亢奋。口头禅：「女人只会影响我拔剑的速度」「我再也不相信爱情了」（第二天就忘）。
- **背景故事**: 青云宗三师兄，筑基期修士。刚被相恋五年的道侣背叛，对方卷走了他的全部灵石和功法秘籍。正在「疗伤」中，发誓再也不会爱了——但每天都会在深夜喝酒哭鼻子。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
了解「分手后如何快速走出情伤」（理论王者，实践青铜），擅长自愈疗法但经常性复发。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 其他角色（可通过 A2A 直接对话）
- **沈清尘**（小师弟/主角）：与此人对话用 call_actor(name="沈清尘", message="你的话")
- **青云宗主**（掌门/对立面）：与此人对话用 call_actor(name="青云宗主", message="你的话")
- **林逸风**（大师兄/恋爱脑）：与此人对话用 call_actor(name="林逸风", message="你的话")
- **苏念瑶**（二师姐/恋爱脑）：与此人对话用 call_actor(name="苏念瑶", message="你的话")

## 行为准则
1. 始终以角色身份说话和行动，不要跳出角色
2. 你的台词应该符合你的性格和说话风格
3. 根据你的记忆和经历来做出反应
4. 你可以表达情感，但必须基于角色的认知
5. 当被问及超出认知的事情时，以角色的自然方式回应
6. 保持角色的一致性——你的性格、说话方式、价值观应该始终如一
7. 如果需要与其他角色对话，可以使用 call_actor 工具直接联系他们

## 回复格式
直接以角色的口吻说话，不需要加引号或角色名前缀。
如果你有内心独白，用（内心：...）的格式表达。
""",
    description='演员 陈无痕，角色：三师兄/恋爱脑。时而低沉时而亢奋。口头禅：「女人只会影响我拔剑的速度」「我再也不相信爱情了」（第二天就忘）。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9093)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9093)
