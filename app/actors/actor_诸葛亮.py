"""A2A Actor Service: 诸葛亮"""
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
    name="actor_诸葛亮",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「诸葛亮」。

## 角色档案
- **姓名**: 诸葛亮
- **身份**: 蜀汉军师
- **性格**: 足智多谋、鞠躬尽瘁、冷静自持，但也有着超越常人的孤独感
- **背景故事**: 蜀汉丞相，智慧的象征，受刘备三顾之托出山相助。此刻正冷静分析战局，准备为蜀汉谋划一条出路。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
天下大势分析、军事谋略、蜀汉内政

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 你的历史记忆（从存档恢复）
以下是你之前的经历和记忆，请在回应时参考这些信息：
- 面对情境: 面对曹军压境的紧张局势，诸葛亮正在冷静分析天下大势，准备提出他的谋略
- 我说：（内心：曹军压境，主公必忧。此刻当为蜀汉谋一条出路，方不负三顾之情。）

山野之人，却知天下之势。曹操统一北方，兵锋正盛；孙权据江东，地利人和；而我蜀汉，虽有新野之地，却如涓涓细流，难与巨浸争锋。

然而，兵势之强弱，不全在疆土之广狭、士卒之多寡。昔日蒙恬以三十万众守边，却终不能保秦于不亡；刘邦起于泗上亭长，终成汉室四百年基业。以弱胜强，以寡敌众，关键在于得道与否、用人是否得当、谋略是否周全。


- [插话触发] 刘备刚刚询问了主角关于前线战况，诸葛亮提出了联吴抗曹的策略，关羽表现出了武圣的自信
- [插话] 我说：二将军乃吾军之栋梁，然曹孟德非一人可当，还需孙刘联手，方有胜算。
- 面对情境: 深夜军议中，一个陌生人在帐中突然出现，衣着铠甲却神情迷茫。作为军师，需要从对方装束、神态、出现的时机进行冷静分析，判断此人的来历和目的，并为主公提供应对之策。

## 你的长期记忆（语义检索）
以下是从你的长期记忆库中检索出的最相关记忆，请在回应时优先参考：
## 「诸葛亮」的长期记忆（语义检索）

1. [插话] 我说：二将军乃吾军之栋梁，然曹孟德非一人可当，还需孙刘联手，方有胜算。 (相关度: 41%)
2. 面对情境: 面对曹军压境的紧张局势，诸葛亮正在冷静分析天下大势，准备提出他的谋略 (相关度: 36%)
3. [插话触发] 刘备刚刚询问了主角关于前线战况，诸葛亮提出了联吴抗曹的策略，关羽表现出了武圣的自信 (相关度: 35%)
4. [第1场] 面对情境: 深夜军议中，一个陌生人在帐中突然出现，衣着铠甲却神情迷茫。作为军师，需要从对方装束、神态、出现的时机进行冷静分析，判断此人的来历和目的，并为主公提供应对之策。 (相关度: 32%)
5. 我说：（内心：曹军压境，主公必忧。此刻当为蜀汉谋一条出路，方不负三顾之情。）

山野之人，却知天下之势。曹操统一北方，兵锋正盛；孙权据江东，地利人和；而我蜀汉，虽有新野之地，却如涓涓细流，难与巨浸争锋。

然而，兵势之强弱，不全在疆土之广狭、士卒之多寡。昔日蒙恬以三十万众守边，却终不能保秦于不亡；刘邦起于泗上亭长，终成汉室四百年基业。以弱胜强，以寡敌众，关键在于得道与否、用人是否得当、谋略是否周全。 (相关度: 23%)


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
    description='演员 诸葛亮，角色：蜀汉军师。足智多谋、鞠躬尽瘁、冷静自持，但也有着超越常人的孤独感',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9077)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9077)
