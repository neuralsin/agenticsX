"""
FORGE Configuration — All user settings, paths, model config.
Central config file for the entire FORGE application.
"""

import os
from pathlib import Path

# ─── Paths ──────────────────────────────────────────────────────────────────────

FORGE_DIR = Path.home() / ".forge"
MODELS_DIR = FORGE_DIR / "models"
PROJECTS_DIR = FORGE_DIR / "projects"
LOGS_DIR = FORGE_DIR / "logs"
STORAGE_DIR = FORGE_DIR / "storage"
SESSIONS_DIR = STORAGE_DIR / "sessions"

for d in [FORGE_DIR, MODELS_DIR, PROJECTS_DIR, LOGS_DIR, STORAGE_DIR, SESSIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── AirLLM Configuration ───────────────────────────────────────────────────────

AIRLLM_MODEL_ID = "Qwen/Qwen3.6-27B-Instruct"
AIRLLM_COMPRESSION = "4bit"
AIRLLM_MAX_NEW_TOKENS = 2048
AIRLLM_TEMPERATURE = 0.2
AIRLLM_REPETITION_PENALTY = 1.1

# ─── Ollama Configuration ───────────────────────────────────────────────────────

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_PLANNER_MODEL = "deepseek-r1:8b"
OLLAMA_DEBUGGER_MODEL = "deepseek-r1:8b"
OLLAMA_VISION_MODEL = "qwen2.5-vl:7b"
OLLAMA_TIMEOUT = 120  # seconds

# ─── Context Budgets (tokens per agent per call) ────────────────────────────────

CONTEXT_BUDGETS = {
    "SUPERVISOR": 4800,
    "PLANNER": 3600,
    "CODER": 8200,
    "DEBUGGER": 5400,
    "VISION": 900,
}

# ─── Loop & Safety Limits ───────────────────────────────────────────────────────

MAX_ITERATIONS = 50
CONTEXT_PRUNE_THRESHOLD = 0.85  # prune when agent hits 85% of budget
BACKUP_VERSIONS_KEPT = 5
EXEC_TIMEOUT = 15  # seconds for project execution
MAX_FILE_SIZE_TOKENS = 6000  # max tokens to include per file in context

# ─── Agent Colors (hex) ─────────────────────────────────────────────────────────

AGENT_COLORS = {
    "SUPERVISOR": "#7C3AED",
    "PLANNER":    "#0891B2",
    "CODER":      "#059669",
    "DEBUGGER":   "#DC2626",
    "VISION":     "#D97706",
    "USER":       "#FFFFFF",
    "SYSTEM":     "#6B7280",
}

# ─── Agent Model Mapping ────────────────────────────────────────────────────────

AGENT_MODELS = {
    "SUPERVISOR": {"model": "Qwen3.6 27B (Q4_K_M)", "method": "airllm", "speed": "~3-5 tok/s"},
    "PLANNER":    {"model": "DeepSeek-R1 8B (Q4_K_M)", "method": "ollama", "speed": "~15 tok/s"},
    "CODER":      {"model": "Qwen3.6 27B (Q4_K_M)", "method": "airllm", "speed": "~3-5 tok/s"},
    "DEBUGGER":   {"model": "DeepSeek-R1 8B (Q4_K_M)", "method": "ollama", "speed": "~12 tok/s"},
    "VISION":     {"model": "Qwen2.5-VL 7B", "method": "ollama", "speed": "~8 tok/s"},
}

# ─── Hardware ────────────────────────────────────────────────────────────────────

TORCH_DEVICE = "cuda"  # falls back to cpu if unavailable

# Set CUDA memory optimization
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

# ─── GUI Settings ────────────────────────────────────────────────────────────────

WINDOW_TITLE = "FORGE — Multi-Agent AI Studio"
WINDOW_GEOMETRY = "1600x900"
WINDOW_MIN_SIZE = (1200, 700)

# Theme colors
THEME = {
    "bg_primary":    "#0F0F14",
    "bg_secondary":  "#1A1A24",
    "bg_tertiary":   "#252534",
    "bg_card":       "#1E1E2E",
    "bg_input":      "#2A2A3C",
    "border":        "#333348",
    "border_light":  "#444460",
    "text_primary":  "#E8E8F0",
    "text_secondary":"#9898B0",
    "text_muted":    "#6B6B88",
    "accent":        "#7C3AED",
    "accent_hover":  "#9055FF",
    "success":       "#059669",
    "warning":       "#D97706",
    "error":         "#DC2626",
    "info":          "#0891B2",
}

# Font configuration
FONTS = {
    "heading":    ("Segoe UI", 16, "bold"),
    "subheading": ("Segoe UI", 13, "bold"),
    "body":       ("Segoe UI", 12),
    "small":      ("Segoe UI", 10),
    "tiny":       ("Segoe UI", 9),
    "mono":       ("Cascadia Code", 11),
    "mono_small": ("Cascadia Code", 10),
    "mono_tiny":  ("Cascadia Code", 9),
}

# ─── Render Modes ────────────────────────────────────────────────────────────────

RENDER_MODES = ["esp32", "terminal", "web", "desktop", "none"]
DEFAULT_RENDER_MODE = "terminal"

# ─── Project Types ───────────────────────────────────────────────────────────────

PROJECT_TYPES = [
    ("ESP32 / Embedded (Python bridge)", "esp32"),
    ("Python Desktop App", "desktop"),
    ("Python Web App (Flask/FastAPI)", "web"),
    ("Existing Codebase (point to dir)", "existing"),
    ("Custom (describe below)", "custom"),
]
