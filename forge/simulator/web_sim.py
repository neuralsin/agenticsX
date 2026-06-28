"""
FORGE Web Simulator — HTML/CSS preview via pywebview or embedded browser.
Provides live web preview for Flask/FastAPI projects.
"""

import os
import threading
import subprocess
import time


class WebSimulator:
    """
    Web preview simulator for Python web applications.
    Launches the web app and opens a preview window.
    """

    def __init__(self, project_path: str, port: int = 5000):
        self.project_path = project_path
        self.port = port
        self._server_process = None
        self._webview_window = None
        self._running = False

    def start(self, entry_file: str = "app.py"):
        """Start the web server and open preview."""
        self._running = True
        
        # Start the web server
        self._start_server(entry_file)
        
        # Wait for server to be ready
        time.sleep(2)
        
        # Open preview window
        self._open_preview()

    def stop(self):
        """Stop the web server and close preview."""
        self._running = False
        
        if self._server_process and self._server_process.poll() is None:
            try:
                self._server_process.terminate()
                self._server_process.wait(timeout=5)
            except Exception:
                try:
                    self._server_process.kill()
                except Exception:
                    pass
            self._server_process = None

    def restart(self, entry_file: str = "app.py"):
        """Restart the web server (hot reload)."""
        self.stop()
        time.sleep(1)
        self.start(entry_file)

    def _start_server(self, entry_file: str):
        """Start the Python web server as a subprocess."""
        entry_path = entry_file
        if not os.path.isabs(entry_path):
            entry_path = os.path.join(self.project_path, entry_file)

        env = {**os.environ, "FLASK_ENV": "development", 
               "PYTHONPATH": self.project_path}

        try:
            self._server_process = subprocess.Popen(
                ["python", entry_path],
                cwd=self.project_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            pass

    def _open_preview(self):
        """Open a webview preview window."""
        try:
            import pywebview

            def run():
                self._webview_window = pywebview.create_window(
                    "FORGE Web Preview",
                    url=f"http://localhost:{self.port}",
                    width=800,
                    height=600,
                )
                pywebview.start()

            threading.Thread(target=run, daemon=True).start()
        except ImportError:
            # Fallback: open in default browser
            import webbrowser
            webbrowser.open(f"http://localhost:{self.port}")

    def screenshot(self, path: str):
        """Take a screenshot of the web preview."""
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(path)
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        return self._running and self._server_process is not None \
               and self._server_process.poll() is None
