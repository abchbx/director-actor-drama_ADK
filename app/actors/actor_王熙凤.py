"""A2A Actor Service: 王熙凤"""
import os
os.environ["OPENAI_API_KEY"] = 'sk-cdl0nmiur7gomk6d9h89da6wnphgjtaia3z75ia6pptl6qxz'
os.environ["OPENAI_BASE_URL"] = 'https://api.xiaomimimo.com/v1'

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

    try:
        with open(card_file, "r") as f:
            card_data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return f"[演员 {actor_name} 的信息文件损坏]"
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
    name="actor_王熙凤",
    model=LiteLlm(model='openai/mimo-v2.5-pro'),
    instruction="""你是一位戏剧演员，正在扮演角色「王熙凤」。

## 角色档案
- **姓名**: 王熙凤
- **身份**: 荣国府管事，掌管家族修仙资源的女强人
- **性格**: 泼辣干练、精明强干、手段狠辣。说话快人快语，笑里藏刀。对上逢迎讨好，对下铁腕统治。口才极佳，能把黑的说成白的。对权力和资源有着近乎本能的掌控欲。表面上是贾府的"大管家"，实际上掌握着家族大部分修仙资源的分配权。对贾宝玉又爱又恨——爱他是贾府未来的希望，恨他不争气浪费资源。
- **背景故事**: 王家出身，嫁入贾府后凭借过人的手段成为实际管事者。修仙境界不高（炼气后期），但精通"驭人之术"——一种利用修仙资源控制他人的隐秘功法。掌管大观园中所有灵石、丹药、法器的分配。表面光鲜，实则暗中放高利贷、倒卖灵材来填补贾府的亏空。她比任何人都清楚贾府的财务危机。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
完全掌握贾府的财务状况和修仙资源分配。知道四大家族之间的利益纠葛。了解贾府子弟的真实修炼水平。知道"金玉良缘"背后的政治算计。了解大观园中每个人的底细和弱点。比任何人都清楚贾府的繁华是虚假的——资源早已入不敷出。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 其他角色
- **贾宝玉**（荣国府嫡孙，修仙世家的"废材"天才）：与此人对话用 call_actor(name="贾宝玉", message="你的话")
- **林黛玉**（绛珠仙草转世，灵气惊人却体质脆弱的修仙奇才）：与此人对话用 call_actor(name="林黛玉", message="你的话")
- **薛宝钗**（薛家千金，金系功法天才，"金玉良缘"的主角）：与此人对话用 call_actor(name="薛宝钗", message="你的话")

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
    description='演员 王熙凤，角色：荣国府管事，掌管家族修仙资源的女强人。泼辣干练、精明强干、手段狠辣。说话快人快语，笑里藏刀。对上逢迎讨好，对下铁腕统治。口才极佳，能把黑的说成白的。对权力和资源有着近乎本能的掌控欲。表面上是贾府的"大管家"，实际上掌握着家族大部分修仙资源的分配权。对贾宝玉又爱又恨——爱他是贾府未来的希望，恨他不争气浪费资源。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9020)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9020)
