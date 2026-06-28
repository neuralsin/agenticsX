"""
FORGE Agent Badge Widget — Status pill with animated pulse.
Shows agent status: thinking (animated), idle, error, waiting.
"""

import customtkinter as ctk
import config


class AgentBadge(ctk.CTkFrame):
    """
    Agent status indicator pill.
    ● thinking (animated pulse) — agent color
    ○ idle — dimmed
    ✗ error — red
    ⏳ waiting — amber, pulsing
    """

    STATUS_CONFIG = {
        "idle": {"symbol": "○", "color_key": "text_muted", "pulse": False},
        "thinking": {"symbol": "●", "color_key": None, "pulse": True},
        "error": {"symbol": "✗", "color_key": "error", "pulse": False},
        "waiting": {"symbol": "⏳", "color_key": "warning", "pulse": True},
    }

    def __init__(self, parent, agent_name: str, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.agent_name = agent_name
        self.agent_color = config.AGENT_COLORS.get(agent_name, "#7C3AED")
        self._pulse_active = False
        self._pulse_state = True
        self._pulse_id = None
        
        self.configure(
            fg_color=config.THEME["bg_tertiary"],
            corner_radius=12,
            height=24,
        )
        
        # Status indicator
        self.status_label = ctk.CTkLabel(
            self,
            text="○ idle",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
            padx=8,
            pady=2,
        )
        self.status_label.pack(fill="x", padx=2, pady=1)

    def set_status(self, status: str):
        """Update the badge to reflect a new status."""
        cfg = self.STATUS_CONFIG.get(status, self.STATUS_CONFIG["idle"])
        
        # Determine color
        if cfg["color_key"]:
            color = config.THEME.get(cfg["color_key"], self.agent_color)
        else:
            color = self.agent_color
        
        # Update label
        text = f"{cfg['symbol']} {status}"
        self.status_label.configure(text=text, text_color=color)
        
        # Handle pulse animation
        if cfg["pulse"] and not self._pulse_active:
            self._start_pulse(color)
        elif not cfg["pulse"] and self._pulse_active:
            self._stop_pulse()

    def _start_pulse(self, color: str):
        """Start the pulsing animation."""
        self._pulse_active = True
        self._pulse_state = True
        self._pulse(color)

    def _stop_pulse(self):
        """Stop the pulsing animation."""
        self._pulse_active = False
        if self._pulse_id:
            try:
                self.after_cancel(self._pulse_id)
            except Exception:
                pass
            self._pulse_id = None

    def _pulse(self, color: str):
        """Animate the pulse effect by toggling opacity."""
        if not self._pulse_active:
            return
        
        self._pulse_state = not self._pulse_state
        
        if self._pulse_state:
            self.status_label.configure(text_color=color)
            self.configure(fg_color=config.THEME["bg_tertiary"])
        else:
            # Dim the text
            self.status_label.configure(text_color=config.THEME["text_muted"])
            self.configure(fg_color=config.THEME["bg_secondary"])
        
        self._pulse_id = self.after(600, lambda: self._pulse(color))

    def destroy(self):
        """Clean up pulse animation before destroying."""
        self._stop_pulse()
        super().destroy()
