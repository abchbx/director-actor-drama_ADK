"""First-launch interactive tutorial for Director-Actor Drama System.

Detects first-time users and walks them through core commands
with step-by-step guidance before the main interactive loop begins.
"""

import os

# Marker file to track tutorial completion
_TUTORIAL_MARKER = os.path.join(os.path.dirname(__file__), ".tutorial_completed")


def is_first_launch() -> bool:
    """Check if this is the user's first time launching the app."""
    return not os.path.exists(_TUTORIAL_MARKER)


def mark_tutorial_completed():
    """Mark the tutorial as completed so it won't show again."""
    with open(_TUTORIAL_MARKER, "w", encoding="utf-8") as f:
        f.write("completed\n")


def reset_tutorial():
    """Reset tutorial state so it shows again on next launch."""
    if os.path.exists(_TUTORIAL_MARKER):
        os.remove(_TUTORIAL_MARKER)


def run_tutorial():
    """Run the interactive first-launch tutorial.

    Walks the user through the basic workflow:
    1. Start a drama
    2. Understand actors & cognitive boundaries
    3. Advance the story
    4. Use key commands
    5. Save & continue
    """
    print()
    print("🌟" * 30)
    print()
    print("  欢迎来到「导演-演员戏剧创作系统」！")
    print("  看起来你是第一次使用，让我带你快速了解基本操作。")
    print()
    print("🌟" * 30)
    print()

    # Step 1: Core concept
    _step(
        "第一步：理解核心概念",
        [
            "本系统采用「导演 + 演员」双Agent架构：",
            "",
            "  🎭 导演 (Director) — 你对话的对象，统筹全局、旁白、剧本编写",
            "  🎬 演员 (Actor)    — 独立运行的AI角色，各有记忆和认知边界",
            "",
            "关键理念：每个演员只知道角色该知道的事，",
            "他们之间通过A2A协议真正隔离，产生真实的戏剧冲突！",
        ],
    )

    # Step 2: Starting a drama
    _step(
        "第二步：启动你的第一部剧作",
        [
            "使用 /start 命令开始创作，例如：",
            "",
            '  /start 一个现代都市中两个陌生人的偶遇',
            '  /start 古代王朝的宫廷斗争',
            '  /start 科幻世界中的太空冒险',
            "",
            "导演会自动：发现多重视角 → 生成大纲 → 创建角色 → 开始第一场戏",
            "你只需要给出一个主题，剩下的交给导演！",
        ],
    )

    # Step 3: Core commands
    _step(
        "第三步：掌握核心命令",
        [
            "创作过程中，你可以用这些命令掌控剧情：",
            "",
            "  /next           → 推进到下一场戏",
            "  /action <描述>  → 注入一个事件（如：/action 突然下起了暴雨）",
            "  /steer <方向>   → 引导下一场方向（如：/steer 让冲突升级）",
            "  /auto [N]       → 自动推进 N 场戏（默认3场）",
            "  /end            → 终幕：生成结局 + 导出完整剧本",
            "",
            "也可以直接输入文字与导演交流想法！",
        ],
    )

    # Step 4: Advanced features
    _step(
        "第四步：进阶功能",
        [
            "当你熟悉基本操作后，可以探索更多功能：",
            "",
            "  /storm [焦点]   → 触发视角审视，重新发现剧情可能性",
            "  /cast           → 查看所有角色及其状态",
            "  /status         → 查看当前剧情进度和冲突信息",
            "  /save [名称]    → 保存当前进度",
            "  /load <名称>    → 加载之前的存档",
            "  /export         → 将剧本导出为 Markdown 文件",
            "  /list           → 列出所有已保存的剧作",
        ],
    )

    # Step 5: Tips
    _step(
        "第五步：创作小贴士",
        [
            "💡 新手建议：",
            "",
            "  1. 从简单主题开始，熟悉后再挑战复杂剧情",
            "  2. /action 是推动剧情的利器，大胆注入意外事件",
            "  3. /steer 可以微调方向，但不必每场都引导",
            "  4. /auto 适合让故事自然发展，观察角色如何互动",
            "  5. 记得 /save 保存进度，避免丢失创作成果",
            "  6. /help 随时可以查看命令列表",
        ],
    )

    # Completion
    print()
    print("🎉" * 30)
    print()
    print("  教程完成！你已经准备好开始创作了！")
    print()
    print("  试试输入：/start 你的第一个剧作主题")
    print()
    print("  如果想再看教程，输入 /tutorial 即可。")
    print()
    print("🎉" * 30)
    print()

    mark_tutorial_completed()


def _step(title: str, lines: list[str]):
    """Display a tutorial step and wait for user to continue."""
    print(f"  📖 {title}")
    print("  " + "─" * 50)
    for line in lines:
        print(f"  {line}")
    print("  " + "─" * 50)
    print()
    try:
        input("  按 Enter 继续 → ")
    except (EOFError, KeyboardInterrupt):
        print()
        return
    print()
