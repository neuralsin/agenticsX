"""
FORGE Chat Hub Panel — Center panel: multi-agent conversation feed.
Chronological feed of all agent messages with colored borders,
streaming text, filters, and special message types.
"""

import customtkinter as ctk
import tkinter as tk
from datetime import datetime
import config


class ChatMessage(ctk.CTkFrame):
    """
    Single message bubble in the chat hub.
    Features colored left border (agent color), role tag, content.
    """

    def __init__(self, parent, agent_name: str, content: str, 
                 role: str = "assistant", **kwargs):
        super().__init__(parent, **kwargs)
        
        self.agent_name = agent_name
        agent_color = config.AGENT_COLORS.get(agent_name, "#6B7280")
        
        self.configure(
            fg_color=config.THEME["bg_card"],
            corner_radius=8,
            border_width=0,
        )
        
        # Inner layout with colored left border
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=(3, 0))
        
        # Left color bar
        color_bar = ctk.CTkFrame(
            inner, fg_color=agent_color,
            width=3, corner_radius=2,
        )
        color_bar.pack(side="left", fill="y", padx=(0, 8), pady=2)
        
        # Content area
        content_area = ctk.CTkFrame(inner, fg_color="transparent")
        content_area.pack(fill="both", expand=True, padx=(0, 8), pady=6)
        
        # Header: [AGENT_NAME] timestamp
        header = ctk.CTkFrame(content_area, fg_color="transparent")
        header.pack(fill="x")
        
        ctk.CTkLabel(
            header, text=f"[{agent_name}]",
            font=config.FONTS["small"],
            text_color=agent_color,
            anchor="w",
        ).pack(side="left")
        
        # Role indicator
        if role == "system":
            role_text = "system"
            role_color = config.THEME["text_muted"]
        elif role == "user":
            role_text = "user"
            role_color = config.THEME["text_secondary"]
        else:
            role_text = "response"
            role_color = config.THEME["text_muted"]
        
        ctk.CTkLabel(
            header, text=role_text,
            font=config.FONTS["tiny"],
            text_color=role_color,
            anchor="w",
        ).pack(side="left", padx=(6, 0))
        
        # Timestamp
        ts = datetime.now().strftime("%H:%M:%S")
        ctk.CTkLabel(
            header, text=ts,
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        ).pack(side="right")
        
        # Message content
        # Determine special styling based on content
        is_code = "```" in content or content.startswith("### FILE:")
        is_debug = agent_name == "DEBUGGER" or "[DEBUG]" in content
        is_steering = "[STEERING]" in content or "[USER STEERING]" in content
        is_plan = "PLAN:" in content or content.startswith("PLAN\n")
        
        if is_steering:
            # White text on dark background
            self.configure(
                border_width=1,
                border_color="#FFFFFF",
            )
        elif is_debug:
            self.configure(
                border_width=1,
                border_color=config.THEME["error"],
            )
        
        # Content text
        self.content_label = ctk.CTkLabel(
            content_area, text=content,
            font=config.FONTS["small"] if not is_code else config.FONTS["mono_small"],
            text_color=config.THEME["text_primary"],
            anchor="w",
            justify="left",
            wraplength=500,
        )
        self.content_label.pack(fill="x", pady=(4, 0))

    def update_content(self, new_content: str):
        """Update message content (for streaming)."""
        self.content_label.configure(text=new_content)


class ChatHubPanel(ctk.CTkFrame):
    """
    Center panel — chronological multi-agent conversation feed.
    Features: agent filter buttons, search bar, streaming display.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.configure(
            fg_color=config.THEME["bg_secondary"],
            corner_radius=0,
        )
        
        self.messages = []
        self.active_filters = set()  # Empty = show all
        self.search_query = ""
        
        # ── Header with filters ──────────────────────────────────
        header = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0, height=44,
        )
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text="CONVERSATION HUB",
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
        ).pack(side="left", padx=12, pady=8)
        
        # Search bar
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            header, placeholder_text="🔍 Search messages...",
            font=config.FONTS["small"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            width=160, height=28,
            textvariable=self.search_var,
        )
        self.search_entry.pack(side="right", padx=8, pady=8)
        self.search_var.trace_add("write", self._on_search)
        
        # Filter bar
        filter_bar = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_primary"],
            corner_radius=0, height=32,
        )
        filter_bar.pack(fill="x")
        filter_bar.pack_propagate(False)
        
        self.filter_buttons = {}
        agents = ["ALL", "SUPERVISOR", "PLANNER", "CODER", "DEBUGGER", "VISION", "USER"]
        
        for agent in agents:
            color = config.AGENT_COLORS.get(agent, config.THEME["text_secondary"])
            btn = ctk.CTkButton(
                filter_bar, text=agent[:3] if agent != "ALL" else "ALL",
                font=config.FONTS["tiny"],
                fg_color="transparent",
                text_color=color if agent != "ALL" else config.THEME["text_primary"],
                hover_color=config.THEME["bg_tertiary"],
                width=40, height=24,
                corner_radius=4,
                command=lambda a=agent: self._toggle_filter(a),
            )
            btn.pack(side="left", padx=2, pady=4)
            self.filter_buttons[agent] = btn
        
        # ── Messages area (scrollable) ──────────────────────────
        self.messages_container = ctk.CTkScrollableFrame(
            self, fg_color=config.THEME["bg_primary"],
            scrollbar_button_color=config.THEME["border"],
            scrollbar_button_hover_color=config.THEME["border_light"],
        )
        self.messages_container.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Welcome message
        self._add_system_message(
            "FORGE is ready. Set a project goal and press ▶ START to begin."
        )

    def add_message(self, agent_name: str, content: str, 
                    role: str = "assistant"):
        """Add a new message to the feed."""
        # Check if this message should be visible (filter check)
        if self.active_filters and agent_name not in self.active_filters:
            # Store but don't display
            self.messages.append({
                "agent": agent_name, "content": content,
                "role": role, "widget": None, "visible": False,
            })
            return
        
        # Create message widget
        msg_widget = ChatMessage(
            self.messages_container, agent_name, content, role,
        )
        msg_widget.pack(fill="x", padx=6, pady=3)
        
        self.messages.append({
            "agent": agent_name, "content": content,
            "role": role, "widget": msg_widget, "visible": True,
        })
        
        # Auto-scroll to bottom
        self.messages_container._parent_canvas.yview_moveto(1.0)
        
        # Limit message widgets to prevent memory issues
        if len(self.messages) > 200:
            old = self.messages.pop(0)
            if old["widget"]:
                old["widget"].destroy()

    def _add_system_message(self, text: str):
        """Add a system-level message."""
        self.add_message("SYSTEM", text, "system")

    def _toggle_filter(self, agent_name: str):
        """Toggle agent filter."""
        if agent_name == "ALL":
            self.active_filters.clear()
            # Reset all button styles
            for name, btn in self.filter_buttons.items():
                color = config.AGENT_COLORS.get(name, config.THEME["text_secondary"])
                if name == "ALL":
                    btn.configure(fg_color=config.THEME["accent"])
                else:
                    btn.configure(fg_color="transparent")
        else:
            if agent_name in self.active_filters:
                self.active_filters.discard(agent_name)
            else:
                self.active_filters.add(agent_name)
            
            # Update button styles
            self.filter_buttons["ALL"].configure(fg_color="transparent")
            for name, btn in self.filter_buttons.items():
                if name == "ALL":
                    continue
                if name in self.active_filters:
                    btn.configure(fg_color=config.THEME["bg_tertiary"])
                else:
                    btn.configure(fg_color="transparent")
        
        self._refresh_visibility()

    def _refresh_visibility(self):
        """Refresh message visibility based on active filters."""
        for msg_data in self.messages:
            widget = msg_data.get("widget")
            if widget is None:
                continue
            
            should_show = (not self.active_filters or 
                          msg_data["agent"] in self.active_filters)
            
            if should_show and not msg_data["visible"]:
                widget.pack(fill="x", padx=6, pady=3)
                msg_data["visible"] = True
            elif not should_show and msg_data["visible"]:
                widget.pack_forget()
                msg_data["visible"] = False

    def _on_search(self, *args):
        """Handle search input changes."""
        query = self.search_var.get().strip().lower()
        self.search_query = query
        
        for msg_data in self.messages:
            widget = msg_data.get("widget")
            if widget is None:
                continue
            
            if not query:
                # Show based on filter only
                should_show = (not self.active_filters or 
                              msg_data["agent"] in self.active_filters)
            else:
                # Show if matches search AND filter
                matches_search = query in msg_data["content"].lower()
                matches_filter = (not self.active_filters or 
                                 msg_data["agent"] in self.active_filters)
                should_show = matches_search and matches_filter
            
            if should_show and not msg_data["visible"]:
                widget.pack(fill="x", padx=6, pady=3)
                msg_data["visible"] = True
            elif not should_show and msg_data["visible"]:
                widget.pack_forget()
                msg_data["visible"] = False

    def clear(self):
        """Clear all messages."""
        for msg_data in self.messages:
            if msg_data["widget"]:
                msg_data["widget"].destroy()
        self.messages.clear()
