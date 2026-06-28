"""
FORGE — Multi-Agent AI Development Studio
Entry point. Launches the CustomTkinter GUI.

A desktop GUI application that runs a team of 7 specialized AI agents
to autonomously plan, code, debug, visually verify, and refine any software project.

Built for: 12GB RAM · RTX 4050 6GB VRAM · i5-12450HX
Runtime: AirLLM (layer-sliced inference) + Ollama (small/vision models)
Framework: Python + CustomTkinter (native desktop, no browser)
"""

import sys
import os

# ── MUST be first: add forge root to Python path ──────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── MUST be before any CTk widget import: set theme ───────────────────────────
# This prevents the phantom purple "dark-blue" default window from appearing.
import customtkinter as ctk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")  # base theme (overridden by our Obsidian config)

# ── Single-instance guard ─────────────────────────────────────────────────────
import tempfile
import atexit

_LOCK_FILE = os.path.join(tempfile.gettempdir(), "forge_running.lock")

def _is_already_running() -> bool:
    """Return True if another FORGE instance holds the lock file."""
    if not os.path.exists(_LOCK_FILE):
        return False
    try:
        with open(_LOCK_FILE, "r") as f:
            pid = int(f.read().strip())
        # Check if that PID is still alive
        import psutil
        if psutil.pid_exists(pid) and pid != os.getpid():
            return True
    except Exception:
        pass
    return False

def _write_lock():
    """Write our PID to the lock file."""
    try:
        with open(_LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

def _remove_lock():
    """Remove the lock file on clean exit."""
    try:
        if os.path.exists(_LOCK_FILE):
            os.remove(_LOCK_FILE)
    except Exception:
        pass


def main():
    """Launch the FORGE application."""

    # ── Single-instance guard ─────────────────────────────────────────────
    if _is_already_running():
        # Show a small warning instead of a second window
        import tkinter.messagebox as mb
        mb.showwarning(
            "FORGE Already Running",
            "A FORGE instance is already open.\n"
            "Close the existing window before starting a new one."
        )
        return

    _write_lock()
    atexit.register(_remove_lock)

    # ── Create the single root window ─────────────────────────────────────
    root = ctk.CTk()

    # Apply our Obsidian background IMMEDIATELY so there is no flash of the
    # default dark-blue purple theme between window creation and app init.
    from config import THEME
    root.configure(fg_color=THEME["bg_primary"])   # "#0A0A0B" — obsidian black
    root.title("FORGE — Multi-Agent AI Studio")
    root.geometry("1600x900")
    root.minsize(1200, 700)

    # Set window icon (if available)
    try:
        icon_path = os.path.join(os.path.dirname(__file__), "forge_icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    # ── Boot the application ──────────────────────────────────────────────
    from gui.app import ForgeApp  # imported here, after root exists
    app = ForgeApp(root)

    # ── Enter the GUI event loop ──────────────────────────────────────────
    root.mainloop()


if __name__ == "__main__":
    main()
