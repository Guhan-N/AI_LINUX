"""Persistent SQLite memory store with Full-Text Search (FTS5) for continuous learning."""

import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from linagent.core.config import load_config
from linagent.core.tools import ToolResult, default_registry

from contextlib import contextmanager

class MemoryStore:
    def __init__(self, db_path: Optional[str] = None):
        cfg = load_config()
        self.db_path = Path(db_path or cfg.memory_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize tables and FTS5 search index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # Try creating FTS5 virtual table for fast full-text search
            try:
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                        key,
                        content,
                        category,
                        content='memories',
                        content_rowid='id'
                    )
                """)
                # Triggers to keep FTS in sync
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                        INSERT INTO memories_fts(rowid, key, content, category)
                        VALUES (new.id, new.key, new.content, new.category);
                    END;
                """)
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                        INSERT INTO memories_fts(memories_fts, rowid, key, content, category)
                        VALUES ('delete', old.id, old.key, old.content, old.category);
                    END;
                """)
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                        INSERT INTO memories_fts(memories_fts, rowid, key, content, category)
                        VALUES ('delete', old.id, old.key, old.content, old.category);
                        INSERT INTO memories_fts(rowid, key, content, category)
                        VALUES (new.id, new.key, new.content, new.category);
                    END;
                """)
            except sqlite3.OperationalError:
                # FTS5 might not be enabled in rare minimal sqlite builds
                pass

            conn.commit()

    def store(self, key: str, content: str, category: str = "fact") -> int:
        """Store or update a memory."""
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Check if key + category already exists
            cursor.execute(
                "SELECT id FROM memories WHERE category = ? AND key = ?",
                (category, key),
            )
            row = cursor.fetchone()
            if row:
                mem_id = row["id"]
                cursor.execute(
                    "UPDATE memories SET content = ?, updated_at = ? WHERE id = ?",
                    (content, now, mem_id),
                )
            else:
                cursor.execute(
                    "INSERT INTO memories (category, key, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (category, key, content, now, now),
                )
                mem_id = cursor.lastrowid
            conn.commit()
            return mem_id

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search memories using FTS5 or LIKE fallback."""
        results: List[Dict[str, Any]] = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Try FTS5 match first
            try:
                # Sanitize query for FTS5 syntax
                clean_q = '"' + query.replace('"', '""') + '"'
                cursor.execute(
                    """
                    SELECT m.id, m.category, m.key, m.content, m.updated_at
                    FROM memories_fts f
                    JOIN memories m ON f.rowid = m.id
                    WHERE memories_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (clean_q, limit),
                )
                for r in cursor.fetchall():
                    results.append(dict(r))
            except Exception:
                pass

            # If FTS yielded nothing or failed, use LIKE
            if not results:
                like_pat = f"%{query}%"
                cursor.execute(
                    """
                    SELECT id, category, key, content, updated_at
                    FROM memories
                    WHERE key LIKE ? OR content LIKE ? OR category LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (like_pat, like_pat, like_pat, limit),
                )
                for r in cursor.fetchall():
                    results.append(dict(r))

        return results

    def list_all(self, category: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List stored memories."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    "SELECT id, category, key, content, updated_at FROM memories WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                    (category, limit),
                )
            else:
                cursor.execute(
                    "SELECT id, category, key, content, updated_at FROM memories ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                )
            return [dict(r) for r in cursor.fetchall()]

    def delete(self, key: str, category: Optional[str] = None) -> bool:
        """Delete a memory by key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute("DELETE FROM memories WHERE key = ? AND category = ?", (key, category))
            else:
                cursor.execute("DELETE FROM memories WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0

# Default global instance
default_memory = MemoryStore()

@default_registry.register(
    name="remember_fact",
    description="Store a piece of knowledge, user preference, server details, or workflow rule into long-term memory.",
)
def remember_fact(key: str, content: str, category: str = "preference") -> ToolResult:
    """Save a fact to long-term memory."""
    mem_id = default_memory.store(key=key, content=content, category=category)
    return ToolResult(
        success=True,
        output=f"Successfully remembered [{category}] '{key}': {content}",
        data={"id": mem_id, "key": key, "category": category},
    )

@default_registry.register(
    name="recall_memories",
    description="Search long-term memory for previously remembered facts, preferences, server details, or user requests.",
)
def recall_memories(query: str, limit: int = 5) -> ToolResult:
    """Search stored memories."""
    results = default_memory.search(query=query, limit=limit)
    if not results:
        return ToolResult(
            success=True,
            output=f"No memories found matching query: '{query}'",
            data={"results": []},
        )

    formatted = []
    for r in results:
        formatted.append(f"* [{r['category'].upper()}] {r['key']}: {r['content']}")

    return ToolResult(
        success=True,
        output="\n".join(formatted),
        data={"results": results},
    )

@default_registry.register(
    name="learn_solution",
    description="Record an error fix, debugging step, or Linux recipe into memory for future instant recall.",
)
def learn_solution(problem_description: str, solution_steps: str) -> ToolResult:
    """Store a problem-solution pair."""
    mem_id = default_memory.store(
        key=problem_description,
        content=solution_steps,
        category="solution",
    )
    return ToolResult(
        success=True,
        output=f"Learned solution for '{problem_description}'. Will be recalled on similar problems.",
        data={"id": mem_id},
    )

@default_registry.register(
    name="find_solution",
    description="Find previously recorded troubleshooting solutions or fixes for a given problem or error message.",
)
def find_solution(problem_query: str) -> ToolResult:
    """Find past solutions."""
    results = default_memory.search(query=problem_query, limit=3)
    solutions = [r for r in results if r.get("category") == "solution"]
    if not solutions:
        return ToolResult(
            success=True,
            output=f"No past solutions found in memory for '{problem_query}'.",
        )

    formatted = []
    for s in solutions:
        formatted.append(f"Problem: {s['key']}\nSolution:\n{s['content']}\n")

    return ToolResult(
        success=True,
        output="\n---\n".join(formatted),
        data={"solutions": solutions},
    )
