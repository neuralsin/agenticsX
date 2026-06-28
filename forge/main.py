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

# ── Single-instance guard (socket-based — OS auto-releases on crash) ──────────
import socket as _socket

_LOCK_PORT   = 47392          # arbitrary port unlikely to be in use
_lock_socket = None           # kept alive as a module-level reference


def _kill_port_owner():
    """Kill any process listening on _LOCK_PORT (i.e. a stale FORGE)."""
    import subprocess, os
    try:
        # Find PID owning the port
        out = subprocess.check_output(
            f"netstat -ano | findstr :{_LOCK_PORT}",
            shell=True, text=True, stderr=subprocess.DEVNULL
        )
        for line in out.strip().splitlines():
            parts = line.split()
            if parts and parts[-1].isdigit():
                pid = int(parts[-1])
                if pid != os.getpid():
                    subprocess.call(
                        f"taskkill /F /PID {pid}",
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
    except Exception:
        pass
    import time as _time
    _time.sleep(0.5)           # let the OS release the port


def _try_bind() -> bool:
    """Attempt to bind the lock socket. Returns True on success."""
    global _lock_socket
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 0)
        s.bind(("127.0.0.1", _LOCK_PORT))
        s.listen(1)
        _lock_socket = s
        return True
    except OSError:
        return False


def _acquire_lock() -> bool:
    """
    Grab the singleton lock.
    If another FORGE is running, kill it and grab the lock.
    Returns True when we own the lock, False if something went badly wrong.
    """
    if _try_bind():
        return True                # no other instance — we own it
    # Another instance is running — kill it, then retry once
    _kill_port_owner()
    return _try_bind()


def _release_lock():
    """Close the lock socket on clean exit (crash = OS auto-releases)."""
    global _lock_socket
    if _lock_socket:
        try:
            _lock_socket.close()
        except Exception:
            pass
        _lock_socket = None







def main():
    """Launch the FORGE application."""

    # ── Single-instance guard ─────────────────────────────────────────────
    # Kills any stale/crashed FORGE on the same port and takes ownership.
    if not _acquire_lock():
        # Very unlikely — port couldn't be grabbed even after kill attempt
        import tkinter.messagebox as mb
        mb.showerror(
            "FORGE — Launch Error",
            f"Could not acquire lock on port {_LOCK_PORT}.\n"
            "Try running: taskkill /F /IM python.exe\n"
            "Then relaunch FORGE."
        )
        return

    # Register cleanup
    import atexit
    atexit.register(_release_lock)

    # Handle Ctrl+C / SIGTERM gracefully
    import signal
    def _signal_cleanup(sig, frame):
        _release_lock()
        sys.exit(0)
    try:
        signal.signal(signal.SIGINT,  _signal_cleanup)
        signal.signal(signal.SIGTERM, _signal_cleanup)
    except Exception:
        pass





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
    import traceback, datetime

    _LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forge_crash.log")

    try:
        main()
    except Exception as _exc:
        _tb = traceback.format_exc()
        _ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Write to log file next to main.py
        try:
            with open(_LOG, "a", encoding="utf-8") as _lf:
                _lf.write(f"\n{'='*60}\n{_ts}\n{_tb}\n")
        except Exception:
            pass
        # Also show in a messagebox so it's visible even without a console
        try:
            import tkinter.messagebox as _mb
            _mb.showerror(
                "FORGE — Crash",
                f"FORGE crashed with an unexpected error.\n\n"
                f"{str(_exc)[:400]}\n\n"
                f"Full traceback saved to:\n{_LOG}"
            )
        except Exception:
            pass
        _release_lock()
        sys.exit(1)
