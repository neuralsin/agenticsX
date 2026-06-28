"""
FORGE Terminal Simulator — Terminal output capture and display.
Captures subprocess stdout/stderr for terminal-based projects.
"""

import subprocess
import os
import threading
import time
import queue


class TerminalSimulator:
    """
    Terminal output simulator.
    Captures and buffers subprocess output for display in the GUI.
    """

    def __init__(self, project_path: str, max_lines: int = 500):
        self.project_path = project_path
        self.max_lines = max_lines
        self._output_buffer = []
        self._process = None
        self._running = False
        self._output_queue = queue.Queue()
        self._callbacks = []  # (line_text) -> None

    def run(self, entry_file: str, timeout: int = 30) -> tuple[bool, str, str]:
        """
        Run a script and capture output line by line.
        Returns (success, stdout, stderr).
        """
        entry_path = entry_file
        if not os.path.isabs(entry_path):
            entry_path = os.path.join(self.project_path, entry_file)

        env = {
            **os.environ,
            "FORGE_SIM": "1",
            "PYTHONPATH": self.project_path,
            "PYTHONUNBUFFERED": "1",
        }

        self._running = True
        self._output_buffer = []
        stdout_lines = []
        stderr_lines = []

        try:
            self._process = subprocess.Popen(
                ["python", entry_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.project_path,
                env=env,
                bufsize=1,  # Line buffered
            )

            # Read stdout in a thread
            def read_stdout():
                for line in iter(self._process.stdout.readline, ""):
                    if not self._running:
                        break
                    line = line.rstrip("\n")
                    stdout_lines.append(line)
                    self._add_output(f"[OUT] {line}")

            # Read stderr in a thread
            def read_stderr():
                for line in iter(self._process.stderr.readline, ""):
                    if not self._running:
                        break
                    line = line.rstrip("\n")
                    stderr_lines.append(line)
                    self._add_output(f"[ERR] {line}")

            t1 = threading.Thread(target=read_stdout, daemon=True)
            t2 = threading.Thread(target=read_stderr, daemon=True)
            t1.start()
            t2.start()

            # Wait for completion
            self._process.wait(timeout=timeout)
            t1.join(timeout=2)
            t2.join(timeout=2)

            success = self._process.returncode == 0
            return success, "\n".join(stdout_lines), "\n".join(stderr_lines)

        except subprocess.TimeoutExpired:
            self.kill()
            return False, "\n".join(stdout_lines), \
                   "\n".join(stderr_lines) + f"\nTIMEOUT: exceeded {timeout}s"
        except Exception as e:
            return False, "", str(e)
        finally:
            self._running = False

    def run_interactive(self, entry_file: str):
        """
        Start an interactive long-running process.
        Output is streamed via callbacks.
        """
        entry_path = entry_file
        if not os.path.isabs(entry_path):
            entry_path = os.path.join(self.project_path, entry_file)

        env = {
            **os.environ,
            "FORGE_SIM": "1",
            "PYTHONPATH": self.project_path,
            "PYTHONUNBUFFERED": "1",
        }

        self._running = True
        self._output_buffer = []

        try:
            self._process = subprocess.Popen(
                ["python", entry_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.project_path,
                env=env,
                bufsize=1,
            )

            def read_output():
                for line in iter(self._process.stdout.readline, ""):
                    if not self._running:
                        break
                    self._add_output(line.rstrip("\n"))

            threading.Thread(target=read_output, daemon=True).start()
        except Exception as e:
            self._add_output(f"[ERROR] {str(e)}")
            self._running = False

    def kill(self):
        """Kill the running process."""
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._running = False

    def _add_output(self, line: str):
        """Add a line to the output buffer and notify callbacks."""
        self._output_buffer.append(line)
        if len(self._output_buffer) > self.max_lines:
            self._output_buffer.pop(0)
        
        for cb in self._callbacks:
            try:
                cb(line)
            except Exception:
                pass

    def get_output(self) -> list[str]:
        """Get all buffered output lines."""
        return list(self._output_buffer)

    def clear_output(self):
        """Clear the output buffer."""
        self._output_buffer = []

    def add_callback(self, callback):
        """Add a callback for new output lines."""
        self._callbacks.append(callback)

    @property
    def is_running(self) -> bool:
        return self._running and self._process is not None \
               and self._process.poll() is None
