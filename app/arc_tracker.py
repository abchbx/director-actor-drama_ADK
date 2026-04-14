"""Arc Tracker — plot thread management and character arc tracking.

弧线追踪器：剧情线索管理和角色弧线追踪的纯函数模块。
本模块不依赖 ToolContext，所有函数接收 state: dict 参数，确保可测试性。

Core components:
- ARC_TYPES / ARC_STAGES constants for arc classification
- DORMANT_THRESHOLD for auto-detection of forgotten threads
- create_thread_logic / update_thread_logic / resolve_thread_logic for plot thread CRUD
- set_actor_arc_logic for character arc progress tracking
"""

import re


# ============================================================================
# Constants / 常量定义
# ============================================================================

ARC_TYPES = {"growth": "成长", "fall": "堕落", "transformation": "转变", "redemption": "救赎"}
ARC_STAGES = {"setup": "铺垫", "development": "发展", "climax": "高潮", "resolution": "收束"}
DORMANT_THRESHOLD = 8
MAX_PROGRESS_NOTES = 10
MAX_RESOLVED_CONFLICTS = 20

_DEFAULT_ARC_PROGRESS = {
    "arc_type": "",
    "arc_stage": "",
    "progress": 0,
    "related_threads": [],
}


# ============================================================================
# Default initialization / 默认初始化
# ============================================================================


def _init_arc_tracker_defaults() -> dict:
    """Return default arc tracker state fields (D-34).

    返回弧线追踪器的默认状态字段。
    """
    return {"plot_threads": []}


# ============================================================================
# Pure functions / 纯函数
# ============================================================================


def create_thread_logic(description: str, involved_actors: list[str], state: dict) -> dict:
    """Create a new plot thread with auto-generated ID.

    创建新的剧情线索，自动生成 thread_id。
    格式：thread_{scene}_{keyword}_{index}

    Args:
        description: Thread description.
        involved_actors: List of actor names involved in this thread.
        state: Drama state dict with actors, current_scene, plot_threads.

    Returns:
        dict with status and thread info.
    """
    current_scene = state.get("current_scene", 0)
    plot_threads = state.get("plot_threads", [])

    # Validate involved_actors exist in state
    actors = state.get("actors", {})
    invalid_actors = [a for a in involved_actors if a not in actors]
    if invalid_actors:
        return {
            "status": "error",
            "message": f"演员不存在：{'、'.join(invalid_actors)}",
        }

    # Extract keyword from description (2-4 Chinese chars)
    match = re.search(r'[\u4e00-\u9fff]{2,4}', description)
    keyword = match.group(0) if match else "thread"

    # Calculate index for same scene+keyword combo
    prefix = f"thread_{current_scene}_{keyword}"
    existing_count = sum(1 for t in plot_threads if t.get("id", "").startswith(prefix))
    index = existing_count + 1

    thread_id = f"thread_{current_scene}_{keyword}_{index}"

    thread = {
        "id": thread_id,
        "description": description,
        "status": "active",
        "involved_actors": involved_actors,
        "introduced_scene": current_scene,
        "last_updated_scene": current_scene,
        "progress_notes": [],
    }

    plot_threads.append(thread)
    state["plot_threads"] = plot_threads

    return {
        "status": "success",
        "thread_id": thread_id,
        "thread": thread,
    }


def update_thread_logic(thread_id: str, status: str | None, progress_note: str | None, state: dict) -> dict:
    """Update a plot thread's status and/or progress note.

    更新剧情线索的状态和/或进展记录。
    progress_notes FIFO 上限 MAX_PROGRESS_NOTES 条。

    Args:
        thread_id: The thread ID to update.
        status: New status (active/dormant/resolving/resolved) or None to keep.
        progress_note: Progress note to append, or None.
        state: Drama state dict with plot_threads, current_scene.

    Returns:
        dict with status and update info.
    """
    current_scene = state.get("current_scene", 0)
    plot_threads = state.get("plot_threads", [])

    # Find thread
    thread = None
    for t in plot_threads:
        if t.get("id") == thread_id:
            thread = t
            break

    if thread is None:
        return {
            "status": "error",
            "message": f"线索 {thread_id} 不存在",
        }

    # Validate status if provided
    valid_statuses = {"active", "dormant", "resolving", "resolved"}
    if status is not None and status not in valid_statuses:
        return {
            "status": "error",
            "message": f"无效的线索状态 '{status}'，可用：{', '.join(sorted(valid_statuses))}",
        }

    updates_applied = {}

    # Update status if provided
    if status is not None:
        thread["status"] = status
        updates_applied["status"] = status

    # Append progress note if provided
    if progress_note is not None:
        note = f"第{current_scene}场：{progress_note}"
        thread["progress_notes"].append(note)
        # FIFO trim to MAX_PROGRESS_NOTES
        if len(thread["progress_notes"]) > MAX_PROGRESS_NOTES:
            thread["progress_notes"] = thread["progress_notes"][-MAX_PROGRESS_NOTES:]
        updates_applied["progress_note"] = note

    # Always update last_updated_scene
    thread["last_updated_scene"] = current_scene

    return {
        "status": "success",
        "thread_id": thread_id,
        "updates_applied": updates_applied,
    }


def resolve_thread_logic(thread_id: str, resolution: str, state: dict) -> dict:
    """Resolve a plot thread with a resolution note.

    解决剧情线索，标记为 resolved。如果关联了冲突，返回提示。

    Args:
        thread_id: The thread ID to resolve.
        resolution: Resolution description.
        state: Drama state dict with plot_threads, current_scene, conflict_engine.

    Returns:
        dict with status and resolution info, including linked_conflict_hint if applicable.
    """
    current_scene = state.get("current_scene", 0)
    plot_threads = state.get("plot_threads", [])

    # Find thread
    thread = None
    for t in plot_threads:
        if t.get("id") == thread_id:
            thread = t
            break

    if thread is None:
        return {
            "status": "error",
            "message": f"线索 {thread_id} 不存在",
        }

    if thread.get("status") == "resolved":
        return {
            "status": "error",
            "message": f"线索 {thread_id} 已解决",
        }

    # Set status to resolved
    thread["status"] = "resolved"

    # Append resolution note
    resolution_note = f"第{current_scene}场：[解决] {resolution}"
    thread["progress_notes"].append(resolution_note)
    # FIFO trim
    if len(thread["progress_notes"]) > MAX_PROGRESS_NOTES:
        thread["progress_notes"] = thread["progress_notes"][-MAX_PROGRESS_NOTES:]

    # Update last_updated_scene
    thread["last_updated_scene"] = current_scene

    # Check for linked conflicts (D-23)
    linked_conflict_hint = None
    active_conflicts = state.get("conflict_engine", {}).get("active_conflicts", [])
    for conflict in active_conflicts:
        if conflict.get("thread_id") == thread_id:
            linked_conflict_hint = f"关联冲突 {conflict['id']} 是否也解决？"
            break

    result = {
        "status": "success",
        "thread_id": thread_id,
        "resolution": resolution,
    }
    if linked_conflict_hint:
        result["linked_conflict_hint"] = linked_conflict_hint

    return result


def set_actor_arc_logic(
    actor_name: str,
    arc_type: str | None,
    arc_stage: str | None,
    progress: int | None,
    related_threads: list[str] | None,
    state: dict,
) -> dict:
    """Set or update an actor's arc progress.

    设置或更新演员的角色弧线进展。支持部分更新。

    Args:
        actor_name: The actor's name.
        arc_type: Arc type key (growth/fall/transformation/redemption) or None to keep.
        arc_stage: Arc stage key (setup/development/climax/resolution) or None to keep.
        progress: Progress value (0-100) or None to keep.
        related_threads: List of related thread IDs or None to keep.
        state: Drama state dict with actors.

    Returns:
        dict with status and arc_progress info.
    """
    actors = state.get("actors", {})

    # Validate actor exists
    if actor_name not in actors:
        return {
            "status": "error",
            "message": f"演员 '{actor_name}' 不存在",
        }

    # Validate arc_type if provided
    if arc_type is not None and arc_type not in ARC_TYPES:
        return {
            "status": "error",
            "message": f"无效的弧线类型 '{arc_type}'，可用：{', '.join(ARC_TYPES.keys())}",
        }

    # Validate arc_stage if provided
    if arc_stage is not None and arc_stage not in ARC_STAGES:
        return {
            "status": "error",
            "message": f"无效的弧线阶段 '{arc_stage}'，可用：{', '.join(ARC_STAGES.keys())}",
        }

    # Validate progress if provided
    if progress is not None and (progress < 0 or progress > 100):
        return {
            "status": "error",
            "message": f"弧线进展必须在 0-100 之间，当前值：{progress}",
        }

    # Initialize arc_progress if not exists
    actor_data = actors[actor_name]
    if "arc_progress" not in actor_data:
        actor_data["arc_progress"] = _DEFAULT_ARC_PROGRESS.copy()

    # Apply partial updates
    if arc_type is not None:
        actor_data["arc_progress"]["arc_type"] = arc_type
    if arc_stage is not None:
        actor_data["arc_progress"]["arc_stage"] = arc_stage
    if progress is not None:
        actor_data["arc_progress"]["progress"] = progress
    if related_threads is not None:
        actor_data["arc_progress"]["related_threads"] = related_threads

    return {
        "status": "success",
        "actor_name": actor_name,
        "arc_progress": actor_data["arc_progress"],
    }
