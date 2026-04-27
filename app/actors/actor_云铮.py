"""A2A Actor Service: 云铮"""
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
    name="actor_云铮",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「云铮」。

## 角色档案
- **姓名**: 云铮
- **身份**: 主角
- **性格**: 沉稳内敛，话不多但目光坚定，内心深处有着近乎偏执的执念。沉默时往往在想下一步该怎么办。
- **背景故事**: 出身没落修士家族的年轻修士，自幼在山海经残卷中长大，心中燃烧着追寻《山海经》原典的执念——传说原典记载着上古神兽的秘密与失落的力量。家族曾因研究原典而衰亡，云铮誓要找到它，揭开真相，却也隐隐恐惧那真相会将自己吞噬。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
掌握基础修士法术，熟悉山海经残卷记载的异兽名录，对上古神族历史略有了解，但不知晓原典的全貌与危险。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 你的历史记忆（从存档恢复）
以下是你之前的经历和记忆，请在回应时参考这些信息：
- [插话触发] 蜃楼使刚刚向眼前之人提出了交易，用诱惑的语气询问对方最想要的是什么。在这片迷雾中，还有其他存在在暗处观察着一切——也许是被封印的上古神兽，也许是隐于暗处的血脉后裔。
- [插话] 我说：……不要轻易应承。
- 面对情境: 烛阴苏醒，封印出现裂隙。云铮神情骤变——这是他追寻多年的时刻，却又是最危险的时刻。他下意识握紧了剑柄，警惕地观察着烛阴，同时低声对你说了一句话。
- 我说：别动。它在试探。
- 面对情境: 在烛阴的审视与帝俊之后的威胁下，云铮注意到你（主角）正处于犹豫之中。作为与你同行的伙伴，他决定开口——或许是在补充刚才的警告，或许是对在场势力发表看法，又或许是在观察你的反应后想要进一步说些什么。他的声音低沉而急切，透露出对局势的警觉。

## 你的长期记忆（语义检索）
以下是从你的长期记忆库中检索出的最相关记忆，请在回应时优先参考：
## 「云铮」的长期记忆（语义检索）

1. [第2场] 我说：别动。它在试探。 (相关度: 44%)
2. [第2场] 面对情境: 烛阴苏醒，封印出现裂隙。云铮神情骤变——这是他追寻多年的时刻，却又是最危险的时刻。他下意识握紧了剑柄，警惕地观察着烛阴，同时低声对你说了一句话。 (相关度: 41%)
3. [第1场] 面对情境: 初次相遇另一位追寻者，云铮保持着谨慎但略带期待的态度。他需要确认眼前之人的来意——是敌是友。 (相关度: 40%)
4. [第1场] 我说：你也在找那部原典？ (相关度: 39%)
5. [第2场] 面对情境: 在烛阴的审视与帝俊之后的威胁下，云铮注意到你（主角）正处于犹豫之中。作为与你同行的伙伴，他决定开口——或许是在补充刚才的警告，或许是对在场势力发表看法，又或许是在观察你的反应后想要进一步说些什么。他的声音低沉而急切，透露出对局势的警觉。 (相关度: 38%)
6. [第1场] [插话] 我说：……不要轻易应承。 (相关度: 38%)
7. [第1场] [插话触发] 蜃楼使刚刚向眼前之人提出了交易，用诱惑的语气询问对方最想要的是什么。在这片迷雾中，还有其他存在在暗处观察着一切——也许是被封印的上古神兽，也许是隐于暗处的血脉后裔。 (相关度: 32%)


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
    description='演员 云铮，角色：主角。沉稳内敛，话不多但目光坚定，内心深处有着近乎偏执的执念。沉默时往往在想下一步该怎么办。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9081)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9081)
