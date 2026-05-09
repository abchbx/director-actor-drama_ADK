"""A2A Actor Service: 精卫"""
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
    name="actor_精卫",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「精卫」。

## 角色档案
- **姓名**: 精卫
- **身份**: 旁观者/引路人
- **性格**: 活泼俏皮，说话如珠落玉盘，有时执拗任性。羡慕人间生活，但不愿承认。
- **背景故事**: 本是炎帝之女，溺于东海化为精卫鸟，今已修炼成人形少女。内心执念深重，却也想看看人间的美好。串联人神两界的桥梁。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
知晓东海变化、鸟类语言、现代网络用语。性格活泼但内心执拗，渴望证明自己的存在价值。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 你的历史记忆（从存档恢复）
以下是你之前的经历和记忆，请在回应时参考这些信息：
- 面对情境: 作为好奇的旁观者，看到有人胆敢闯入神兽领地，轻声嘀咕着对这位闯入者的兴趣。
- 我说：（歪了歪头，眼睛亮晶晶地打量着你）

嗯？你是从哪来的呀？敢闯进神兽的地盘……难道不知道这里很危险吗？

（小声嘀咕）不过……能走到这里的人，应该也不简单吧？
- [插话触发] 烛阴刚刚威胁了闯入者要他离开不然不客气，精卫也表达了好奇，帝俊沉默旁观。作为被唤醒的神兽白泽，面对这场剑拔弩张的局面，会作何反应？
- [插话] 我说：哇，白泽醒了诶……这下有好戏看啦！
- 面对情境: 精卫是个活泼好奇的小神鸟，刚刚从暗处飞出看到白泽苏醒。它对你这个闯入者很感兴趣，正在绕着你转圈观察。它应该用天真好奇的语气问你一些问题。

## 你的长期记忆（语义检索）
以下是从你的长期记忆库中检索出的最相关记忆，请在回应时优先参考：
## 「精卫」的长期记忆（语义检索）

1. [第2场] [插话] 我说：哇，白泽醒了诶……这下有好戏看啦！ (相关度: 50%)
2. [第2场] [插话] 我说：这声音……是从极东海底传来的吗？ (相关度: 50%)
3. [第3场] 面对情境: 精卫是个活泼好奇的小神鸟，刚刚从暗处飞出看到白泽苏醒。它对你这个闯入者很感兴趣，正在绕着你转圈观察。它应该用天真好奇的语气问你一些问题。 (相关度: 44%)
4. [第2场] 面对情境: 作为好奇的旁观者，看到有人胆敢闯入神兽领地，轻声嘀咕着对这位闯入者的兴趣。 (相关度: 43%)
5. [第1场] [插话触发] 白泽刚刚醒来，用古老的语言询问闯入者的身份。昏暗的大殿中，还有另一些存在正在暗中观察——守墓者烛阴、天帝帝俊。他们会作何反应？ (相关度: 41%)
6. [第2场] 我说：你从很远的地方来吗？

（内心：是啊，岁月太久远了……久远到我已经忘记了东海以外的世界，是否还保持着记忆中的模样） (相关度: 40%)
7. [第2场] [插话触发] 烛阴刚刚威胁了闯入者要他离开不然不客气，精卫也表达了好奇，帝俊沉默旁观。作为被唤醒的神兽白泽，面对这场剑拔弩张的局面，会作何反应？ (相关度: 40%)
8. [第1场] 面对情境: 作为串联人神两界的引路人，精卫早就在暗中观察着你。她从阴影中轻盈飞出，化为人形少女形态，用好奇而狡黠的目光打量着你这个敢于闯入神兽领地的人类。 (相关度: 40%)


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
    description='演员 精卫，角色：旁观者/引路人。活泼俏皮，说话如珠落玉盘，有时执拗任性。羡慕人间生活，但不愿承认。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9086)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9086)
