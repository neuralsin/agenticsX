"""
FORGE Agent Team Panel — Left panel showing 5 agent cards with live status.
Each card: name, model, status dot (animated), token counters, sparkline.
"""

import customtkinter as ctk
import tkinter as tk
from gui.widgets.agent_badge import AgentBadge
from gui.widgets.token_meter import TokenMeter
import config


class AgentCard(ctk.CTkFrame):
    """
    Individual agent card showing:
    - Agent name + model
    - Status badge (animated pulse)
    - Token count (total)
    - Mini sparkline of last 10 calls
    - Click to expand: details
    """

    def __init__(self, parent, agent_name: str, **kwargs):
        super().__init__(parent, **kwargs)

        self.agent_name = agent_name
        # Pull info from the nested DEFAULT_AGENT_MODELS dict
        _info = config.DEFAULT_AGENT_MODELS.get(agent_name, {})
        self.agent_info = {
            "model": _info.get("display_name", _info.get("model_id", "Unknown")),
            "speed": _info.get("speed", ""),
        }
        self.agent_color = config.AGENT_COLORS.get(agent_name, "#7C3AED")
        self.expanded = False
        self.tokens_history = []
        
        self.configure(
            fg_color=config.THEME["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=config.THEME["border"],
        )
        
        # ── Main content ─────────────────────────────────────────
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="x", padx=10, pady=8)
        
        # Top row: color dot + name + status
        top_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        top_row.pack(fill="x")
        
        # Color indicator dot
        self.color_dot = ctk.CTkLabel(
            top_row, text="◉",
            font=("Segoe UI", 14),
            text_color=self.agent_color,
            width=20,
        )
        self.color_dot.pack(side="left")
        
        # Agent name
        self.name_label = ctk.CTkLabel(
            top_row, text=agent_name,
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
            anchor="w",
        )
        self.name_label.pack(side="left", padx=(4, 0))
        
        # Status badge
        self.badge = AgentBadge(top_row, agent_name)
        self.badge.pack(side="right")
        
        # Model name row
        model_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        model_row.pack(fill="x", pady=(2, 0))
        
        model_name = self.agent_info.get("model", "Unknown")
        self.model_label = ctk.CTkLabel(
            model_row, text=model_name,
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
            anchor="w",
        )
        self.model_label.pack(side="left", padx=(24, 0))
        
        speed = self.agent_info.get("speed", "")
        if speed:
            self.speed_label = ctk.CTkLabel(
                model_row, text=speed,
                font=config.FONTS["tiny"],
                text_color=config.THEME["text_muted"],
                anchor="e",
            )
            self.speed_label.pack(side="right")
        
        # Token stats row
        stats_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        stats_row.pack(fill="x", pady=(6, 0))
        
        self.token_label = ctk.CTkLabel(
            stats_row, text="0 tokens",
            font=config.FONTS["small"],
            text_color=self.agent_color,
            anchor="w",
        )
        self.token_label.pack(side="left", padx=(24, 0))
        
        self.calls_label = ctk.CTkLabel(
            stats_row, text="0 calls",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
            anchor="e",
        )
        self.calls_label.pack(side="right")
        
        # Sparkline canvas
        self.sparkline_canvas = tk.Canvas(
            self.main_frame, height=20, 
            bg=config.THEME["bg_card"],
            highlightthickness=0,
        )
        self.sparkline_canvas.pack(fill="x", padx=(24, 0), pady=(4, 0))

        # Live activity text (shows what agent is doing right now)
        self.activity_label = ctk.CTkLabel(
            self.main_frame,
            text="",
            font=config.FONTS["tiny"],
            text_color=self.agent_color,
            anchor="w",
            wraplength=200,
        )
        self.activity_label.pack(fill="x", padx=(24, 0), pady=(2, 0))
        self.activity_label.pack_forget()  # Hidden until there's activity
        
        # ── Expandable details (hidden by default) ───────────────
        self.details_frame = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0,
        )
        # Not packed initially
        
        self.detail_text = ctk.CTkLabel(
            self.details_frame,
            text="Last in: 0 | Last out: 0 | Time: 0.0s",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_secondary"],
            wraplength=200,
            justify="left",
        )
        self.detail_text.pack(padx=10, pady=6, anchor="w")
        
        # Click to expand
        self.bind("<Button-1>", self._toggle_expand)
        self.main_frame.bind("<Button-1>", self._toggle_expand)
        for child in self.main_frame.winfo_children():
            child.bind("<Button-1>", self._toggle_expand)


    def _toggle_expand(self, event=None):
        """Toggle the expanded details section."""
        self.expanded = not self.expanded
        if self.expanded:
            self.details_frame.pack(fill="x", padx=1, pady=(0, 1))
        else:
            self.details_frame.pack_forget()

    def update_stats(self, stats: dict):
        """Update the card with new agent statistics."""
        # Update status badge
        status = stats.get("status", "idle")
        self.badge.set_status(status)
        
        # Visual glow when thinking — highlight the card border
        if status == "thinking":
            self.configure(border_color=self.agent_color)
        else:
            self.configure(border_color=config.THEME["border"])

        # Show/update live activity text
        last_error = stats.get("last_error", "")
        if status == "thinking":
            self.activity_label.configure(text="Reasoning...")
            self.activity_label.pack(fill="x", padx=(24, 0), pady=(2, 0))
        elif status == "error" and last_error:
            self.activity_label.configure(
                text=f"Error: {last_error[:80]}",
                text_color=config.THEME["error"],
            )
            self.activity_label.pack(fill="x", padx=(24, 0), pady=(2, 0))
        elif stats.get("calls", 0) > 0:
            resp_time = stats.get("last_response_time", 0)
            self.activity_label.configure(
                text=f"Last call: {resp_time:.1f}s",
                text_color=self.agent_color,
            )
            self.activity_label.pack(fill="x", padx=(24, 0), pady=(2, 0))
        else:
            self.activity_label.pack_forget()

        # Update token count
        total = stats.get("tokens_total", 0)
        if total >= 1000:
            token_text = f"{total/1000:.1f}K tokens"
        else:
            token_text = f"{total} tokens"
        self.token_label.configure(text=token_text)
        
        # Update call count
        calls = stats.get("calls", 0)
        self.calls_label.configure(text=f"{calls} calls")
        
        # Update detail text
        last_in = stats.get("tokens_last_in", 0)
        last_out = stats.get("tokens_last_out", 0)
        resp_time = stats.get("last_response_time", 0.0)
        self.detail_text.configure(
            text=f"Last in: {last_in} | Last out: {last_out} | "
                 f"Time: {resp_time:.1f}s\n"
                 f"Error: {stats.get('last_error', 'none')[:100]}"
        )
        
        # Update sparkline
        history = stats.get("tokens_history", [])
        if history:
            self._draw_sparkline(history)


    def _draw_sparkline(self, values: list):
        """Draw a mini sparkline chart of token usage."""
        self.sparkline_canvas.delete("all")
        
        if not values or len(values) < 2:
            return
        
        w = self.sparkline_canvas.winfo_width()
        h = 18
        
        if w <= 10:
            w = 180  # Default width before render
        
        max_val = max(values) if max(values) > 0 else 1
        step = w / (len(values) - 1) if len(values) > 1 else w
        
        points = []
        for i, val in enumerate(values):
            x = i * step
            y = h - (val / max_val) * (h - 2)
            points.append((x, y))
        
        # Draw line
        if len(points) >= 2:
            flat_points = []
            for x, y in points:
                flat_points.extend([x, y])
            self.sparkline_canvas.create_line(
                *flat_points,
                fill=self.agent_color,
                width=1.5,
                smooth=True,
            )
        
        # Draw dots at each point
        for x, y in points:
            self.sparkline_canvas.create_oval(
                x - 2, y - 2, x + 2, y + 2,
                fill=self.agent_color, outline="",
            )


class AgentTeamPanel(ctk.CTkFrame):
    """
    Left panel containing 5 agent cards with live status.
    Shows all agents in the team with their current state.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.configure(
            fg_color=config.THEME["bg_secondary"],
            corner_radius=0,
            width=260,
        )
        
        # Panel header
        header = ctk.CTkFrame(self, fg_color="transparent", height=40)
        header.pack(fill="x", padx=12, pady=(12, 8))
        
        ctk.CTkLabel(
            header, text="AGENT TEAM",
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
        ).pack(side="left")
        
        # Team status indicator
        self.team_status = ctk.CTkLabel(
            header, text="● Ready",
            font=config.FONTS["tiny"],
            text_color=config.THEME["success"],
        )
        self.team_status.pack(side="right")
        
        # Scrollable agent cards container
        self.cards_container = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=config.THEME["border"],
            scrollbar_button_hover_color=config.THEME["border_light"],
        )
        self.cards_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        
        # Create agent cards (all 7 agents)
        self.agent_cards = {}
        agent_order = [
            "SUPERVISOR", "PLANNER", "CODER",
            "DEBUGGER", "VISION", "AUDITOR", "TESTER"
        ]
        
        for agent_name in agent_order:
            card = AgentCard(
                self.cards_container, agent_name,
            )
            card.pack(fill="x", pady=(0, 6))
            self.agent_cards[agent_name] = card
        
        # AirLLM model load progress
        self.load_frame = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=8, height=40,
        )
        self.load_frame.pack(fill="x", padx=8, pady=(0, 8))
        
        self.load_label = ctk.CTkLabel(
            self.load_frame, text="AirLLM: Not loaded",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        self.load_label.pack(side="left", padx=8, pady=4)
        
        self.load_progress = ctk.CTkProgressBar(
            self.load_frame, height=6,
            corner_radius=3,
            progress_color=config.AGENT_COLORS["SUPERVISOR"],
            fg_color=config.THEME["bg_primary"],
        )
        self.load_progress.pack(fill="x", padx=8, pady=(0, 6))
        self.load_progress.set(0)

    def update_agent(self, agent_name: str, stats: dict):
        """Update a specific agent card."""
        if agent_name in self.agent_cards:
            self.agent_cards[agent_name].update_stats(stats)

    def update_all(self, all_stats: dict):
        """Update all agent cards from a stats dict."""
        for agent_name, stats in all_stats.items():
            self.update_agent(agent_name, stats)

    def set_agent_status(self, agent_name: str, status: str):
        """Set just the status for an agent."""
        if agent_name in self.agent_cards:
            self.agent_cards[agent_name].badge.set_status(status)
        
        # Update team status
        any_thinking = any(
            card.badge.status_label.cget("text").endswith("thinking")
            for card in self.agent_cards.values()
        )
        if any_thinking:
            self.team_status.configure(text="● Working", 
                                       text_color=config.THEME["accent"])
        else:
            self.team_status.configure(text="● Ready",
                                       text_color=config.THEME["success"])

    def update_load_progress(self, progress: float, message: str):
        """Update AirLLM model loading progress."""
        self.load_progress.set(progress)
        self.load_label.configure(text=f"AirLLM: {message}")
