"""
FORGE Log Stream Widget — Scrolling log with color coding.
Displays timestamped, color-coded log entries with auto-scroll.
"""

import customtkinter as ctk
import tkinter as tk
from datetime import datetime
import config


class LogStream(ctk.CTkFrame):
    """
    Scrolling log display with color-coded entries.
    Supports agent-colored messages, timestamps, and auto-scroll.
    """

    def __init__(self, parent, max_entries: int = 500, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.max_entries = max_entries
        self.entry_count = 0
        self.auto_scroll = True
        
        self.configure(
            fg_color=config.THEME["bg_primary"],
            corner_radius=6,
        )
        
        # Text widget for log display
        self.text_widget = tk.Text(
            self,
            wrap="word",
            font=("Cascadia Code", 9),
            bg=config.THEME["bg_primary"],
            fg=config.THEME["text_primary"],
            insertbackground=config.THEME["text_primary"],
            selectbackground=config.THEME["accent"],
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=4,
            state="disabled",
            cursor="arrow",
        )
        
        # Scrollbar
        self.scrollbar = tk.Scrollbar(
            self, orient="vertical",
            command=self.text_widget.yview,
        )
        self.text_widget.configure(yscrollcommand=self._on_scroll)
        
        self.scrollbar.pack(side="right", fill="y")
        self.text_widget.pack(fill="both", expand=True)
        
        # Configure tags for each agent color
        for agent_name, color in config.AGENT_COLORS.items():
            self.text_widget.tag_configure(
                f"agent_{agent_name}",
                foreground=color,
                font=("Cascadia Code", 9, "bold"),
            )
            self.text_widget.tag_configure(
                f"content_{agent_name}",
                foreground=config.THEME["text_primary"],
                lmargin1=20,
                lmargin2=20,
            )
        
        # Special tags
        self.text_widget.tag_configure("timestamp",
            foreground=config.THEME["text_muted"],
            font=("Cascadia Code", 8),
        )
        self.text_widget.tag_configure("system",
            foreground=config.THEME["text_secondary"],
            font=("Cascadia Code", 9, "italic"),
        )
        self.text_widget.tag_configure("error",
            foreground=config.THEME["error"],
        )
        self.text_widget.tag_configure("steering",
            foreground="#FFFFFF",
            background="#333348",
            font=("Cascadia Code", 9, "bold"),
        )
        self.text_widget.tag_configure("separator",
            foreground=config.THEME["border"],
        )

    def add_entry(self, agent_name: str, content: str, role: str = "assistant"):
        """Add a log entry with agent coloring."""
        self.text_widget.configure(state="normal")
        
        # Prune old entries if needed
        if self.entry_count >= self.max_entries:
            self.text_widget.delete("1.0", "3.0")
        
        # Timestamp
        ts = datetime.now().strftime("%H:%M:%S")
        self.text_widget.insert("end", f"  {ts} ", "timestamp")
        
        # Agent name tag
        agent_tag = f"agent_{agent_name}"
        if agent_name not in config.AGENT_COLORS:
            agent_tag = "system"
        
        self.text_widget.insert("end", f"[{agent_name}] ", agent_tag)
        
        # Content with appropriate tag
        if role == "system":
            self.text_widget.insert("end", content, "system")
        elif "[STEERING]" in content:
            self.text_widget.insert("end", content, "steering")
        elif "[ERROR]" in content or "[ERR]" in content:
            self.text_widget.insert("end", content, "error")
        else:
            content_tag = f"content_{agent_name}"
            if content_tag not in [str(t) for t in self.text_widget.tag_names()]:
                content_tag = "system"
            self.text_widget.insert("end", content, content_tag)
        
        self.text_widget.insert("end", "\n")
        
        self.entry_count += 1
        self.text_widget.configure(state="disabled")
        
        # Auto-scroll to bottom
        if self.auto_scroll:
            self.text_widget.see("end")

    def add_separator(self):
        """Add a visual separator line."""
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", 
            "  " + "─" * 60 + "\n", "separator")
        self.text_widget.configure(state="disabled")

    def clear(self):
        """Clear all log entries."""
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.configure(state="disabled")
        self.entry_count = 0

    def _on_scroll(self, *args):
        """Handle scroll events to toggle auto-scroll."""
        self.scrollbar.set(*args)
        # If user scrolled up, disable auto-scroll
        if float(args[1]) < 1.0:
            self.auto_scroll = False
        else:
            self.auto_scroll = True

    def search(self, query: str) -> int:
        """
        Search for text in the log. Highlights matches.
        Returns number of matches found.
        """
        self.text_widget.tag_remove("search_highlight", "1.0", "end")
        
        if not query:
            return 0
        
        self.text_widget.tag_configure("search_highlight",
            background="#7C3AED",
            foreground="#FFFFFF",
        )
        
        count = 0
        start = "1.0"
        while True:
            pos = self.text_widget.search(query, start, "end", nocase=True)
            if not pos:
                break
            end_pos = f"{pos}+{len(query)}c"
            self.text_widget.tag_add("search_highlight", pos, end_pos)
            start = end_pos
            count += 1
        
        return count
