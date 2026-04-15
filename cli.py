#!/usr/bin/env python3
"""CLI interface for the Director-Actor Drama System (A2A version).

Provides an interactive command-line interface for the drama system.
Actors run as independent A2A services, ensuring true multi-agent isolation.
"""

import asyncio
import atexit
import os
import re
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

load_dotenv(os.path.join(os.path.dirname(__file__), "app", ".env"))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent
from app.actor_service import stop_all_actor_services
from app.api.lock import acquire_lock, release_lock

APP_NAME = "app"
USER_ID = "drama_user"
SESSION_ID = "drama_session"

# Register cleanup
atexit.register(lambda: stop_all_actor_services())


def print_banner():
    """Print the welcome banner."""
    print("=" * 60)
    print("  🎭 导演-演员戏剧创作系统 (A2A 多Agent架构)")
    print("  Director-Actor Drama System")
    print("=" * 60)
    print()
    print("  架构说明:")
    print("  - 导演 Agent: 统筹全局、旁白、剧本编写")
    print("  - 演员 Agent: 独立 A2A 服务，各自拥有会话和记忆")
    print("  - 认知边界: 通过 A2A 物理隔离天然保证")
    print()
    print("  命令列表:")
    print("  /start <主题>   - 开始新剧作")
    print("  /next           - 推进下一场")
    print("  /action <描述>  - 注入具体事件")
    print("  /steer <方向>   - 设置下一场方向引导")
    print("  /auto [N]       - 自动推进 N 场（默认3场）")
    print("  /end            - 终幕：生成终幕旁白 + 导出剧本")
    print("  /storm [焦点]   - 触发视角审视")
    print("  /save [名称]    - 保存进度（含对话记录）")
    print("  /load <名称>    - 加载进度")
    print("  /export         - 导出剧本为 Markdown")
    print("  /list           - 列出所有已保存的剧本")
    print("  /cast           - 查看角色列表（含A2A状态）")
    print("  /status         - 查看当前状态")
    print("  /help           - 显示帮助")
    print("  /quit           - 退出系统（自动保存）")
    print()
    print("  也可以直接输入文字与导演对话。")
    print("=" * 60)
    print()


async def run_interactive():
    """Run the interactive CLI loop."""
    # D-07: Check lock file — refuse to start if API is already running
    try:
        acquire_lock()
    except RuntimeError as e:
        print(f"\n❌ {e}")
        return

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    print_banner()

    while True:
        try:
            user_input = input("\n🎬 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 再见！")
            break

        if not user_input:
            continue

        # D-04: /auto without number defaults to 3 scenes
        if user_input.lower() == "/auto":
            user_input = "/auto 3"

        # Handle local commands
        if user_input == "/quit":
            print("\n💾 正在自动保存...")
            await _send_message(runner, "/save")
            print("\n🛑 正在停止所有演员 A2A 服务...")
            stop_all_actor_services()
            release_lock()
            print("\n👋 再见！期待下次继续你的戏剧创作！")
            break

        if user_input == "/help":
            print_banner()
            continue

        # Send to agent
        response = await _send_message(runner, user_input)
        if response:
            print(f"\n🎭 导演: {response}")


def _extract_actors_from_response(resp: dict) -> str:
    """Extract actor names from write_scene response for scene summary (D-15)."""
    # Try explicit actors_in_scene field first
    actors = resp.get("actors_in_scene", [])
    if actors:
        return "、".join(actors)
    # Fallback: extract "🎭 角色名" pattern from dialogue/scene content
    dialogue = resp.get("dialogue_content", "") or resp.get("formatted_scene", "")
    pattern = r"🎭\s*(\S+?)（"
    matches = re.findall(pattern, dialogue)
    if matches:
        return "、".join(matches)
    return ""


async def _send_message(runner: Runner, message: str) -> str:
    """Send a message to the agent and collect the response."""
    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )

    response_parts = []
    # Content fields from tool responses that should be displayed to the user
    _content_keys = [
        "formatted_narration",
        "formatted_dialogue",
        "formatted_scene",
        "dialogue",
        "narration",
        "message",
    ]

    # Spinner for LLM wait indicator (D-13/D-14)
    console = Console()
    spinner = Spinner("dots", text=" 🤔 思考中...")
    live = Live(spinner, console=console, transient=True)
    spinner_active = False

    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=content,
        ):
            # Start spinner on first non-final event (LLM is processing)
            if not spinner_active and not event.is_final_response():
                try:
                    live.start()
                    spinner_active = True
                except Exception:
                    # Fallback: simple text indicator if Live fails
                    print("⏳ 思考中...")
                    spinner_active = True

            if event.is_final_response():
                # Stop spinner before printing final response
                if spinner_active:
                    try:
                        live.stop()
                    except Exception:
                        print("\r✅ 完成！\n")
                    spinner_active = False
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_parts.append(part.text)
            elif event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        fn_name = part.function_call.name
                        fn_args = part.function_call.args
                        if fn_name in [
                            "start_drama",
                            "create_actor",
                            "next_scene",
                            "user_action",
                            "save_drama",
                            "load_drama",
                            "export_drama",
                            "auto_advance",    # Phase 5
                            "steer_drama",     # Phase 5
                            "end_drama",       # Phase 5
                            "trigger_storm",   # Phase 5
                        ]:
                            args_str = str(fn_args)
                            if len(args_str) > 80:
                                args_str = args_str[:80] + "..."
                            print(f"  ⚙️ {fn_name}({args_str})")
                    if part.function_response:
                        # Display content from tool responses so users can see
                        # dialogue, narration, scene content, etc.
                        resp = part.function_response.response
                        if resp:
                            for key in _content_keys:
                                if key in resp and resp[key]:
                                    text = str(resp[key]).strip()
                                    if text:
                                        print(f"\n{text}")
                                    break  # Only show the first matching key

                            # D-15: Scene summary display
                            if "scene_number" in resp and "scene_title" in resp:
                                scene_num = resp.get("scene_number", "?")
                                scene_title = resp.get("scene_title", "")
                                actors_in_scene = _extract_actors_from_response(resp)
                                if actors_in_scene:
                                    print(f"\n── 第{scene_num}场：{scene_title} ── 参演：{actors_in_scene}")
                                else:
                                    print(f"\n── 第{scene_num}场：{scene_title} ──")
    except Exception as e:
        # Ensure spinner is stopped on error (T-12-07)
        if spinner_active:
            try:
                live.stop()
            except Exception:
                pass
            spinner_active = False

        # D-13: Unified Chinese error messages with fix suggestions
        err_msg = str(e)
        if "rate limit" in err_msg.lower() or "429" in err_msg:
            return "[错误] API 调用频率超限，请稍等几秒后重试。"
        elif "timeout" in err_msg.lower():
            return "[错误] 请求超时，LLM 响应较慢。可重试当前操作。"
        elif "api_key" in err_msg.lower() or "unauthorized" in err_msg.lower():
            return "[错误] API 密钥无效，请检查 .env 中的配置。"
        else:
            return f"[错误] {err_msg}\n💡 如持续出现，可尝试 /save 保存后 /load 重新加载。"
    finally:
        # Ensure spinner is always stopped (T-12-07 mitigation)
        if spinner_active:
            try:
                live.stop()
            except Exception:
                pass

    return "\n".join(response_parts)


def main():
    """Main entry point."""
    try:
        asyncio.run(run_interactive())
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
    finally:
        stop_all_actor_services()
        release_lock()  # D-07: Ensure cleanup even on exception


if __name__ == "__main__":
    main()
