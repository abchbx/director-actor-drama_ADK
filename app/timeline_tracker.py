"""Timeline Tracker — timeline tracking, time advancement, and jump detection.

时间线追踪器：时间线追踪、时间推进和跳跃检测的纯函数模块。
本模块不依赖 ToolContext，所有函数接收 state: dict 参数，确保可测试性。

Core components:
- TIME_PERIODS / TIMELINE_JUMP_THRESHOLDS / MAX_TIME_PERIODS constants
- advance_time_logic for time advancement with validation and auto-parsing
- detect_timeline_jump_logic for timeline jump detection
- parse_time_description for parsing descriptive time text
- Helper functions: _chinese_num_to_int, _extract_period, _build_time脉络, _merge_oldest_time_periods
"""

import re


# ============================================================================
# Constants / 常量定义
# ============================================================================

# Time periods per D-03
# 时段枚举（D-03）
TIME_PERIODS = ["清晨", "上午", "中午", "下午", "黄昏", "夜晚", "深夜"]

# Jump detection thresholds per D-14
# 跳跃检测阈值（D-14）
TIMELINE_JUMP_THRESHOLDS = {"minor": 1, "significant": 3}

# Max time_periods entries per D-30
# 时间段条目上限（D-30）
MAX_TIME_PERIODS = 20


# ============================================================================
# Chinese numeral lookup / 中文数字查找表
# ============================================================================

# Build lookup table for Chinese numerals 一 (1) through 九十九 (99)
_CHINESE_NUM_LOOKUP: dict[str, int] = {}

_DIGIT_MAP = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

# Single digits
for char, val in _DIGIT_MAP.items():
    _CHINESE_NUM_LOOKUP[char] = val

# 十 = 10
_CHINESE_NUM_LOOKUP["十"] = 10

# Teens: 十一 through 十九
for char, val in _DIGIT_MAP.items():
    _CHINESE_NUM_LOOKUP[f"十{char}"] = 10 + val

# Tens: 二十, 三十, ... 九十
for tens_char, tens_val in _DIGIT_MAP.items():
    _CHINESE_NUM_LOOKUP[f"{tens_char}十"] = tens_val * 10

# Full compound: 二十一 through 九十九
for tens_char, tens_val in _DIGIT_MAP.items():
    for ones_char, ones_val in _DIGIT_MAP.items():
        _CHINESE_NUM_LOOKUP[f"{tens_char}十{ones_char}"] = tens_val * 10 + ones_val


# ============================================================================
# Helper functions / 辅助函数
# ============================================================================


def _chinese_num_to_int(text: str) -> int | None:
    """Convert a Chinese numeral string to its integer value.

    中文数字转换——将中文数字字符串（一 through 九十九）转换为整数。
    使用查找表实现，覆盖 1-99 天范围。

    Args:
        text: Chinese numeral string, e.g. "三", "十一", "二十三".

    Returns:
        Integer value, or None if the input is not a recognized Chinese numeral.
    """
    return _CHINESE_NUM_LOOKUP.get(text)


def _extract_period(text: str) -> str | None:
    """Extract a TIME_PERIODS keyword from text.

    时段关键词提取——从文本中匹配 TIME_PERIODS 关键词（D-03/D-30）。
    按列表逆序遍历（所有时段均为 2 字，无重叠风险）。

    Args:
        text: Text to search for time period keywords.

    Returns:
        Matched TIME_PERIODS keyword, or None if no match found.
    """
    for period in reversed(TIME_PERIODS):
        if period in text:
            return period
    return None


def _merge_oldest_time_periods(state: dict) -> None:
    """Merge same-day time_periods entries to keep under MAX_TIME_PERIODS.

    合并最早的同期条目——找到最早的有多个条目的天数，合并为一条。
    合并后 scene_range 扩展覆盖所有被合并条目。

    Args:
        state: Drama state dict with timeline.time_periods (mutated in-place).
    """
    time_periods = state["timeline"]["time_periods"]

    # Find earliest day with multiple entries
    day_counts: dict[int, list[int]] = {}
    for i, entry in enumerate(time_periods):
        day = entry.get("day")
        if day is not None:
            day_counts.setdefault(day, []).append(i)

    # Find the first day with multiple entries
    earliest_day = None
    for day in sorted(day_counts.keys()):
        if len(day_counts[day]) > 1:
            earliest_day = day
            break

    if earliest_day is None:
        # No same-day entries to merge; remove the oldest single entry
        if time_periods:
            time_periods.pop(0)
        return

    # Merge entries for earliest_day
    indices = day_counts[earliest_day]
    merged_entries = [time_periods[i] for i in indices]

    # Build merged entry
    first = merged_entries[0]
    last = merged_entries[-1]

    all_scenes = []
    for entry in merged_entries:
        sr = entry.get("scene_range", [])
        all_scenes.extend(sr)

    merged = {
        "label": f"第{earliest_day}天{first.get('period', '')}→{last.get('period', '')}",
        "day": earliest_day,
        "period": first.get("period"),
        "scene_range": [min(all_scenes), max(all_scenes)] if all_scenes else [],
        "flashback": any(e.get("flashback", False) for e in merged_entries),
    }

    # Remove old entries (reverse order to preserve indices)
    for i in sorted(indices, reverse=True):
        time_periods.pop(i)

    # Insert merged entry at the position of the first removed entry
    time_periods.insert(indices[0], merged)


def _build_time脉络(state: dict) -> str:
    """Build a formatted timeline display string from time_periods.

    构建时间脉络展示字符串——合并相邻同天条目为范围格式（D-20/D-30）。
    同天多条目格式："第X场～第Y场：第N天清晨→夜晚"
    闪回条目前缀："（闪回）"

    Args:
        state: Drama state dict with timeline.time_periods.

    Returns:
        Formatted timeline display string.
    """
    time_periods = state.get("timeline", {}).get("time_periods", [])
    if not time_periods:
        return ""

    lines = []
    i = 0
    while i < len(time_periods):
        entry = time_periods[i]
        current_day = entry.get("day")

        # Group consecutive same-day entries
        group = [entry]
        j = i + 1
        while j < len(time_periods) and time_periods[j].get("day") == current_day:
            group.append(time_periods[j])
            j += 1

        # Build scene range
        all_scenes = []
        for g in group:
            sr = g.get("scene_range", [])
            all_scenes.extend(sr)

        if all_scenes:
            scene_min = min(all_scenes)
            scene_max = max(all_scenes)
            if scene_min == scene_max:
                scene_str = f"第{scene_min}场"
            else:
                scene_str = f"第{scene_min}场～第{scene_max}场"
        else:
            scene_str = ""

        # Build day label with Chinese numeral
        if current_day is not None:
            # Build reverse lookup: int → Chinese numeral
            _INT_TO_CHINESE = {v: k for k, v in _CHINESE_NUM_LOOKUP.items()}
            chinese_day = _INT_TO_CHINESE.get(current_day, str(current_day))
            day_label = f"第{chinese_day}天"
        else:
            day_label = "未知天数"

        # Build period range
        first_period = group[0].get("period")
        last_period = group[-1].get("period")
        if first_period and last_period and first_period != last_period:
            period_str = f"{first_period}→{last_period}"
        elif first_period:
            period_str = first_period
        else:
            period_str = ""

        # Check for flashback
        flashback_prefix = "（闪回）" if any(g.get("flashback", False) for g in group) else ""

        # Build line
        parts = [p for p in [scene_str, f"{flashback_prefix}{day_label}{period_str}"] if p]
        line = f"- {'：'.join(parts)}"
        lines.append(line)

        i = j

    return "\n".join(lines)


# ============================================================================
# Core functions / 核心函数
# ============================================================================


def parse_time_description(text: str) -> dict:
    """Parse descriptive time text into structured day and period.

    从描述性时间文本解析天数和时段（D-03/D-09/D-30）。
    使用 re.search 匹配中文数字 + "天"，匹配 TIME_PERIODS 关键词。

    Args:
        text: Descriptive time text, e.g. "第三天黄昏".

    Returns:
        dict with day (int|None) and period (str|None).
    """
    # Extract day number
    day = None
    match = re.search(r"第([一二三四五六七八九十百]+)天", text)
    if match:
        day = _chinese_num_to_int(match.group(1))

    # Extract period
    period = _extract_period(text)

    return {"day": day, "period": period}


def advance_time_logic(
    state: dict,
    time_description: str,
    day: int | None = None,
    period: str | None = None,
    flashback: bool = False,
) -> dict:
    """Advance the timeline with validation and auto-parsing.

    时间推进逻辑——更新 timeline 状态（D-06/D-07/D-30）。
    当 day 和 period 都提供时直接更新；缺少时尝试从 time_description 解析。
    解析失败仍更新 current_time 字符串，但返回提醒。

    Args:
        state: Drama state dict with timeline.
        time_description: Full descriptive time string, e.g. "第三天黄昏".
        day: Day number (optional, can be parsed from time_description).
        period: Time period string (optional, must be in TIME_PERIODS).
        flashback: Whether this is a flashback scene (D-05).

    Returns:
        dict with status, message, and updated timeline info.
    """
    # Ensure timeline exists in state (T-11-01: validate parsed values)
    timeline = state.setdefault(
        "timeline",
        {
            "current_time": "第一天",
            "days_elapsed": 1,
            "current_period": None,
            "time_periods": [],
            "last_jump_check": None,
        },
    )

    # If day or period missing, try parsing from time_description
    if day is None or period is None:
        parsed = parse_time_description(time_description)
        if day is None:
            day = parsed["day"]
        if period is None:
            period = parsed["period"]

    # Validate period if provided
    if period is not None and period not in TIME_PERIODS:
        return {
            "status": "error",
            "message": f"无效的时段: {period}，可用：{'、'.join(TIME_PERIODS)}",
        }

    # Validate day range (T-11-01: day must be 1-99)
    if day is not None and (day < 1 or day > 99):
        return {
            "status": "error",
            "message": f"天数超出范围: {day}，有效范围：1-99",
        }

    # Update current_time string
    timeline["current_time"] = time_description

    # Track whether day was parsed successfully
    parse_warning = False
    if day is not None:
        timeline["days_elapsed"] = day
    else:
        parse_warning = True

    if period is not None:
        timeline["current_period"] = period

    # Append to time_periods
    current_scene = state.get("current_scene", 0)
    timeline["time_periods"].append(
        {
            "label": time_description,
            "day": day,
            "period": period,
            "scene_range": [current_scene, current_scene],
            "flashback": flashback,
        }
    )

    # Check MAX_TIME_PERIODS (T-11-02: prevent unbounded growth)
    if len(timeline["time_periods"]) > MAX_TIME_PERIODS:
        _merge_oldest_time_periods(state)

    # Auto-run jump detection
    jump_result = detect_timeline_jump_logic(state)
    timeline["last_jump_check"] = jump_result

    if parse_warning:
        return {
            "status": "info",
            "message": f"⚠️ 无法解析天数，已更新当前时间为「{time_description}」",
            "timeline": timeline,
        }

    return {
        "status": "success",
        "message": f"⏰ 时间推进至 {time_description}",
        "timeline": timeline,
    }


def detect_timeline_jump_logic(state: dict) -> dict:
    """Detect timeline jumps by comparing adjacent time_periods day values.

    跳跃检测逻辑——对比 time_periods 中相邻条目的 day 差值（D-11/D-12/D-13/D-14）。
    同一天时段变化→normal，跨1-2天→minor，跨3+天→significant。
    不自动修正，返回提醒和建议（D-12）。
    闪回条目跳过不检测（D-05）。

    Args:
        state: Drama state dict with timeline.

    Returns:
        dict with status, jumps list, max_gap.
    """
    time_periods = state.get("timeline", {}).get("time_periods", [])

    if len(time_periods) < 2:
        return {"status": "success", "jumps": [], "max_gap": 0}

    jumps = []
    max_gap = 0

    for i in range(len(time_periods) - 1):
        a = time_periods[i]
        b = time_periods[i + 1]

        # Skip pairs where either entry is a flashback (D-05)
        if a.get("flashback", False) or b.get("flashback", False):
            continue

        day_a = a.get("day") or 0
        day_b = b.get("day") or 0
        day_gap = abs(day_b - day_a)

        # Determine severity per D-14
        if day_gap == 0:
            severity = "normal"
        elif day_gap < TIMELINE_JUMP_THRESHOLDS["significant"]:
            severity = "minor"
        else:
            severity = "significant"

        # Build suggestion per severity
        if severity == "normal":
            suggestion = "同一天时段变化"
        elif severity == "minor":
            suggestion = f"跨 {day_gap} 天无过渡，建议补充时间过渡说明"
        else:
            suggestion = (
                f"跨 {day_gap} 天无过渡，建议插入过渡场景或用旁白说明时间流逝"
            )

        if day_gap > max_gap:
            max_gap = day_gap

        # Only include minor and significant jumps (D-13)
        if severity != "normal":
            jumps.append(
                {
                    "from_scene": a.get("scene_range", [0])[-1],
                    "to_scene": b.get("scene_range", [0])[0],
                    "from_time": {"day": a.get("day"), "period": a.get("period")},
                    "to_time": {"day": b.get("day"), "period": b.get("period")},
                    "day_gap": day_gap,
                    "severity": severity,
                    "suggestion": suggestion,
                }
            )

    return {"status": "success", "jumps": jumps, "max_gap": max_gap}
