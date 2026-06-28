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
        {
            "id": "Qwen/Qwen2.5-7B-GGUF",
            "name": "Qwen 2.5 7B",
            "size": "~4 GB",
            "vram": "~3 GB",
            "engine": "AirLLM",
            "desc": "Smallest AirLLM option. Fast inference, limited reasoning.",
            "recommended": False,
        },
    ],
    # Ollama models
    "ollama": [
        {
            "id": "deepseek-r1:8b",
            "name": "DeepSeek-R1 8B",
            "size": "~4.9 GB",
            "vram": "~5 GB (or CPU)",
            "engine": "Ollama",
            "desc": "Strong reasoning model for PLANNER, DEBUGGER, TESTER.",
            "recommended": True,
        },
        {
            "id": "deepseek-r1:14b",
            "name": "DeepSeek-R1 14B",
            "size": "~8.9 GB",
            "vram": "~9 GB",
            "engine": "Ollama",
            "desc": "Larger reasoning variant. Needs more VRAM.",
            "recommended": False,
        },
        {
            "id": "qwen2.5-coder:7b",
            "name": "Qwen 2.5 Coder 7B",
            "size": "~4.4 GB",
            "vram": "~5 GB",
            "engine": "Ollama",
            "desc": "Code-specialized model, good for DEBUGGER.",
            "recommended": False,
        },
        {
            "id": "codellama:7b",
            "name": "Code Llama 7B",
            "size": "~3.8 GB",
            "vram": "~4 GB",
            "engine": "Ollama",
            "desc": "Meta's code-focused model.",
            "recommended": False,
        },
    ],
    # Vision models (Ollama)
    "vision": [
        {
            "id": "qwen2.5-vl:7b",
            "name": "Qwen 2.5 VL 7B",
            "size": "~5.1 GB",
            "vram": "~5.5 GB",
            "engine": "Ollama",
            "desc": "Vision-language model for screenshot analysis.",
            "recommended": True,
        },
        {
            "id": "llava:7b",
            "name": "LLaVA 7B",
            "size": "~4.5 GB",
            "vram": "~5 GB",
            "engine": "Ollama",
            "desc": "Older vision model, still capable.",
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

        # Scrollable agent list
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=config.THEME["border"],
        )
        scroll.pack(fill="both", expand=True, padx=12, pady=8)

        for mapping in _AGENT_MODEL_MAP:
            self._add_agent_row(scroll, mapping)

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
