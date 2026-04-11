#!/usr/bin/env python3
"""CLI interface for the Director-Actor Drama System (A2A version).

Provides an interactive command-line interface for the drama system.
Actors run as independent A2A services, ensuring true multi-agent isolation.
"""

import asyncio
import atexit
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "app", ".env"))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent
from app.actor_service import stop_all_actor_services

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
    print("  /action <描述>  - 注入事件")
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

        # Handle local commands
        if user_input == "/quit":
            print("\n💾 正在自动保存...")
            await _send_message(runner, "/save")
            print("\n🛑 正在停止所有演员 A2A 服务...")
            stop_all_actor_services()
            print("\n👋 再见！期待下次继续你的戏剧创作！")
            break

        if user_input == "/help":
            print_banner()
            continue

        # Send to agent
        response = await _send_message(runner, user_input)
        if response:
            print(f"\n🎭 导演: {response}")


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

    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=content,
        ):
            if event.is_final_response():
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
    except Exception as e:
        return f"[错误] {e}"

    return "\n".join(response_parts)


def main():
    """Main entry point."""
    try:
        asyncio.run(run_interactive())
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
    finally:
        stop_all_actor_services()


if __name__ == "__main__":
    main()
