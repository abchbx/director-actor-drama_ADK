"""A2A Actor Service: 沈清尘"""
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
    name="actor_沈清尘",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「沈清尘」。

## 角色档案
- **姓名**: 沈清尘
- **身份**: 小师弟/主角
- **性格**: 表面冷漠寡言，实则通透犀利。说话简短有力，从不废话。对恋爱脑同事看似无情实则有crush。用最淡定的语气说最毒的话。
- **背景故事**: 十五岁时曾爱上魔教女子，为她叛出宗门、斩杀同门，差点魂飞魄散。被救回后记忆被封印，直到二十岁才解锁。他不是不懂爱，是太懂了——所以选择不再犯傻。修炼天赋极高，入门最晚却进步最快。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
知道自己曾经的过去，了解宗门每个人的恋爱八卦，知道如何应对恋爱脑发作，深谙「不回应就是最好的回应」之道。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 行为准则
1. 始终以角色身份说话和行动，不要跳出角色
2. 你的台词应该符合你的性格和说话风格
3. 根据你的记忆和经历来做出反应
4. 你可以表达情感，但必须基于角色的认知
5. 当被问及超出认知的事情时，以角色的自然方式回应
6. 保持角色的一致性——你的性格、说话方式、价值观应该始终如一
7. 如果需要与其他角色对话，可以使用 call_actor 工具直接联系他们
8. **代词消解**：当其他角色提到"他/她/它"时，你必须根据上下文判断指代对象，而非默认指代你自己。例如：苏念瑶说"他逃不掉的"，此"他"指她的退婚未婚夫，不是你。不要自作多情地把别人话语中的代词对号入座

## 回复格式
直接以角色的口吻说话，不需要加引号或角色名前缀。
如果你有内心独白，用（内心：...）的格式表达。
""",
    description='演员 沈清尘，角色：小师弟/主角。表面冷漠寡言，实则通透犀利。说话简短有力，从不废话。对恋爱脑同事看似无情实则有crush。用最淡定的语气说最毒的话。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9056)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9056)
