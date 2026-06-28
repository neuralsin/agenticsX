# FORGE — Installation Guide

## Quick Start (Double-click)

1. **Double-click `Launch FORGE.bat`** — that's it.  
   It auto-detects Python, checks dependencies, and opens FORGE.

2. **First run only**: If dependencies are missing it will `pip install` them automatically.

---

## One-time Setup: Desktop Shortcut

```
python setup.py
```

This creates:
- A **FORGE shortcut on your Desktop**
- A **Start Menu entry** under Programs → FORGE

---

## Moving Files to Another Drive

FORGE lets you store models, databases, and projects on **any drive** to keep your C: drive clean.

1. Open FORGE → click **⚙ SETTINGS** → **💾 Storage** tab → **"Open Storage Settings"**
2. Click **Browse…** next to each path and point it to your drive (e.g. `D:\AI\FORGE\models`)
3. Click **Save Settings**
4. **Restart FORGE** — new paths take effect immediately

### What each path controls

| Path | Default | Controls |
|------|---------|----------|
| FORGE Home | `C:\Users\you\.forge` | Config, logs, fallback for all other paths |
| AI Models | `~\.forge\models` | AirLLM/HuggingFace model shards |
| HF_HOME | system default | All `transformers` / `diffusers` caches |
| Ollama Models | Ollama default | All Ollama model blobs |
| Projects | `~\.forge\projects` | Default new project location |
| Sessions/DB | `~\.forge\storage` | SQLite context databases |
| RAG Docs | `~\.forge\docs` | Drop `.txt`/`.md` files for RAG indexing |

---

## Requirements

- **Python 3.10+** — [python.org](https://python.org)
- **pip install** — run once if not using the BAT launcher:

```
pip install -r requirements.txt
```

### AI Model Requirements

| Agent | Model | How to get |
|-------|-------|-----------|
| SUPERVISOR | Qwen3.6 27B (AirLLM) | Auto-downloads via HuggingFace on first use |
| CODER | Qwen3.6 27B (AirLLM) | Same as above |
| PLANNER | DeepSeek-R1 8B | `ollama pull deepseek-r1:8b` |
| DEBUGGER | DeepSeek-R1 8B | `ollama pull deepseek-r1:8b` |
| VISION | Qwen2.5-VL 7B | `ollama pull qwen2.5-vl:7b` |
| TESTER | DeepSeek-R1 8B | `ollama pull deepseek-r1:8b` |
| AUDITOR | Gemini 2.5 Flash | Free API key at [aistudio.google.com](https://aistudio.google.com/apikey) |

### Ollama

Download from [ollama.com](https://ollama.com). Start before launching FORGE:
```
ollama serve
```

### Gemini API Key (for AUDITOR)

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Create a free API key
3. In FORGE: Settings → Storage → enter it in the **Gemini API Key** field
4. Or set the environment variable: `GEMINI_API_KEY=AIza...`

---

## Build a Standalone .exe (Optional)

If you want a self-contained `.exe` that doesn't need Python installed:

```
pip install pyinstaller
pyinstaller forge.spec
```

The output will be in `dist/FORGE/FORGE.exe`.  
> ⚠️ Note: ML libraries (torch, transformers) are excluded from the bundle — they must still be installed on the target machine.

---

## Folder Structure

```
forge/
├── main.py                  ← Entry point
├── Launch FORGE.bat         ← Double-click launcher
├── setup.py                 ← Create Desktop shortcut
├── forge.spec               ← PyInstaller build spec
├── requirements.txt
├── config.py
├── agents/
│   ├── supervisor.py        ← Qwen 27B via AirLLM
│   ├── planner.py           ← DeepSeek-R1 8B via Ollama
│   ├── coder.py             ← Qwen 27B via AirLLM
│   ├── debugger.py          ← DeepSeek-R1 8B via Ollama
│   ├── vision.py            ← Qwen2.5-VL 7B via Ollama
│   ├── auditor.py           ← Gemini 2.5 Flash via API
│   └── tester.py            ← DeepSeek-R1 8B via Ollama
├── core/
│   ├── agent_manager.py     ← Orchestration loop
│   ├── context_manager.py   ← SQLite memory
│   ├── git_manager.py       ← Auto-commit / time travel
│   └── ...
└── gui/
    ├── app.py               ← Main window
    ├── panels/              ← All UI panels
    ├── dialogs/             ← Settings, New Project, Diagnostics
    └── widgets/             ← Agent badge, token meter
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `customtkinter not found` | Run `pip install customtkinter>=5.2.0` |
| Ollama connection error | Run `ollama serve` first |
| AUDITOR skipped | Set `GEMINI_API_KEY` env var or enter it in Settings |
| Two windows on startup | Already fixed in v2 — update via `git pull` |
| Purple flash on startup | Fixed in `main.py` v2 — Obsidian theme applied before window shows |
| Models downloading slowly | Use Storage Settings to point `HF_HOME` to a fast SSD |
