# FORGE — PyInstaller Spec
# Build a single-directory .exe bundle:
#   pip install pyinstaller
#   pyinstaller forge.spec

import sys
from pathlib import Path

block_cipher = None
FORGE_ROOT = Path(SPECPATH)

a = Analysis(
    [str(FORGE_ROOT / 'main.py')],
    pathex=[str(FORGE_ROOT)],
    binaries=[],
    datas=[
        # Include all GUI asset files
        (str(FORGE_ROOT / 'forge_icon.ico'), '.') if (FORGE_ROOT / 'forge_icon.ico').exists() else None,
    ],
    hiddenimports=[
        # CustomTkinter internals
        'customtkinter',
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageGrab',
        # FORGE modules
        'config',
        'agents.base_agent', 'agents.airllm_agent', 'agents.ollama_agent',
        'agents.supervisor', 'agents.planner', 'agents.coder',
        'agents.debugger', 'agents.vision', 'agents.auditor', 'agents.tester',
        'core.context_manager', 'core.agent_manager', 'core.diff_engine',
        'core.executor', 'core.file_watcher', 'core.token_counter',
        'core.git_manager', 'core.ast_indexer', 'core.rag_librarian',
        'core.stitch_bridge', 'core.model_registry',
        'gui.app',
        'gui.panels.agent_team', 'gui.panels.chat_hub',
        'gui.panels.code_editor', 'gui.panels.simulator_panel',
        'gui.panels.context_stats', 'gui.panels.steering_bar',
        'gui.widgets.agent_badge', 'gui.widgets.token_meter',
        'gui.dialogs.new_project', 'gui.dialogs.diagnostics',
        'gui.dialogs.storage_settings',
        # Optional ML libraries — include if installed
        'tiktoken', 'pygments', 'watchdog',
        'google.generativeai',
        'psutil', 'pynvml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude huge ML packages from the .exe (loaded from disk at runtime)
        'torch', 'transformers', 'airllm',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out None entries from datas
a.datas = [(src, dst, kind) for src, dst, kind in a.datas if src]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FORGE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,            # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(FORGE_ROOT / 'forge_icon.ico') if (FORGE_ROOT / 'forge_icon.ico').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FORGE',
)
