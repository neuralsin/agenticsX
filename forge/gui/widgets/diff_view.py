"""
FORGE Diff View Widget — Red/green diff display with line numbers.
Shows file diffs in a syntax-highlighted scrollable view.
"""

import customtkinter as ctk
from tkinter import font as tkfont
import config


class DiffView(ctk.CTkFrame):
    """
    Diff display widget with red deletions, green additions, 
    and dimmed unchanged lines. Includes line numbers.
    """

    COLORS = {
        "add_bg": "#0D2818",
        "add_fg": "#4ADE80",
        "add_gutter": "#166534",
        "remove_bg": "#2D0A0A",
        "remove_fg": "#F87171",
        "remove_gutter": "#991B1B",
        "unchanged_fg": "#6B6B88",
        "unchanged_bg": "transparent",
        "line_num": "#4B5563",
        "separator": "#333348",
    }

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.configure(
            fg_color=config.THEME["bg_card"],
            corner_radius=8,
        )
        
        # Header
        self.header_frame = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0, height=30,
        )
        self.header_frame.pack(fill="x", padx=1, pady=(1, 0))
        
        self.filename_label = ctk.CTkLabel(
            self.header_frame,
            text="No file selected",
            font=config.FONTS["mono_small"],
            text_color=config.THEME["text_secondary"],
            anchor="w",
        )
        self.filename_label.pack(side="left", padx=10, pady=4)
        
        self.stats_label = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
            anchor="e",
        )
        self.stats_label.pack(side="right", padx=10, pady=4)
        
        # Diff content area — using a Text widget for colored lines
        self.text_frame = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_primary"],
            corner_radius=0,
        )
        self.text_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        # Scrollable text widget
        import tkinter as tk
        
        self.text_widget = tk.Text(
            self.text_frame,
            wrap="none",
            font=("Cascadia Code", 10),
            bg=config.THEME["bg_primary"],
            fg=config.THEME["text_primary"],
            insertbackground=config.THEME["text_primary"],
            selectbackground=config.THEME["accent"],
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=4,
            state="disabled",
        )
        
        # Scrollbar
        self.scrollbar_y = tk.Scrollbar(
            self.text_frame, orient="vertical",
            command=self.text_widget.yview
        )
        self.scrollbar_x = tk.Scrollbar(
            self.text_frame, orient="horizontal",
            command=self.text_widget.xview
        )
        
        self.text_widget.configure(
            yscrollcommand=self.scrollbar_y.set,
            xscrollcommand=self.scrollbar_x.set,
        )
        
        self.scrollbar_y.pack(side="right", fill="y")
        self.scrollbar_x.pack(side="bottom", fill="x")
        self.text_widget.pack(fill="both", expand=True)
        
        # Configure text tags for diff coloring
        self.text_widget.tag_configure("add",
            foreground=self.COLORS["add_fg"],
            background=self.COLORS["add_bg"],
        )
        self.text_widget.tag_configure("remove",
            foreground=self.COLORS["remove_fg"],
            background=self.COLORS["remove_bg"],
        )
        self.text_widget.tag_configure("unchanged",
            foreground=self.COLORS["unchanged_fg"],
        )
        self.text_widget.tag_configure("line_num",
            foreground=self.COLORS["line_num"],
        )
        self.text_widget.tag_configure("header",
            foreground=config.THEME["info"],
            font=("Cascadia Code", 10, "bold"),
        )

    def set_diff(self, diff_lines: list[dict], filename: str = ""):
        """
        Display a diff.
        diff_lines: list of {type: 'add'|'remove'|'unchanged', 
                             content: str, old_line: int, new_line: int}
        """
        import tkinter as tk
        
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")
        
        if filename:
            self.filename_label.configure(text=f"📄 {filename}")
        
        adds = sum(1 for d in diff_lines if d["type"] == "add")
        removes = sum(1 for d in diff_lines if d["type"] == "remove")
        self.stats_label.configure(
            text=f"+{adds} / -{removes}" if (adds or removes) else ""
        )
        
        for line_data in diff_lines:
            line_type = line_data["type"]
            content = line_data["content"]
            old_num = line_data.get("old_line", "")
            new_num = line_data.get("new_line", "")
            
            # Format line number gutter
            old_str = f"{old_num:>4}" if old_num else "    "
            new_str = f"{new_num:>4}" if new_num else "    "
            
            # Prefix symbol
            if line_type == "add":
                prefix = "+"
                tag = "add"
            elif line_type == "remove":
                prefix = "-"
                tag = "remove"
            else:
                prefix = " "
                tag = "unchanged"
            
            line_text = f" {old_str} {new_str} {prefix} {content}\n"
            self.text_widget.insert("end", line_text, tag)
        
        self.text_widget.configure(state="disabled")

    def set_unified_diff(self, diff_text: str, filename: str = ""):
        """Display a unified diff string."""
        import tkinter as tk
        
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")
        
        if filename:
            self.filename_label.configure(text=f"📄 {filename}")
        
        adds = 0
        removes = 0
        
        for line in diff_text.split("\n"):
            if line.startswith("+++") or line.startswith("---"):
                self.text_widget.insert("end", line + "\n", "header")
            elif line.startswith("@@"):
                self.text_widget.insert("end", line + "\n", "header")
            elif line.startswith("+"):
                self.text_widget.insert("end", line + "\n", "add")
                adds += 1
            elif line.startswith("-"):
                self.text_widget.insert("end", line + "\n", "remove")
                removes += 1
            else:
                self.text_widget.insert("end", line + "\n", "unchanged")
        
        self.stats_label.configure(
            text=f"+{adds} / -{removes}" if (adds or removes) else ""
        )
        
        self.text_widget.configure(state="disabled")

    def clear(self):
        """Clear the diff view."""
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.configure(state="disabled")
        self.filename_label.configure(text="No file selected")
        self.stats_label.configure(text="")

    def set_code(self, code: str, filename: str = ""):
        """Display plain code (not a diff)."""
        import tkinter as tk
        
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")
        
        if filename:
            self.filename_label.configure(text=f"📄 {filename}")
        self.stats_label.configure(text="")
        
        for i, line in enumerate(code.split("\n"), 1):
            line_text = f" {i:>4}  {line}\n"
            self.text_widget.insert("end", line_text, "unchanged")
        
        self.text_widget.configure(state="disabled")
