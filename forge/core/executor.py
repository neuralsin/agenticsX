"""
FORGE Executor — Sandboxed code runner, subprocess management.
Runs project code in a controlled environment with output capture.
"""

import subprocess
import os
import time
import threading
import signal

import config


class Executor:
    """
    Sandboxed code runner for FORGE projects.
    Captures stdout/stderr, handles timeouts, provides kill capability.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self._process = None
        self._lock = threading.Lock()

    def run(self, entry_file: str, timeout: int = None,
            extra_env: dict = None) -> tuple[bool, str, str, int]:
        """
        Run the project entry point, capture output.
        
        Args:
            entry_file: Path to the entry file (relative to project_path).
            timeout: Execution timeout in seconds.
            extra_env: Additional environment variables.
        
        Returns:
            Tuple of (success, stdout, stderr, duration_ms).
        """
        if timeout is None:
            timeout = config.EXEC_TIMEOUT

        # Build environment
        env = {**os.environ}
        env["FORGE_SIM"] = "1"
        env["PYTHONPATH"] = self.project_path
        env["PYTHONUNBUFFERED"] = "1"
        if extra_env:
            env.update(extra_env)

        # Resolve entry file path
        entry_path = entry_file
        if not os.path.isabs(entry_path):
            entry_path = os.path.join(self.project_path, entry_file)

        if not os.path.exists(entry_path):
            return False, "", f"Entry file not found: {entry_path}", 0

        start_time = time.time()
        
        try:
            with self._lock:
                self._process = subprocess.Popen(
                    ["python", entry_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=self.project_path,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP 
                        if os.name == 'nt' else 0,
                )
            
            stdout, stderr = self._process.communicate(timeout=timeout)
            duration_ms = int((time.time() - start_time) * 1000)
            success = self._process.returncode == 0
            
            return success, stdout or "", stderr or "", duration_ms

        except subprocess.TimeoutExpired:
            self.kill()
            duration_ms = int((time.time() - start_time) * 1000)
            return False, "", f"TIMEOUT: Process exceeded {timeout}s limit", duration_ms

        except FileNotFoundError:
            duration_ms = int((time.time() - start_time) * 1000)
            return False, "", "Python interpreter not found", duration_ms

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return False, "", f"Execution error: {str(e)}", duration_ms

        finally:
            with self._lock:
                self._process = None

    def run_command(self, command: str, timeout: int = 30) -> tuple[bool, str, str, int]:
        """
        Run an arbitrary command (e.g., pip install, git commands).
        
        Args:
            command: Shell command to execute.
            timeout: Execution timeout in seconds.
        
        Returns:
            Tuple of (success, stdout, stderr, duration_ms).
        """
        start_time = time.time()
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_path,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            return result.returncode == 0, result.stdout, result.stderr, duration_ms

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return False, "", f"TIMEOUT: Command exceeded {timeout}s limit", duration_ms

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return False, "", str(e), duration_ms

    def kill(self):
        """Kill the currently running process."""
        with self._lock:
            if self._process and self._process.poll() is None:
                try:
                    if os.name == 'nt':
                        self._process.terminate()
                    else:
                        os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
                try:
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        self._process.kill()
                    except (ProcessLookupError, OSError):
                        pass

    @property
    def is_running(self) -> bool:
        """Check if a process is currently running."""
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def check_python_available(self) -> bool:
        """Verify Python interpreter is available."""
        try:
            result = subprocess.run(
                ["python", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
