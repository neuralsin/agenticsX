"""
FORGE Steering Bar Panel — Bottom input: user injection / steering.
Text input, RUN/PAUSE/STOP controls, steering history, quick presets.
"""

import customtkinter as ctk
import tkinter as tk
from datetime import datetime
import config


class SteeringBar(ctk.CTkFrame):
    """
    Bottom input bar for user steering injection.
    Features: text input, control buttons, quick presets, history.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.configure(
            fg_color=config.THEME["bg_tertiary"],
            corner_radius=0,
            height=64,
        )
        self.pack_propagate(False)
        
        # Callbacks
        self.on_start = None       # (goal: str) -> None
        self.on_pause = None       # () -> None
        self.on_resume = None      # () -> None
        self.on_stop = None        # () -> None
        self.on_steering = None    # (text: str) -> None
        self.on_replan = None      # () -> None
        self.on_skip = None        # () -> None
        self.on_retry = None       # () -> None
        self.on_ask_agent = None   # () -> None
        
        self.is_running = False
        self.is_paused = False
        self.steering_history = []
        
        # ── Main layout ──────────────────────────────────────────
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=8, pady=6)
        
        # ── Control buttons (left) ───────────────────────────────
        controls = ctk.CTkFrame(main, fg_color="transparent")
        controls.pack(side="left", padx=(0, 8))
        
        self.start_btn = ctk.CTkButton(
            controls, text="▶ START",
            font=config.FONTS["subheading"],
            fg_color=config.THEME["success"],
            hover_color="#047857",
            width=120, height=40,
            corner_radius=8,
            command=self._on_start,
        )
        self.start_btn.pack(side="left", padx=6)
        
        self.pause_btn = ctk.CTkButton(
            controls, text="‖ PAUSE",
            font=config.FONTS["small"],
            fg_color=config.THEME["warning"],
            hover_color="#B45309",
            width=72, height=32,
            corner_radius=6,
            command=self._on_pause,
        )
        self.pause_btn.pack(side="left", padx=2)
        
        self.stop_btn = ctk.CTkButton(
            controls, text="■ STOP",
            font=config.FONTS["small"],
            fg_color=config.THEME["error"],
            hover_color="#B91C1C",
            width=68, height=32,
            corner_radius=6,
            command=self._on_stop,
        )
        self.stop_btn.pack(side="left", padx=2)
        
        # Status indicator
        self.status_indicator = ctk.CTkLabel(
            controls, text="● IDLE",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
            width=70,
        )
        self.status_indicator.pack(side="left", padx=(8, 0))
        
        # ── Text input (center) ──────────────────────────────────
        input_frame = ctk.CTkFrame(main, fg_color="transparent")
        input_frame.pack(side="left", fill="x", expand=True, padx=4)
        
        self.text_input = ctk.CTkEntry(
            input_frame,
            placeholder_text="⚡ TYPE YOUR GOAL HERE, then press ENTER or ▶ START ⚡",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["accent"],
            text_color=config.THEME["text_primary"],
            placeholder_text_color=config.THEME["text_muted"],
            height=40,
            corner_radius=8,
            border_width=2,
        )
        self.text_input.pack(fill="x", expand=True)
        
        # Bind Shift+Enter and Enter for sending
        self.text_input.bind("<Return>", self._on_enter)
        self.text_input.bind("<Shift-Return>", self._on_shift_enter)
        
        # ── Quick presets (right) ────────────────────────────────
        presets = ctk.CTkFrame(main, fg_color="transparent")
        presets.pack(side="right", padx=(8, 0))
        
        preset_buttons = [
            ("🔄", "Replan", self._on_replan),
            ("⏩", "Skip", self._on_skip),
            ("🔁", "Retry", self._on_retry),
            ("💬", "Ask", self._on_ask_agent),
            ("📜", "History", self._show_history),
        ]
        
        for icon, tooltip, command in preset_buttons:
            btn = ctk.CTkButton(
                presets, text=icon,
                font=("Segoe UI", 13),
                fg_color="transparent",
                hover_color=config.THEME["bg_input"],
                width=32, height=32,
                corner_radius=6,
                command=command,
            )
            btn.pack(side="left", padx=1)
            # Tooltip via binding
            btn.bind("<Enter>", lambda e, t=tooltip: self._show_tooltip(e, t))
            btn.bind("<Leave>", self._hide_tooltip)
        
        # Tooltip label (hidden by default)
        self._tooltip = None

    def _on_enter(self, event=None):
        """Handle Enter key — send steering if running, start if idle."""
        text = self.text_input.get().strip()
        if not text:
            return "break"
        
        if self.is_running:
            self._send_steering(text)
        else:
            # Use as goal and start
            if self.on_start:
                self.on_start(text)
            self._set_running_state(True)
        
        self.text_input.delete(0, "end")
        return "break"

    def _on_shift_enter(self, event=None):
        """Handle Shift+Enter — always send as steering."""
        text = self.text_input.get().strip()
        if text:
            self._send_steering(text)
            self.text_input.delete(0, "end")
        return "break"

    def _send_steering(self, text: str):
        """Send a steering injection."""
        self.steering_history.append({
            "content": text,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })
        if self.on_steering:
            self.on_steering(text)

    def _on_start(self):
        """Handle START button."""
        text = self.text_input.get().strip()
        if text and self.on_start:
            self.on_start(text)
            self.text_input.delete(0, "end")
            self._set_running_state(True)
        elif not text and self.on_resume and self.is_paused:
            self.on_resume()
            self._set_running_state(True, resumed=True)

    def _on_pause(self):
        """Handle PAUSE button."""
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self.status_indicator.configure(
                text="● PAUSED",
                text_color=config.THEME["warning"],
            )
            self.start_btn.configure(text="▶ RESUME")
            if self.on_pause:
                self.on_pause()

    def _on_stop(self):
        """Handle STOP button."""
        self._set_running_state(False)
        if self.on_stop:
            self.on_stop()

    def _on_replan(self):
        """Quick preset: trigger replan."""
        if self.on_replan:
            self.on_replan()
        else:
            self._send_steering("[REPLAN] User requests replanning.")

    def _on_skip(self):
        """Quick preset: skip current step."""
        if self.on_skip:
            self.on_skip()
        else:
            self._send_steering("[SKIP] Skip current step and move to next.")

    def _on_retry(self):
        """Quick preset: retry current step."""
        if self.on_retry:
            self.on_retry()
        else:
            self._send_steering("[RETRY] Retry the current step.")

    def _on_ask_agent(self):
        """Quick preset: open direct conversation with an agent."""
        if self.on_ask_agent:
            self.on_ask_agent()

    def _set_running_state(self, running: bool, resumed: bool = False):
        """Update UI to reflect running/stopped state."""
        self.is_running = running
        self.is_paused = False
        
        if running:
            self.status_indicator.configure(
                text="● RUNNING",
                text_color=config.THEME["success"],
            )
            self.start_btn.configure(text="▶ RUNNING", 
                                      fg_color=config.THEME["bg_input"])
            self.text_input.configure(
                placeholder_text="Type to inject steering... (Enter to send)"
            )
        else:
            self.status_indicator.configure(
                text="● IDLE",
                text_color=config.THEME["text_muted"],
            )
            self.start_btn.configure(text="▶ START",
                                      fg_color=config.THEME["success"])
            self.text_input.configure(
                placeholder_text="Enter project goal and press START..."
            )

    def set_running(self, running: bool):
        """External method to set running state."""
        self._set_running_state(running)

    def _show_history(self):
        """Show steering history in a popup."""
        if not self.steering_history:
            return
        
        popup = ctk.CTkToplevel(self)
        popup.title("Steering History")
        popup.geometry("400x300")
        popup.configure(fg_color=config.THEME["bg_secondary"])
        popup.attributes("-topmost", True)
        
        scroll = ctk.CTkScrollableFrame(
            popup, fg_color=config.THEME["bg_primary"],
        )
        scroll.pack(fill="both", expand=True, padx=8, pady=8)
        
        for entry in reversed(self.steering_history):
            frame = ctk.CTkFrame(
                scroll, fg_color=config.THEME["bg_card"],
                corner_radius=6,
            )
            frame.pack(fill="x", pady=2)
            
            ctk.CTkLabel(
                frame, text=entry["timestamp"],
                font=config.FONTS["tiny"],
                text_color=config.THEME["text_muted"],
            ).pack(side="left", padx=8, pady=4)
            
            ctk.CTkLabel(
                frame, text=entry["content"],
                font=config.FONTS["small"],
                text_color=config.THEME["text_primary"],
                wraplength=300,
                justify="left",
            ).pack(side="left", padx=4, pady=4)

    def _show_tooltip(self, event, text: str):
        """Show a tooltip near the button."""
        if self._tooltip:
            self._tooltip.destroy()
        
        self._tooltip = ctk.CTkLabel(
            self,
            text=text,
            font=config.FONTS["tiny"],
            fg_color=config.THEME["bg_card"],
            corner_radius=4,
            text_color=config.THEME["text_primary"],
            padx=6, pady=2,
        )
        self._tooltip.place(
            x=event.widget.winfo_x() + event.widget.winfo_width() // 2,
            y=event.widget.winfo_y() - 20,
            anchor="s",
        )

    def _hide_tooltip(self, event=None):
        """Hide the tooltip."""
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None
