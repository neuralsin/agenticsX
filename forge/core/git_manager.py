"""
FORGE Git Manager — Git-backed time travel and branching.
Auto-commits after each approved change, enables instant revert.
Ties iterations to Git commits for full history.
"""

import os
import subprocess
import time
from typing import Optional

import config


class GitManager:
    """
    Manages Git operations for time-travel debugging.
    Auto-commits on approved changes, supports revert to any iteration.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self._initialized = False

    def init_repo(self) -> bool:
        """Initialize a git repo if not already one."""
        if self._is_git_repo():
            self._initialized = True
            return True
        success, _, _ = self._run_git("init")
        if success:
            # Create .gitignore for .forge internals
            gitignore_path = os.path.join(self.project_path, ".gitignore")
            if not os.path.exists(gitignore_path):
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write(
                        "# FORGE internals\n"
                        ".forge/context.db\n"
                        ".forge/context.db-wal\n"
                        ".forge/context.db-shm\n"
                        ".forge/frames/\n"
                        "__pycache__/\n"
                        "*.pyc\n"
                        ".venv/\n"
                        "venv/\n"
                        "node_modules/\n"
                    )
            # Initial commit
            self._run_git("add", "-A")
            self._run_git("commit", "-m",
                          f"{config.GIT_COMMIT_PREFIX} Initial commit")
            self._initialized = True
        return success

    def commit_iteration(self, iteration: int, description: str,
                         files: list[str] = None) -> Optional[str]:
        """
        Commit the current state tagged with the iteration number.
        Returns the commit hash, or None on failure.
        """
        if not self._ensure_init():
            return None

        if files:
            for f in files:
                self._run_git("add", f)
        else:
            self._run_git("add", "-A")

        # Check if there are changes to commit
        success, stdout, _ = self._run_git("status", "--porcelain")
        if not stdout.strip():
            return self._get_head_hash()

        msg = f"{config.GIT_COMMIT_PREFIX} Iteration {iteration}: {description}"
        success, _, _ = self._run_git("commit", "-m", msg)

        if success:
            return self._get_head_hash()
        return None

    def get_timeline(self) -> list[dict]:
        """
        Get the iteration timeline as a list of commit records.
        Returns: [{iteration, hash, description, timestamp, short_hash}]
        """
        if not self._ensure_init():
            return []

        success, stdout, _ = self._run_git(
            "log", "--oneline", "--format=%H|%h|%s|%ai", "--reverse"
        )
        if not success or not stdout.strip():
            return []

        timeline = []
        for line in stdout.strip().split("\n"):
            parts = line.split("|", 3)
            if len(parts) < 4:
                continue

            full_hash, short_hash, subject, date_str = parts
            iteration = 0

            # Try to extract iteration number from commit message
            prefix = f"{config.GIT_COMMIT_PREFIX} Iteration "
            if prefix in subject:
                try:
                    iter_part = subject.split(prefix)[1].split(":")[0]
                    iteration = int(iter_part.strip())
                except (ValueError, IndexError):
                    pass

            # Extract description
            desc = subject
            if ":" in subject:
                desc = subject.split(":", 1)[1].strip()

            timeline.append({
                "hash": full_hash,
                "short_hash": short_hash,
                "iteration": iteration,
                "description": desc,
                "timestamp": date_str.strip(),
                "subject": subject,
            })

        return timeline

    def revert_to(self, commit_hash: str) -> tuple[bool, str]:
        """
        Revert the project to a specific commit.
        WARNING: This is destructive — uses git reset --hard.
        Returns (success, message).
        """
        if not self._ensure_init():
            return False, "Git not initialized"

        # First, save current state as a backup branch
        ts = int(time.time())
        self._run_git("branch", f"forge-backup-{ts}")

        # Reset hard to the target
        success, stdout, stderr = self._run_git(
            "reset", "--hard", commit_hash
        )

        if success:
            return True, f"Reverted to {commit_hash[:8]}"
        return False, stderr or "Failed to revert"

    def get_diff_between(self, hash_a: str,
                         hash_b: str = "HEAD") -> str:
        """Get unified diff between two commits."""
        if not self._ensure_init():
            return ""

        success, stdout, _ = self._run_git(
            "diff", hash_a, hash_b, "--stat"
        )
        if success:
            _, full_diff, _ = self._run_git("diff", hash_a, hash_b)
            return full_diff
        return ""

    def get_changed_files_since(self, commit_hash: str) -> list[str]:
        """Get list of files changed since a specific commit."""
        if not self._ensure_init():
            return []

        success, stdout, _ = self._run_git(
            "diff", "--name-only", commit_hash, "HEAD"
        )
        if success and stdout.strip():
            return stdout.strip().split("\n")
        return []

    def get_current_iteration(self) -> int:
        """Get the latest iteration number from git log."""
        timeline = self.get_timeline()
        if timeline:
            return max(e["iteration"] for e in timeline)
        return 0

    def _get_head_hash(self) -> Optional[str]:
        """Get the current HEAD commit hash."""
        success, stdout, _ = self._run_git("rev-parse", "HEAD")
        if success:
            return stdout.strip()
        return None

    def _is_git_repo(self) -> bool:
        """Check if the project directory is a git repo."""
        return os.path.isdir(os.path.join(self.project_path, ".git"))

    def _ensure_init(self) -> bool:
        """Ensure git is initialized."""
        if self._initialized:
            return True
        if self._is_git_repo():
            self._initialized = True
            return True
        return self.init_repo()

    def _run_git(self, *args) -> tuple[bool, str, str]:
        """Run a git command in the project directory."""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            return (
                result.returncode == 0,
                result.stdout,
                result.stderr,
            )
        except FileNotFoundError:
            return False, "", "Git not found. Install git."
        except subprocess.TimeoutExpired:
            return False, "", "Git command timed out"
        except Exception as e:
            return False, "", str(e)
