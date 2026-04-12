# Coding Conventions

**Analysis Date:** 2026-04-11

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `actor_service.py`, `state_manager.py`, `tools.py`)
- Actor service files: `actor_{角色名}.py` where 角色名 is the Chinese character name (e.g., `actor_苏念.py`, `actor_朱棣.py`)
- Actor card JSON: `actor_{safe_name}_card.json` where safe_name sanitizes non-alphanumeric chars to `_`
- Test files: `test_{module}.py` (e.g., `test_agent.py`, `test_dummy.py`)
- Eval sets: `{name}.evalset.json` (e.g., `basic.evalset.json`)

**Functions:**
- Public tool functions: `snake_case` (e.g., `start_drama`, `create_actor`, `actor_speak`)
- Private helper functions: `_snake_case` prefix (e.g., `_get_state`, `_set_state`, `_call_a2a_sdk`, `_sanitize_name`)
- STORM framework functions: `storm_{verb}_{noun}` pattern (e.g., `storm_discover_perspectives`, `storm_add_research_result`, `storm_set_outline`)
- Sub-agents (module-level): `_storm_{role}` prefix (e.g., `_storm_discoverer`, `_storm_researcher`, `_storm_outliner`, `_storm_director`)

**Variables:**
- Module-level constants: `UPPER_SNAKE_CASE` (e.g., `ACTOR_BASE_PORT`, `DRAMAS_DIR`, `OPENAI_API_KEY`)
- Module-level mutable state: `_snake_case` prefix (e.g., `_actor_processes`, `_conversation_log`, `_current_drama_folder`)
- Local variables: `snake_case` (e.g., `actor_name`, `tool_context`, `state`)

**Types:**
- Pydantic models: `PascalCase` (e.g., `Feedback` in `app/app_utils/typing.py`)
- Type annotations use Python 3.10+ union syntax: `str | None` instead of `Optional[str]`, `list[dict]` instead of `List[Dict]`
- Return types: almost always `dict` for tool functions and state manager functions

## Code Style

**Formatting:**
- Tool: `ruff format` (configured in `pyproject.toml`)
- Line length: 88 (ruff default)
- Target Python: 3.10+

**Linting:**
- Tool: `ruff check` (configured in `pyproject.toml`)
- Enabled rule sets: `E` (pycodestyle), `F` (pyflakes), `W` (warnings), `I` (isort), `C` (comprehensions), `B` (bugbear), `UP` (pyupgrade), `RUF` (ruff-specific)
- Ignored rules: `E501` (line too long), `C901` (too complex), `B006` (mutable default args)
- Spell check: `codespell` with `ignore-words-list = "rouge"`
- Type checker: `ty` (Astral's Rust-based type checker) — most rules set to `ignore` for third-party compatibility

**Key lint commands:**
```bash
make lint  # runs codespell + ruff check + ruff format --check + ty check
```

## Import Organization

**Order** (enforced by ruff isort with `known-first-party = ["app", "frontend"]`):
1. Standard library (`os`, `json`, `asyncio`, `sys`, `subprocess`, etc.)
2. Third-party (`dotenv`, `google.adk.*`, `a2a.*`, `pydantic`, `httpx`, `uvicorn`)
3. First-party (`from .state_manager import ...`, `from .actor_service import ...`)

**Path Aliases:**
- Relative imports within `app/`: `from .tools import ...`, `from .state_manager import ...`
- No path alias configuration (no `sys.path` hacks)

**Example from `app/tools.py`:**
```python
import os
from datetime import datetime

from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import ToolContext

from .state_manager import (
    add_narration,
    add_conversation,
    ...
)
from .actor_service import (
    create_actor_service,
    ...
)
```

## Docstring Patterns

**Format:** Google-style docstrings, **bilingual Chinese+English**

All public functions use this pattern:
```python
def create_actor(
    actor_name: str,
    role: str,
    personality: str,
    background: str,
    knowledge_scope: str,
    tool_context: ToolContext,
) -> dict:
    """Create a new actor/character as an A2A service. The director uses this to add characters.

    Each actor runs as an independent A2A agent with its own session and memory,
    ensuring true cognitive boundary isolation.

    Args:
        actor_name: The name of the character.
        role: The character's role (e.g., protagonist, antagonist, mentor).
        personality: Personality traits and speaking style (e.g., "沉稳冷静，说话简短有力").
        background: The character's backstory.
        knowledge_scope: What this character knows (defines cognitive boundary).

    Returns:
        dict with creation status and A2A connection info.
    """
```

**Key conventions:**
- First line: English imperative summary sentence
- Second paragraph: English elaboration (optional)
- `Args:`: One line per parameter, type is NOT repeated (it's in the signature)
- `Returns:`: Describes the dict structure, often starts with "dict with..."
- Chinese text appears in parameter descriptions and return values when referring to domain concepts
- Module docstrings at top of file describe the module's purpose, often bilingual

**Private function docstrings:**
- Still use Google-style but may be shorter
- Example: `"""Get the folder path for the current drama."""`

## Tool Function Patterns

**Every tool function follows this signature pattern:**
```python
def tool_name(param1: str, param2: str, tool_context: ToolContext) -> dict:
```

**Key rules:**
1. `tool_context: ToolContext` is always the **last** positional parameter
2. Async tools use `async def` (e.g., `actor_speak` in `app/tools.py`)
3. Return value is always a `dict` with at minimum `"status"` and `"message"` keys

**Return dict format:**
```python
# Success
{
    "status": "success",
    "message": "描述性中文消息",  # Always includes Chinese user-facing message
    # ... domain-specific keys
}

# Error
{
    "status": "error",
    "message": "Error description",
}

# Info
{
    "status": "info",
    "message": "Informational message",
}
```

**State access pattern:**
```python
# Read state
state = tool_context.state.get("drama", {})
theme = state.get("theme", "")

# Write state (always through state_manager)
_set_state(state, tool_context)  # Auto-persists to disk
```

**Emoji usage in messages:** Tool return messages frequently use emoji for visual markers:
- 🎭 theater/drama, 🎬 direction/narration, 📝 recording, 📁 file paths, 💾 saving, ▶️ start, ⚠️ warnings

## Actor Definition Pattern

Actors are defined as **generated code files**, not hardcoded. The pattern:

1. `app/actor_service.py` → `generate_actor_agent_code()` produces a complete Python file
2. Written to `app/actors/actor_{safe_name}.py`
3. Launched as subprocess (`subprocess.Popen`)
4. Each actor gets a JSON card file at `app/actors/actor_{safe_name}_card.json`

**Generated actor file structure:**
```python
"""A2A Actor Service: {actor_name}"""
import os
os.environ["OPENAI_API_KEY"] = '...'
os.environ["OPENAI_BASE_URL"] = '...'

import uvicorn
from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

# Optional: call_actor tool for inter-actor A2A communication
async def call_actor(actor_name: str, message: str, tool_context=None) -> str:
    ...

actor_agent = Agent(
    name="actor_{name}",
    model=LiteLlm(model='openai/claude-sonnet-4-6'),
    instruction="""你是一位戏剧演员，正在扮演角色「{name}」。
    
## 角色档案
- **姓名**: ...
- **身份**: ...
- **性格**: ...
- **背景故事**: ...

## 认知边界（极其重要，必须严格遵守）
你只知道以下内容：
{knowledge_scope}

## 行为准则
1-7 条规则...

## 回复格式
直接以角色的口吻说话，不需要加引号或角色名前缀。
如果你有内心独白，用（内心：...）的格式表达。
""",
    description='...',
    tools=[call_actor],
)

app = to_a2a(actor_agent, host="localhost", port={port})

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port={port})
```

**Key actor conventions:**
- Instruction is always in **Chinese** with markdown section headers
- `认知边界` (cognitive boundary) section is mandatory and strict
- `行为准则` (behavior guidelines) section is standardized
- `回复格式` (response format) requires inner monologue in `（内心：...）` format
- Each actor runs on a deterministic port: `ACTOR_BASE_PORT + (md5(name) % 100)`
- Maximum 10 actors per drama (enforced in `app/state_manager.py:register_actor`)

## State Management Conventions

**State structure** (stored in `tool_context.state["drama"]`):
```python
{
    "theme": str,              # Drama theme/premise
    "status": str,             # brainstorming | storm_discovering | storm_researching | storm_outlining | acting | paused | completed
    "current_scene": int,      # Current scene number (0-based start)
    "scenes": list[dict],      # Scene records
    "actors": dict,            # {actor_name: {role, personality, background, knowledge_scope, memory, emotions, port, ...}}
    "narration_log": list,     # Director narration entries
    "storm": {                 # STORM framework data
        "perspectives": list,
        "research_results": list,
        "outline": dict,
    },
    "created_at": str,         # ISO format timestamp
    "updated_at": str,         # ISO format timestamp
}
```

**Key naming conventions in state:**
- `snake_case` for all state keys
- Chinese values allowed in string fields (e.g., `"status": "brainstorming"`, emotion labels like `"愤怒"`)
- Timestamps always in ISO format via `datetime.now().isoformat()`
- Actor emotion mapping: English key → Chinese display label (e.g., `"angry"` → `"愤怒"`)

**Persistence pattern:**
- In-memory: `tool_context.state["drama"]` (primary)
- On-disk: `app/dramas/{sanitized_theme}/state.json` (auto-synced via `_set_state`)
- Snapshots: `app/dramas/{sanitized_theme}/snapshot_{name}.json`
- Conversations: `app/dramas/{sanitized_theme}/conversations/conversation_log.json`

**File naming sanitization:**
```python
def _sanitize_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
```

## Error Handling Patterns

**Tool function error handling:**
```python
# State validation - return error dict
if actor_info["status"] != "success":
    return actor_info  # Pass through error

# A2A communication - catch and format gracefully
try:
    actor_dialogue = await _call_a2a_sdk(card_file, prompt, actor_name, port)
except Exception as e:
    err_type = type(e).__name__
    msg = str(e).lower()
    if "connect" in err_type or "refused" in msg:
        actor_dialogue = f"[{actor_name}连接失败(端口:{port})。请用create_actor重启服务。]"
    elif "timeout" in msg:
        actor_dialogue = f"[{actor_name}响应超时。LLM推理可能较慢，稍后重试。]"
    else:
        actor_dialogue = f"[{actor_name}调用失败({err_type}): {e}]"
```

**General patterns:**
- No custom exception classes — use dict returns with `"status": "error"`
- A2A errors wrapped in Chinese bracket notation: `[角色名错误描述]`
- File I/O errors handled with `try/except` around `json.load`/`json.dump`
- Process management: `terminate()` → `wait(timeout=5)` → `kill()` escalation in `app/actor_service.py:_stop_actor_process`

## File Naming Conventions

**Source files:** `snake_case.py` — no hyphens, no camelCase
**Generated actor files:** `actor_{name}.py` where `{name}` is the original character name with non-alphanumeric chars replaced by `_`
**JSON data:** `snake_case.json` (e.g., `state.json`, `conversation_log.json`)
**Markdown exports:** `{sanitized_theme}.md`
**Config files:** `snake_case.json` for eval configs

## Chinese Language Usage Patterns

This is a **bilingual codebase** with these conventions:

| Context | Language | Example |
|---------|----------|---------|
| Code identifiers (functions, vars) | English | `start_drama`, `actor_speak`, `storm_discover` |
| Docstring first line | English | `"""Create a new actor/character as an A2A service."""` |
| Docstring details | Mixed | Parameter descriptions often Chinese |
| Tool return messages | Chinese | `"戏剧「{theme}」已启动！"` |
| Agent instructions | Chinese | Full system prompts in Chinese with markdown structure |
| User-facing strings | Chinese | All CLI output, status messages, error messages to users |
| Code comments | English | `# Track running actor processes` |
| Section headers | Chinese | `## 核心任务`, `## 角色档案`, `## 认知边界` |
| State values | Mixed | Statuses: English (`"acting"`, `"brainstorming"`); Emotions: English key, Chinese display |
| File/directory names | Chinese allowed | `actor_苏念.py`, `actor_朱棣.py` |

**Markdown in Chinese text:** Uses Chinese punctuation inside Chinese content (「」for quotes, 、for comma separation, 。for period).

## Module Design

**Exports:**
- `app/__init__.py` exports `app` (the ADK App instance)
- `app/agent.py` defines `root_agent` and `app` as module-level variables
- No barrel files (no `__init__.py` re-exports beyond top-level)
- `app/app_utils/` has no `__init__.py` — import directly from modules

**Sub-agent pattern in `app/agent.py`:**
```python
# Module-level sub-agents (private by convention, _prefix)
_storm_discoverer = Agent(name="storm_discoverer", ...)
_storm_researcher = Agent(name="storm_researcher", ...)
_storm_outliner = Agent(name="storm_outliner", ...)
_storm_director = Agent(name="storm_director", ...)

# Custom router class
class StormRouter(BaseAgent):
    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        ...

# Root agent composes sub-agents
root_agent = StormRouter(
    name="storm_director_root",
    sub_agents=[_storm_discoverer, _storm_researcher, _storm_outliner, _storm_director],
)
```

---

*Convention analysis: 2026-04-11*
