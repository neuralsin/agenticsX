"""
FORGE New Project Dialog — Modal dialog for creating/opening projects.
Project name, location, type, render mode, entry file selection.
"""

import customtkinter as ctk
from tkinter import filedialog
import os
import config


class NewProjectDialog(ctk.CTkToplevel):
    """
    Modal dialog for creating a new FORGE project.
    Returns project configuration dict on CREATE.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.title("FORGE — New Project")
        self.geometry("480x620")
        self.minsize(420, 580)
        self.configure(fg_color=config.THEME["bg_secondary"])
        
        # Center on parent
        self.transient(parent)
        self.grab_set()
        
        self.result = None  # Will hold the project config on CREATE
        
        # ── Header ───────────────────────────────────────────────
        header = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0, height=50,
        )
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text="⚒️  FORGE — New Project",
            font=config.FONTS["heading"],
            text_color=config.THEME["text_primary"],
        ).pack(side="left", padx=16, pady=10)
        
        # ── Form content ─────────────────────────────────────────
        form = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
        )
        form.pack(fill="both", expand=True, padx=20, pady=16)
        
        # ── Project Name ─────────────────────────────────────────
        ctk.CTkLabel(
            form, text="Project Name",
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
        ).pack(anchor="w", pady=(0, 4))
        
        self.name_entry = ctk.CTkEntry(
            form,
            placeholder_text="MyProject",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            height=36,
            corner_radius=8,
        )
        self.name_entry.pack(fill="x", pady=(0, 12))
        
        # ── Location ─────────────────────────────────────────────
        ctk.CTkLabel(
            form, text="Location",
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
        ).pack(anchor="w", pady=(0, 4))
        
        loc_frame = ctk.CTkFrame(form, fg_color="transparent")
        loc_frame.pack(fill="x", pady=(0, 12))
        
        self.location_var = ctk.StringVar(
            value=str(config.PROJECTS_DIR)
        )
        self.location_entry = ctk.CTkEntry(
            loc_frame,
            textvariable=self.location_var,
            font=config.FONTS["small"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            height=36,
            corner_radius=8,
        )
        self.location_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
        ctk.CTkButton(
            loc_frame, text="Browse...",
            font=config.FONTS["small"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_primary"],
            width=80, height=36,
            corner_radius=8,
            command=self._browse_location,
        ).pack(side="right")
        
        # ── Project Type ─────────────────────────────────────────
        ctk.CTkLabel(
            form, text="Project Type",
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
        ).pack(anchor="w", pady=(0, 4))
        
        self.type_var = ctk.StringVar(value="desktop")
        
        for display_name, value in config.PROJECT_TYPES:
            rb = ctk.CTkRadioButton(
                form,
                text=display_name,
                variable=self.type_var,
                value=value,
                font=config.FONTS["small"],
                text_color=config.THEME["text_secondary"],
                fg_color=config.THEME["accent"],
                border_color=config.THEME["border"],
                hover_color=config.THEME["accent_hover"],
            )
            rb.pack(anchor="w", pady=2, padx=(8, 0))
        
        # Spacer
        ctk.CTkFrame(form, fg_color="transparent", height=8).pack()
        
        # ── Render Mode ──────────────────────────────────────────
        ctk.CTkLabel(
            form, text="Render Mode",
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
        ).pack(anchor="w", pady=(8, 4))
        
        self.render_var = ctk.StringVar(value="terminal")
        
        render_options = [
            ("ESP32 ILI9341 (240×320)", "esp32"),
            ("Terminal output", "terminal"),
            ("Web browser preview", "web"),
            ("Screenshot (desktop app)", "desktop"),
            ("None (code-only)", "none"),
        ]
        
        for display_name, value in render_options:
            rb = ctk.CTkRadioButton(
                form,
                text=display_name,
                variable=self.render_var,
                value=value,
                font=config.FONTS["small"],
                text_color=config.THEME["text_secondary"],
                fg_color=config.THEME["accent"],
                border_color=config.THEME["border"],
                hover_color=config.THEME["accent_hover"],
            )
            rb.pack(anchor="w", pady=2, padx=(8, 0))
        
        # ── Entry File ───────────────────────────────────────────
        ctk.CTkLabel(
            form, text="Entry File",
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
        ).pack(anchor="w", pady=(12, 4))
        
        self.entry_var = ctk.StringVar(value="main.py")
        self.entry_entry = ctk.CTkEntry(
            form,
            textvariable=self.entry_var,
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            height=36,
            corner_radius=8,
        )
        self.entry_entry.pack(fill="x", pady=(0, 8))
        
        # ── Buttons ──────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent", height=50)
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))
        
        ctk.CTkButton(
            btn_frame, text="CANCEL",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_primary"],
            width=100, height=40,
            corner_radius=8,
            command=self._cancel,
        ).pack(side="left")
        
        ctk.CTkButton(
            btn_frame, text="CREATE →",
            font=config.FONTS["body"],
            fg_color=config.THEME["accent"],
            hover_color=config.THEME["accent_hover"],
            text_color="#FFFFFF",
            width=120, height=40,
            corner_radius=8,
            command=self._create,
        ).pack(side="right")
        
        # Focus name entry
        self.name_entry.focus_set()
        
        # Bind Enter key
        self.bind("<Return>", lambda e: self._create())
        self.bind("<Escape>", lambda e: self._cancel())

    def _browse_location(self):
        """Open folder browser dialog."""
        path = filedialog.askdirectory(
            title="Select Project Location",
            initialdir=str(config.PROJECTS_DIR),
        )
        if path:
            self.location_var.set(path)

    def _create(self):
        """Create the project and return config."""
        name = self.name_entry.get().strip()
        if not name:
            self.name_entry.configure(border_color=config.THEME["error"])
            return
        
        location = self.location_var.get().strip()
        project_path = os.path.join(location, name)
        
        # Create project directory
        os.makedirs(project_path, exist_ok=True)
        os.makedirs(os.path.join(project_path, ".forge"), exist_ok=True)
        os.makedirs(os.path.join(project_path, ".forge", "backups"), exist_ok=True)
        os.makedirs(os.path.join(project_path, ".forge", "frames"), exist_ok=True)
        
        self.result = {
            "name": name,
            "path": project_path,
            "type": self.type_var.get(),
            "render_mode": self.render_var.get(),
            "entry_file": self.entry_var.get().strip() or "main.py",
        }
        
        self.grab_release()
        self.destroy()

    def _cancel(self):
        """Cancel and close dialog."""
        self.result = None
        self.grab_release()
        self.destroy()

    def get_result(self) -> dict:
        """Get the project configuration result (call after dialog closes)."""
        return self.result
