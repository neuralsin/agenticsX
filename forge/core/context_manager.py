"""
FORGE Context Manager — Disk-backed context store using SQLite.
Never loads full history into RAM. Retrieves only what each agent needs.
Implements the full schema from spec Section 2.
"""

import sqlite3
import time
import zlib
import os
import re
import math
from pathlib import Path
from collections import Counter

from core.token_counter import count_tokens, truncate_to_tokens
import config


class ContextManager:
    """
    Disk-as-Memory context store.
    12GB RAM limits in-memory context. FORGE solves this by treating SQLite
    on disk as the primary context store. Agents never hold full history in RAM.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(config.STORAGE_DIR / "context.db")
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local SQLite connection."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        """Initialize the SQLite schema — all 6 tables + 3 indexes from spec."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                -- Core message store
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    agent_name  TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    token_count INTEGER DEFAULT 0,
                    timestamp   REAL NOT NULL,
                    iteration   INTEGER DEFAULT 0,
                    importance  INTEGER DEFAULT 5
                );

                -- Project file snapshots (compressed)
                CREATE TABLE IF NOT EXISTS file_snapshots (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    filepath    TEXT NOT NULL,
                    content     BLOB NOT NULL,
                    token_count INTEGER DEFAULT 0,
                    iteration   INTEGER DEFAULT 0,
                    timestamp   REAL NOT NULL
                );

                -- Per-agent context windows
                CREATE TABLE IF NOT EXISTS agent_contexts (
                    agent_name  TEXT PRIMARY KEY,
                    session_id  TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    token_budget  INTEGER DEFAULT 8192,
                    tokens_used   INTEGER DEFAULT 0,
                    last_updated  REAL NOT NULL
                );

                -- Execution results
                CREATE TABLE IF NOT EXISTS exec_results (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    iteration   INTEGER NOT NULL,
                    exit_code   INTEGER,
                    stdout      TEXT,
                    stderr      TEXT,
                    duration_ms INTEGER,
                    timestamp   REAL NOT NULL
                );

                -- Vision feedback records
                CREATE TABLE IF NOT EXISTS vision_reports (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    iteration   INTEGER NOT NULL,
                    screenshot_path TEXT,
                    feedback    TEXT,
                    issues_found INTEGER DEFAULT 0,
                    timestamp   REAL NOT NULL
                );

                -- User steering injections
                CREATE TABLE IF NOT EXISTS steering_inputs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    iteration   INTEGER NOT NULL,
                    content     TEXT NOT NULL,
                    applied     INTEGER DEFAULT 0,
                    timestamp   REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session 
                    ON messages(session_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_messages_agent 
                    ON messages(session_id, agent_name);
                CREATE INDEX IF NOT EXISTS idx_files_session 
                    ON file_snapshots(session_id, filepath);
            """)
            conn.commit()
        finally:
            conn.close()

    # ─── Message CRUD ────────────────────────────────────────────────────────────

    def save_message(self, session_id: str, agent_name: str, role: str,
                     content: str, token_count: int = 0, iteration: int = 0,
                     importance: int = 5):
        """Save a message to the message store."""
        if token_count == 0:
            token_count = count_tokens(content)
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO messages 
                   (session_id, agent_name, role, content, token_count, 
                    timestamp, iteration, importance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, agent_name, role, content, token_count,
                 time.time(), iteration, importance)
            )
            conn.commit()
        finally:
            conn.close()

    def get_recent_messages(self, session_id: str, agent_name: str = None,
                           limit: int = 10) -> list[dict]:
        """Get recent messages, optionally filtered by agent."""
        conn = self._get_conn()
        try:
            if agent_name:
                rows = conn.execute(
                    """SELECT agent_name, role, content, token_count, timestamp, 
                              iteration, importance
                       FROM messages 
                       WHERE session_id = ? AND agent_name = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (session_id, agent_name, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT agent_name, role, content, token_count, timestamp,
                              iteration, importance
                       FROM messages 
                       WHERE session_id = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (session_id, limit)
                ).fetchall()
            
            return [dict(row) for row in reversed(rows)]
        finally:
            conn.close()

    def get_all_messages(self, session_id: str) -> list[dict]:
        """Get all messages for a session (for export/display)."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT agent_name, role, content, token_count, timestamp,
                          iteration, importance
                   FROM messages 
                   WHERE session_id = ?
                   ORDER BY timestamp ASC""",
                (session_id,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def count_messages(self, session_id: str) -> int:
        """Count total messages in a session."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def search_messages(self, session_id: str, query: str, 
                        limit: int = 20) -> list[dict]:
        """Search messages by content."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT agent_name, role, content, token_count, timestamp
                   FROM messages
                   WHERE session_id = ? AND content LIKE ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (session_id, f"%{query}%", limit)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ─── Smart Context Retrieval ─────────────────────────────────────────────────

    def get_agent_context(self, agent_name: str, session_id: str,
                          current_task: str) -> tuple[list[dict], int]:
        """
        Builds the message list for an agent call using:
        1. Agent's system prompt (always included)
        2. Most recent N messages from this agent (recency)
        3. Top-K messages by importance score (relevance)
        4. Current codebase slice (only files relevant to task)
        5. Latest execution result
        6. Latest vision report (if applicable)
        7. Any pending user steering inputs
        """
        budget = self._get_budget(agent_name)
        messages = []
        tokens_used = 0

        # 1. System prompt (always)
        sys_prompt = self._get_system_prompt(agent_name)
        messages.append({"role": "system", "content": sys_prompt})
        tokens_used += count_tokens(sys_prompt)

        # 2. Pending steering inputs (highest priority after system)
        steering = self.get_pending_steering(session_id)
        if steering:
            steering_text = f"[USER STEERING]\n{steering}"
            steering_tokens = count_tokens(steering_text)
            if tokens_used + steering_tokens < budget * 0.2:
                messages.append({"role": "user", "content": steering_text})
                tokens_used += steering_tokens

        # 3. Recent agent-specific history (last 5 exchanges)
        history = self._get_recent_history(agent_name, session_id, limit=5)
        for msg in history:
            t = count_tokens(msg["content"])
            if tokens_used + t < budget * 0.6:
                messages.append(msg)
                tokens_used += t

        # 4. Relevant Codebase Slice (using AST if enabled)
        project_path = getattr(self, 'current_project_path', "")
        
        slice_budget = budget * 0.4
        if tokens_used < budget * 0.8:
            code_slice = self._get_relevant_files(session_id, current_task, int(slice_budget), project_path)
            if code_slice:
                messages.append({"role": "user", "content": code_slice})
                tokens_used += count_tokens(code_slice)

        # 5. Latest exec result
        exec_result = self._get_latest_exec(session_id)
        if exec_result:
            exec_tokens = count_tokens(exec_result)
            if tokens_used + exec_tokens < budget:
                messages.append({"role": "user", "content": exec_result})
                tokens_used += exec_tokens

        return messages, tokens_used

    def _get_budget(self, agent_name: str) -> int:
        """Get the token budget for an agent."""
        return config.CONTEXT_BUDGETS.get(agent_name, 4096)

    def _get_system_prompt(self, agent_name: str) -> str:
        """Get the stored system prompt for an agent, or a default."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT system_prompt FROM agent_contexts WHERE agent_name = ?",
                (agent_name,)
            ).fetchone()
            if row:
                return row["system_prompt"]
            return f"You are {agent_name}, an AI agent in the FORGE development system."
        finally:
            conn.close()

    def set_system_prompt(self, agent_name: str, session_id: str,
                          system_prompt: str, token_budget: int = None):
        """Set or update the system prompt for an agent."""
        if token_budget is None:
            token_budget = self._get_budget(agent_name)
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO agent_contexts 
                   (agent_name, session_id, system_prompt, token_budget, 
                    tokens_used, last_updated)
                   VALUES (?, ?, ?, ?, 0, ?)""",
                (agent_name, session_id, system_prompt, token_budget, time.time())
            )
            conn.commit()
        finally:
            conn.close()

    def _get_recent_history(self, agent_name: str, session_id: str,
                            limit: int = 5) -> list[dict]:
        """Get recent message history for an agent."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT role, content FROM messages
                   WHERE session_id = ? AND agent_name = ? AND importance > 1
                   ORDER BY timestamp DESC LIMIT ?""",
                (session_id, agent_name, limit * 2)
            ).fetchall()
            return [{"role": row["role"], "content": row["content"]} 
                    for row in reversed(rows)]
        finally:
            conn.close()

    def _get_relevant_files(self, session_id: str, task: str,
                            token_limit: int, project_path: str = "") -> str:
        """
        Retrieves relevant codebase context using ASTIndexer if enabled.
        """
        if config.AST_ENABLED and project_path:
            from core.ast_indexer import ASTIndexer
            indexer = ASTIndexer(project_path)
            
            context = indexer.get_symbol_map() + "\n\n"
            tokens = count_tokens(context)
            
            if token_limit - tokens > 500:
                context += indexer.get_relevant_symbols(task, token_limit - tokens)
            
            return context
        return ""

    def _get_latest_exec(self, session_id: str) -> str:
        """Get the latest execution result as formatted text."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT exit_code, stdout, stderr, duration_ms, iteration
                   FROM exec_results
                   WHERE session_id = ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (session_id,)
            ).fetchone()
            
            if not row:
                return ""
            
            parts = [f"[LAST EXECUTION — Iteration {row['iteration']}]"]
            parts.append(f"Exit Code: {row['exit_code']}")
            parts.append(f"Duration: {row['duration_ms']}ms")
            
            if row["stdout"]:
                stdout = row["stdout"][:1000]
                parts.append(f"STDOUT:\n{stdout}")
            if row["stderr"]:
                stderr = row["stderr"][:1500]
                parts.append(f"STDERR:\n{stderr}")
            
            return "\n".join(parts)
        finally:
            conn.close()

    # ─── Steering ────────────────────────────────────────────────────────────────

    def add_steering(self, session_id: str, content: str, iteration: int = 0):
        """Add a user steering injection."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO steering_inputs 
                   (session_id, iteration, content, applied, timestamp)
                   VALUES (?, ?, ?, 0, ?)""",
                (session_id, iteration, content, time.time())
            )
            conn.commit()
        finally:
            conn.close()

    def get_pending_steering(self, session_id: str) -> str:
        """Get all pending steering inputs, mark them as applied."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT id, content FROM steering_inputs
                   WHERE session_id = ? AND applied = 0
                   ORDER BY timestamp ASC""",
                (session_id,)
            ).fetchall()
            
            if not rows:
                return ""
            
            # Mark as applied
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE steering_inputs SET applied = 1 WHERE id IN ({placeholders})",
                ids
            )
            conn.commit()
            
            return "\n".join(row["content"] for row in rows)
        finally:
            conn.close()

    # ─── Export & Import ────────────────────────────────────────────────────────

    def export_session(self, session_id: str, export_path: str) -> bool:
        """Export session to a JSON file."""
        import json
        messages = self.get_all_messages(session_id)
        try:
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump({"session_id": session_id, "messages": messages}, f, indent=2)
            return True
        except Exception:
            return False

    def import_session(self, session_id: str, import_path: str) -> bool:
        """Import session from a JSON file."""
        import json
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "messages" not in data:
                return False
                
            conn = self._get_conn()
            try:
                for msg in data["messages"]:
                    conn.execute(
                        """INSERT INTO messages 
                           (session_id, agent_name, role, content, token_count, 
                            timestamp, iteration, importance)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (session_id, msg["agent_name"], msg["role"], 
                         msg["content"], msg.get("token_count", 0), 
                         msg["timestamp"], msg.get("iteration", 0), 
                         msg.get("importance", 5))
                    )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception:
            return False

    def get_steering_history(self, session_id: str) -> list[dict]:
        """Get all steering inputs for a session."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT content, applied, timestamp, iteration
                   FROM steering_inputs
                   WHERE session_id = ?
                   ORDER BY timestamp DESC""",
                (session_id,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ─── File Snapshots ──────────────────────────────────────────────────────────

    def save_file_snapshot(self, session_id: str, filepath: str,
                          content: str, iteration: int = 0):
        """Save a compressed file snapshot."""
        compressed = zlib.compress(content.encode("utf-8"))
        token_count = count_tokens(content)
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO file_snapshots 
                   (session_id, filepath, content, token_count, iteration, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, filepath, compressed, token_count, 
                 iteration, time.time())
            )
            conn.commit()
        finally:
            conn.close()

    def get_latest_file(self, session_id: str, filepath: str) -> str:
        """Get the latest snapshot of a file."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT content FROM file_snapshots
                   WHERE session_id = ? AND filepath = ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (session_id, filepath)
            ).fetchone()
            if row:
                return zlib.decompress(row["content"]).decode("utf-8")
            return ""
        finally:
            conn.close()

    def get_project_files(self, session_id: str) -> list[str]:
        """Get list of all file paths in the project."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT DISTINCT filepath FROM file_snapshots
                   WHERE session_id = ?
                   ORDER BY filepath ASC""",
                (session_id,)
            ).fetchall()
            return [row["filepath"] for row in rows]
        finally:
            conn.close()

    # ─── Execution Results ───────────────────────────────────────────────────────

    def save_exec_result(self, session_id: str, iteration: int,
                         exit_code: int, stdout: str, stderr: str,
                         duration_ms: int):
        """Save an execution result."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO exec_results 
                   (session_id, iteration, exit_code, stdout, stderr, 
                    duration_ms, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, iteration, exit_code, stdout, stderr,
                 duration_ms, time.time())
            )
            conn.commit()
        finally:
            conn.close()

    # ─── Vision Reports ──────────────────────────────────────────────────────────

    def save_vision_report(self, session_id: str, iteration: int,
                           screenshot_path: str, feedback: str,
                           issues_found: int):
        """Save a vision analysis report."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO vision_reports 
                   (session_id, iteration, screenshot_path, feedback, 
                    issues_found, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, iteration, screenshot_path, feedback,
                 issues_found, time.time())
            )
            conn.commit()
        finally:
            conn.close()

    def get_latest_vision_report(self, session_id: str) -> dict:
        """Get the most recent vision report."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT * FROM vision_reports
                   WHERE session_id = ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (session_id,)
            ).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    # ─── Context Pruning ─────────────────────────────────────────────────────────

    def compress_old_history(self, session_id: str, agent_name: str,
                            keep_recent: int = 10):
        """
        Summarize old messages in-DB.
        Replaces N old messages with 1 summary message.
        Runs automatically when any agent exceeds 85% token budget.
        
        The actual summarization would be done by PLANNER model, but here
        we implement the DB operations. The calling code provides the summary.
        """
        conn = self._get_conn()
        try:
            # Get all messages for this agent
            rows = conn.execute(
                """SELECT id, content, token_count FROM messages
                   WHERE session_id = ? AND agent_name = ? AND importance > 1
                   ORDER BY timestamp ASC""",
                (session_id, agent_name)
            ).fetchall()

            if len(rows) <= keep_recent:
                return  # Nothing to prune

            # Mark old messages as low importance (keep in DB but deprioritize)
            old_ids = [row["id"] for row in rows[:-keep_recent]]
            if old_ids:
                placeholders = ",".join("?" * len(old_ids))
                conn.execute(
                    f"UPDATE messages SET importance = 1 WHERE id IN ({placeholders})",
                    old_ids
                )
                conn.commit()
        finally:
            conn.close()

    def save_summary(self, session_id: str, agent_name: str, summary: str):
        """Save a context summary message with high importance."""
        self.save_message(session_id, agent_name, "system", 
                         f"[CONTEXT SUMMARY]\n{summary}",
                         importance=9)

    # ─── Stats ───────────────────────────────────────────────────────────────────

    def get_db_size_mb(self) -> float:
        """Get the database file size in MB."""
        try:
            size_bytes = os.path.getsize(self.db_path)
            return round(size_bytes / (1024 * 1024), 2)
        except OSError:
            return 0.0

    def get_session_stats(self, session_id: str) -> dict:
        """Get comprehensive stats for a session."""
        conn = self._get_conn()
        try:
            msg_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?",
                (session_id,)
            ).fetchone()["cnt"]
            
            total_tokens = conn.execute(
                "SELECT COALESCE(SUM(token_count), 0) as total FROM messages WHERE session_id = ?",
                (session_id,)
            ).fetchone()["total"]
            
            file_count = conn.execute(
                "SELECT COUNT(DISTINCT filepath) as cnt FROM file_snapshots WHERE session_id = ?",
                (session_id,)
            ).fetchone()["cnt"]
            
            exec_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM exec_results WHERE session_id = ?",
                (session_id,)
            ).fetchone()["cnt"]
            
            return {
                "message_count": msg_count,
                "total_tokens": total_tokens,
                "file_count": file_count,
                "exec_count": exec_count,
                "db_size_mb": self.get_db_size_mb(),
            }
        finally:
            conn.close()
