"""
FORGE Model Picker Dialog — Live, graphical model selection.
Shows each agent's model, its size, engine, and lets the user
pick from a list of available models with one-click download info.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

import config


# ── Model catalog: all supported models with metadata ────────────────────────

_MODEL_CATALOG = {
    # AirLLM models (layer-sliced, can run 27B on 6GB VRAM)
    "airllm": [
        {
            "id": "Qwen/Qwen3.6-27B-GGUF",
            "name": "Qwen 3.6 27B",
            "size": "~15 GB (sharded)",
            "vram": "~5.5 GB",
            "engine": "AirLLM",
            "desc": "Best reasoning model for SUPERVISOR + CODER. Layer-sliced inference.",
            "recommended": True,
        },
        {
            "id": "Qwen/Qwen2.5-14B-GGUF",
            "name": "Qwen 2.5 14B",
            "size": "~8 GB",
            "vram": "~4 GB",
            "engine": "AirLLM",
            "desc": "Lighter alternative. Faster but less capable for complex tasks.",
            "recommended": False,
        },
    ],
    # Ollama models
    "ollama": [
        {
            "id": "qwen3.6:27b",
            "name": "Qwen 3.6 27B ⭐ (Text + Vision)",
            "size": "~17 GB",
            "vram": "~15-18 GB (or CPU offload)",
            "engine": "Ollama",
            "desc": "Top-ranked agentic coder. Natively multimodal — handles text AND vision. Replaces all previous models.",
            "recommended": True,
        },
        {
            "id": "deepseek-r1:8b",
            "name": "DeepSeek-R1 8B",
            "size": "~4.9 GB",
            "vram": "~5 GB (or CPU)",
            "engine": "Ollama",
            "desc": "Strong reasoning model. Good fallback if 27B is too slow.",
            "recommended": False,
        },
        {
            "id": "qwen2.5-coder:7b",
            "name": "Qwen 2.5 Coder 7B",
            "size": "~4.4 GB",
            "vram": "~5 GB",
            "engine": "Ollama",
            "desc": "Code-specialized model, compact alternative for DEBUGGER.",
            "recommended": False,
        },
    ],
    # Vision models — qwen3.6 handles vision natively, but listing fallbacks too
    "vision": [
        {
            "id": "qwen3.6:27b",
            "name": "Qwen 3.6 27B ⭐ (Native Multimodal)",
            "size": "~17 GB",
            "vram": "~15-18 GB",
            "engine": "Ollama",
            "desc": "Natively multimodal — text + image reasoning. Best choice for VISION agent.",
            "recommended": True,
        },
        {
            "id": "qwen2.5-vl:7b",
            "name": "Qwen 2.5 VL 7B",
            "size": "~5.1 GB",
            "vram": "~5.5 GB",
            "engine": "Ollama",
            "desc": "Compact vision model. Good fallback if 27B is too slow.",
            "recommended": False,
        },
    ],
    # Gemini API models
    "gemini": [
        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "size": "Cloud (free tier)",
            "vram": "0 GB",
            "engine": "Google API",
            "desc": "Fast, free cloud model for AUDITOR agent.",
            "recommended": True,
        },
        {
            "id": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "size": "Cloud (paid)",
            "vram": "0 GB",
            "engine": "Google API",
            "desc": "More capable but costs money.",
            "recommended": False,
        },
    ],
}

# Mapping: which agent uses which catalog + config key
_AGENT_MODEL_MAP = [
    {
        "agent": "SUPERVISOR",
        "label": "SUPERVISOR — Lead Architect",
        "icon": "👑",
        "catalog": "airllm",
        "config_key": "AIRLLM_MODEL_ID",
        "current": config.AIRLLM_MODEL_ID,
    },
    {
        "agent": "CODER",
        "label": "CODER — Code Writer",
        "icon": "💻",
        "catalog": "airllm",
        "config_key": "AIRLLM_MODEL_ID",
        "current": config.AIRLLM_MODEL_ID,
    },
    {
        "agent": "PLANNER",
        "label": "PLANNER — Task Decomposer",
        "icon": "📝",
        "catalog": "ollama",
        "config_key": "OLLAMA_PLANNER_MODEL",
        "current": config.OLLAMA_PLANNER_MODEL,
    },
    {
        "agent": "DEBUGGER",
        "label": "DEBUGGER — Error Analyst",
        "icon": "🐛",
        "catalog": "ollama",
        "config_key": "OLLAMA_DEBUGGER_MODEL",
        "current": config.OLLAMA_DEBUGGER_MODEL,
    },
    {
        "agent": "TESTER",
        "label": "TESTER — Unit Test Generator",
        "icon": "🧪",
        "catalog": "ollama",
        "config_key": "OLLAMA_TESTER_MODEL",
        "current": config.OLLAMA_TESTER_MODEL,
    },
    {
        "agent": "VISION",
        "label": "VISION — Screenshot Analyst",
        "icon": "👁",
        "catalog": "vision",
        "config_key": "OLLAMA_VISION_MODEL",
        "current": config.OLLAMA_VISION_MODEL,
    },
    {
        "agent": "AUDITOR",
        "label": "AUDITOR — Independent Reviewer",
        "icon": "⚖",
        "catalog": "gemini",
        "config_key": "GEMINI_MODEL",
        "current": config.GEMINI_MODEL,
    },
]


class ModelPickerDialog(ctk.CTkToplevel):
    """
    Graphical model picker.
    Shows all 7 agents, their current model, and allows picking from the catalog.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("FORGE — Model Configuration")
        self.geometry("780x720")
        self.configure(fg_color=config.THEME["bg_secondary"])
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(650, 500)

        # Check installed Ollama models via API ping
        self._installed_ollama = []
        try:
            from agents.ollama_agent import OllamaAgent
            self._installed_ollama = OllamaAgent.list_available_models()
        except Exception:
            pass

        self._selections: dict[str, str] = {}
        self._build_ui()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=config.THEME["bg_tertiary"],
                              corner_radius=0, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="🤖  Model Configuration",
            font=config.FONTS["heading"],
            text_color=config.THEME["text_primary"],
        ).pack(side="left", padx=16, pady=12)

        ctk.CTkLabel(
            header,
            text="Pick the best model for each agent",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        ).pack(side="right", padx=16)

        # Hardware info banner
        hw_frame = ctk.CTkFrame(self, fg_color=config.THEME["bg_primary"],
                                corner_radius=0, height=30)
        hw_frame.pack(fill="x")
        hw_frame.pack_propagate(False)

        hw_text = "Your hardware: "
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024**3)
            hw_text += f"RAM: {ram_gb:.0f} GB"
        except Exception:
            hw_text += "RAM: ?"
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode()
            vram = pynvml.nvmlDeviceGetMemoryInfo(h).total / (1024**3)
            hw_text += f"  |  GPU: {name} ({vram:.0f} GB VRAM)"
            pynvml.nvmlShutdown()
        except Exception:
            hw_text += "  |  GPU: ?"

        ctk.CTkLabel(
            hw_frame, text=hw_text,
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_secondary"],
        ).pack(side="left", padx=12, pady=4)

        # Scrollable agent list (Tabview)
        self.tabview = ctk.CTkTabview(self, fg_color="transparent",
                                      segmented_button_selected_color=config.THEME["accent"],
                                      segmented_button_selected_hover_color=config.THEME["accent_hover"],
                                      segmented_button_unselected_color=config.THEME["bg_tertiary"])
        self.tabview.pack(fill="both", expand=True, padx=12, pady=4)
        
        tab_mapping = self.tabview.add("Agent Model Mapping")
        tab_installer = self.tabview.add("Model & CUDA Installer")

        # Tab 1: Agent Mapping
        scroll = ctk.CTkScrollableFrame(
            tab_mapping, fg_color="transparent",
            scrollbar_button_color=config.THEME["border"],
        )
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        for mapping in _AGENT_MODEL_MAP:
            self._add_agent_row(scroll, mapping)

        # Tab 2: Model & CUDA Installer
        self._build_installer_tab(tab_installer)

        # Bottom buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 14))

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
            btn_row, text="💾  Save Model Choices",
            font=config.FONTS["body"],
            fg_color=config.THEME["accent"],
            hover_color=config.THEME["accent_hover"],
            text_color="#FFFFFF",
            width=180, height=38, corner_radius=8,
            command=self._save,
        ).pack(side="right")

    def _add_agent_row(self, parent, mapping: dict):
        """Add a single agent model picker row."""
        agent = mapping["agent"]
        catalog = _MODEL_CATALOG.get(mapping["catalog"], [])
        current = mapping["current"]
        color = config.AGENT_COLORS.get(agent, "#7C3AED")

        card = ctk.CTkFrame(parent, fg_color=config.THEME["bg_card"],
                            corner_radius=10, border_width=1,
                            border_color=config.THEME["border"])
        card.pack(fill="x", pady=4)

        # Agent header
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 2))

        ctk.CTkLabel(
            top, text=mapping["icon"],
            font=("Segoe UI Emoji", 15),
        ).pack(side="left")

        ctk.CTkLabel(
            top, text=f"  {mapping['label']}",
            font=config.FONTS["small"],
            text_color=color,
            anchor="w",
        ).pack(side="left")

        # Current model badge
        ctk.CTkLabel(
            top, text=f"Current: {current}",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        ).pack(side="right")

        # Model options
        options_frame = ctk.CTkFrame(card, fg_color="transparent")
        options_frame.pack(fill="x", padx=12, pady=(4, 8))

        var = tk.StringVar(value=current)
        self._selections[mapping["config_key"]] = current

        for model in catalog:
            is_current = model["id"] == current
            is_rec = model.get("recommended", False)

            opt_frame = ctk.CTkFrame(
                options_frame,
                fg_color=config.THEME["bg_tertiary"] if is_current
                    else "transparent",
                corner_radius=6,
            )
            opt_frame.pack(fill="x", pady=1)

            rb = ctk.CTkRadioButton(
                opt_frame,
                text="",
                variable=var,
                value=model["id"],
                radiobutton_width=16, radiobutton_height=16,
                fg_color=color,
                border_color=config.THEME["border_light"],
                hover_color=color,
                command=lambda k=mapping["config_key"], v=var: (
                    self._selections.__setitem__(k, v.get())
                ),
            )
            rb.pack(side="left", padx=(8, 4), pady=4)

            # Model name + recommended badge
            name_text = model["name"]
            if is_rec:
                name_text += "  ★"
            ctk.CTkLabel(
                opt_frame, text=name_text,
                font=config.FONTS["small"],
                text_color=config.THEME["text_primary"] if not is_rec
                    else config.THEME["accent"],
                anchor="w",
            ).pack(side="left", padx=(0, 8))

            # Size + VRAM
            ctk.CTkLabel(
                opt_frame,
                text=f"{model['size']}  |  VRAM: {model['vram']}",
                font=config.FONTS["tiny"],
                text_color=config.THEME["text_muted"],
            ).pack(side="left")

            # Engine badge
            ctk.CTkLabel(
                opt_frame, text=model["engine"],
                font=config.FONTS["tiny"],
                text_color=config.THEME["info"],
            ).pack(side="right", padx=8)

            # Live status / Download for Ollama
            if model["engine"] == "Ollama":
                is_installed = any(m.startswith(model["id"]) for m in self._installed_ollama)
                if is_installed:
                    ctk.CTkLabel(
                        opt_frame, text="✔ Installed",
                        font=config.FONTS["tiny"], text_color=config.THEME["success"]
                    ).pack(side="right", padx=8)
                else:
                    ctk.CTkButton(
                        opt_frame, text="⬇ Download",
                        font=config.FONTS["tiny"], fg_color="transparent",
                        border_width=1, border_color=config.THEME["warning"],
                        text_color=config.THEME["warning"], hover_color=config.THEME["bg_card"],
                        width=60, height=20, corner_radius=4,
                        command=lambda m=model["id"]: self._download_ollama(m)
                    ).pack(side="right", padx=8)

    def _download_ollama(self, model_name: str):
        """Launch a terminal to download the Ollama model."""
        import subprocess
        subprocess.Popen(
            ["cmd.exe", "/c", f"echo Downloading {model_name}... && ollama pull {model_name} && pause"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        messagebox.showinfo(
            "Downloading", 
            f"Started downloading {model_name} in a new terminal window.\n\nPlease wait for it to finish.",
            parent=self
        )

    def _build_installer_tab(self, parent):
        """Build the Model & CUDA Installer tab."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        # ─── 1. CUDA / PyTorch Section ───
        cuda_frame = ctk.CTkFrame(frame, fg_color=config.THEME["bg_card"], corner_radius=10, border_width=1, border_color=config.THEME["border"])
        cuda_frame.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(cuda_frame, text="⚡ PyTorch & CUDA (GPU) Acceleration", font=config.FONTS["subheading"], text_color=config.THEME["accent"]).pack(anchor="w", padx=12, pady=(8, 2))

        import torch
        cuda_ok = torch.cuda.is_available()
        if cuda_ok:
            device_name = torch.cuda.get_device_name(0)
            status_text = f"🟢 PyTorch + CUDA OK (Running on GPU: {device_name})"
            status_color = config.THEME["success"]
        else:
            status_text = "🔴 PyTorch is running on CPU only (CUDA not available)"
            status_color = config.THEME["error"]

        ctk.CTkLabel(cuda_frame, text=status_text, font=config.FONTS["small"], text_color=status_color).pack(anchor="w", padx=12, pady=4)

        # Fix/Reinstall button
        fix_btn = ctk.CTkButton(
            cuda_frame, text="Fix CUDA (Install PyTorch with CUDA 12.1)",
            font=config.FONTS["tiny"], fg_color=config.THEME["accent"],
            hover_color=config.THEME["accent_hover"],
            command=self._install_pytorch_cuda
        )
        fix_btn.pack(anchor="w", padx=12, pady=(4, 12))

        # ─── 2. Ollama Models Section ───
        ollama_frame = ctk.CTkFrame(frame, fg_color=config.THEME["bg_card"], corner_radius=10, border_width=1, border_color=config.THEME["border"])
        ollama_frame.pack(fill="both", expand=True, padx=4)

        ctk.CTkLabel(ollama_frame, text="🦙 Ollama Model Downloader", font=config.FONTS["subheading"], text_color=config.THEME["info"]).pack(anchor="w", padx=12, pady=(8, 2))

        # Show detected models for transparency
        detected_text = "Detected installed Ollama models: " + (", ".join(self._installed_ollama) if self._installed_ollama else "None")
        ctk.CTkLabel(ollama_frame, text=detected_text, font=config.FONTS["tiny"], text_color=config.THEME["text_muted"], wraplength=600, justify="left").pack(anchor="w", padx=12, pady=(0, 4))

        # Scrollable list for models
        model_scroll = ctk.CTkScrollableFrame(ollama_frame, fg_color="transparent", height=200)
        model_scroll.pack(fill="both", expand=True, padx=8, pady=4)

        # Merge Ollama & Vision catalog models
        all_downloadable = _MODEL_CATALOG["ollama"] + _MODEL_CATALOG["vision"]
        for model in all_downloadable:
            row = ctk.CTkFrame(model_scroll, fg_color=config.THEME["bg_tertiary"], corner_radius=6)
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(row, text=model["name"], font=config.FONTS["small"], text_color=config.THEME["text_primary"]).pack(side="left", padx=8, pady=4)
            ctk.CTkLabel(row, text=f"({model['size']})", font=config.FONTS["tiny"], text_color=config.THEME["text_muted"]).pack(side="left", padx=4)

            is_installed = any(m.startswith(model["id"]) for m in self._installed_ollama)
            if is_installed:
                ctk.CTkLabel(row, text="✔ Installed", font=config.FONTS["tiny"], text_color=config.THEME["success"]).pack(side="right", padx=12)
            else:
                ctk.CTkButton(
                    row, text="Download", font=config.FONTS["tiny"],
                    fg_color=config.THEME["warning"], text_color="#000000",
                    hover_color="#D97706", width=70, height=20, corner_radius=4,
                    command=lambda m=model["id"]: self._download_ollama(m)
                ).pack(side="right", padx=12)

        # Custom pull entry
        custom_frame = ctk.CTkFrame(ollama_frame, fg_color="transparent")
        custom_frame.pack(fill="x", padx=12, pady=10)

        self.custom_model_var = tk.StringVar()
        entry = ctk.CTkEntry(
            custom_frame, placeholder_text="Enter any Ollama model (e.g., llama3, mistral)...",
            font=config.FONTS["small"], fg_color=config.THEME["bg_input"],
            border_color=config.THEME["border"], text_color=config.THEME["text_primary"],
            textvariable=self.custom_model_var, height=28
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            custom_frame, text="Download Custom", font=config.FONTS["tiny"],
            fg_color=config.THEME["info"], hover_color=config.THEME["accent_hover"],
            width=120, height=28,
            command=self._download_custom_ollama
        ).pack(side="right")

    def _install_pytorch_cuda(self):
        """Reinstall PyTorch with CUDA 12.1 in a new terminal."""
        import sys
        import subprocess
        py_path = sys.executable
        # Use cmd.exe /k directly with CREATE_NEW_CONSOLE to prevent instant exit and show errors
        cmd = f'echo Installing PyTorch with CUDA 12.1 support... && "{py_path}" -m pip install torch --index-url https://download.pytorch.org/whl/cu121 --force-reinstall --no-cache-dir && echo. && echo Finished! Restart FORGE. && pause'
        subprocess.Popen(
            ["cmd.exe", "/k", cmd],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        messagebox.showinfo("PyTorch CUDA Installer", "Started PyTorch CUDA installation in a new terminal window.\n\nKeep an eye on it to make sure it completes!")

    def _download_custom_ollama(self):
        """Download custom model typed in entry."""
        m = self.custom_model_var.get().strip()
        if not m:
            return
        self._download_ollama(m)

    def _save(self):
        """Save selections to user settings."""
        # Build config key -> value mapping
        updates = {}
        for key, model_id in self._selections.items():
            # Map config keys to settings.json keys
            settings_key = key.lower()
            updates[settings_key] = model_id

        config.save_user_settings(updates)

        messagebox.showinfo(
            "Saved",
            "Model choices saved.\n\n"
            "Restart FORGE for new models to take effect.\n"
            "You may need to download new models first:\n"
            "  ollama pull <model_name>",
            parent=self,
        )
        self.destroy()
