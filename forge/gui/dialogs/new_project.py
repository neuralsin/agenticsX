"""
FORGE Project Dialog — New + Open Existing projects.
Fully replaces new_project.py with a dual-mode dialog.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import os
import config


class NewProjectDialog(ctk.CTkToplevel):
    """
    Modal dialog for creating OR opening a FORGE project.
    Returns a project configuration dict, or None if cancelled.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.title("FORGE — Project")
        self.geometry("520x680")
        self.minsize(460, 600)
        self.configure(fg_color=config.THEME["bg_secondary"])

        self.transient(parent)
        self.grab_set()

        self.result = None
        self._mode = tk.StringVar(value="new")  # "new" or "open"

        # ── Header ───────────────────────────────────────────────
        header = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0, height=52,
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="⚒️  FORGE",
            font=config.FONTS["heading"],
            text_color=config.THEME["accent"],
        ).pack(side="left", padx=16, pady=10)

        ctk.CTkLabel(
            header, text="Project Setup",
            font=config.FONTS["subheading"],
            text_color=config.THEME["text_primary"],
        ).pack(side="left", pady=10)

        # ── Mode toggle ──────────────────────────────────────────
        mode_frame = ctk.CTkFrame(self, fg_color=config.THEME["bg_tertiary"],
                                  corner_radius=0, height=42)
        mode_frame.pack(fill="x")
        mode_frame.pack_propagate(False)

        self._new_btn = ctk.CTkButton(
            mode_frame, text="＋  New Project",
            font=config.FONTS["body"],
            fg_color=config.THEME["accent"],
            hover_color=config.THEME["accent_hover"],
            text_color="#FFFFFF",
            height=30, corner_radius=6, width=160,
            command=self._switch_new,
        )
        self._new_btn.pack(side="left", padx=(12, 4), pady=6)

        self._open_btn = ctk.CTkButton(
            mode_frame, text="📂  Open Existing",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_secondary"],
            height=30, corner_radius=6, width=160,
            command=self._switch_open,
        )
        self._open_btn.pack(side="left", padx=4, pady=6)

        # ── Scrollable form ──────────────────────────────────────
        self._form = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._form.pack(fill="both", expand=True, padx=20, pady=12)

        self._build_form()

        # ── Bottom buttons ───────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent", height=54)
        btn_frame.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkButton(
            btn_frame, text="✕  Cancel",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_secondary"],
            width=110, height=42, corner_radius=8,
            command=self._cancel,
        ).pack(side="left")

        self._action_btn = ctk.CTkButton(
            btn_frame, text="CREATE  →",
            font=config.FONTS["body"],
            fg_color=config.THEME["accent"],
            hover_color=config.THEME["accent_hover"],
            text_color="#FFFFFF",
            width=130, height=42, corner_radius=8,
            command=self._submit,
        )
        self._action_btn.pack(side="right")

        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self._cancel())
        self.name_entry.focus_set()

    # ── Form builder ─────────────────────────────────────────────

    def _build_form(self):
        """Build the full form (shared fields + mode-specific)."""
        f = self._form

        # Project Name (new mode only)
        self._name_section = ctk.CTkFrame(f, fg_color="transparent")
        self._name_section.pack(fill="x", pady=(0, 2))

        ctk.CTkLabel(self._name_section, text="Project Name",
                     font=config.FONTS["subheading"],
                     text_color=config.THEME["text_primary"],
                     ).pack(anchor="w")

        self.name_entry = ctk.CTkEntry(
            self._name_section,
            placeholder_text="MyAwesomeApp",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            height=36, corner_radius=8,
        )
        self.name_entry.pack(fill="x", pady=(4, 12))

        # Location / existing path
        ctk.CTkLabel(f, text="Location",
                     font=config.FONTS["subheading"],
                     text_color=config.THEME["text_primary"],
                     ).pack(anchor="w")

        loc_frame = ctk.CTkFrame(f, fg_color="transparent")
        loc_frame.pack(fill="x", pady=(4, 12))

        self.location_var = ctk.StringVar(value=str(config.PROJECTS_DIR))
        self.location_entry = ctk.CTkEntry(
            loc_frame,
            textvariable=self.location_var,
            font=config.FONTS["small"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            height=36, corner_radius=8,
        )
        self.location_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(
            loc_frame, text="Browse…",
            font=config.FONTS["small"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_primary"],
            width=82, height=36, corner_radius=8,
            command=self._browse_location,
        ).pack(side="right")

        # ── New-only section ─────────────────────────────────────
        self._new_only_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._new_only_frame.pack(fill="x")

        # Project Type
        ctk.CTkLabel(self._new_only_frame, text="Project Type",
                     font=config.FONTS["subheading"],
                     text_color=config.THEME["text_primary"],
                     ).pack(anchor="w", pady=(0, 4))

        self.type_var = ctk.StringVar(value="custom")
        for display_name, value in config.PROJECT_TYPES:
            ctk.CTkRadioButton(
                self._new_only_frame,
                text=display_name, variable=self.type_var, value=value,
                font=config.FONTS["small"],
                text_color=config.THEME["text_secondary"],
                fg_color=config.THEME["accent"],
                border_color=config.THEME["border"],
                hover_color=config.THEME["accent_hover"],
            ).pack(anchor="w", pady=2, padx=(8, 0))

        ctk.CTkFrame(self._new_only_frame, fg_color="transparent",
                     height=6).pack()

        # Render Mode
        ctk.CTkLabel(self._new_only_frame, text="Render / Simulation Mode",
                     font=config.FONTS["subheading"],
                     text_color=config.THEME["text_primary"],
                     ).pack(anchor="w", pady=(6, 4))

        render_hint = ctk.CTkLabel(
            self._new_only_frame,
            text="VISION agent audits the output regardless of mode chosen.",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        render_hint.pack(anchor="w", padx=8)

        self.render_var = ctk.StringVar(value="terminal")
        render_options = [
            ("🖥  Desktop app (screenshot)", "desktop"),
            ("🌐  Web / HTML (rendered in simulator)", "web"),
            ("📟  Terminal / CLI output", "terminal"),
            ("📺  ESP32 ILI9341 (240×320)", "esp32"),
            ("🚫  None (code-only, no execution)", "none"),
        ]
        for display_name, value in render_options:
            ctk.CTkRadioButton(
                self._new_only_frame,
                text=display_name, variable=self.render_var, value=value,
                font=config.FONTS["small"],
                text_color=config.THEME["text_secondary"],
                fg_color=config.THEME["accent"],
                border_color=config.THEME["border"],
                hover_color=config.THEME["accent_hover"],
            ).pack(anchor="w", pady=2, padx=(8, 0))

        ctk.CTkFrame(self._new_only_frame, fg_color="transparent",
                     height=6).pack()

        # Entry file
        ctk.CTkLabel(self._new_only_frame, text="Entry File",
                     font=config.FONTS["subheading"],
                     text_color=config.THEME["text_primary"],
                     ).pack(anchor="w", pady=(6, 4))

        self.entry_var = ctk.StringVar(value="main.py")
        ctk.CTkEntry(
            self._new_only_frame,
            textvariable=self.entry_var,
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            height=36, corner_radius=8,
        ).pack(fill="x", pady=(0, 8))

    # ── Mode switching ────────────────────────────────────────────

    def _switch_new(self):
        self._mode.set("new")
        self._new_btn.configure(fg_color=config.THEME["accent"],
                                text_color="#FFFFFF")
        self._open_btn.configure(fg_color=config.THEME["bg_input"],
                                 text_color=config.THEME["text_secondary"])
        self._name_section.pack(fill="x", pady=(0, 2), before=self.location_entry.master)
        self._new_only_frame.pack(fill="x")
        self._action_btn.configure(text="CREATE  →")
        self.location_var.set(str(config.PROJECTS_DIR))

    def _switch_open(self):
        self._mode.set("open")
        self._open_btn.configure(fg_color=config.THEME["accent"],
                                 text_color="#FFFFFF")
        self._new_btn.configure(fg_color=config.THEME["bg_input"],
                                text_color=config.THEME["text_secondary"])
        self._name_section.pack_forget()
        self._new_only_frame.pack_forget()
        self._action_btn.configure(text="OPEN  →")
        # Auto-browse for the folder immediately
        self._browse_location()

    # ── Browse ────────────────────────────────────────────────────

    def _browse_location(self):
        if self._mode.get() == "open":
            path = filedialog.askdirectory(
                title="Select Existing Project Folder",
                initialdir=str(config.PROJECTS_DIR),
            )
            if path:
                self.location_var.set(path)
        else:
            path = filedialog.askdirectory(
                title="Select Location for New Project",
                initialdir=str(config.PROJECTS_DIR),
            )
            if path:
                self.location_var.set(path)

    # ── Submit ────────────────────────────────────────────────────

    def _submit(self):
        if self._mode.get() == "new":
            self._create()
        else:
            self._open_existing()

    def _create(self):
        """Create a new project."""
        name = self.name_entry.get().strip()
        if not name:
            self.name_entry.configure(border_color=config.THEME["error"])
            return

        location = self.location_var.get().strip()
        project_path = os.path.join(location, name)

        os.makedirs(project_path, exist_ok=True)
        os.makedirs(os.path.join(project_path, ".forge"), exist_ok=True)
        os.makedirs(os.path.join(project_path, ".forge", "backups"),
                    exist_ok=True)
        os.makedirs(os.path.join(project_path, ".forge", "frames"),
                    exist_ok=True)

        self.result = {
            "name": name,
            "path": project_path,
            "type": self.type_var.get(),
            "render_mode": self.render_var.get(),
            "entry_file": self.entry_var.get().strip() or "main.py",
            "stitch_project_id": "",
        }
        self.grab_release()
        self.destroy()

    def _open_existing(self):
        """Open an existing project folder."""
        path = self.location_var.get().strip()
        if not path or not os.path.isdir(path):
            self.location_entry.configure(border_color=config.THEME["error"])
            return

        # Detect entry file
        entry = "main.py"
        for candidate in ("main.py", "app.py", "index.html", "index.js",
                          "index.py", "server.py"):
            if os.path.exists(os.path.join(path, candidate)):
                entry = candidate
                break

        # Detect render mode from project structure
        render = "terminal"
        if os.path.exists(os.path.join(path, "index.html")):
            render = "web"
        elif any(f.endswith((".pyw", ".exe")) for f in os.listdir(path)
                 if os.path.isfile(os.path.join(path, f))):
            render = "desktop"

        # Detect project type
        ptype = "custom"
        for f in os.listdir(path):
            if f.endswith((".html", ".css", ".js")):
                ptype = "web"
                break
            if f.endswith(".ino"):
                ptype = "esp32"
                break

        name = os.path.basename(path)

        # Ensure .forge dirs exist
        os.makedirs(os.path.join(path, ".forge"), exist_ok=True)
        os.makedirs(os.path.join(path, ".forge", "backups"), exist_ok=True)
        os.makedirs(os.path.join(path, ".forge", "frames"), exist_ok=True)

        self.result = {
            "name": name,
            "path": path,
            "type": ptype,
            "render_mode": render,
            "entry_file": entry,
            "stitch_project_id": "",
        }
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()

    def get_result(self) -> dict:
        return self.result
