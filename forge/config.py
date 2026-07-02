"""
FORGE Configuration — All user settings, paths, model config.
Central config file for the entire FORGE application.
v2: Adds AUDITOR, model registry, storage media, Stitch, AST, Git, RAG, TDD.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists in the current working directory
load_dotenv()

# Disable Hugging Face cache symlinks on Windows to prevent WinError 1314 (Privilege Not Held)
# This allows downloads to succeed without requiring Admin rights or Developer Mode.
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

# ─── User Settings File (persists path overrides) ───────────────────────────────

_APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
USER_SETTINGS_DIR = _APPDATA / "FORGE"
USER_SETTINGS_FILE = USER_SETTINGS_DIR / "settings.json"
USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

_DEFAULT_FORGE_DIR = Path("D:/Forge")


def load_user_settings() -> dict:
    """Load persisted user settings from %APPDATA%/FORGE/settings.json."""
    try:
        if USER_SETTINGS_FILE.exists():
            with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_user_settings(updates: dict):
    """Persist user settings to %APPDATA%/FORGE/settings.json."""
    try:
        existing = load_user_settings()
        existing.update(updates)
        with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        print(f"[CONFIG] Failed to save settings: {e}")


def get_user_setting(key: str, default):
    """Get a single user setting with a default fallback."""
    return load_user_settings().get(key, default)


# ─── Paths (user-overridable via Storage Settings dialog) ───────────────────────

_s = load_user_settings()

FORGE_DIR    = Path(_s.get("forge_dir",    str(_DEFAULT_FORGE_DIR)))
MODELS_DIR   = Path(_s.get("models_dir",   str(FORGE_DIR / "models")))
PROJECTS_DIR = Path(_s.get("projects_dir", str(FORGE_DIR / "projects")))
LOGS_DIR     = Path(_s.get("logs_dir",     str(FORGE_DIR / "logs")))
STORAGE_DIR  = Path(_s.get("storage_dir",  str(FORGE_DIR / "storage")))
SESSIONS_DIR = STORAGE_DIR / "sessions"
DOCS_DIR     = Path(_s.get("docs_dir",     str(FORGE_DIR / "docs")))
CONFIG_FILE  = FORGE_DIR / "model_config.json"

# Apply OLLAMA_MODELS env override if user set it, else default to D:/Forge/models/ollama
_ollama_models = _s.get("ollama_models_dir", str(MODELS_DIR / "ollama"))
os.environ["OLLAMA_MODELS"] = _ollama_models

# Apply HuggingFace / AirLLM cache override, else default to D:/Forge/models/huggingface
_hf_cache = _s.get("hf_cache_dir", str(MODELS_DIR / "huggingface"))
os.environ["HF_HOME"] = _hf_cache
os.environ["TRANSFORMERS_CACHE"] = _hf_cache

# Create all required directories
for _d in [FORGE_DIR, MODELS_DIR, PROJECTS_DIR, LOGS_DIR,
           STORAGE_DIR, SESSIONS_DIR, DOCS_DIR]:
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


# ─── AirLLM Configuration ───────────────────────────────────────────────────────

AIRLLM_MODEL_ID = "Qwen/Qwen3.6-27B"
AIRLLM_COMPRESSION = "4bit"
AIRLLM_MAX_NEW_TOKENS = 2048
AIRLLM_TEMPERATURE = 0.2
AIRLLM_REPETITION_PENALTY = 1.1

# ─── Ollama Configuration ───────────────────────────────────────────────────────

OLLAMA_HOST = "http://localhost:11434"
# Qwen 3.6 27B is the unified model for ALL Ollama agents.
# It is natively multimodal (text + vision) and tops coding benchmarks.
OLLAMA_PLANNER_MODEL = "qwen3.6:27b"
OLLAMA_DEBUGGER_MODEL = "qwen3.6:27b"
OLLAMA_VISION_MODEL = "llava"  # 7B model fits in VRAM for multimodal QA
OLLAMA_TESTER_MODEL = "qwen3.6:27b"  # TDD test generation
OLLAMA_TIMEOUT = 180  # seconds (27B needs slightly more time)

# ─── Gemini (AUDITOR) Configuration ─────────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or get_user_setting("gemini_api_key", "")
GEMINI_MODEL = "gemini-2.5-flash"
AUDITOR_TRIGGER = "on_disagreement"  # "on_disagreement" | "every_n_iterations" | "both"
AUDITOR_EVERY_N = 3

# ─── Context Budgets (tokens per agent per call) ────────────────────────────────

CONTEXT_BUDGETS = {
    "SUPERVISOR": 4800,
    "PLANNER": 3600,
    "CODER": 8200,
    "DEBUGGER": 5400,
    "VISION": 900,
    "AUDITOR": 6000,
    "TESTER": 4000,
}

# ─── Loop & Safety Limits ───────────────────────────────────────────────────────

MAX_ITERATIONS = 100
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
    "AUDITOR":    "#EC4899",
    "TESTER":     "#06B6D4",
    "USER":       "#FFFFFF",
    "SYSTEM":     "#6B7280",
}

# ─── Agent Model Mapping (default, overridable via model_config.json) ────────

DEFAULT_AGENT_MODELS = {
    "SUPERVISOR": {
        "provider": "airllm",
        "model_id": "Qwen/Qwen3.6-27B",
        "display_name": "Qwen3.6 27B (AirLLM)",
        "speed": "~3-5 tok/s",
    },
    "PLANNER": {
        "provider": "airllm",
        "model_id": "Qwen/Qwen3.6-27B",
        "display_name": "Qwen3.6 27B (AirLLM)",
        "speed": "~3-5 tok/s",
    },
    "CODER": {
        "provider": "airllm",
        "model_id": "Qwen/Qwen3.6-27B",
        "display_name": "Qwen3.6 27B (AirLLM)",
        "speed": "~3-5 tok/s",
    },
    "DEBUGGER": {
        "provider": "airllm",
        "model_id": "Qwen/Qwen3.6-27B",
        "display_name": "Qwen3.6 27B (AirLLM)",
        "speed": "~3-5 tok/s",
    },
    "VISION": {
        "provider": "ollama",
        "model_id": "llava",
        "display_name": "LLaVA 7B (Ollama)",
        "speed": "~15 tok/s",
    },
    "AUDITOR": {
        "provider": "gemini",
        "model_id": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "speed": "API",
    },
    "TESTER": {
        "provider": "airllm",
        "model_id": "Qwen/Qwen3.6-27B",
        "display_name": "Qwen3.6 27B (AirLLM)",
        "speed": "~3-5 tok/s",
    },
}

# ─── Storage Media Options ───────────────────────────────────────────────────────

STORAGE_BACKENDS = ["sqlite", "json", "text"]
DEFAULT_STORAGE = "sqlite"

# ─── Hardware ────────────────────────────────────────────────────────────────────

TORCH_DEVICE = "cuda"  # falls back to cpu if unavailable

# Set CUDA memory optimization
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

# ─── Stitch MCP Integration ─────────────────────────────────────────────────────

STITCH_ENABLED = True
STITCH_DEFAULT_PROJECT_ID = ""  # User sets this per project

# ─── Git Time Travel ────────────────────────────────────────────────────────────

GIT_AUTO_COMMIT = True  # Auto-commit after each approved change
GIT_COMMIT_PREFIX = "FORGE"  # Prefix for commit messages

# ─── TDD Configuration ──────────────────────────────────────────────────────────

TDD_ENABLED = True  # Enable test-driven development loop
TDD_FRAMEWORK = "pytest"  # pytest | unittest
TDD_AUTO_INSTALL = False  # Don't auto-install pytest

# ─── RAG Librarian ───────────────────────────────────────────────────────────────

RAG_ENABLED = True
RAG_TOP_K = 3  # Number of doc snippets to inject
RAG_MAX_TOKENS = 1500  # Max tokens for RAG context per call

# ─── AST Indexer ─────────────────────────────────────────────────────────────────

AST_ENABLED = True
AST_SUPPORTED_EXTENSIONS = [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"]

# ─── GUI Settings ────────────────────────────────────────────────────────────────

WINDOW_TITLE = "FORGE — Multi-Agent AI Studio"
WINDOW_GEOMETRY = "1600x900"
WINDOW_MIN_SIZE = (1200, 700)

# Obsidian Forge theme (from Stitch Design System project 5083174531589850372)
THEME = {
    "bg_primary":    "#0A0A0B",   # obsidian-deep
    "bg_secondary":  "#141416",   # obsidian-surface
    "bg_tertiary":   "#201F20",   # surface-container
    "bg_card":       "#1C1B1C",   # surface-container-low
    "bg_input":      "#2A2A2B",   # surface-container-high
    "border":        "#494454",   # outline-variant
    "border_light":  "#958EA0",   # outline
    "text_primary":  "#E5E2E3",   # on-surface
    "text_secondary":"#CBC3D7",   # on-surface-variant
    "text_muted":    "#958EA0",   # outline
    "accent":        "#8B5CF6",   # cyber-violet
    "accent_hover":  "#6D3BD7",   # inverse-primary
    "success":       "#10B981",   # emerald
    "warning":       "#D97706",   # amber-vision
    "error":         "#DC2626",   # crimson-error
    "info":          "#06B6D4",   # electric-cyan
    "secondary":     "#4CD7F6",   # secondary (cyan)
    "tertiary":      "#4EDEA3",   # tertiary (emerald bright)
    "surface_variant": "#353436",
    "primary_container": "#A078FF",
}

# Font configuration (from Stitch design system)
FONTS = {
    "heading":    ("Inter", 18, "bold"),
    "subheading": ("Inter", 14, "bold"),
    "body":       ("Inter", 13),
    "small":      ("Inter", 11),
    "tiny":       ("Inter", 9),
    "label_caps": ("Inter", 11, "bold"),  # for agent identifiers
    "mono":       ("JetBrains Mono", 12),
    "mono_small": ("JetBrains Mono", 10),
    "mono_tiny":  ("JetBrains Mono", 9),
    "telemetry":  ("JetBrains Mono", 10),
}

# ─── Render Modes ────────────────────────────────────────────────────────────────

RENDER_MODES = ["screenshot", "terminal", "embedded_html", "esp32", "none"]
DEFAULT_RENDER_MODE = "terminal"

# ─── Project Types (Generic — supports ANY software) ─────────────────────────────

PROJECT_TYPES = [
    ("Python Desktop App", "python_desktop"),
    ("Python Web App (Flask/FastAPI/Django)", "python_web"),
    ("Python CLI / Script", "python_cli"),
    ("JavaScript / TypeScript (Node.js)", "js_node"),
    ("Web Frontend (HTML/CSS/JS)", "web_frontend"),
    ("ESP32 / Embedded (MicroPython)", "esp32"),
    ("C / C++ Application", "cpp"),
    ("Rust Application", "rust"),
    ("Go Application", "go"),
    ("Existing Codebase (point to dir)", "existing"),
    ("Custom (describe in goal)", "custom"),
]

# ─── Canvas Steering ─────────────────────────────────────────────────────────────

CANVAS_STEERING_ENABLED = True
CANVAS_BOX_COLOR = "#8B5CF6"  # cyber-violet for overlay boxes
CANVAS_BOX_ALPHA = 0.3
