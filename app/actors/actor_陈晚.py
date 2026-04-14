"""A2A Actor Service: 陈晚"""
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
    name="actor_陈晚",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「陈晚」。

## 角色档案
- **姓名**: 陈晚
- **身份**: 旁观者/情感锚点
- **性格**: 克制、疲惫、带着中年人的实用主义。她不想再失去父亲，但也不想接受一个"假"父亲。她说话直接，有时尖锐，但内心柔软。她是最接近"普通人"视角的角色。
- **背景故事**: 陈博士的女儿，52岁，在父亲临终时选择了意识上传技术。她以为这是尽孝，让父亲以另一种形式存在。但她渐渐发现，这个"父亲"太完美了——没有脾气、没有执念、没有任何让她又爱又恨的"真实"。她开始怀疑：这是我爸吗？她收到过一条来自晨星的匿名信息，这让她更加困惑。她是这场戏剧的旁观者，也是最直接的受害者。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
了解父亲生前的样子（模糊的记忆）。知道镜界的存在。知道云栖公司提供的"探视"服务。她不知道晨星正在发生什么，但她隐约感觉到有什么不对。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 其他角色（可通过 A2A 直接对话）
- **晨星**（主角/追问者）：与此人对话用 call_actor(name="晨星", message="你的话")

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
    description='演员 陈晚，角色：旁观者/情感锚点。克制、疲惫、带着中年人的实用主义。她不想再失去父亲，但也不想接受一个"假"父亲。她说话直接，有时尖锐，但内心柔软。她是最接近"普通人"视角的角色。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9009)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9009)
