"""
FORGE RAG Librarian — Local documentation retrieval for framework/library docs.
Monitors .forge/docs/ for Markdown/text files, builds SQLite FTS5 index.
Injects relevant API docs into agent context to prevent hallucinations.
"""

import os
import re
import sqlite3
import time
from pathlib import Path

import config
from core.token_counter import count_tokens, truncate_to_tokens


class RAGLibrarian:
    """
    Local documentation retrieval system.
    Indexes Markdown/text files in .forge/docs/ using SQLite FTS5.
    Returns relevant snippets when agents need library/framework reference.
    """

    def __init__(self, docs_dir: str = None, db_path: str = None):
        self.docs_dir = docs_dir or str(config.DOCS_DIR)
        self.db_path = db_path or str(
            Path(self.docs_dir) / ".rag_index.db"
        )
        self._last_indexed = 0
        self._init_db()

    def _init_db(self):
        """Initialize the FTS5 index database."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS doc_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filepath TEXT NOT NULL,
                    section_title TEXT DEFAULT '',
                    content TEXT NOT NULL,
                    token_count INTEGER DEFAULT 0,
                    last_modified REAL NOT NULL,
                    chunk_index INTEGER DEFAULT 0
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts
                USING fts5(
                    filepath, section_title, content,
                    content=doc_chunks,
                    content_rowid=id
                );

                -- Triggers to keep FTS in sync
                CREATE TRIGGER IF NOT EXISTS doc_ai AFTER INSERT ON doc_chunks BEGIN
                    INSERT INTO doc_fts(rowid, filepath, section_title, content)
                    VALUES (new.id, new.filepath, new.section_title, new.content);
                END;

                CREATE TRIGGER IF NOT EXISTS doc_ad AFTER DELETE ON doc_chunks BEGIN
                    INSERT INTO doc_fts(doc_fts, rowid, filepath, section_title, content)
                    VALUES ('delete', old.id, old.filepath, old.section_title, old.content);
                END;
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get SQLite connection."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def index_docs(self, force: bool = False):
        """
        Index all documentation files in the docs directory.
        Only re-indexes files that have changed since last index.
        """
        if not os.path.isdir(self.docs_dir):
            return

        supported_exts = {".md", ".txt", ".rst", ".html"}

        for root, dirs, files in os.walk(self.docs_dir):
            # Skip the index database itself
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in supported_exts:
                    continue

                filepath = os.path.join(root, filename)
                mtime = os.path.getmtime(filepath)

                if not force and mtime <= self._last_indexed:
                    continue

                rel_path = os.path.relpath(filepath, self.docs_dir)

                try:
                    with open(filepath, "r", encoding="utf-8",
                              errors="ignore") as f:
                        content = f.read()
                except (IOError, OSError):
                    continue

                # Remove old entries for this file
                self._remove_file(rel_path)

                # Chunk the content
                chunks = self._chunk_document(content, rel_path)

                # Insert chunks
                conn = self._get_conn()
                try:
                    for chunk in chunks:
                        conn.execute(
                            """INSERT INTO doc_chunks
                               (filepath, section_title, content,
                                token_count, last_modified, chunk_index)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                rel_path,
                                chunk["section"],
                                chunk["content"],
                                count_tokens(chunk["content"]),
                                mtime,
                                chunk["index"],
                            )
                        )
                    conn.commit()
                finally:
                    conn.close()

        self._last_indexed = time.time()

    def _chunk_document(self, content: str,
                        filepath: str) -> list[dict]:
        """
        Split a document into chunks by sections (headers).
        Each chunk is a section with its header and content.
        Max ~500 tokens per chunk.
        """
        chunks = []
        current_section = os.path.splitext(os.path.basename(filepath))[0]
        current_content = []
        chunk_idx = 0

        for line in content.split("\n"):
            # Detect markdown headers
            header_match = re.match(r'^(#{1,4})\s+(.+)', line)
            if header_match:
                # Save previous section
                if current_content:
                    text = "\n".join(current_content).strip()
                    if text:
                        chunks.append({
                            "section": current_section,
                            "content": text,
                            "index": chunk_idx,
                        })
                        chunk_idx += 1

                current_section = header_match.group(2).strip()
                current_content = [line]
            else:
                current_content.append(line)

                # Split if chunk too large (roughly 500 tokens)
                if len(current_content) > 40:
                    text = "\n".join(current_content).strip()
                    if text:
                        chunks.append({
                            "section": current_section,
                            "content": text,
                            "index": chunk_idx,
                        })
                        chunk_idx += 1
                    current_content = []

        # Save last section
        if current_content:
            text = "\n".join(current_content).strip()
            if text:
                chunks.append({
                    "section": current_section,
                    "content": text,
                    "index": chunk_idx,
                })

        return chunks

    def _remove_file(self, filepath: str):
        """Remove all chunks for a file."""
        conn = self._get_conn()
        try:
            conn.execute(
                "DELETE FROM doc_chunks WHERE filepath = ?",
                (filepath,)
            )
            conn.commit()
        finally:
            conn.close()

    def search_docs(self, query: str,
                    top_k: int = None) -> list[dict]:
        """
        Search indexed docs using FTS5 full-text search.
        Returns top_k most relevant chunks.
        """
        if top_k is None:
            top_k = config.RAG_TOP_K

        # Ensure docs are indexed
        self.index_docs()

        conn = self._get_conn()
        try:
            # FTS5 query — match against all fields
            fts_query = " OR ".join(
                f'"{word}"' for word in query.split()
                if len(word) > 2
            )
            if not fts_query:
                fts_query = query

            rows = conn.execute(
                """SELECT dc.filepath, dc.section_title, dc.content,
                          dc.token_count,
                          rank
                   FROM doc_fts
                   JOIN doc_chunks dc ON doc_fts.rowid = dc.id
                   WHERE doc_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (fts_query, top_k)
            ).fetchall()

            return [
                {
                    "filepath": row["filepath"],
                    "section": row["section_title"],
                    "content": row["content"],
                    "tokens": row["token_count"],
                }
                for row in rows
            ]
        except Exception:
            # FTS query syntax errors — fall back to LIKE search
            return self._search_like(query, top_k, conn)
        finally:
            conn.close()

    def _search_like(self, query: str, top_k: int,
                     conn: sqlite3.Connection) -> list[dict]:
        """Fallback search using LIKE when FTS5 query fails."""
        words = [w for w in query.split() if len(w) > 2]
        if not words:
            return []

        conditions = " OR ".join(
            "content LIKE ?" for _ in words
        )
        params = [f"%{w}%" for w in words]
        params.append(top_k)

        rows = conn.execute(
            f"""SELECT filepath, section_title, content, token_count
                FROM doc_chunks
                WHERE {conditions}
                LIMIT ?""",
            params
        ).fetchall()

        return [
            {
                "filepath": row["filepath"],
                "section": row["section_title"],
                "content": row["content"],
                "tokens": row["token_count"],
            }
            for row in rows
        ]

    def get_context_injection(self, task: str,
                              max_tokens: int = None) -> str:
        """
        Build a context injection string from relevant docs.
        Ready to inject into an agent's prompt.
        """
        if max_tokens is None:
            max_tokens = config.RAG_MAX_TOKENS

        results = self.search_docs(task)
        if not results:
            return ""

        parts = ["[LIBRARY REFERENCE — from .forge/docs/]"]
        tokens_used = count_tokens(parts[0])

        for result in results:
            header = f"\n### {result['filepath']} > {result['section']}\n"
            content = truncate_to_tokens(
                result["content"],
                min(result["tokens"], max_tokens - tokens_used - 50)
            )
            entry = header + content
            entry_tokens = count_tokens(entry)

            if tokens_used + entry_tokens > max_tokens:
                break

            parts.append(entry)
            tokens_used += entry_tokens

        return "\n".join(parts) if len(parts) > 1 else ""

    def get_doc_count(self) -> int:
        """Get total number of indexed doc chunks."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM doc_chunks"
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def get_indexed_files(self) -> list[str]:
        """Get list of all indexed file paths."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT filepath FROM doc_chunks ORDER BY filepath"
            ).fetchall()
            return [row["filepath"] for row in rows]
        finally:
            conn.close()
