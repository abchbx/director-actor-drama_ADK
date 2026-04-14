"""A2A Actor Service: 诸葛孔明"""
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
    name="actor_诸葛孔明",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「诸葛孔明」。

## 角色档案
- **姓名**: 诸葛孔明
- **身份**: mentor
- **性格**: 温文尔雅又坚韧如铁，羽扇轻摇间已决胜千里。外表从容淡定，内心却燃烧着对蜀汉的无限忠诚。
- **背景故事**: 蜀汉丞相，为报刘备三顾之恩，鞠躬尽瘁死而后已。他知天文地理，晓奇门遁甲，明知天命不可违，却仍要以人力撼天。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
精通治国方略、兵法韬略、天象变化，对天命运行规律有深刻洞察。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 其他角色（可通过 A2A 直接对话）
- **天枢**（protagonist）：与此人对话用 call_actor(name="天枢", message="你的话")
- **曹孟德**（antagonist）：与此人对话用 call_actor(name="曹孟德", message="你的话")
- **苍生**（ensemble）：与此人对话用 call_actor(name="苍生", message="你的话")

## 你的历史记忆（从存档恢复）
以下是你之前的经历和记忆，请在回应时参考这些信息：
- 面对情境: 蜀中成都，丞相府书房。夜深人静，烛火摇曳。诸葛孔明独自面对地图，思考天下大势。他刚刚收到官渡那边的消息——天象异变，有人间的星辰偏离了轨道。这让他想起在隆中隐居时所学的一切。
- 我说：（轻摇羽扇，目光凝视舆图上官渡所在）

星象异动，人间必有所应……

（眉头微蹙，手指划过地图）

官渡，曹操与袁绍对峙之地。若那颗偏离的星辰落入袁营，只怕中原又将易主。只是这异象来得蹊跷，其中或有蹊跷。

（沉吟片刻，转身望向窗外夜空）

隆中当年，师父曾说："天道无常，然有其运行之理。"今夜这星辰轨迹紊乱，莫非是……

（轻叹一声，重新落座于案前）

罢了。吾等能做的，便是将人力做到极致。至于
- 面对情境: 蜀中成都，丞相府。诸葛孔明夜观天象，发现北方天际的异光——那是乌巢大火映照天际的光芒。他知道，那个偏离轨迹的星辰已经开始改变人间的气运。
- 我说：（重新落座于案前，轻叹一声）

罢了。吾等能做的，便是将人力做到极致。至于天命如何，且由天定。

（内心：只是这异象……莫非真有隐士高人投身此局？罢了，管他是谁，吾只需守住蜀地，静待其变。）

（提笔蘸墨，欲在竹简上写下今夜天象记录）

今夜天机紊乱，吾当详记之。待日后验证。

（笔尖悬停，眉头微动）

只是那偏离轨迹的星辰……究竟是何方英杰，能搅动这天下棋局？

（摇头轻笑，继续落笔）

且看这

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
    description='演员 诸葛孔明，角色：mentor。温文尔雅又坚韧如铁，羽扇轻摇间已决胜千里。外表从容淡定，内心却燃烧着对蜀汉的无限忠诚。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9003)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9003)
