"""
FORGE — Multi-Agent AI Development Studio
Entry point. Launches the CustomTkinter GUI.

A desktop GUI application that runs a team of 5 specialized local AI agents
to autonomously plan, code, debug, visually verify, and refine any software project.

Built for: 12GB RAM · RTX 4050 6GB VRAM · i5-12450HX
Runtime: AirLLM (layer-sliced inference) + Ollama (small/vision models)
Framework: Python + CustomTkinter (native desktop, no browser)
"""

import sys
import os

# Add forge root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from gui.app import ForgeApp


def main():
    """Launch the FORGE application."""
    # Set appearance
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    
    # Create root window
    root = ctk.CTk()
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
    
    # Create the FORGE application
    app = ForgeApp(root)
    
    # Start the main loop
    root.mainloop()


if __name__ == "__main__":
    main()
