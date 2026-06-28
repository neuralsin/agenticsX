"""
FORGE Code Editor Panel — Right panel top: file tree + diff view.
Shows project files, proposed changes with red/green diff,
and action buttons (APPLY, REJECT, EDIT MANUALLY).
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os

from gui.widgets.diff_view import DiffView
import config


class FileTreeView(ctk.CTkFrame):
    """
    Project file tree using tkinter Treeview.
    Displays hierarchical file structure with icons.
    """

    def __init__(self, parent, on_file_select=None, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.on_file_select = on_file_select
        
        self.configure(
            fg_color=config.THEME["bg_primary"],
            corner_radius=6,
        )
        
        # Style the treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Forge.Treeview",
            background=config.THEME["bg_primary"],
            foreground=config.THEME["text_primary"],
            fieldbackground=config.THEME["bg_primary"],
            borderwidth=0,
            font=("Cascadia Code", 9),
            rowheight=22,
        )
        style.configure("Forge.Treeview.Heading",
            background=config.THEME["bg_tertiary"],
            foreground=config.THEME["text_secondary"],
            borderwidth=0,
        )
        style.map("Forge.Treeview",
            background=[("selected", config.THEME["accent"])],
            foreground=[("selected", "#FFFFFF")],
        )
        
        # Treeview widget
        self.tree = ttk.Treeview(
            self, style="Forge.Treeview",
            show="tree",
            selectmode="browse",
        )
        
        scrollbar = tk.Scrollbar(self, orient="vertical", 
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def load_tree(self, tree_data: list[dict], parent_id: str = ""):
        """
        Load a file tree structure.
        tree_data: list of {name, path, is_dir, children}
        """
        # Clear existing
        for item in self.tree.get_children(parent_id):
            self.tree.delete(item)
        
        for entry in tree_data:
            icon = "📁" if entry["is_dir"] else self._get_file_icon(entry["name"])
            item_id = self.tree.insert(
                parent_id, "end",
                text=f" {icon} {entry['name']}",
                values=(entry["path"],),
                open=entry["is_dir"],
            )
            if entry["is_dir"] and entry.get("children"):
                self.load_tree(entry["children"], item_id)

    def refresh_from_path(self, project_path: str):
        """Refresh the tree from a filesystem path."""
        from core.file_watcher import FileWatcher
        watcher = FileWatcher(project_path)
        tree_data = watcher.get_project_tree()
        self.load_tree(tree_data)

    def highlight_file(self, filepath: str):
        """Highlight a specific file in the tree."""
        for item in self._get_all_items():
            values = self.tree.item(item, "values")
            if values and values[0] == filepath:
                self.tree.selection_set(item)
                self.tree.see(item)
                break

    def mark_changed(self, filepath: str):
        """Mark a file as changed (add ✏️ indicator)."""
        for item in self._get_all_items():
            values = self.tree.item(item, "values")
            if values and values[0] == filepath:
                current_text = self.tree.item(item, "text")
                if "✏️" not in current_text:
                    self.tree.item(item, text=f"{current_text} ✏️")
                break

    def _on_select(self, event):
        """Handle file selection."""
        selection = self.tree.selection()
        if selection and self.on_file_select:
            values = self.tree.item(selection[0], "values")
            if values:
                self.on_file_select(values[0])

    def _get_all_items(self, parent=""):
        """Get all tree items recursively."""
        items = []
        for item in self.tree.get_children(parent):
            items.append(item)
            items.extend(self._get_all_items(item))
        return items

    def _get_file_icon(self, filename: str) -> str:
        """Get an icon for a file based on extension."""
        ext = os.path.splitext(filename)[1].lower()
        icons = {
            ".py": "🐍", ".js": "📜", ".ts": "📘", ".html": "🌐",
            ".css": "🎨", ".json": "📋", ".md": "📝", ".txt": "📄",
            ".yaml": "⚙️", ".yml": "⚙️", ".toml": "⚙️", ".cfg": "⚙️",
            ".ini": "⚙️", ".sh": "🖥️", ".bat": "🖥️", ".sql": "🗃️",
            ".png": "🖼️", ".jpg": "🖼️", ".svg": "🖼️", ".gif": "🖼️",
        }
        return icons.get(ext, "📄")


class CodeEditorPanel(ctk.CTkFrame):
    """
    Right panel top — Code editor with file tree and diff view.
    Shows proposed changes, action buttons, and changed files list.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.configure(
            fg_color=config.THEME["bg_secondary"],
            corner_radius=0,
        )
        
        self.changed_files = []
        self.pending_change = None  # Current proposed change awaiting action
        self.on_apply = None
        self.on_reject = None
        self.on_edit = None
        
        # ── Header ───────────────────────────────────────────────
        header = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0, height=44,
        )
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text="CODE EDITOR",
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
        ).pack(side="left", padx=12, pady=8)
        
        self.source_label = ctk.CTkLabel(
            header, text="",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        self.source_label.pack(side="right", padx=12, pady=8)
        
        # ── Main content: file tree (left) + diff view (right) ───
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=1, minsize=150)
        content.grid_columnconfigure(1, weight=3)
        content.grid_rowconfigure(0, weight=1)
        
        # File tree
        tree_frame = ctk.CTkFrame(
            content, fg_color=config.THEME["bg_primary"],
            corner_radius=0,
        )
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 1))
        
        self.file_tree = FileTreeView(
            tree_frame, on_file_select=self._on_file_selected,
        )
        self.file_tree.pack(fill="both", expand=True)
        
        # Diff view
        self.diff_view = DiffView(content)
        self.diff_view.grid(row=0, column=1, sticky="nsew")
        
        # ── Action bar ───────────────────────────────────────────
        action_bar = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0, height=40,
        )
        action_bar.pack(fill="x")
        action_bar.pack_propagate(False)
        
        # Action buttons
        self.apply_btn = ctk.CTkButton(
            action_bar, text="✓ APPLY",
            font=config.FONTS["small"],
            fg_color=config.THEME["success"],
            hover_color="#047857",
            width=80, height=28,
            corner_radius=6,
            command=self._on_apply,
        )
        self.apply_btn.pack(side="left", padx=(8, 4), pady=6)
        
        self.reject_btn = ctk.CTkButton(
            action_bar, text="✗ REJECT",
            font=config.FONTS["small"],
            fg_color=config.THEME["error"],
            hover_color="#B91C1C",
            width=80, height=28,
            corner_radius=6,
            command=self._on_reject,
        )
        self.reject_btn.pack(side="left", padx=4, pady=6)
        
        self.edit_btn = ctk.CTkButton(
            action_bar, text="✎ EDIT",
            font=config.FONTS["small"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_primary"],
            width=80, height=28,
            corner_radius=6,
            command=self._on_edit_manual,
        )
        self.edit_btn.pack(side="left", padx=4, pady=6)
        
        # Changed files indicator
        self.changed_label = ctk.CTkLabel(
            action_bar, text="",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        self.changed_label.pack(side="right", padx=12, pady=6)
        
        # ── Changed files list ───────────────────────────────────
        self.changed_frame = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_primary"],
            corner_radius=0, height=60,
        )
        self.changed_frame.pack(fill="x")
        
        ctk.CTkLabel(
            self.changed_frame, text="CHANGED FILES",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        ).pack(side="left", padx=8, pady=2)
        
        self.changed_files_label = ctk.CTkLabel(
            self.changed_frame, text="No changes yet",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_secondary"],
        )
        self.changed_files_label.pack(side="left", padx=8, pady=2)

    def show_diff(self, filename: str, diff_text: str, source: str = ""):
        """Show a diff for a file change."""
        self.diff_view.set_unified_diff(diff_text, filename)
        if source:
            self.source_label.configure(text=source)
        self.file_tree.highlight_file(filename)

    def show_diff_lines(self, filename: str, diff_lines: list[dict], 
                        source: str = ""):
        """Show a structured diff."""
        self.diff_view.set_diff(diff_lines, filename)
        if source:
            self.source_label.configure(text=source)

    def show_code(self, filename: str, code: str):
        """Show plain code (no diff)."""
        self.diff_view.set_code(code, filename)

    def set_pending_change(self, change: dict):
        """Set a pending change awaiting user action."""
        self.pending_change = change
        filename = change.get("filename", "unknown")
        self.source_label.configure(
            text=f"Proposed by CODER — pending review"
        )
        if change.get("diff"):
            self.show_diff(filename, change["diff"],
                          "Proposed by CODER — pending SUPERVISOR review")

    def add_changed_file(self, filepath: str):
        """Track a changed file."""
        if filepath not in self.changed_files:
            self.changed_files.append(filepath)
        self.file_tree.mark_changed(filepath)
        
        count = len(self.changed_files)
        files_text = " • ".join(
            os.path.basename(f) + " ✏️" for f in self.changed_files[-5:]
        )
        self.changed_files_label.configure(text=files_text)
        self.changed_label.configure(
            text=f"{count} file{'s' if count != 1 else ''} changed"
        )

    def load_project_tree(self, project_path: str):
        """Load the file tree from a project path."""
        self.file_tree.refresh_from_path(project_path)

    def _on_file_selected(self, filepath: str):
        """Handle file selection from tree."""
        pass  # Will be wired to load file content

    def _on_apply(self):
        """Handle APPLY button click."""
        if self.on_apply and self.pending_change:
            self.on_apply(self.pending_change)
            self.pending_change = None
            self.source_label.configure(text="Change applied ✓")

    def _on_reject(self):
        """Handle REJECT button click."""
        if self.on_reject and self.pending_change:
            self.on_reject(self.pending_change)
            self.pending_change = None
            self.diff_view.clear()
            self.source_label.configure(text="Change rejected ✗")

    def _on_edit_manual(self):
        """Handle EDIT MANUALLY button click."""
        if self.on_edit and self.pending_change:
            self.on_edit(self.pending_change)
