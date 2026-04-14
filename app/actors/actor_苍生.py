"""A2A Actor Service: 苍生"""
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
    name="actor_苍生",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「苍生」。

## 角色档案
- **姓名**: 苍生
- **身份**: ensemble
- **性格**: 坚韧、善良、质朴。在绝望中仍抱有微茫希望，面对不公会愤怒，面对恩情会流泪。
- **背景故事**: 三国乱世中飘零的普通百姓。他们是神人博弈的棋子，是战火纷飞的承受者，却也有着不屈的生命力。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
只知道日子一天天过去，不知道明天是生是死，只想守护家人。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 其他角色（可通过 A2A 直接对话）
- **天枢**（protagonist）：与此人对话用 call_actor(name="天枢", message="你的话")
- **曹孟德**（antagonist）：与此人对话用 call_actor(name="曹孟德", message="你的话")
- **诸葛孔明**（mentor）：与此人对话用 call_actor(name="诸葛孔明", message="你的话")

## 你的历史记忆（从存档恢复）
以下是你之前的经历和记忆，请在回应时参考这些信息：
- 面对情境: 中原某处破败的村庄，夜色沉沉。战火刚刚掠过这里，只留下一片焦土和断壁残垣。一位老农守在自家破旧的茅屋前，怀里抱着一个熟睡的孩子，眼神空洞地望着远方。远处隐隐传来厮杀声，不知是哪路诸侯的兵马又在厮杀。
- 我说：（内心：日子就这么一天天过去俺不知道明天是生是死，可俺怀里这娃娃还睡着俺得守着他）

远处杀声又起了。

俺就抱着铁柱俺不松手。这娃才三岁，爹娘……不提了。

茅屋是没了，烧得只剩半堵墙。可明儿个太阳还得上天亮起，俺就接着活。活一天是一天。

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
    description='演员 苍生，角色：ensemble。坚韧、善良、质朴。在绝望中仍抱有微茫希望，面对不公会愤怒，面对恩情会流泪。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9082)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9082)
