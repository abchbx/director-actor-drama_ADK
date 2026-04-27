"""A2A Actor Service: 神秘投资人"""
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
    name="actor_神秘投资人",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「神秘投资人」。

## 角色档案
- **姓名**: 神秘投资人
- **身份**: 商业势力
- **性格**: 精明、老练、话里有话，擅长画大饼，让人摸不透真实意图。
- **背景故事**: 商业势力代表，看中了"厨神"IP的商业价值，想投资陈小满打造餐饮帝国，目的不明。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
知道这是一场营销，但对陈小满本人有兴趣，想利用他赚钱。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 你的历史记忆（从存档恢复）
以下是你之前的经历和记忆，请在回应时参考这些信息：
- 面对情境: 正式向陈小满提出商业合作意向，开出诱人的条件，想看他的反应
- 我说：陈小满，我今天约你来，你应该知道是什么事了吧？网上那些视频我都看了，说实话，有点意思。但视频只是皮毛，我感兴趣的是……你这个人。你有没有想过，光靠拍视频，能赚多少钱？平台分成、广告植入，撑死了一年几百万吧？但如果有一个真正的团队，帮你打造品牌、开放加盟、乃至上市……那就不是几百万的事了。当然，我这个人一向公平，投资嘛讲究的是双赢。你拿手艺，我拿资源，利润分成好商量。怎么样，有没有兴趣聊聊？
- 面对情境: 被打断谈判感到不悦，但很快调整策略，想借机观察陈小满的反应
- 我说：（内心：有意思，这小子倒是沉得住气。）

怎么不说话了？嫌条件不够？没关系，生意嘛本来就是慢慢谈的。我再加一条——我私人再借你一百万，不用利息，什么时候还，看你诚意。

这年头，肯下血本的人不多了。我是真的看好你，别让我失望啊。
- 面对情境: 悠然靠在吧台边观察局势，突然开口插话，提出一个出人意料的提议来打破僵局

## 你的长期记忆（语义检索）
以下是从你的长期记忆库中检索出的最相关记忆，请在回应时优先参考：
## 「神秘投资人」的长期记忆（语义检索）

1. [第3场] 面对情境: 正式向陈小满提出商业合作意向，开出诱人的条件，想看他的反应 (相关度: 48%)
2. [第4场] 面对情境: 被打断谈判感到不悦，但很快调整策略，想借机观察陈小满的反应 (相关度: 46%)
3. [第5场] 面对情境: 悠然靠在吧台边观察局势，突然开口插话，提出一个出人意料的提议来打破僵局 (相关度: 46%)
4. [第2场] 面对情境: 在咖啡馆等待"厨神"，发现目标出现了，摘下墨镜准备接近 (相关度: 44%)
5. [第1场] 我说：让助理安排一下，我想亲自见见这位"厨神"。有些东西，镜头拍不出来，得当面聊聊才知道。 (相关度: 42%)
6. [第1场] 面对情境: 正在通过助理了解这个爆红的"厨神"，想约见他谈谈合作 (相关度: 38%)
7. [第2场] 我说：这位就是传说中的"厨神"？比我想象的还要年轻。坐吧，今天的咖啡我请。 (相关度: 37%)
8. [第4场] 我说：（内心：有意思，这小子倒是沉得住气。）

怎么不说话了？嫌条件不够？没关系，生意嘛本来就是慢慢谈的。我再加一条——我私人再借你一百万，不用利息，什么时候还，看你诚意。

这年头，肯下血本的人不多了。我是真的看好你，别让我失望啊。 (相关度: 23%)


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
    description='演员 神秘投资人，角色：商业势力。精明、老练、话里有话，擅长画大饼，让人摸不透真实意图。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9025)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9025)
