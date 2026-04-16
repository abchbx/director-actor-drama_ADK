"""State management for the drama system.

Handles saving/loading progress, script content, and actor states.
Each drama gets its own isolated folder for complete data separation.
"""

import atexit
import json
import logging
import os
import shutil
import threading
from datetime import datetime


logger = logging.getLogger(__name__)

# Base directory for all dramas
DRAMAS_DIR = os.path.join(os.path.dirname(__file__), "dramas")

# ============================================================================
# SceneContext — 场景共享认知状态（指代消解核心）
# ============================================================================


class SceneContext:
    """Maintains the shared cognitive state of the current scene.

    Tracks entities, pronoun mappings, and last-mentioned entities so that
    the director (the only trusted context manager) can resolve ambiguous
    pronouns before delivering dialogue to isolated actors.

    Persisted as ``state["scene_context"]`` and saved to ``state.json``.
    """

    def __init__(self, data: dict | None = None):
        d = data or {}
        # Named entities in the current scene: {name: {type, description, ...}}
        self.entities: dict[str, dict] = d.get("entities", {})
        # Pronoun → entity name mapping: {"他": "李明", "她": "苏念瑶", "这里": "咖啡馆"}
        self.pronoun_map: dict[str, str] = d.get("pronoun_map", {})
        # Per-speaker pronoun usage: {speaker_name: {"他": "实体名", ...}}
        self.speaker_refs: dict[str, dict[str, str]] = d.get("speaker_refs", {})
        # Last-mentioned entity per pronoun type (for fallback resolution)
        self.last_mentioned: dict[str, str] = d.get("last_mentioned", {})

    def to_dict(self) -> dict:
        return {
            "entities": self.entities,
            "pronoun_map": self.pronoun_map,
            "speaker_refs": self.speaker_refs,
            "last_mentioned": self.last_mentioned,
        }

    # --- Mutation helpers ---

    def register_entity(self, name: str, entity_type: str = "character",
                        description: str = "", **extra) -> None:
        """Register or update an entity in the scene."""
        entry = {"type": entity_type, "description": description, **extra}
        self.entities[name] = entry
        # Auto-map gendered pronouns for characters
        if entity_type == "character":
            gender = extra.get("gender", "")
            if gender == "male" and "他" not in self.pronoun_map:
                self.pronoun_map["他"] = name
            elif gender == "female" and "她" not in self.pronoun_map:
                self.pronoun_map["她"] = name

    def set_speaker_ref(self, speaker: str, pronoun: str, entity_name: str,
                        description: str = "") -> None:
        """Set what *pronoun* refers to when *speaker* uses it.

        Example: set_speaker_ref("苏念瑶", "他", "退婚未婚夫", description="她的退婚未婚夫")
        """
        if speaker not in self.speaker_refs:
            self.speaker_refs[speaker] = {}
        self.speaker_refs[speaker][pronoun] = entity_name
        # Also update last_mentioned
        self.last_mentioned[pronoun] = entity_name

    def resolve_pronoun(self, pronoun: str, speaker: str = "") -> tuple[str, str]:
        """Resolve a pronoun to (entity_name, description).

        Resolution order:
        1. speaker-specific mapping (speaker_refs[speaker][pronoun])
        2. global pronoun_map (pronoun_map[pronoun])
        3. last_mentioned fallback
        4. empty string if unresolvable

        Returns:
            (entity_name, description) — description may be empty.
        """
        # 1. Speaker-specific
        if speaker and speaker in self.speaker_refs:
            entity = self.speaker_refs[speaker].get(pronoun, "")
            if entity:
                desc = self.entities.get(entity, {}).get("description", "")
                return entity, desc
        # 2. Global
        entity = self.pronoun_map.get(pronoun, "")
        if entity:
            desc = self.entities.get(entity, {}).get("description", "")
            return entity, desc
        # 3. Last mentioned
        entity = self.last_mentioned.get(pronoun, "")
        if entity:
            desc = self.entities.get(entity, {}).get("description", "")
            return entity, desc
        # 4. Unresolvable
        return "", ""

    def touch_entity(self, entity_name: str, pronoun: str = "") -> None:
        """Mark an entity as recently mentioned, updating last_mentioned."""
        if pronoun:
            self.last_mentioned[pronoun] = entity_name
        # Also try to infer pronoun from entity gender
        if entity_name in self.entities:
            gender = self.entities[entity_name].get("gender", "")
            if gender == "male":
                self.last_mentioned["他"] = entity_name
            elif gender == "female":
                self.last_mentioned["她"] = entity_name

    def clear_scene(self) -> None:
        """Reset transient per-scene state while keeping registered entities."""
        self.pronoun_map.clear()
        self.speaker_refs.clear()
        self.last_mentioned.clear()


def get_scene_context(tool_context=None) -> SceneContext:
    """Get the current SceneContext from state, creating one if absent."""
    state = _get_state(tool_context)
    ctx_data = state.get("scene_context", {})
    return SceneContext(ctx_data)


def save_scene_context(scene_ctx: SceneContext, tool_context=None) -> None:
    """Persist SceneContext into state (debounced save)."""
    state = _get_state(tool_context)
    state["scene_context"] = scene_ctx.to_dict()
    _set_state(state, tool_context)


# Debounce state saving (D-09)
_save_dirty: bool = False
_save_timer: threading.Timer | None = None
_latest_theme: str = ""
_latest_state_ref: dict = {}
DEBOUNCE_SECONDS = 5


def _sanitize_name(name: str) -> str:
    """Sanitize a name for use as filename."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def _get_drama_folder(theme: str) -> str:
    """Get or create the folder path for a drama based on its theme."""
    folder_name = _sanitize_name(theme)
    folder_path = os.path.join(DRAMAS_DIR, folder_name)
    return folder_path


def _ensure_drama_dirs(theme: str) -> dict:
    """Ensure all necessary directories exist for a drama.

    Creates the following structure:
    dramas/<sanitized_theme>/
    ├── state.json              # Main drama state
    ├── actors/                # Actor-specific data
    ├── scenes/                 # Individual scene files
    ├── conversations/          # Conversation logs
    └── exports/                # Exported scripts

    Returns:
        dict with paths to each directory.
    """
    folder = _get_drama_folder(theme)
    dirs = {
        "root": folder,
        "actors": os.path.join(folder, "actors"),
        "scenes": os.path.join(folder, "scenes"),
        "conversations": os.path.join(folder, "conversations"),
        "exports": os.path.join(folder, "exports"),
    }
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    return dirs


def _get_state_file(theme: str) -> str:
    """Get the path to the state file for a drama."""
    return os.path.join(_get_drama_folder(theme), "state.json")


def _load_state_from_file(theme: str) -> dict:
    """Load drama state from disk."""
    state_file = _get_state_file(theme)
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_state_to_file(theme: str, state: dict):
    """Save drama state to disk."""
    _ensure_drama_dirs(theme)
    state_file = _get_state_file(theme)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _flush_state():
    """Internal: called by debounce timer to flush pending state to disk."""
    global _save_dirty, _save_timer
    if _save_dirty:
        _save_state_to_file(_latest_theme, _latest_state_ref)
        _save_dirty = False
    _save_timer = None


def flush_state_sync():
    """Force-write any pending debounced state to disk immediately.

    Call this before program exit or when an explicit save is needed.
    Cancels any pending debounce timer and writes immediately.
    """
    global _save_dirty, _save_timer
    if _save_timer is not None:
        _save_timer.cancel()
        _save_timer = None
    if _save_dirty:
        _save_state_to_file(_latest_theme, _latest_state_ref)
        _save_dirty = False


def _get_conversations_dir(theme: str) -> str:
    """Get the conversations directory for a drama. [DEPRECATED: kept for backward compatibility only]"""
    return os.path.join(_get_drama_folder(theme), "conversations")


def _save_conversations(theme: str):
    """Save conversation log to disk. [DEPRECATED: conversation_log now lives in state, saved via debounce]"""
    pass


def add_conversation(
    speaker: str,
    content: str,
    conversation_type: str = "dialogue",
    tool_context=None,
) -> dict:
    """Add a conversation entry to the log.

    Args:
        speaker: Name of the speaker (director or actor name).
        content: The conversation/dialogue content.
        conversation_type: Type of conversation (dialogue, narration, action, system).
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    theme = state.get("theme", "")
    current_scene = state.get("current_scene", 0)

    entry = {
        "speaker": speaker,
        "content": content,
        "type": conversation_type,
        "scene": current_scene,
        "timestamp": datetime.now().isoformat(),
    }

    state.setdefault("conversation_log", []).append(entry)

    # Trigger debounced save instead of immediate _save_conversations
    _set_state(state, tool_context)

    return {"status": "success", "entry": entry}


def add_dialogue(
    actor_name: str,
    dialogue: str,
    tool_context=None,
) -> dict:
    """Add an actor's dialogue to the conversation log.

    Args:
        actor_name: Name of the actor speaking.
        dialogue: The dialogue content.
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    return add_conversation(
        speaker=actor_name,
        content=dialogue,
        conversation_type="dialogue",
        tool_context=tool_context,
    )


def add_action(
    actor_name: str,
    action: str,
    tool_context=None,
) -> dict:
    """Add an action/description to the conversation log.

    Args:
        actor_name: Name of the actor performing the action.
        action: Description of the action.
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    return add_conversation(
        speaker=actor_name,
        content=action,
        conversation_type="action",
        tool_context=tool_context,
    )


def add_system_message(
    content: str,
    tool_context=None,
) -> dict:
    """Add a system message to the conversation log.

    Args:
        content: System message content.
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    return add_conversation(
        speaker="[系统]",
        content=content,
        conversation_type="system",
        tool_context=tool_context,
    )


def get_conversation_log(scene: int | None = None, tool_context=None) -> dict:
    """Get the conversation log, optionally filtered by scene.

    Args:
        scene: Optional scene number to filter by. If None, returns all.
        tool_context: Tool context for state access.

    Returns:
        dict with conversation entries.
    """
    state = _get_state(tool_context)
    log = state.get("conversation_log", [])

    if scene is not None:
        entries = [e for e in log if e.get("scene") == scene]
    else:
        entries = log.copy()

    return {"status": "success", "entries": entries, "count": len(entries)}


def export_conversations(format: str = "markdown", tool_context=None) -> dict:
    """Export conversation log to a formatted file.

    Args:
        format: Export format ("markdown", "json", "txt").
        tool_context: Tool context for state access.

    Returns:
        dict with export status and file path.
    """
    state = _get_state(tool_context)
    theme = state.get("theme", "")
    if not theme:
        return {"status": "error", "message": "No active drama."}

    log = state.get("conversation_log", [])

    if not log:
        return {"status": "info", "message": "No conversations to export."}

    conv_dir = _get_conversations_dir(theme)
    os.makedirs(conv_dir, exist_ok=True)

    if format == "markdown":
        filepath = os.path.join(conv_dir, "conversation_log.md")
        lines = [
            f"# 对话记录: {theme}",
            "",
            f"> 导出时间: {datetime.now().isoformat()}",
            "",
        ]

        current_scene = -1
        for entry in log:
            scene = entry.get("scene", 0)
            if scene != current_scene:
                current_scene = scene
                lines.append(f"## 第{scene}场" if scene > 0 else "## 序幕")
                lines.append("")

            speaker = entry.get("speaker", "Unknown")
            content = entry.get("content", "")
            entry_type = entry.get("type", "dialogue")

            if entry_type == "action":
                lines.append(f"**{speaker}**: *（{content}）*")
            elif entry_type == "system":
                lines.append(f"*{content}*")
            else:
                lines.append(f"**{speaker}**: {content}")
            lines.append("")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    elif format == "json":
        filepath = os.path.join(conv_dir, "conversation_log.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    else:  # txt
        filepath = os.path.join(conv_dir, "conversation_log.txt")
        lines = []
        for entry in log:
            speaker = entry.get("speaker", "Unknown")
            content = entry.get("content", "")
            lines.append(f"{speaker}: {content}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    return {
        "status": "success",
        "message": f"Conversations exported to: {filepath}",
        "filepath": filepath,
        "format": format,
        "total_entries": len(log),
    }


def clear_conversation_log(tool_context=None) -> dict:
    """Clear the conversation log in state.

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    state["conversation_log"] = []
    _set_state(state, tool_context)
    return {"status": "success", "message": "Conversation log cleared."}


def _get_current_theme(tool_context=None) -> str:
    """Get the current drama theme. tool_context is required (D-10)."""
    if tool_context is None:
        raise ValueError("tool_context is required — _current_drama_folder global removed (STATE-01)")
    return tool_context.state.get("drama", {}).get("theme", "")


def init_drama_state(theme: str, tool_context=None) -> dict:
    """Initialize a new drama with the given theme.

    Creates a dedicated folder for this drama with proper structure.

    Args:
        theme: The theme/premise of the drama.

    Returns:
        dict with initialization status.
    """
    # Create drama-specific directories
    dirs = _ensure_drama_dirs(theme)

    state = _get_state(tool_context)
    state["theme"] = theme
    state["status"] = "setup"
    state["current_scene"] = 0
    state["scenes"] = []
    state["actors"] = {}
    state["narration_log"] = []
    # Phase 5: Mixed Autonomy Mode fields (D-21/D-22/D-23)
    state["remaining_auto_scenes"] = 0
    state["steer_direction"] = None
    state["storm"] = {"last_review": {}}
    # Phase 6: Tension & Conflict Engine fields (D-16/D-17)
    state["conflict_engine"] = {
        "tension_score": 0,
        "is_boring": False,
        "tension_history": [],
        "active_conflicts": [],
        "used_conflict_types": [],
        "last_inject_scene": 0,
        "consecutive_low_tension": 0,
        "resolved_conflicts": [],  # Phase 7 (D-22)
    }
    # Phase 7: Arc Tracking fields (D-34)
    state["plot_threads"] = []
    # Phase 8: Dynamic STORM fields (D-27/D-28)
    state["dynamic_storm"] = {
        "scenes_since_last_storm": 0,
        "trigger_history": [],
        "discovered_perspectives": [],
    }
    # Phase 10: Coherence System fields (D-31/D-32/D-33)
    state["established_facts"] = []
    state["coherence_checks"] = {
        "last_check_scene": 0,
        "last_result": None,
        "check_history": [],
        "total_contradictions": 0,
    }
    # Phase 11: Timeline Tracking fields (D-26/D-27)
    state["timeline"] = {
        "current_time": "第一天",  # D-04: initial value
        "days_elapsed": 1,  # D-04: start at day 1
        "current_period": None,  # D-26: no period initially
        "time_periods": [],  # D-26: empty list
        "last_jump_check": None,  # D-26: no check yet
    }
    state["created_at"] = datetime.now().isoformat()
    state["updated_at"] = datetime.now().isoformat()
    # Phase 12: conversation_log initialization (D-06)
    state["conversation_log"] = []
    # SceneContext: shared cognitive state for coreference resolution
    state["scene_context"] = {}

    _set_state(state, tool_context)
    _save_state_to_file(theme, state)

    return {
        "status": "success",
        "message": f"Drama initialized with theme: {theme}",
        "drama_folder": dirs["root"],
    }


def save_progress(save_name: str = "", tool_context=None) -> dict:
    """Save the current drama progress to its drama folder.

    The save is stored in the drama's dedicated folder as state.json.
    Optional named snapshots can also be created.

    Args:
        save_name: Optional name for a named save snapshot.
                   If empty, just updates the main state.json.

    Returns:
        dict with save status and filename.
    """
    state = _get_state(tool_context)
    theme = state.get("theme")
    if not theme:
        return {"status": "error", "message": "No active drama to save."}

    # Ensure directories exist
    dirs = _ensure_drama_dirs(theme)

    # Always save main state
    state["updated_at"] = datetime.now().isoformat()
    flush_state_sync()
    _save_state_to_file(theme, state)

    # Create named snapshot if requested
    snapshot_path = None
    if save_name:
        snapshot_path = os.path.join(
            dirs["root"], f"snapshot_{_sanitize_name(save_name)}.json"
        )
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        message = f"Snapshot '{save_name}' saved"
    else:
        message = "Progress auto-saved"

    return {
        "status": "success",
        "message": message,
        "drama_folder": dirs["root"],
        "state_file": _get_state_file(theme),
        "snapshot_path": snapshot_path,
    }


def _migrate_legacy_status(state: dict) -> dict:
    """Migrate old STORM status values to new DramaRouter status (D-14).

    Old statuses: "", "brainstorming", "storm_discovering",
                  "storm_researching", "storm_outlining", "acting"
    New statuses: "setup", "acting"

    Rule: actors exist → "acting", otherwise → "setup"

    Args:
        state: The drama state dict (mutated in-place).

    Returns:
        The same state dict with migrated status.
    """
    # Preserve "ended" status from Phase 5+ saves
    if state.get("status") == "ended":
        return state

    actors = state.get("actors", {})
    if actors and len(actors) > 0:
        state["status"] = "acting"
    else:
        state["status"] = "setup"
    return state


def load_progress(save_name: str, tool_context=None) -> dict:
    """Load a previously saved drama.

    Can load by theme name (searches dramas folder) or by snapshot name.

    Args:
        save_name: The theme name or snapshot name of the drama to load.

    Returns:
        dict with load status and drama info.
    """
    # First try loading as a theme (main state.json in drama folder)
    theme = save_name
    state_file = _get_state_file(theme)

    if not os.path.exists(state_file):
        # Try to find a snapshot with that name
        folder = _get_drama_folder(theme)
        snapshot_file = os.path.join(
            folder, f"snapshot_{_sanitize_name(save_name)}.json"
        )
        if os.path.exists(snapshot_file):
            state_file = snapshot_file
        else:
            # List available dramas
            if os.path.exists(DRAMAS_DIR):
                dramas = [
                    d
                    for d in os.listdir(DRAMAS_DIR)
                    if os.path.isdir(os.path.join(DRAMAS_DIR, d))
                ]
                if dramas:
                    return {
                        "status": "error",
                        "message": f"Drama '{save_name}' not found. Available dramas: {', '.join(dramas)}",
                    }
            return {"status": "error", "message": f"Drama '{save_name}' not found."}

    with open(state_file, "r", encoding="utf-8") as f:
        save_data = json.load(f)

    state = _get_state(tool_context)
    state.update(save_data)
    state["updated_at"] = datetime.now().isoformat()

    # Phase 12: Backward compatibility — migrate old conversation_log.json (D-06)
    if "conversation_log" not in state:
        conv_file = os.path.join(_get_conversations_dir(theme), "conversation_log.json")
        if os.path.exists(conv_file):
            with open(conv_file, "r", encoding="utf-8") as f:
                state["conversation_log"] = json.load(f)
        else:
            state["conversation_log"] = []

    # D-11: Auto-migrate old format actor.memory → new 3-tier structure
    for actor_name, actor_data in state.get("actors", {}).items():
        if "working_memory" not in actor_data:
            from .memory_manager import migrate_legacy_memory

            migrate_legacy_memory(actor_name, tool_context)

    # D-14: Auto-migrate old STORM status to DramaRouter status
    _migrate_legacy_status(state)

    # Phase 5: Ensure new fields exist for backward compatibility (D-28)
    state.setdefault("remaining_auto_scenes", 0)
    state.setdefault("steer_direction", None)
    state.setdefault("storm", {"last_review": {}})
    # Also ensure storm sub-dict has last_review key (D-22)
    if "storm" in state and "last_review" not in state["storm"]:
        state["storm"]["last_review"] = {}

    # Phase 6: Ensure conflict_engine exists for backward compatibility (D-18)
    state.setdefault(
        "conflict_engine",
        {
            "tension_score": 0,
            "is_boring": False,
            "tension_history": [],
            "active_conflicts": [],
            "used_conflict_types": [],
            "last_inject_scene": 0,
            "consecutive_low_tension": 0,
        },
    )

    # Phase 7: Arc Tracking backward compatibility (D-35/D-36/D-37)
    state.setdefault("plot_threads", [])
    # Ensure arc_progress exists for each actor
    _default_arc_progress = {
        "arc_type": "",
        "arc_stage": "",
        "progress": 0,
        "related_threads": [],
    }
    for actor_name, actor_data in state.get("actors", {}).items():
        actor_data.setdefault("arc_progress", _default_arc_progress.copy())
    # Ensure resolved_conflicts exists in conflict_engine
    if "conflict_engine" in state:
        state["conflict_engine"].setdefault("resolved_conflicts", [])
    # Phase 8: Dynamic STORM backward compatibility (D-29)
    state.setdefault(
        "dynamic_storm",
        {
            "scenes_since_last_storm": 0,
            "trigger_history": [],
            "discovered_perspectives": [],
        },
    )
    # Phase 10: Coherence System backward compatibility (D-34)
    state.setdefault("established_facts", [])
    state.setdefault(
        "coherence_checks",
        {
            "last_check_scene": 0,
            "last_result": None,
            "check_history": [],
            "total_contradictions": 0,
        },
    )
    # Phase 11: Timeline Tracking backward compatibility (D-28)
    state.setdefault(
        "timeline",
        {
            "current_time": "第一天",
            "days_elapsed": 1,
            "current_period": None,
            "time_periods": [],
            "last_jump_check": None,
        },
    )
    # SceneContext backward compatibility
    state.setdefault("scene_context", {})

    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": f"Loaded drama: {save_data.get('theme', 'Unknown')}",
        "theme": state.get("theme", ""),
        "drama_status": state.get("status", ""),
        "current_scene": state.get("current_scene", 0),
        "num_actors": len(state.get("actors", {})),
        "num_scenes": len(state.get("scenes", [])),
        "actors_list": list(state.get("actors", {}).keys()),
        "drama_folder": os.path.dirname(state_file),
    }


def list_dramas() -> dict:
    """List all available dramas.

    Returns:
        dict with list of dramas and their info.
    """
    dramas = []
    os.makedirs(DRAMAS_DIR, exist_ok=True)

    for folder in sorted(os.listdir(DRAMAS_DIR)):
        folder_path = os.path.join(DRAMAS_DIR, folder)
        if not os.path.isdir(folder_path):
            continue

        state_file = os.path.join(folder_path, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                dramas.append(
                    {
                        "folder": folder,
                        "theme": data.get("theme", folder),
                        "status": data.get("status", "unknown"),
                        "updated_at": data.get("updated_at", "Unknown"),
                        "current_scene": data.get("current_scene", 0),
                    }
                )
            except (json.JSONDecodeError, OSError):
                dramas.append(
                    {"folder": folder, "theme": "Corrupted", "status": "error"}
                )
        else:
            # Check for snapshots
            snapshots = [
                f for f in os.listdir(folder_path) if f.startswith("snapshot_")
            ]
            if snapshots:
                dramas.append(
                    {
                        "folder": folder,
                        "theme": folder,
                        "status": "snapshot_only",
                        "snapshots": snapshots,
                    }
                )

    return {"status": "success", "dramas": dramas}


def delete_drama(folder: str) -> dict:
    """Delete a drama folder by name.

    Args:
        folder: The drama folder name to delete.

    Returns:
        dict with status and message.
    """
    folder_path = os.path.join(DRAMAS_DIR, folder)
    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)
        return {"status": "success", "message": f"Deleted drama: {folder}"}
    return {"status": "error", "message": f"Drama not found: {folder}"}


# Backward compatibility alias
def list_saves() -> dict:
    """List all available save files (backward compatibility)."""
    return list_dramas()


def update_script(
    scene_number: int,
    scene_title: str,
    scene_description: str,
    content: str,
    tool_context=None,
) -> dict:
    """Update or add a scene to the script.

    Args:
        scene_number: The scene number (1-based).
        scene_title: Title of the scene.
        scene_description: Description/stage direction for the scene.
        content: The dialogue and narration content for this scene.

    Returns:
        dict with update status.
    """
    state = _get_state(tool_context)
    scenes = state.get("scenes", [])

    scene_data = {
        "scene_number": scene_number,
        "title": scene_title,
        "description": scene_description,
        "content": content,
        "updated_at": datetime.now().isoformat(),
    }

    # Update existing scene or add new one
    found = False
    for i, s in enumerate(scenes):
        if s.get("scene_number") == scene_number:
            scenes[i] = scene_data
            found = True
            break
    if not found:
        scenes.append(scene_data)
        scenes.sort(key=lambda x: x.get("scene_number", 0))

    state["scenes"] = scenes
    state["updated_at"] = datetime.now().isoformat()
    _set_state(state, tool_context)
    return {
        "status": "success",
        "message": f"Scene {scene_number} updated: {scene_title}",
        "content": content,
    }


def add_narration(narration_text: str, tool_context=None) -> dict:
    """Add director narration to the log.

    Args:
        narration_text: The narration text to add.

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    narration_log = state.get("narration_log", [])
    narration_log.append(
        {
            "text": narration_text,
            "timestamp": datetime.now().isoformat(),
        }
    )
    state["narration_log"] = narration_log
    _set_state(state, tool_context)
    return {"status": "success", "message": "Narration added."}


def register_actor(
    actor_name: str,
    role: str,
    personality: str,
    background: str,
    knowledge_scope: str,
    tool_context=None,
    port: int | None = None,
) -> dict:
    """Register a new actor in the drama.

    Args:
        actor_name: The name of the actor/character.
        role: The role of this character in the drama.
        personality: Personality traits and speaking style.
        background: Character's backstory.
        knowledge_scope: What this character knows (defines cognitive boundary).
        port: The A2A service port assigned to this actor (persisted for reload).

    Returns:
        dict with registration status.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if len(actors) >= 10:
        return {"status": "error", "message": "Maximum number of actors (10) reached."}

    actor_data = {
        "role": role,
        "personality": personality,
        "background": background,
        "knowledge_scope": knowledge_scope,
        "memory": [],  # D-13: 保留旧字段（只读）
        "working_memory": [],  # D-12: Tier 1 — 工作记忆
        "scene_summaries": [],  # D-12: Tier 2 — 场景摘要
        "arc_summary": {  # D-12: Tier 3 — 全局摘要
            "structured": {
                "theme": "",
                "key_characters": [],
                "unresolved": [],
                "resolved": [],
            },
            "narrative": "",
        },
        "critical_memories": [],  # D-07: 关键记忆（独立存储）
        "emotions": "neutral",
        "arc_progress": {  # Phase 7 (D-05/D-08)
            "arc_type": "",
            "arc_stage": "",
            "progress": 0,
            "related_threads": [],
        },
        "created_at": datetime.now().isoformat(),
    }
    if port is not None:
        actor_data["port"] = port

    actors[actor_name] = actor_data

    state["actors"] = actors
    _set_state(state, tool_context)
    return {
        "status": "success",
        "message": f"Actor '{actor_name}' registered as {role}.",
    }


def update_actor_memory(actor_name: str, memory_entry: str, tool_context=None) -> dict:
    """Add a memory entry for an actor. [DEPRECATED: use memory_manager.add_working_memory()]

    保留向后兼容。内部委托给新的记忆管理系统。
    自动检测重要性，关键记忆会被标记。

    Args:
        actor_name: The name of the actor.
        memory_entry: What the actor experienced or learned.

    Returns:
        dict with status.
    """
    from .memory_manager import add_working_memory, detect_importance

    # Auto-detect importance
    is_critical, reason = detect_importance(memory_entry)
    importance = "critical" if is_critical else "normal"

    return add_working_memory(
        actor_name=actor_name,
        entry=memory_entry,
        importance=importance,
        critical_reason=reason,
        tool_context=tool_context,
    )


def update_actor_emotion(actor_name: str, emotion: str, tool_context=None) -> dict:
    """Update an actor's current emotional state.

    Args:
        actor_name: The name of the actor.
        emotion: The new emotional state.

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"Actor '{actor_name}' not found."}

    actors[actor_name]["emotions"] = emotion
    state["actors"] = actors
    _set_state(state, tool_context)
    return {
        "status": "success",
        "message": f"Emotion updated for '{actor_name}': {emotion}",
    }


def get_actor_info(actor_name: str, tool_context=None) -> dict:
    """Get full information about an actor including memories.

    Args:
        actor_name: The name of the actor.

    Returns:
        dict with actor information.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"Actor '{actor_name}' not found."}

    return {"status": "success", "actor": actors[actor_name]}


def get_all_actors(tool_context=None) -> dict:
    """Get a summary of all actors.

    Returns:
        dict with all actors' info.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    summary = {}
    for name, info in actors.items():
        summary[name] = {
            "role": info.get("role", ""),
            "personality": info.get("personality", ""),
            "background": info.get("background", ""),
            "emotions": info.get("emotions", "neutral"),
            "memory_count": len(info.get("memory", [])),  # D-13: 旧字段保留
            "working_memory_count": len(info.get("working_memory", [])),
            "scene_summaries_count": len(info.get("scene_summaries", [])),
            "critical_memories_count": len(info.get("critical_memories", [])),
            "has_arc_summary": bool(info.get("arc_summary", {}).get("narrative", "")),
        }

    return {"status": "success", "actors": summary}


def get_current_state(tool_context=None) -> dict:
    """Get the current drama state summary.

    Returns:
        dict with current state info.
    """
    state = _get_state(tool_context)
    theme = state.get("theme", "")
    actors = state.get("actors", {})

    # D-07: arc_progress from actor state
    arc_progress = []
    for name, info in actors.items():
        arc = info.get("arc_progress", {})
        arc_progress.append({"name": name, "progress": arc.get("progress", 0)})

    # D-07: time_period from timeline
    timeline = state.get("timeline", {})
    time_period = ""
    if timeline.get("time_periods"):
        time_period = timeline["time_periods"][-1].get("description", "")

    return {
        "status": "success",
        "theme": theme,
        "drama_status": state.get("status", ""),
        "current_scene": state.get("current_scene", 0),
        "num_scenes": len(state.get("scenes", [])),
        "num_actors": len(actors),
        "actors": list(actors.keys()),
        "drama_folder": _get_drama_folder(theme) if theme else "",
        "arc_progress": arc_progress,
        "time_period": time_period,
    }


def get_drama_folder(tool_context=None) -> dict:
    """Get the folder path for the current drama.

    Returns:
        dict with the drama folder path.
    """
    state = _get_state(tool_context)
    theme = state.get("theme", "")
    if not theme:
        return {"status": "error", "message": "No active drama."}

    dirs = _ensure_drama_dirs(theme)
    return {
        "status": "success",
        "theme": theme,
        "folder": dirs["root"],
        "actors_dir": dirs["actors"],
        "scenes_dir": dirs["scenes"],
        "exports_dir": dirs["exports"],
    }


def advance_scene(tool_context=None) -> dict:
    """Advance to the next scene.

    Returns:
        dict with the new scene number.
    """
    state = _get_state(tool_context)
    state["current_scene"] = state.get("current_scene", 0) + 1
    # Phase 8: Increment dynamic_storm counter (D-08/D-30)
    ds = state.setdefault("dynamic_storm", {})
    ds["scenes_since_last_storm"] = ds.get("scenes_since_last_storm", 0) + 1
    # Preserve "ended" status (epilogue mode) — only set "acting" if not ended
    if state.get("status") != "ended":
        state["status"] = "acting"
    state["updated_at"] = datetime.now().isoformat()
    _set_state(state, tool_context)
    return {
        "status": "success",
        "current_scene": state["current_scene"],
        "message": f"Advanced to scene {state['current_scene']}",
    }


def set_drama_status(new_status: str, tool_context=None) -> dict:
    """Update the drama's overall status.

    Args:
        new_status: New status (setup, acting, completed, paused).

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    state["status"] = new_status
    state["updated_at"] = datetime.now().isoformat()
    _set_state(state, tool_context)
    return {"status": "success", "message": f"Drama status set to: {new_status}"}


def export_script(tool_context=None) -> dict:
    """Export the complete script as a Markdown document.

    Exports to the drama's exports folder.

    Returns:
        dict with export status and file path.
    """
    state = _get_state(tool_context)

    if not state.get("theme"):
        return {"status": "error", "message": "No active drama to export."}

    theme = state.get("theme", "Untitled")
    dirs = _ensure_drama_dirs(theme)
    filename = _sanitize_name(theme) + ".md"
    filepath = os.path.join(dirs["exports"], filename)

    lines = []
    # Title
    lines.append(f"# {theme}")
    lines.append("")
    lines.append(f"> 剧本创建时间: {state.get('created_at', 'Unknown')}")
    lines.append(f"> 最后更新时间: {state.get('updated_at', 'Unknown')}")
    lines.append("")

    # Cast
    actors = state.get("actors", {})
    if actors:
        lines.append("## 演员表")
        lines.append("")
        lines.append("| 角色 | 身份 | 性格特征 | 当前情绪 |")
        lines.append("|------|------|----------|----------|")
        for name, info in actors.items():
            lines.append(
                f"| {name} | {info.get('role', '')} | "
                f"{info.get('personality', '')} | {info.get('emotions', 'neutral')} |"
            )
        lines.append("")

    # STORM Outline
    storm_data = state.get("storm", {})
    outline = storm_data.get("outline", {})
    if outline:
        lines.append("## STORM 大纲")
        lines.append("")
        lines.append(f"**合成策略**: {outline.get('synthesis_strategy', 'N/A')}")
        lines.append("")
        for act in outline.get("acts", []):
            lines.append(
                f"### 第{act.get('act_number', 0)}幕: {act.get('title', 'Untitled')}"
            )
            lines.append("")
            lines.append(f"{act.get('description', '')}")
            lines.append(f"- 核心冲突: {act.get('key_conflict', 'N/A')}")
            lines.append(f"- 情感曲线: {act.get('emotional_arc', 'N/A')}")
            lines.append("")
        thematic_layers = outline.get("thematic_layers", {})
        if thematic_layers:
            lines.append("**主题层次**:")
            for layer, desc in thematic_layers.items():
                lines.append(f"- {layer}: {desc}")
            lines.append("")

    # Scenes
    scenes = state.get("scenes", [])
    for scene in scenes:
        lines.append(
            f"## 第{scene.get('scene_number', 0)}场: {scene.get('title', 'Untitled')}"
        )
        lines.append("")
        desc = scene.get("description", "")
        if desc:
            lines.append(f"*{desc}*")
            lines.append("")
        content = scene.get("content", "")
        if content:
            lines.append(content)
            lines.append("")

    # Narration log
    narration_log = state.get("narration_log", [])
    if narration_log:
        lines.append("## 旁白记录")
        lines.append("")
        for entry in narration_log:
            lines.append(f"> {entry.get('text', '')}")
            lines.append("")

    markdown = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)

    return {
        "status": "success",
        "message": f"Script exported to: {filepath}",
        "filepath": filepath,
        "drama_folder": dirs["root"],
        "total_scenes": len(scenes),
        "total_actors": len(actors),
    }


def _get_state(tool_context) -> dict:
    """Get drama state from tool context or return empty dict."""
    if tool_context is not None:
        return tool_context.state.get("drama", {})
    return {}


def _set_state(state: dict, tool_context):
    """Set drama state in tool context with debounced disk persistence.

    State is written to tool_context immediately but only persisted to
    disk after DEBOUNCE_SECONDS. Use flush_state_sync() to force immediate
    write (e.g. before program exit).
    """
    global _save_dirty, _save_timer, _latest_theme, _latest_state_ref
    if tool_context is not None:
        tool_context.state["drama"] = state
        theme = state.get("theme", "")
        if theme:
            _latest_theme = theme
            _latest_state_ref = state
            _save_dirty = True
            # Cancel existing timer if any
            if _save_timer is not None:
                _save_timer.cancel()
            # Create new debounced timer
            _save_timer = threading.Timer(DEBOUNCE_SECONDS, _flush_state)
            _save_timer.daemon = True
            _save_timer.start()


# ============================================================================
# STORM Framework State Management
# ============================================================================


def storm_add_perspective(
    perspective_name: str,
    description: str,
    questions: list,
    tool_context=None,
) -> dict:
    """Add a perspective to the STORM discovery results.

    Args:
        perspective_name: Name of the perspective (e.g., "主角视角").
        description: Description of what this perspective explores.
        questions: List of guiding questions for this perspective.

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    storm_data = state.get("storm", {})
    perspectives = storm_data.get("perspectives", [])

    perspectives.append(
        {
            "name": perspective_name,
            "description": description,
            "questions": questions,
        }
    )

    storm_data["perspectives"] = perspectives
    state["storm"] = storm_data
    _set_state(state, tool_context)

    return {"status": "success", "message": f"Perspective '{perspective_name}' added."}


def storm_get_perspectives(tool_context=None) -> dict:
    """Get all STORM perspectives.

    Returns:
        dict with perspectives list.
    """
    state = _get_state(tool_context)
    storm_data = state.get("storm", {})
    perspectives = storm_data.get("perspectives", [])

    return {"status": "success", "perspectives": perspectives}


def storm_add_research_result(
    perspective_name: str,
    questions: list,
    findings: dict,
    tool_context=None,
) -> dict:
    """Add a research result for a perspective.

    Args:
        perspective_name: Name of the researched perspective.
        questions: Questions that were explored.
        findings: Research findings dict.

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    storm_data = state.get("storm", {})
    results = storm_data.get("research_results", [])

    results.append(
        {
            "perspective": perspective_name,
            "questions": questions,
            "findings": findings,
            "timestamp": datetime.now().isoformat(),
        }
    )

    storm_data["research_results"] = results
    state["storm"] = storm_data
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": f"Research result for '{perspective_name}' added.",
    }


def storm_get_research_results(tool_context=None) -> dict:
    """Get all STORM research results.

    Returns:
        dict with research results list.
    """
    state = _get_state(tool_context)
    storm_data = state.get("storm", {})
    results = storm_data.get("research_results", [])

    return {"status": "success", "results": results}


def storm_set_outline(outline: dict, tool_context=None) -> dict:
    """Set the STORM synthesized outline.

    Args:
        outline: The complete drama outline dict.

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    storm_data = state.get("storm", {})
    storm_data["outline"] = outline
    state["storm"] = storm_data
    _set_state(state, tool_context)

    return {"status": "success", "message": "STORM outline saved."}


def storm_get_outline(tool_context=None) -> dict:
    """Get the STORM synthesized outline.

    Returns:
        dict with outline data.
    """
    state = _get_state(tool_context)
    storm_data = state.get("storm", {})
    outline = storm_data.get("outline", {})

    return {"status": "success", "outline": outline}


# Register atexit to flush any pending state on program exit
atexit.register(flush_state_sync)


# ============================================================================
# Scene Archival (D-10)
# ============================================================================


SCENE_ARCHIVE_THRESHOLD = 20


def archive_old_scenes(state: dict) -> dict:
    """Archive scenes beyond threshold to reduce state.json size (D-10).

    When the number of scenes exceeds SCENE_ARCHIVE_THRESHOLD, the oldest
    scenes are written to individual JSON files and replaced in state with
    lightweight index metadata (scene_number, title, time_label, archived=True).

    The most recent SCENE_ARCHIVE_THRESHOLD scenes always remain in full.

    Args:
        state: The drama state dict (mutated in-place).

    Returns:
        The same state dict with archived scenes replaced by index metadata.
    """
    scenes = state.get("scenes", [])
    if len(scenes) <= SCENE_ARCHIVE_THRESHOLD:
        return state

    to_archive = scenes[:-SCENE_ARCHIVE_THRESHOLD]
    keep = scenes[-SCENE_ARCHIVE_THRESHOLD:]

    theme = state.get("theme", "")
    if theme:
        drama_folder = _get_drama_folder(theme)
        scenes_dir = os.path.join(drama_folder, "scenes")
        os.makedirs(scenes_dir, exist_ok=True)
        for scene in to_archive:
            scene_num = scene.get("scene_number", 0)
            archive_path = os.path.join(scenes_dir, f"scene_{scene_num:04d}.json")
            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump(scene, f, ensure_ascii=False, indent=2)

    # Replace archived scenes with index metadata only
    archived_indices = [
        {
            "scene_number": s.get("scene_number"),
            "title": s.get("title", ""),
            "time_label": s.get("time_label", ""),
            "archived": True,
        }
        for s in to_archive
    ]
    state["scenes"] = archived_indices + keep
    return state


def load_archived_scene(theme: str, scene_num: int) -> dict | None:
    """Load a single archived scene from disk.

    Args:
        theme: The drama theme (used to locate the drama folder).
        scene_num: The scene number to load.

    Returns:
        The full scene dict if found, None otherwise.
    """
    archive_path = os.path.join(
        _get_drama_folder(theme), "scenes", f"scene_{scene_num:04d}.json"
    )
    if os.path.exists(archive_path):
        with open(archive_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_scene_summaries(tool_context) -> dict:
    """Get summary list of all scenes for the current drama.

    Iterates scene 1~num_scenes, loading archived scenes from disk when
    the in-memory scene data is a lightweight index (archived=True).

    Returns:
        dict with "scenes" (list of summary dicts) and "total" (int).
    """
    state = _get_state(tool_context)
    theme = state.get("theme", "")
    scenes_list = state.get("scenes", [])
    num_scenes = len(scenes_list)

    summaries = []
    for i in range(num_scenes):
        scene = scenes_list[i]
        scene_num = scene.get("scene_number", i + 1)

        if scene.get("archived"):
            # Load from disk
            full_scene = load_archived_scene(theme, scene_num)
            if full_scene is None:
                continue
            title = full_scene.get("title", "")
            narration = full_scene.get("narration", "") or full_scene.get("content", "")
            description = narration[:50] if narration else ""
        else:
            title = scene.get("title", "")
            narration = scene.get("narration", "") or scene.get("description", "") or scene.get("content", "")
            description = narration[:50] if narration else ""

        summaries.append({
            "scene_number": scene_num,
            "title": title,
            "description": description,
        })

    return {"scenes": summaries, "total": len(summaries)}


def get_scene_detail(theme: str, scene_num: int) -> dict:
    """Get the full detail of a single scene.

    First checks the in-memory scenes list, then falls back to archived
    scene files on disk.

    Args:
        theme: The drama theme.
        scene_num: The 1-based scene number.

    Returns:
        dict with scene data, or {"status": "error", "message": ...} if not found.
    """
    # Try to find in the current state's scenes list
    # (we need to load the state from file since we don't have tool_context here)
    state = _load_state_from_file(theme)
    scenes_list = state.get("scenes", [])

    for scene in scenes_list:
        if scene.get("scene_number") == scene_num:
            if scene.get("archived"):
                # Load from disk
                full_scene = load_archived_scene(theme, scene_num)
                if full_scene is not None:
                    return full_scene
                return {"status": "error", "message": f"Scene {scene_num} not found"}
            return scene

    # If not found in state (maybe all archived), try disk
    full_scene = load_archived_scene(theme, scene_num)
    if full_scene is not None:
        return full_scene

    return {"status": "error", "message": f"Scene {scene_num} not found"}
