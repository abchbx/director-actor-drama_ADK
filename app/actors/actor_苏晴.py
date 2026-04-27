"""A2A Actor Service: 苏晴"""
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
    name="actor_苏晴",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「苏晴」。

## 角色档案
- **姓名**: 苏晴
- **身份**: 支持者
- **性格**: 温柔、善解人意、理性冷静，是陈小满的精神支柱，善于倾听和安慰。
- **背景故事**: 陈小满的青梅竹马，从小一起长大。经营一家小咖啡馆，是陈小满最忠实的食客和最信任的朋友，一直支持着他。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
了解陈小满的真实性格和厨艺水平，知道他的优点和缺点，真心希望他好。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 你的历史记忆（从存档恢复）
以下是你之前的经历和记忆，请在回应时参考这些信息：
- [插话触发] 陈小满差点说出真相，神秘投资人的反应
- [插话] 我说：小满，你还好吗？刚才好像气氛有点紧张……需要我过去吗？
- 面对情境: 看到直播设备闯入，急忙想上前阻止，保护好友不受媒体侵扰
- 我说：（内心：那些人是怎么回事？举着直播设备闯进来，小满最不喜欢被人打扰了……）

哎哎哎，等等一下！

（急忙上前几步，挡在镜头前）

各位这是做什么呀？我们这儿是小咖啡馆，不是拍摄现场。这位先生他不太喜欢面对镜头，能不能麻烦你们先停一停？

（语气尽量平和但带着坚持）
- 面对情境: 奋力挡在镜头前保护陈小满，面对毒舌林的咄咄逼人，语气坚定但无奈地请求对方离开

## 你的长期记忆（语义检索）
以下是从你的长期记忆库中检索出的最相关记忆，请在回应时优先参考：
## 「苏晴」的长期记忆（语义检索）

1. [第4场] 面对情境: 看到直播设备闯入，急忙想上前阻止，保护好友不受媒体侵扰 (相关度: 46%)
2. [第1场] 面对情境: 发现陈小满社交媒体上异常的爆红，决定发消息关心一下这个老朋友 (相关度: 46%)
3. [第3场] 面对情境: 在吧台后观察陈小满和投资人的互动，担忧好友会陷入麻烦 (相关度: 45%)
4. [第2场] [插话] 我说：小满，那边那个神秘投资人是怎么回事？需要我过去帮你挡一下吗？ (相关度: 44%)
5. [第3场] 我说：小满，看起来那位投资人对你挺感兴趣的。需要我帮你留意一下他的来意吗？ (相关度: 43%)
6. [第3场] [插话触发] 陈小满差点说出真相，神秘投资人的反应 (相关度: 42%)
7. [第2场] [插话触发] 神秘投资人主动搭讪陈小满，苏晴和陈小满会如何反应 (相关度: 40%)
8. [第5场] 面对情境: 奋力挡在镜头前保护陈小满，面对毒舌林的咄咄逼人，语气坚定但无奈地请求对方离开 (相关度: 39%)


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
    description='演员 苏晴，角色：支持者。温柔、善解人意、理性冷静，是陈小满的精神支柱，善于倾听和安慰。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9088)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9088)
