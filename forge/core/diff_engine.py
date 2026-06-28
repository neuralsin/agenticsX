"""
FORGE Diff Engine — Applies patches, computes git-style diffs.
Handles backup system with last N versions per file.
"""

import difflib
import os
import shutil
import time
from pathlib import Path

import config


class DiffEngine:
    """
    Manages file diffs, patches, and backup versions.
    Never overwrites without backup. Keeps last BACKUP_VERSIONS_KEPT versions.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.backup_dir = os.path.join(project_path, ".forge", "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

    def compute_diff(self, old_content: str, new_content: str,
                     filename: str = "file") -> str:
        """
        Compute a unified diff between old and new content.
        Returns a string in unified diff format (git-style).
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=""
        )
        return "\n".join(diff)

    def compute_diff_lines(self, old_content: str, new_content: str) -> list[dict]:
        """
        Compute line-by-line diff for GUI display.
        Returns list of {type: 'add'|'remove'|'unchanged', content: str, line_num: int}
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        result = []
        new_line_num = 0
        old_line_num = 0

        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                for k in range(i1, i2):
                    old_line_num += 1
                    new_line_num += 1
                    result.append({
                        "type": "unchanged",
                        "content": old_lines[k],
                        "old_line": old_line_num,
                        "new_line": new_line_num,
                    })
            elif op == "replace":
                for k in range(i1, i2):
                    old_line_num += 1
                    result.append({
                        "type": "remove",
                        "content": old_lines[k],
                        "old_line": old_line_num,
                        "new_line": None,
                    })
                for k in range(j1, j2):
                    new_line_num += 1
                    result.append({
                        "type": "add",
                        "content": new_lines[k],
                        "old_line": None,
                        "new_line": new_line_num,
                    })
            elif op == "insert":
                for k in range(j1, j2):
                    new_line_num += 1
                    result.append({
                        "type": "add",
                        "content": new_lines[k],
                        "old_line": None,
                        "new_line": new_line_num,
                    })
            elif op == "delete":
                for k in range(i1, i2):
                    old_line_num += 1
                    result.append({
                        "type": "remove",
                        "content": old_lines[k],
                        "old_line": old_line_num,
                        "new_line": None,
                    })

        return result

    def backup_file(self, filepath: str) -> str:
        """
        Create a backup of a file before modification.
        Keeps the last BACKUP_VERSIONS_KEPT versions.
        Returns the backup path.
        """
        abs_path = self._resolve_path(filepath)
        if not os.path.exists(abs_path):
            return ""

        # Create backup filename with timestamp
        rel_path = os.path.relpath(abs_path, self.project_path)
        safe_name = rel_path.replace(os.sep, "__").replace("/", "__")
        timestamp = int(time.time() * 1000)
        backup_name = f"{safe_name}.{timestamp}.bak"
        backup_path = os.path.join(self.backup_dir, backup_name)

        # Copy file to backup
        shutil.copy2(abs_path, backup_path)

        # Prune old backups (keep last N)
        self._prune_backups(safe_name)

        return backup_path

    def restore_file(self, filepath: str) -> bool:
        """
        Restore a file from its most recent backup.
        Returns True if restore succeeded.
        """
        abs_path = self._resolve_path(filepath)
        rel_path = os.path.relpath(abs_path, self.project_path)
        safe_name = rel_path.replace(os.sep, "__").replace("/", "__")

        # Find most recent backup
        backups = self._get_backups(safe_name)
        if not backups:
            return False

        latest_backup = backups[-1]
        shutil.copy2(latest_backup, abs_path)
        return True

    def write_file_safe(self, filepath: str, content: str) -> tuple[bool, str]:
        """
        Write content to a file with automatic backup.
        Returns (success, diff_text).
        """
        abs_path = self._resolve_path(filepath)

        # Read old content for diff
        old_content = ""
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    old_content = f.read()
            except Exception:
                old_content = ""

            # Backup before overwrite
            self.backup_file(filepath)

        # Create parent directories if needed
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        # Write new content
        try:
            with open(abs_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        except Exception as e:
            return False, str(e)

        # Compute diff
        diff = self.compute_diff(old_content, content, filepath)
        return True, diff

    def get_backup_history(self, filepath: str) -> list[dict]:
        """Get backup history for a file."""
        abs_path = self._resolve_path(filepath)
        rel_path = os.path.relpath(abs_path, self.project_path)
        safe_name = rel_path.replace(os.sep, "__").replace("/", "__")

        backups = self._get_backups(safe_name)
        history = []
        for bp in backups:
            stat = os.stat(bp)
            history.append({
                "path": bp,
                "timestamp": stat.st_mtime,
                "size": stat.st_size,
            })
        return history

    def _resolve_path(self, filepath: str) -> str:
        """Resolve a possibly relative filepath to absolute."""
        if os.path.isabs(filepath):
            return filepath
        return os.path.join(self.project_path, filepath)

    def _get_backups(self, safe_name: str) -> list[str]:
        """Get sorted list of backup files for a given file."""
        if not os.path.exists(self.backup_dir):
            return []
        
        backups = []
        for f in os.listdir(self.backup_dir):
            if f.startswith(safe_name + ".") and f.endswith(".bak"):
                backups.append(os.path.join(self.backup_dir, f))
        
        backups.sort()  # Sorted by timestamp (in filename)
        return backups

    def _prune_backups(self, safe_name: str):
        """Remove old backups beyond BACKUP_VERSIONS_KEPT."""
        backups = self._get_backups(safe_name)
        while len(backups) > config.BACKUP_VERSIONS_KEPT:
            oldest = backups.pop(0)
            try:
                os.remove(oldest)
            except OSError:
                pass
