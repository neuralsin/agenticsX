"""
FORGE Token Meter Widget — Animated token counter with fill bar.
Shows per-agent token usage with color-coded progress.
"""

import customtkinter as ctk
import config


class TokenMeter(ctk.CTkFrame):
    """
    Animated token meter widget.
    Shows a colored progress bar with label and count.
    Turns orange at 80%, red at 95%.
    """

    def __init__(self, parent, agent_name: str, max_tokens: int = 4096,
                 **kwargs):
        super().__init__(parent, **kwargs)
        
        self.agent_name = agent_name
        self.max_tokens = max_tokens
        self.current_tokens = 0
        self.color = config.AGENT_COLORS.get(agent_name, "#7C3AED")
        
        self.configure(
            fg_color="transparent",
            height=28,
        )
        
        # Layout
        self.grid_columnconfigure(1, weight=1)
        
        # Agent name label
        self.name_label = ctk.CTkLabel(
            self,
            text=agent_name[:4],
            font=config.FONTS["tiny"],
            text_color=self.color,
            width=42,
            anchor="w",
        )
        self.name_label.grid(row=0, column=0, padx=(0, 4))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=10,
            corner_radius=3,
            progress_color=self.color,
            fg_color=config.THEME["bg_tertiary"],
        )
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.progress_bar.set(0)
        
        # Token count label
        self.count_label = ctk.CTkLabel(
            self,
            text="0",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
            width=70,
            anchor="e",
        )
        self.count_label.grid(row=0, column=2)

    def update_value(self, tokens: int, animate: bool = True):
        """Update the token meter value."""
        self.current_tokens = tokens
        ratio = min(1.0, tokens / self.max_tokens) if self.max_tokens > 0 else 0
        
        # Update color based on usage level
        if ratio >= 0.95:
            bar_color = config.THEME["error"]
        elif ratio >= 0.80:
            bar_color = config.THEME["warning"]
        else:
            bar_color = self.color
        
        self.progress_bar.configure(progress_color=bar_color)
        self.progress_bar.set(ratio)
        
        # Format count: "2.4K / 4.8K"
        def fmt(n):
            if n >= 1000:
                return f"{n/1000:.1f}K"
            return str(n)
        
        self.count_label.configure(
            text=f"{fmt(tokens)}/{fmt(self.max_tokens)}"
        )

    def set_max(self, max_tokens: int):
        """Update the maximum token budget."""
        self.max_tokens = max_tokens
        self.update_value(self.current_tokens)
