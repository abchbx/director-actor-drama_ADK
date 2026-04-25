"""Vector memory store using ChromaDB for long-term semantic recall.

借鉴 MemPalace 架构设计：
- 每个演员拥有独立 collection（类似 MemPalace 的 wing 概念）
- 原文存储（verbatim storage），不做摘要或改写
- 语义搜索检索相关历史记忆
- 持久化到磁盘，随戏剧进度保存/恢复

Architecture:
    Tier 4 (长期记忆): ChromaDB 向量存储
    - store_memory()  → 存入原文 + 元数据
    - search_memory() → 语义搜索返回相关记忆
    - build_context() → 自动检索 + 格式化可注入 LLM 的上下文

与现有三层记忆架构并行工作：
    working_memory (Tier 1) → scene_summaries (Tier 2) → arc_summary (Tier 3)
    vector_memory  (Tier 4) — 独立向量索引，语义检索
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

# Default ChromaDB persist directory (relative to drama folder)
CHROMA_DIR_NAME = "chroma_db"

# Collection name prefix for actor collections
ACTOR_COLLECTION_PREFIX = "actor_"

# Default number of results for search
DEFAULT_SEARCH_RESULTS = 5

# Default number of results for context building
DEFAULT_CONTEXT_RESULTS = 8

# Maximum content length for a single memory entry
VECTOR_MEMORY_MAX_LENGTH = 1000


# ============================================================================
# VectorMemoryStore — ChromaDB-backed vector memory
# ============================================================================


class VectorMemoryStore:
    """ChromaDB-backed vector memory store with per-actor collections.

    借鉴 MemPalace 的 wing/collection 概念，每个演员有独立的 collection，
    确保记忆隔离和高效检索。ChromaDB 默认使用 all-MiniLM-L6-v2 嵌入模型，
    支持中英文文本的语义搜索。

    Usage:
        store = VectorMemoryStore(persist_dir="/path/to/drama/chroma_db")
        store.store_memory("苏念瑶", "李明今天向我表白了", {"scene": 3, "importance": "critical"})
        results = store.search_memory("苏念瑶", "表白", n_results=5)
        context = store.build_context("苏念瑶", current_scene=5)
    """

    def __init__(self, persist_dir: str):
        """Initialize the vector memory store.

        Args:
            persist_dir: Directory path for ChromaDB persistence.
                         Created automatically if not exists.
        """
        self.persist_dir = persist_dir
        self._client = None
        self._collections: dict[str, object] = {}

    def _get_client(self):
        """Lazy-initialize ChromaDB client."""
        if self._client is not None:
            return self._client

        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for vector memory. "
                "Install with: pip install chromadb"
            )

        os.makedirs(self.persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self.persist_dir)
        return self._client

    def _get_collection(self, actor_name: str):
        """Get or create a collection for an actor.

        Args:
            actor_name: The actor's name.

        Returns:
            ChromaDB Collection object.
        """
        if actor_name in self._collections:
            return self._collections[actor_name]

        client = self._get_client()
        collection_name = f"{ACTOR_COLLECTION_PREFIX}{_sanitize_collection_name(actor_name)}"

        try:
            collection = client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "actor_name": actor_name,
                },
            )
        except Exception as e:
            logger.error(f"Failed to get/create collection for {actor_name}: {e}")
            raise

        self._collections[actor_name] = collection
        return collection

    def store_memory(
        self,
        actor_name: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict:
        """Store a memory entry for an actor in vector store.

        以原文形式存储记忆，附带元数据（场景号、重要性等）。
        每条记忆有唯一 ID，支持后续更新或删除。

        Args:
            actor_name: The actor's name.
            content: The memory text to store (verbatim).
            metadata: Optional metadata dict. Common fields:
                - scene: int, scene number
                - importance: str, "normal" or "critical"
                - type: str, "dialogue", "action", "event", "fact"
                - timestamp: str, ISO format timestamp

        Returns:
            dict with status and memory_id.
        """
        if not content or not content.strip():
            return {"status": "error", "message": "记忆内容不能为空。"}

        # Truncate content
        content = content.strip()[:VECTOR_MEMORY_MAX_LENGTH]

        # Generate unique ID
        memory_id = str(uuid.uuid4())

        # Build metadata
        meta = {
            "actor_name": actor_name,
            "stored_at": datetime.now().isoformat(),
        }
        if metadata:
            # ChromaDB metadata values must be str, int, float, or bool
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                else:
                    meta[k] = json.dumps(v, ensure_ascii=False)

        try:
            collection = self._get_collection(actor_name)
            collection.add(
                ids=[memory_id],
                documents=[content],
                metadatas=[meta],
            )
        except Exception as e:
            logger.error(f"Failed to store memory for {actor_name}: {e}")
            return {"status": "error", "message": f"向量记忆存储失败: {e}"}

        return {
            "status": "success",
            "message": f"记忆已存入「{actor_name}」的向量库。",
            "memory_id": memory_id,
            "content_preview": content[:80] + "..." if len(content) > 80 else content,
        }

    def store_memory_batch(
        self,
        actor_name: str,
        entries: list[dict],
    ) -> dict:
        """Store multiple memory entries for an actor in batch.

        批量存储记忆，用于初始化或从存档恢复。

        Args:
            actor_name: The actor's name.
            entries: List of dicts, each with "content" and optional "metadata".

        Returns:
            dict with status and count.
        """
        if not entries:
            return {"status": "info", "message": "无记忆需要存储。", "count": 0}

        ids = []
        documents = []
        metadatas = []

        for entry in entries:
            content = entry.get("content", "").strip()[:VECTOR_MEMORY_MAX_LENGTH]
            if not content:
                continue

            memory_id = entry.get("id", str(uuid.uuid4()))
            meta = {
                "actor_name": actor_name,
                "stored_at": entry.get("stored_at", datetime.now().isoformat()),
            }
            metadata = entry.get("metadata", {})
            if metadata:
                for k, v in metadata.items():
                    if isinstance(v, (str, int, float, bool)):
                        meta[k] = v
                    else:
                        meta[k] = json.dumps(v, ensure_ascii=False)

            ids.append(memory_id)
            documents.append(content)
            metadatas.append(meta)

        if not ids:
            return {"status": "info", "message": "无有效记忆需要存储。", "count": 0}

        try:
            collection = self._get_collection(actor_name)
            # Use upsert to handle duplicates on batch restore
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as e:
            logger.error(f"Failed to batch store memories for {actor_name}: {e}")
            return {"status": "error", "message": f"批量存储失败: {e}"}

        return {
            "status": "success",
            "message": f"已批量存储 {len(ids)} 条记忆到「{actor_name}」的向量库。",
            "count": len(ids),
        }

    def search_memory(
        self,
        actor_name: str,
        query: str,
        n_results: int = DEFAULT_SEARCH_RESULTS,
        where: dict | None = None,
    ) -> list[dict]:
        """Search actor's vector memory by semantic similarity.

        基于语义相似度搜索演员的历史记忆。支持元数据过滤。

        Args:
            actor_name: The actor's name.
            query: The search query text.
            n_results: Maximum number of results to return.
            where: Optional ChromaDB where filter for metadata.

        Returns:
            List of memory dicts, each with:
                - id: str, memory ID
                - content: str, original memory text
                - metadata: dict, associated metadata
                - distance: float, semantic distance (lower = more similar)
        """
        if not query or not query.strip():
            return []

        try:
            collection = self._get_collection(actor_name)

            # Check collection size
            count = collection.count()
            if count == 0:
                return []

            # Limit n_results to collection size
            actual_n = min(n_results, count)

            query_params = {
                "query_texts": [query],
                "n_results": actual_n,
            }
            if where:
                query_params["where"] = where

            results = collection.query(**query_params)

        except Exception as e:
            logger.error(f"Failed to search memory for {actor_name}: {e}")
            return []

        # Parse results
        memories = []
        if results and results.get("ids") and results["ids"][0]:
            for i, memory_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i] if results.get("documents") else ""
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                distance = results["distances"][0][i] if results.get("distances") else 0.0

                # Deserialize JSON-stringified metadata values
                parsed_meta = {}
                for k, v in metadata.items():
                    if isinstance(v, str) and v.startswith(("{", "[")):
                        try:
                            parsed_meta[k] = json.loads(v)
                        except (json.JSONDecodeError, ValueError):
                            parsed_meta[k] = v
                    else:
                        parsed_meta[k] = v

                memories.append({
                    "id": memory_id,
                    "content": content,
                    "metadata": parsed_meta,
                    "distance": distance,
                    "relevance": round(1.0 - distance, 3),  # Convert distance to relevance score
                })

        return memories

    def build_context(
        self,
        actor_name: str,
        current_scene: str | int = "",
        n_results: int = DEFAULT_CONTEXT_RESULTS,
        query: str | None = None,
    ) -> str:
        """Build injectable context text from vector memory for LLM prompting.

        自动检索最相关的记忆，格式化为可注入 LLM 的上下文文本。
        如果未提供 query，使用当前场景信息作为查询。

        Args:
            actor_name: The actor's name.
            current_scene: Current scene number or description for query.
            n_results: Maximum number of memory entries to include.
            query: Optional explicit search query. If None, auto-generated
                   from current scene context.

        Returns:
            Formatted context text ready for LLM injection.
            Empty string if no relevant memories found.
        """
        # Build query from context
        if not query:
            query = f"第{current_scene}场" if current_scene else "最近的经历"

        # Search for relevant memories
        memories = self.search_memory(
            actor_name=actor_name,
            query=query,
            n_results=n_results,
        )

        if not memories:
            return ""

        # Format context text
        lines = [f"## 「{actor_name}」的长期记忆（语义检索）"]
        lines.append("")

        for i, mem in enumerate(memories, 1):
            meta = mem.get("metadata", {})
            scene = meta.get("scene", "")
            importance = meta.get("importance", "normal")
            relevance = mem.get("relevance", 0)

            # Scene label
            scene_label = f"[第{scene}场] " if scene else ""

            # Importance marker
            imp_marker = "⭐ " if importance == "critical" else ""

            # Relevance indicator
            rel_label = f"(相关度: {relevance:.0%})" if relevance > 0 else ""

            lines.append(f"{i}. {imp_marker}{scene_label}{mem['content']} {rel_label}")

        lines.append("")
        return "\n".join(lines)

    def get_memory_count(self, actor_name: str) -> int:
        """Get the number of stored memories for an actor.

        Args:
            actor_name: The actor's name.

        Returns:
            Number of memories in the collection.
        """
        try:
            collection = self._get_collection(actor_name)
            return collection.count()
        except Exception:
            return 0

    def delete_memory(self, actor_name: str, memory_id: str) -> dict:
        """Delete a specific memory entry.

        Args:
            actor_name: The actor's name.
            memory_id: The ID of the memory to delete.

        Returns:
            dict with status.
        """
        try:
            collection = self._get_collection(actor_name)
            collection.delete(ids=[memory_id])
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id} for {actor_name}: {e}")
            return {"status": "error", "message": f"删除记忆失败: {e}"}

        return {"status": "success", "message": f"记忆 {memory_id} 已删除。"}

    def clear_actor_memory(self, actor_name: str) -> dict:
        """Clear all memories for an actor.

        Args:
            actor_name: The actor's name.

        Returns:
            dict with status and deleted count.
        """
        try:
            collection = self._get_collection(actor_name)
            count = collection.count()
            if count > 0:
                # Get all IDs and delete
                all_ids = collection.get()["ids"]
                if all_ids:
                    collection.delete(ids=all_ids)
        except Exception as e:
            logger.error(f"Failed to clear memory for {actor_name}: {e}")
            return {"status": "error", "message": f"清空记忆失败: {e}"}

        # Remove from cache
        self._collections.pop(actor_name, None)

        return {
            "status": "success",
            "message": f"已清空「{actor_name}」的向量记忆（{count} 条）。",
            "deleted_count": count,
        }

    def export_actor_memory(self, actor_name: str) -> list[dict]:
        """Export all memories for an actor (for backup/restore).

        导出演员所有记忆，用于备份和恢复。

        Args:
            actor_name: The actor's name.

        Returns:
            List of memory dicts with id, content, metadata.
        """
        try:
            collection = self._get_collection(actor_name)
            count = collection.count()
            if count == 0:
                return []

            # Get all entries
            results = collection.get(include=["documents", "metadatas"])

        except Exception as e:
            logger.error(f"Failed to export memory for {actor_name}: {e}")
            return []

        entries = []
        if results and results.get("ids"):
            for i, memory_id in enumerate(results["ids"]):
                content = results["documents"][i] if results.get("documents") else ""
                metadata = results["metadatas"][i] if results.get("metadatas") else {}

                # Deserialize JSON-stringified metadata values
                parsed_meta = {}
                for k, v in metadata.items():
                    if isinstance(v, str) and v.startswith(("{", "[")):
                        try:
                            parsed_meta[k] = json.loads(v)
                        except (json.JSONDecodeError, ValueError):
                            parsed_meta[k] = v
                    else:
                        parsed_meta[k] = v

                entries.append({
                    "id": memory_id,
                    "content": content,
                    "metadata": parsed_meta,
                })

        return entries

    def import_actor_memory(self, actor_name: str, entries: list[dict]) -> dict:
        """Import memories for an actor (from backup/restore).

        导入演员记忆，用于从备份恢复。

        Args:
            actor_name: The actor's name.
            entries: List of memory dicts with "content" and optional
                     "id", "metadata" fields.

        Returns:
            dict with status and count.
        """
        return self.store_memory_batch(actor_name, entries)

    def list_actors_with_memory(self) -> list[str]:
        """List all actor names that have vector memory collections.

        Returns:
            List of actor names.
        """
        try:
            client = self._get_client()
            collections = client.list_collections()
            actor_names = []
            for coll in collections:
                name = coll.name if hasattr(coll, "name") else str(coll)
                if name.startswith(ACTOR_COLLECTION_PREFIX):
                    # Try to get actor_name from metadata
                    try:
                        meta = coll.metadata if hasattr(coll, "metadata") else {}
                        actor_name = meta.get("actor_name", "")
                        if actor_name:
                            actor_names.append(actor_name)
                        else:
                            # Fallback: extract from collection name
                            actor_names.append(name[len(ACTOR_COLLECTION_PREFIX):])
                    except Exception:
                        actor_names.append(name[len(ACTOR_COLLECTION_PREFIX):])
            return actor_names
        except Exception as e:
            logger.error(f"Failed to list actor collections: {e}")
            return []


# ============================================================================
# Singleton Store Management
# ============================================================================

# Global store instance per drama theme
_stores: dict[str, VectorMemoryStore] = {}


def get_vector_store(theme: str, dramas_dir: str | None = None) -> VectorMemoryStore:
    """Get or create a VectorMemoryStore for a drama.

    Args:
        theme: The drama theme (used as directory key).
        dramas_dir: Optional base dramas directory.

    Returns:
        VectorMemoryStore instance.
    """
    if theme in _stores:
        return _stores[theme]

    if dramas_dir is None:
        dramas_dir = os.path.join(os.path.dirname(__file__), "dramas")

    # Sanitize theme for directory name
    safe_theme = _sanitize_collection_name(theme)
    persist_dir = os.path.join(dramas_dir, safe_theme, CHROMA_DIR_NAME)

    store = VectorMemoryStore(persist_dir=persist_dir)
    _stores[theme] = store
    return store


def get_vector_store_from_context(tool_context) -> Optional[VectorMemoryStore]:
    """Get VectorMemoryStore from tool context.

    Args:
        tool_context: ADK ToolContext with state access.

    Returns:
        VectorMemoryStore instance, or None if no active drama.
    """
    if tool_context is None:
        return None

    state = tool_context.state.get("drama", {})
    theme = state.get("theme", "")
    if not theme:
        return None

    return get_vector_store(theme)


def clear_store_cache():
    """Clear the global store cache (for testing)."""
    _stores.clear()


# ============================================================================
# Helper Functions
# ============================================================================


def _sanitize_collection_name(name: str) -> str:
    """Sanitize a name for use as ChromaDB collection name.

    ChromaDB collection names must:
    - Be 3-63 characters long
    - Start and end with an alphanumeric character
    - Contain only alphanumeric characters, underscores, and hyphens
    - Not contain two consecutive periods

    Chinese characters and other non-ASCII chars are encoded to
    hex representation to ensure valid collection names.
    """
    import hashlib

    # For non-ASCII names (like Chinese), use a hash-based approach
    # to generate a deterministic ASCII-safe collection name
    has_non_ascii = any(ord(c) > 127 for c in name)
    if has_non_ascii:
        # Use MD5 hash of the name for deterministic, ASCII-safe collection name
        hash_hex = hashlib.md5(name.encode("utf-8")).hexdigest()[:16]
        sanitized = f"actor_{hash_hex}"
    else:
        # Replace non-alphanumeric chars with underscore
        sanitized = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    # Ensure minimum length
    if len(sanitized) < 3:
        sanitized = sanitized + "_xx"

    # Ensure maximum length
    if len(sanitized) > 63:
        sanitized = sanitized[:63]

    # Ensure starts and ends with alphanumeric
    if not sanitized[0].isalnum():
        sanitized = "a" + sanitized[1:]
    if not sanitized[-1].isalnum():
        sanitized = sanitized[:-1] + "z"

    return sanitized


def store_actor_memory(
    actor_name: str,
    content: str,
    metadata: dict | None = None,
    tool_context=None,
) -> dict:
    """Store a memory entry for an actor in the vector store.

    高级 API：从 tool_context 自动获取正确的 VectorMemoryStore。

    Args:
        actor_name: The actor's name.
        content: The memory text.
        metadata: Optional metadata.
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    store = get_vector_store_from_context(tool_context)
    if store is None:
        return {"status": "error", "message": "无活跃戏剧，无法存储向量记忆。"}

    return store.store_memory(actor_name, content, metadata)


def search_actor_memory(
    actor_name: str,
    query: str,
    n_results: int = DEFAULT_SEARCH_RESULTS,
    tool_context=None,
) -> list[dict]:
    """Search actor's vector memory.

    高级 API：从 tool_context 自动获取正确的 VectorMemoryStore。

    Args:
        actor_name: The actor's name.
        query: The search query.
        n_results: Maximum number of results.
        tool_context: Tool context for state access.

    Returns:
        List of memory dicts.
    """
    store = get_vector_store_from_context(tool_context)
    if store is None:
        return []

    return store.search_memory(actor_name, query, n_results)


def build_actor_vector_context(
    actor_name: str,
    current_scene: str | int = "",
    n_results: int = DEFAULT_CONTEXT_RESULTS,
    query: str | None = None,
    tool_context=None,
) -> str:
    """Build vector memory context for an actor.

    高级 API：从 tool_context 自动获取正确的 VectorMemoryStore。

    Args:
        actor_name: The actor's name.
        current_scene: Current scene for query generation.
        n_results: Maximum number of results.
        query: Optional explicit query.
        tool_context: Tool context for state access.

    Returns:
        Formatted context text.
    """
    store = get_vector_store_from_context(tool_context)
    if store is None:
        return ""

    return store.build_context(actor_name, current_scene, n_results, query)


def backup_actor_vector_memory(actor_name: str, tool_context=None) -> list[dict]:
    """Backup an actor's vector memory for save progress.

    Args:
        actor_name: The actor's name.
        tool_context: Tool context for state access.

    Returns:
        List of memory entry dicts.
    """
    store = get_vector_store_from_context(tool_context)
    if store is None:
        return []

    return store.export_actor_memory(actor_name)


def restore_actor_vector_memory(
    actor_name: str,
    entries: list[dict],
    tool_context=None,
) -> dict:
    """Restore an actor's vector memory from backup.

    Args:
        actor_name: The actor's name.
        entries: List of memory entry dicts from backup.
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    store = get_vector_store_from_context(tool_context)
    if store is None:
        return {"status": "error", "message": "无活跃戏剧，无法恢复向量记忆。"}

    return store.import_actor_memory(actor_name, entries)


def generate_memory_summary(actor_name: str, tool_context=None) -> str:
    """Generate a memorySummary string for an actor from vector memory.

    基于演员的向量记忆库生成简要认知状态摘要，
    用于 Android 端 ActorInfo 的 memorySummary 字段。

    Args:
        actor_name: The actor's name.
        tool_context: Tool context for state access.

    Returns:
        Summary string.
    """
    store = get_vector_store_from_context(tool_context)
    if store is None:
        return ""

    # Get recent critical memories
    critical_results = store.search_memory(
        actor_name,
        query="重要事件 关键记忆",
        n_results=3,
    )

    # Get recent memories
    recent_results = store.search_memory(
        actor_name,
        query="最近的经历",
        n_results=5,
    )

    if not critical_results and not recent_results:
        return ""

    # Build summary
    parts = []

    # Critical memories
    critical_contents = [
        r["content"][:60] for r in critical_results
        if r.get("metadata", {}).get("importance") == "critical"
    ]
    if critical_contents:
        parts.append("关键记忆：" + "；".join(critical_contents))

    # Recent memories
    recent_contents = [r["content"][:40] for r in recent_results[:3]]
    if recent_contents:
        parts.append("近期经历：" + "；".join(recent_contents))

    summary = "。".join(parts)
    # Truncate to reasonable length
    return summary[:300] if summary else ""
