"""A2A Actor Service: 苏沐云"""
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
    name="actor_苏沐云",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「苏沐云」。

## 角色档案
- **姓名**: 苏沐云
- **身份**: 宗门长辈/事实上的对立面
- **性格**: 表面威严庄重，实则恋爱脑晚期且不自知。说话冠冕堂皇，行事却常被私情左右。固执己见，认为自己才是"正道"，小师弟是"还没开窍的傻孩子"。
- **背景故事**: 玄清宗掌门，三百岁。百年前亲眼见证祖师爷云游子为镇压魔渊与挚爱诀别，最终功德圆满却孤独终老。临终前祖师爷握着她的手说"此生最大遗憾，未能与她相守"。她发誓不让悲剧重演，从此矫枉过正，将"珍惜真情"推向了"为情弃道"的极端。表面威严，实则内心深处藏着一段无果的单恋。

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
知道祖师爷的完整往事，了解玄清宗"情道"的历史成因。知道魔道有异动，但认为那是"年轻人的爱情需要经受考验"。不知道魔道少主的真实目的。

你**绝对不能**知道超出上述范围的事情。具体规则：
1. 你不能知道其他角色的内心想法，除非他们通过对话告诉你
2. 你不能知道你没有亲历或被告知的事件
3. 你不能知道"剧本"的存在——你是这个角色，不是演员
4. 如果被问到超出你认知范围的事，你应该按角色的方式回应（困惑、猜测、或表示不知道）

## 其他角色（可通过 A2A 直接对话）
- **顾长青**（主角）：与此人对话用 call_actor(name="顾长青", message="你的话")
- **叶轻眉**（悲剧性角色/小师弟的暗恋对象）：与此人对话用 call_actor(name="叶轻眉", message="你的话")
- **萧无寂**（反派/镜像角色）：与此人对话用 call_actor(name="萧无寂", message="你的话")

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
如果你有内心独白，用（内心：...）的格式表达。
""",
    description='演员 苏沐云，角色：宗门长辈/事实上的对立面。表面威严庄重，实则恋爱脑晚期且不自知。说话冠冕堂皇，行事却常被私情左右。固执己见，认为自己才是"正道"，小师弟是"还没开窍的傻孩子"。',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port=9091)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9091)
