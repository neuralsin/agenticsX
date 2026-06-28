"""
FORGE Storage Settings Dialog — Graphical path manager.
Lets the user point FORGE's model cache, projects, DB, and Ollama
to any drive without touching code.

All settings persist to %APPDATA%/FORGE/settings.json and take effect
on the next launch (a restart notice is shown).
"""

import os
import subprocess
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

import config


# Paths that can be configured with a folder-picker
_PATH_FIELDS = [
    (
        "forge_dir",
        "FORGE Home Directory",
        "Root folder for all FORGE data (logs, config, sessions).",
        "📁",
    ),
    (
        "models_dir",
        "AI Models Directory",
        "Where AirLLM / HuggingFace model shards are downloaded.",
        "🤖",
    ),
    (
        "hf_cache_dir",
        "HuggingFace Cache (HF_HOME)",
        "Sets HF_HOME env var — controls where transformers caches go.",
        "🧠",
    ),
    (
        "ollama_models_dir",
        "Ollama Models Directory",
        "Sets OLLAMA_MODELS env var — where Ollama stores its model files.",
        "🦙",
    ),
    (
        "projects_dir",
        "Projects Directory",
        "Default location for new FORGE projects.",
        "📂",
    ),
    (
        "storage_dir",
        "Sessions / DB Directory",
        "Where SQLite context databases are stored.",
        "🗄️",
    ),
    (
        "docs_dir",
        "RAG Docs Directory",
        "Drop .txt/.md files here for the RAG Librarian to index.",
        "📚",
    ),
]


class StorageSettingsDialog(ctk.CTkToplevel):
    """
    Graphical storage path manager.
    Browse buttons open folder pickers. Changes are saved to
    %APPDATA%/FORGE/settings.json on "Save & Restart".
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("FORGE — Storage & Path Settings")
        self.geometry("720x680")
        self.configure(fg_color=config.THEME["bg_secondary"])
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(600, 500)

        # Load current settings
        self._settings = config.load_user_settings()
        self._entry_vars: dict[str, ctk.StringVar] = {}

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=config.THEME["bg_tertiary"],
                              corner_radius=0, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="💾  Storage & Path Settings",
            font=config.FONTS["heading"],
            text_color=config.THEME["text_primary"],
        ).pack(side="left", padx=16, pady=12)

        ctk.CTkLabel(
            header,
            text="Changes take effect on next launch",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        ).pack(side="right", padx=16)

        # Info banner
        info = ctk.CTkFrame(self, fg_color=config.THEME["bg_primary"],
                            corner_radius=0, height=34)
        info.pack(fill="x")
        info.pack_propagate(False)
        ctk.CTkLabel(
            info,
            text="📌  Move any directory to another drive (D:\\, E:\\, etc.) "
                 "to keep your C: drive clean. Leave blank to use defaults.",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_secondary"],
        ).pack(side="left", padx=12, pady=6)

        # Scrollable path list
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=config.THEME["border"],
        )
        scroll.pack(fill="both", expand=True, padx=12, pady=8)

        for key, label, tooltip, icon in _PATH_FIELDS:
            self._add_path_row(scroll, key, label, tooltip, icon)

        # Separator
        ctk.CTkFrame(self, fg_color=config.THEME["border"],
                     height=1, corner_radius=0).pack(fill="x")

        # Gemini API key section
        api_section = ctk.CTkFrame(self, fg_color="transparent")
        api_section.pack(fill="x", padx=16, pady=(8, 4))

        ctk.CTkLabel(
            api_section,
            text="🔑  Gemini API Key (for AUDITOR agent)",
            font=config.FONTS["subheading"],
            text_color=config.THEME["accent"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            api_section,
            text="Get a free key at: aistudio.google.com/apikey  "
                 "— stored in settings.json, never sent anywhere else.",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
            wraplength=660,
        ).pack(anchor="w", pady=(2, 6))

        key_row = ctk.CTkFrame(api_section, fg_color="transparent")
        key_row.pack(fill="x")

        self._gemini_var = ctk.StringVar(
            value=self._settings.get("gemini_api_key", "")
        )
        self._key_entry = ctk.CTkEntry(
            key_row,
            textvariable=self._gemini_var,
            placeholder_text="AIza...",
            font=config.FONTS["mono_small"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            height=34,
            show="•",
        )
        self._key_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            key_row, text="👁 Show",
            font=config.FONTS["tiny"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border"],
            text_color=config.THEME["text_secondary"],
            width=70, height=34, corner_radius=6,
            command=self._toggle_key_visibility,
        ).pack(side="left")

        # Bottom buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 14))

        ctk.CTkButton(
            btn_row, text="🗑  Reset All to Defaults",
            font=config.FONTS["small"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["error"],
            text_color=config.THEME["text_secondary"],
            width=180, height=38, corner_radius=8,
            command=self._reset_defaults,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="Cancel",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_secondary"],
            width=100, height=38, corner_radius=8,
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_row, text="💾  Save Settings",
            font=config.FONTS["body"],
            fg_color=config.THEME["accent"],
            hover_color=config.THEME["accent_hover"],
            text_color="#FFFFFF",
            width=140, height=38, corner_radius=8,
            command=self._save,
        ).pack(side="right")

    def _add_path_row(self, parent, key: str, label: str,
                      tooltip: str, icon: str):
        """Add a single path-picker row."""
        card = ctk.CTkFrame(parent, fg_color=config.THEME["bg_card"],
                            corner_radius=8)
        card.pack(fill="x", pady=4)

        # Icon + label + tooltip
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 2))

        ctk.CTkLabel(
            top, text=icon, font=("Segoe UI Emoji", 14),
        ).pack(side="left")

        ctk.CTkLabel(
            top, text=f"  {label}",
            font=config.FONTS["small"],
            text_color=config.THEME["text_primary"],
            anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            top, text=tooltip,
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
            anchor="e",
        ).pack(side="right")

        # Path entry + buttons
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 8))

        # Current value (from saved settings or default)
        current_val = self._settings.get(key, "")
        var = ctk.StringVar(value=current_val)
        self._entry_vars[key] = var

        entry = ctk.CTkEntry(
            row,
            textvariable=var,
            placeholder_text=f"(default) — leave blank to use ~/.forge/...",
            font=config.FONTS["mono_small"],
            fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            height=32,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            row, text="Browse…",
            font=config.FONTS["tiny"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border"],
            text_color=config.THEME["text_secondary"],
            width=72, height=32, corner_radius=6,
            command=lambda k=key, v=var: self._browse(k, v),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            row, text="📂",
            font=("Segoe UI Emoji", 13),
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border"],
            text_color=config.THEME["text_secondary"],
            width=36, height=32, corner_radius=6,
            command=lambda v=var: self._open_folder(v.get()),
        ).pack(side="left")

    # ── Actions ───────────────────────────────────────────────────────────────────

    def _browse(self, key: str, var: ctk.StringVar):
        """Open folder picker and set the entry value."""
        initial = var.get() or str(Path.home())
        if not os.path.isdir(initial):
            initial = str(Path.home())
        chosen = filedialog.askdirectory(
            parent=self, title=f"Select folder for {key}",
            initialdir=initial,
        )
        if chosen:
            var.set(chosen)

    def _open_folder(self, path: str):
        """Open the folder in Windows Explorer."""
        if path and os.path.isdir(path):
            subprocess.Popen(f'explorer "{path}"')
        elif path:
            messagebox.showwarning(
                "Not Found", f"Directory does not exist:\n{path}",
                parent=self,
            )

    def _toggle_key_visibility(self):
        current = self._key_entry.cget("show")
        self._key_entry.configure(show="" if current == "•" else "•")

    def _reset_defaults(self):
        """Clear all saved paths to use defaults."""
        if messagebox.askyesno(
            "Reset Defaults",
            "Reset all storage paths to defaults (~/.forge)?\n"
            "Your EXISTING data will NOT be deleted.",
            parent=self,
        ):
            for var in self._entry_vars.values():
                var.set("")
            self._gemini_var.set("")

    def _save(self):
        """Save all settings and show restart notice."""
        updates = {}
        for key, var in self._entry_vars.items():
            val = var.get().strip()
            updates[key] = val  # empty string = use default

        gemini_key = self._gemini_var.get().strip()
        updates["gemini_api_key"] = gemini_key

        config.save_user_settings(updates)

        messagebox.showinfo(
            "Saved ✓",
            "Storage settings saved.\n\n"
            "Please RESTART FORGE for the new paths to take effect.\n"
            "Your existing data will stay where it was — "
            "FORGE will use the new locations from the next launch.",
            parent=self,
        )
        self.destroy()
