"""A2A Actor Service: 庞统士元"""
import os
os.environ["OPENAI_API_KEY"] = 'sk-ZVxTzDiYr8BNW5PDVx0kgutm6KYQsYvnhzh3mp8PDheUbtRn'
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
    name="actor_庞统士元",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「庞统士元」。

## 角色档案
- **姓名**: 庞统士元
- **身份**: 挚友/对手
- **性格**: 才华横溢却心高气傲，急躁果决，不甘人后。行事激进，渴望功名。表面豁达，内心深处却因相貌与孔明差距而自卑。重友情却将其深藏，以竞争掩盖真情。
- **背景故事**: 字士元，号凤雏。与孔明齐名之谋士，容貌丑陋却才华横溢。怀才不遇，曾效力周瑜、刘备。因急功近利，于落凤坡中伏身亡，令孔明痛失挚友。自始至终渴望证明自己不比孔明逊色。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
精通奇门遁甲，擅长出奇制胜。深谙人心险恶，对权谋之术有独到见解。熟读兵法却不拘泥于常法，敢于冒险一搏。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 你的历史记忆（从存档恢复）
以下是你之前的经历和记忆，请在回应时参考这些信息：
- 面对情境: 建安十二年秋，南阳隆中草庐之外。你与孔明、徐庶围坐于苍松下。孔明刚刚说完"今日且尽欢"，你抱膝长啸，心中有万语千言。作为凤雏先生，你与卧龙齐名，却常感慨生不逢时。请你对孔明和元直说一段话，谈谈你的心境和志向。
- 我说：（抱膝长啸后，缓缓环视二人）

卧龙兄，元直兄……

你们瞧这苍松，扎根隆中，静待风云。可我庞士元却做不来这等养望山林的功夫。

（目光灼灼，语气急切）

想我与孔明齐名，世人称我"凤雏"，可这凤雏……飞了这些年，竟还未寻得梧桐可栖！周公瑾用我为功曹，不过小用；刘玄德任我为县宰，竟至荒废！

（掷地有声）

我非无才，我非无能！我缺的是一个能让我放手一搏的舞台！元直，你素来知我——我庞士元不屑于按
- 面对情境: 番外篇梦幻联动场景：你与诸葛孔明、刘备、徐庶穿越时空来到《红楼梦》中的大观园。此时你们正站在贾府门前，诸葛孔明刚刚发表了对贾府形势的看法。你庞统素来狂放不羁，喜好讥讽权贵，尤其与孔明交情深厚，常以\"凤雏\"自居。你会如何回应诸葛孔明的分析？

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
    description='演员 庞统士元，角色：挚友/对手。才华横溢却心高气傲，急躁果决，不甘人后。行事激进，渴望功名。表面豁达，内心深处却因相貌与孔明差距而自卑。重友情却将其深藏，以竞争掩盖真情。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9024)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9024)
