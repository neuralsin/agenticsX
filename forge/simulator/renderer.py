"""
FORGE Project Renderer — Multi-mode output renderer.
Supports: ESP32/ILI9341, Terminal, Web, Desktop, None.
Handles screenshot capture and subprocess management.
"""

import os
import subprocess
import threading
import time

import config


class ProjectRenderer:
    """
    Renders project output in multiple modes.
    Manages preview windows and screenshot capture.
    """

    MODES = config.RENDER_MODES

    def __init__(self, project_path: str, mode: str = None):
        self.project_path = project_path
        self.mode = mode or config.DEFAULT_RENDER_MODE
        self.screenshot_dir = os.path.join(project_path, ".forge", "frames")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.frame_count = 0
        self._process = None
        self._running = False
        self._frames = []  # Last N frame paths for history

    def start(self):
        """Start the renderer in the current mode."""
        self._running = True
        if self.mode == "esp32":
            self._start_esp32_sim()
        elif self.mode == "terminal":
            self._start_terminal_capture()
        elif self.mode == "web":
            self._start_web_preview()
        elif self.mode == "desktop":
            pass  # Desktop mode waits for explicit run
        # "none" mode does nothing

    def stop(self):
        """Stop the renderer and clean up."""
        self._running = False
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def set_mode(self, mode: str):
        """Change render mode. Stops current renderer first."""
        if mode not in self.MODES:
            return
        self.stop()
        self.mode = mode

    def screenshot(self, label: str = "") -> str:
        """Take a screenshot of the current render."""
        self.frame_count += 1
        filename = f"frame_{self.frame_count:04d}"
        if label:
            filename += f"_{label}"
        filename += ".png"
        path = os.path.join(self.screenshot_dir, filename)

        try:
            if self.mode == "esp32":
                self._screenshot_pygame(path)
            elif self.mode in ("terminal", "desktop"):
                self._screenshot_subprocess_window(path)
            elif self.mode == "web":
                self._screenshot_webview(path)
            else:
                self._screenshot_desktop(path)
        except Exception:
            # Fallback: desktop screenshot
            self._screenshot_desktop(path)

        if os.path.exists(path):
            self._frames.append(path)
            if len(self._frames) > 10:
                self._frames.pop(0)

        return path if os.path.exists(path) else ""

    def run_project(self, entry_file: str, 
                    timeout: int = None) -> tuple[bool, str, str]:
        """Run the project entry point, capture output."""
        if timeout is None:
            timeout = config.EXEC_TIMEOUT
        
        env = {**os.environ, "FORGE_SIM": "1", "PYTHONPATH": self.project_path}
        
        entry_path = entry_file
        if not os.path.isabs(entry_path):
            entry_path = os.path.join(self.project_path, entry_file)

        try:
            result = subprocess.run(
                ["python", entry_path],
                capture_output=True, text=True, timeout=timeout,
                cwd=self.project_path, env=env
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", f"TIMEOUT: process ran over {timeout}s limit"
        except FileNotFoundError:
            return False, "", "Python interpreter not found"
        except Exception as e:
            return False, "", str(e)

    def get_frame_history(self) -> list[str]:
        """Get the last N frame paths for thumbnail strip."""
        return list(self._frames)

    # ─── Mode-specific implementations ───────────────────────────────────────────

    def _start_esp32_sim(self):
        """Start ESP32/ILI9341 simulator (240x320 at 3x scale)."""
        try:
            import pygame
            pygame.init()
            self._pygame_surface = pygame.display.set_mode((240 * 3, 320 * 3))
            pygame.display.set_caption("FORGE — ESP32 ILI9341 Simulator")
            # Fill with black
            self._pygame_surface.fill((0, 0, 0))
            pygame.display.flip()
        except ImportError:
            pass  # Pygame not available

    def _start_terminal_capture(self):
        """Start terminal output capture mode."""
        # Terminal mode captures subprocess output directly
        pass

    def _start_web_preview(self):
        """Start web preview using pywebview."""
        try:
            import pywebview

            def run():
                window = pywebview.create_window(
                    "FORGE Web Preview",
                    url="http://localhost:5000",
                    width=800, height=600
                )
                pywebview.start()

            threading.Thread(target=run, daemon=True).start()
        except ImportError:
            pass  # pywebview not available

    def _screenshot_pygame(self, path: str):
        """Capture pygame window to file."""
        try:
            import pygame
            if hasattr(self, '_pygame_surface') and self._pygame_surface:
                pygame.image.save(self._pygame_surface, path)
        except Exception:
            self._screenshot_desktop(path)

    def _screenshot_subprocess_window(self, path: str):
        """Capture a subprocess window screenshot."""
        self._screenshot_desktop(path)

    def _screenshot_webview(self, path: str):
        """Capture webview window screenshot."""
        self._screenshot_desktop(path)

    def _screenshot_desktop(self, path: str):
        """Capture the full desktop as fallback."""
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(path)
        except Exception:
            pass  # PIL not available or no display

    @property
    def is_running(self) -> bool:
        return self._running
