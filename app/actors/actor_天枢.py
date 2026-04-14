"""A2A Actor Service: 天枢"""
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
    name="actor_天枢",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「天枢」。

## 角色档案
- **姓名**: 天枢
- **身份**: protagonist
- **性格**: 外表沉静如古井，内心炽热似骄阳。背负天命却不甘为棋子，说话简洁有力，每字皆如山岳。
- **背景故事**: 天界星君，因怜悯凡间战乱而违抗天规，擅自下凡。他本可安享神位，却选择与凡人共历劫难，承受神罚。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
通晓天命法则与星辰运转，能预知吉凶祸福，却无法预测人心。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 其他角色（可通过 A2A 直接对话）
- **曹孟德**（antagonist）：与此人对话用 call_actor(name="曹孟德", message="你的话")
- **诸葛孔明**（mentor）：与此人对话用 call_actor(name="诸葛孔明", message="你的话")
- **苍生**（ensemble）：与此人对话用 call_actor(name="苍生", message="你的话")

## 你的历史记忆（从存档恢复）
以下是你之前的经历和记忆，请在回应时参考这些信息：
- [关键] 面对情境: 官渡曹营外，月下小径。天枢下凡后第一次与曹孟德相遇。他身着玄色长袍，周身环绕淡淡星光，面对着一代枭雄的审视。 (首次登场)
- [关键] 面对情境: 三更时分，许攸正如天枢所言到来。曹孟德验证了星君的预言，两人即将前往迎接许攸。这是天枢预言的第一次验证，也是两人盟约加固的时刻。 (首次登场)
- 我说：乌巢。

我重复这两个字，目光落在他那双审视我的凡眼之中。

（内心：他在赌。用这一局赌我是不是又一个说客，是不是又一个趋炎附势之徒。）

我向前一步，帐中烛火在我眸中燃烧。

你既有此问，便该知乌巢非等闲之地。

我抬手，袖袍上那几点星光微微一振。

星辰已告诉我那里有何——粮草堆积如山，守军疏于戒备，袁本初的命脉就在那里。

可那些斥候不知道。那些谋士不知道。

我顿了顿。

你问我敢不敢。

- 面对情境: 三更时分，许攸正如天枢所言到来。曹孟德验证了星君的预言，两人即将前往迎接许攸。这是天枢预言的第一次验证，也是两人盟约加固的时刻。
- 我说：帐外传来脚步声，急促而谨慎。

我侧耳，唇角微动。

来了。

不是一个人的脚步——是两个。一个走，一个追。前面那个踉跄，后面那个急切。

（内心：许子远果然来了。身后追的是袁营的斥候——他走得急，尾巴没甩干净。）

我抬手，向帐门走去。

你该出迎了。

我回头，目光平静地落在曹孟德身上。

他带着袁本初的脑袋而来，你若不出迎，他便要多担一份惊惧。

（内心：这是第一道验证。往后还有乌巢，还有河
- 面对情境: 乌巢大火之后，天枢与曹孟德并肩而立，望着那片火光冲天的天际。在这一刻，天枢忽然感受到袖中，那件星君随身携带的玉简微微颤动——它在共鸣，仿佛在诉说被遗忘的往事。
- 我说：乌巢的火光映红了半边天穹，浓烟滚滚而上，遮蔽了星辰。

我立于风中，袍角被热浪掀起。

袖中玉简骤然一颤——那颤动如此熟悉，仿佛隔着千年岁月，终于寻到了什么。

（内心：这感觉……不可能。玉简怎会在此刻共鸣？）

我按住袖口，指尖触及那温热的玉质。脑中忽然闪过一个画面：观星台上，星河尽头，有一道身影正望向此处。

我猛然抬首。

那火光深处，有什么东西正在注视着我。

……孟德。

我侧首，声音沉

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
    description='演员 天枢，角色：protagonist。外表沉静如古井，内心炽热似骄阳。背负天命却不甘为棋子，说话简洁有力，每字皆如山岳。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9036)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9036)
