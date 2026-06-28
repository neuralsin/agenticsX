"""
FORGE Main Application — The master GUI window.
Wires all panels together, manages the AgentManager,
handles project/session lifecycle.
Implements the full layout from spec Section 7.
"""

import customtkinter as ctk
import tkinter as tk
import time
import os
from datetime import datetime

from gui.panels.agent_team import AgentTeamPanel
from gui.panels.chat_hub import ChatHubPanel
from gui.panels.code_editor import CodeEditorPanel
from gui.panels.simulator_panel import SimulatorPanel
from gui.panels.context_stats import ContextStatsPanel
from gui.panels.steering_bar import SteeringBar
from gui.dialogs.new_project import NewProjectDialog
from gui.dialogs.diagnostics import DiagnosticsDialog

from core.context_manager import ContextManager
from core.agent_manager import AgentManager
from core.file_watcher import FileWatcher

import config


class ForgeApp:
    """
    Main FORGE application class.
    Creates the full layout:
    ┌──────────────────────────────────────────────────────────┐
    │  TOP BAR: Project selector | Session | Settings         │
    ├────────────┬──────────────────────┬──────────────────────┤
    │  AGENT     │   CONVERSATION       │   CODE EDITOR        │
    │  TEAM      │   HUB                │                      │
    │            │                      ├──────────────────────┤
    │            │                      │   PROJECT RENDER     │
    ├────────────┴──────────────────────┴──────────────────────┤
    │  CONTEXT STATS BAR                                       │
    ├──────────────────────────────────────────────────────────┤
    │  STEERING BAR                                            │
    └──────────────────────────────────────────────────────────┘
    """

    def __init__(self, root: ctk.CTk):
        self.root = root
        self.project_path = None
        self.project_name = None
        self.session_id = None
        self.ctx_manager = None
        self.agent_manager = None
        self.file_watcher = None
        self.render_mode = config.DEFAULT_RENDER_MODE
        self.entry_file = "main.py"

        # Build the UI
        self._build_ui()

        # Show new project dialog on first launch
        self.root.after(500, self._check_initial_project)

    def _build_ui(self):
        """Build the complete FORGE UI layout."""

        # ── Top Bar ──────────────────────────────────────────────
        self.top_bar = ctk.CTkFrame(
            self.root,
            fg_color=config.THEME["bg_tertiary"],
            corner_radius=0,
            height=42,
        )
        self.top_bar.pack(fill="x")
        self.top_bar.pack_propagate(False)

        # FORGE logo/title
        logo_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        logo_frame.pack(side="left", padx=12)

        ctk.CTkLabel(
            logo_frame, text="⚒️",
            font=("Segoe UI", 18),
        ).pack(side="left")

        ctk.CTkLabel(
            logo_frame, text="FORGE",
            font=("Segoe UI", 16, "bold"),
            text_color=config.THEME["accent"],
        ).pack(side="left", padx=(4, 0))

        # Project selector
        self.project_label = ctk.CTkButton(
            self.top_bar, text="No Project ▾",
            font=config.FONTS["small"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border"],
            text_color=config.THEME["text_primary"],
            height=28, corner_radius=6,
            command=self._open_project_dialog,
        )
        self.project_label.pack(side="left", padx=12, pady=7)

        # Session selector
        self.session_label = ctk.CTkButton(
            self.top_bar,
            text="Session: —",
            font=config.FONTS["tiny"],
            fg_color="transparent",
            hover_color=config.THEME["bg_input"],
            text_color=config.THEME["text_muted"],
            height=24, corner_radius=4,
            command=self._new_session,
        )
        self.session_label.pack(side="left", padx=4, pady=7)

        # Right side buttons (pack right-to-left)
        ctk.CTkButton(
            self.top_bar, text="⚙ SETTINGS",
            font=config.FONTS["tiny"],
            fg_color="transparent",
            hover_color=config.THEME["bg_input"],
            text_color=config.THEME["text_secondary"],
            width=80, height=24, corner_radius=4,
            command=self._open_settings,
        ).pack(side="right", padx=8, pady=7)

        ctk.CTkButton(
            self.top_bar, text="🩺 DIAGNOSTICS",
            font=config.FONTS["tiny"],
            fg_color="transparent",
            hover_color=config.THEME["bg_input"],
            text_color=config.THEME["info"],
            width=100, height=24, corner_radius=4,
            command=self._open_diagnostics,
        ).pack(side="right", padx=4, pady=7)

        # VSCode button
        ctk.CTkButton(
            self.top_bar, text="</> VSCODE",
            font=config.FONTS["tiny"],
            fg_color="transparent",
            hover_color=config.THEME["bg_input"],
            text_color="#007ACC",
            width=80, height=24, corner_radius=4,
            command=self._open_in_vscode,
        ).pack(side="right", padx=4, pady=7)

        # Git status indicator
        self.git_status_label = ctk.CTkLabel(
            self.top_bar, text="",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        self.git_status_label.pack(side="right", padx=6, pady=7)

        self.rec_indicator = ctk.CTkLabel(
            self.top_bar, text="●REC",
            font=config.FONTS["tiny"],
            text_color=config.THEME["error"],
        )
        self.rec_indicator.pack(side="right", padx=4, pady=7)
        self.rec_indicator.pack_forget()  # Hidden until running

        # ── Main Content Area ────────────────────────────────────
        main_content = ctk.CTkFrame(
            self.root, fg_color=config.THEME["bg_primary"],
            corner_radius=0,
        )
        main_content.pack(fill="both", expand=True)

        # Configure 3-column grid
        main_content.grid_columnconfigure(0, weight=0, minsize=260)
        main_content.grid_columnconfigure(1, weight=3, minsize=400)
        main_content.grid_columnconfigure(2, weight=2, minsize=300)
        main_content.grid_rowconfigure(0, weight=1)

        # ── Left Panel: Agent Team ───────────────────────────────
        self.agent_panel = AgentTeamPanel(main_content)
        self.agent_panel.grid(row=0, column=0, sticky="nsew")

        # Separator
        ctk.CTkFrame(
            main_content, fg_color=config.THEME["border"],
            width=1, corner_radius=0,
        ).grid(row=0, column=0, sticky="nse")

        # ── Center Panel: Conversation Hub ───────────────────────
        self.chat_panel = ChatHubPanel(main_content)
        self.chat_panel.grid(row=0, column=1, sticky="nsew")

        # Separator
        ctk.CTkFrame(
            main_content, fg_color=config.THEME["border"],
            width=1, corner_radius=0,
        ).grid(row=0, column=1, sticky="nse")

        # ── Right Panel: Code Editor (top) + Simulator (bottom) ──
        right_panel = ctk.CTkFrame(
            main_content, fg_color=config.THEME["bg_secondary"],
            corner_radius=0,
        )
        right_panel.grid(row=0, column=2, sticky="nsew")
        right_panel.grid_rowconfigure(0, weight=3)
        right_panel.grid_rowconfigure(1, weight=2)
        right_panel.grid_columnconfigure(0, weight=1)

        # Code editor (top half)
        self.code_panel = CodeEditorPanel(right_panel)
        self.code_panel.grid(row=0, column=0, sticky="nsew")

        # Separator
        ctk.CTkFrame(
            right_panel, fg_color=config.THEME["border"],
            height=1, corner_radius=0,
        ).grid(row=0, column=0, sticky="sew")

        # Simulator (bottom half)
        self.sim_panel = SimulatorPanel(right_panel)
        self.sim_panel.grid(row=1, column=0, sticky="nsew")
        self.sim_panel.on_canvas_steer = self._handle_canvas_steer

        # ── Steering Bar (bottom input) ──────────────────────────
        self.steering_bar = SteeringBar(self.root)
        self.steering_bar.pack(fill="x", side="bottom")

        # ── Context Stats Bar ────────────────────────────────────
        self.stats_panel = ContextStatsPanel(self.root)
        self.stats_panel.pack(fill="x", side="bottom")
        self.stats_panel.on_timeline_requested = self._on_timeline_requested

        # ── Wire up steering callbacks ───────────────────────────
        self.steering_bar.on_start = self._on_start_goal
        self.steering_bar.on_pause = self._on_pause
        self.steering_bar.on_resume = self._on_resume
        self.steering_bar.on_stop = self._on_stop
        self.steering_bar.on_steering = self._on_steering_input
        self.steering_bar.on_replan = self._on_replan
        self.steering_bar.on_skip = self._on_skip
        self.steering_bar.on_retry = self._on_retry

    # ── Project Management ───────────────────────────────────────────────────────

    def _check_initial_project(self):
        """Show project dialog on first launch. Cancelling is fine — app stays open."""
        if self.project_path is None:
            self._open_project_dialog()
            # If user cancelled, show idle state — do NOT exit
            if self.project_path is None:
                self.chat_panel.add_message(
                    "SYSTEM",
                    "👋 Welcome to FORGE!\n\n"
                    "No project loaded yet.\n"
                    "• Click the project selector in the top bar to create or open a project.\n"
                    "• Then enter a goal and press ▶ START.",
                    "system",
                )

    def _open_project_dialog(self):
        """Open the new/open project dialog. Returns without crashing if cancelled."""
        dialog = NewProjectDialog(self.root)
        self.root.wait_window(dialog)

        result = dialog.get_result()
        if result:
            self._handle_new_project_result(result)
        # No else — just stay idle


    def _handle_new_project_result(self, result: dict):
        """Load a project from a dialog result dict."""
        if not result:
            return

        self.project_path = result["path"]
        self.project_name = result["name"]
        self.render_mode = result.get("render_mode", config.DEFAULT_RENDER_MODE)
        self.entry_file = result.get("entry_file", "main.py")
        project_type = result.get("type", "custom")

        # Update UI
        self.project_label.configure(text=f"{self.project_name} ▾")

        # Load file tree into editor
        self.code_panel.load_project_tree(self.project_path)

        # Set render mode
        self.sim_panel.mode_var.set(self.render_mode)

        # Start new session
        self._new_session()

        # Start file watcher
        self._start_file_watcher()

        # Initialize Git repo if auto-commit is enabled
        self._init_git()

        # Welcome message
        self.chat_panel.add_message(
            "SYSTEM",
            f"✅ Project '{self.project_name}' loaded.\n"
            f"📁 Path: {self.project_path}\n"
            f"🔧 Type: {project_type}\n"
            f"🎬 Render: {self.render_mode}\n\n"
            f"Enter your goal below and press ▶ START.",
            "system"
        )

        # Handle Stitch Design System injection
        stitch_id = result.get("stitch_project_id", "")
        if stitch_id and self.ctx_manager:
            self.chat_panel.add_message(
                "SYSTEM", f"🎨 Loading Stitch Design System: {stitch_id}...", "system"
            )
            try:
                from core.stitch_bridge import StitchBridge
                bridge = StitchBridge()
                context = bridge.get_full_context(stitch_id)
                if context:
                    self.ctx_manager.add_steering(self.session_id, context, 0)
                    self.chat_panel.add_message(
                        "SYSTEM", "✅ Design System loaded into agent context.", "system"
                    )
                else:
                    self.chat_panel.add_message(
                        "SYSTEM", "⚠️ No Stitch context returned. Continuing without it.", "system"
                    )
            except Exception as e:
                self.chat_panel.add_message(
                    "SYSTEM", f"⚠️ Stitch load failed: {e}", "system"
                )

    def _start_file_watcher(self):
        """Start watching the project directory for external changes."""
        if not self.project_path or not os.path.isdir(self.project_path):
            return
        if self.file_watcher:
            try:
                self.file_watcher.stop()
            except Exception:
                pass
        try:
            self.file_watcher = FileWatcher(
                self.project_path,
                callback=self._on_file_change
            )
            self.file_watcher.start()
        except Exception as e:
            # File watcher is optional — never crash the app over it
            pass

    # ── Session Management ───────────────────────────────────────────────────────

    def _new_session(self):
        """Create a new session for the current project."""
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        name = self.project_name or "forge"
        self.session_id = f"{name}_{ts}"

        # Initialize context manager (DB lives inside .forge folder)
        if self.project_path:
            forge_dir = os.path.join(self.project_path, ".forge")
            os.makedirs(forge_dir, exist_ok=True)
            db_path = os.path.join(forge_dir, "context.db")
        else:
            db_path = str(config.STORAGE_DIR / "context.db")

        self.ctx_manager = ContextManager(db_path)
        # Let the context manager know the project path for AST indexing
        self.ctx_manager.current_project_path = self.project_path or ""

        # Update session label
        display_ts = datetime.now().strftime("%H:%M:%S")
        self.session_label.configure(text=f"Session: {display_ts} ▾")

    # ── Git Integration ──────────────────────────────────────────────────────────

    def _init_git(self):
        """Initialize git for the current project and update the status indicator."""
        if not self.project_path:
            return
        try:
            from core.git_manager import GitManager
            self._git_mgr = GitManager(self.project_path)
            if config.GIT_AUTO_COMMIT:
                self._git_mgr.init_repo()
            self._update_git_status()
        except Exception as e:
            self.git_status_label.configure(
                text="Git: error", text_color=config.THEME["error"]
            )

    def _update_git_status(self):
        """Refresh the Git status indicator in the top bar."""
        if not hasattr(self, "_git_mgr") or not self._git_mgr:
            self.git_status_label.configure(text="")
            return
        try:
            ok, stdout, _ = self._git_mgr._run_git("status", "--porcelain")
            branch_ok, branch_out, _ = self._git_mgr._run_git(
                "rev-parse", "--abbrev-ref", "HEAD"
            )
            branch = branch_out.strip() if branch_ok else "?"
            if ok:
                changed = len([l for l in stdout.strip().split("\n") if l.strip()])
                if changed == 0:
                    self.git_status_label.configure(
                        text=f"Git: {branch} \u2714",
                        text_color=config.THEME["success"],
                    )
                else:
                    self.git_status_label.configure(
                        text=f"Git: {branch} \u00b7 {changed} changed",
                        text_color=config.THEME["warning"],
                    )
            else:
                self.git_status_label.configure(
                    text="Git: not initialized",
                    text_color=config.THEME["text_muted"],
                )
        except Exception:
            self.git_status_label.configure(text="Git: ?")

    # ── VSCode Integration ───────────────────────────────────────────────────────

    def _open_in_vscode(self):
        """Open the project in VS Code so the user can see live changes."""
        if not self.project_path:
            self.chat_panel.add_message(
                "SYSTEM", "No project loaded. Open a project first.", "system"
            )
            return
        import subprocess
        try:
            subprocess.Popen(
                ["code", self.project_path],
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
                if os.name == "nt" else 0,
            )
            self.chat_panel.add_message(
                "SYSTEM",
                f"Opened VS Code for: {self.project_path}",
                "system",
            )
        except FileNotFoundError:
            self.chat_panel.add_message(
                "SYSTEM",
                "VS Code not found. Install it and add 'code' to PATH.\n"
                "Download: https://code.visualstudio.com/",
                "system",
            )
        except Exception as e:
            self.chat_panel.add_message(
                "SYSTEM", f"Could not launch VS Code: {e}", "system"
            )

    # ── Agent Loop Control ───────────────────────────────────────────────────────


    def _on_start_goal(self, goal: str):
        """Start the agent loop with a goal."""
        if not self.project_path:
            self.chat_panel.add_message(
                "SYSTEM",
                "❌ No project loaded. Create or open a project first.",
                "system"
            )
            return

        if not self.ctx_manager:
            self._new_session()

        # Create fresh agent manager, passing the project's render mode
        self.agent_manager = AgentManager(
            self.ctx_manager, self.project_path, self.session_id,
            render_mode=getattr(self, "render_mode", "terminal"),
        )

        # Wire all callbacks (thread-safe via root.after)
        self.agent_manager.on_message = lambda *a: self.root.after(0, self._on_agent_message, *a)
        self.agent_manager.on_agent_status = lambda *a: self.root.after(0, self._on_agent_status_change, *a)
        self.agent_manager.on_file_changed = lambda *a: self.root.after(0, self._on_file_changed, *a)
        self.agent_manager.on_exec_result = lambda *a: self.root.after(0, self._on_exec_result, *a)
        self.agent_manager.on_vision_report = lambda *a: self.root.after(0, self._on_vision_report, *a)
        self.agent_manager.on_stats_update = lambda *a: self.root.after(0, self._on_stats_update, *a)
        self.agent_manager.on_plan_update = lambda *a: self.root.after(0, self._on_plan_update, *a)
        self.agent_manager.on_complete = lambda *a: self.root.after(0, self._on_complete, *a)
        self.agent_manager.on_error = lambda *a: self.root.after(0, self._on_error, *a)
        self.agent_manager.on_iteration_start = lambda *a: self.root.after(0, self._on_iteration, *a)

        # Show recording indicator
        self.rec_indicator.pack(side="right", padx=4, pady=7)
        self._pulse_rec()

        # Launch
        self.agent_manager.start(goal)
        self.steering_bar.set_running(True)
        self.chat_panel.set_live(True)

    def _on_pause(self):
        """Pause the agent loop."""
        if self.agent_manager:
            self.agent_manager.pause()

    def _on_resume(self):
        """Resume the agent loop."""
        if self.agent_manager:
            self.agent_manager.resume()
            self.steering_bar.set_running(True)

    def _on_stop(self):
        """Stop the agent loop."""
        if self.agent_manager:
            self.agent_manager.stop()
        self.steering_bar.set_running(False)
        self.rec_indicator.pack_forget()
        self.chat_panel.set_live(False)

    def _on_steering_input(self, text: str):
        """Handle user steering injection."""
        if self.agent_manager and self.ctx_manager and self.session_id:
            self.agent_manager.inject_steering(text)
        self.chat_panel.add_message("USER", f"[STEERING] {text}", "user")

    def _handle_canvas_steer(self, x1: int, y1: int, x2: int, y2: int):
        """Handle steering box drawn on simulator canvas."""
        text = (
            f"I highlighted the UI region from ({x1},{y1}) to ({x2},{y2}). "
            f"Please fix/improve that specific area."
        )
        self._on_steering_input(text)

    def _on_replan(self):
        """Trigger a replan."""
        if self.agent_manager:
            self.agent_manager.inject_steering("[REPLAN] User requests full replanning.")

    def _on_skip(self):
        """Skip current step."""
        if self.agent_manager:
            self.agent_manager.skip_step()

    def _on_retry(self):
        """Retry current step."""
        if self.agent_manager:
            self.agent_manager.retry_step()

    # ── Timeline ─────────────────────────────────────────────────────────────────

    def _on_timeline_requested(self):
        """Show Git commit timeline in chat."""
        if not self.agent_manager:
            self.chat_panel.add_message("SYSTEM", "⚠️ No active session.", "system")
            return
        try:
            git_mgr = getattr(self.agent_manager, "git_manager", None)
            if not git_mgr:
                self.chat_panel.add_message("SYSTEM", "⚠️ Git not initialised.", "system")
                return
            timeline = git_mgr.get_timeline()
            if not timeline:
                self.chat_panel.add_message("SYSTEM", "📂 No commits yet.", "system")
                return
            lines = ["🕐 Git Timeline (last 10 commits):"]
            for entry in timeline[-10:]:
                lines.append(
                    f"  [{entry.get('short_hash','?')}] "
                    f"Iter {entry.get('iteration','?')}: "
                    f"{str(entry.get('description',''))[:60]}"
                )
            self.chat_panel.add_message("SYSTEM", "\n".join(lines), "system")
        except Exception as e:
            self.chat_panel.add_message("SYSTEM", f"⚠️ Timeline error: {e}", "system")

    # ── Agent Manager Callbacks ───────────────────────────────────────────────────

    def _on_agent_message(self, agent_name: str, content: str, role: str):
        self.chat_panel.add_message(agent_name, content, role)

    def _on_agent_status_change(self, agent_name: str, status: str):
        self.agent_panel.set_agent_status(agent_name, status)

    def _on_iteration(self, iteration: int):
        """Called at the start of each loop iteration — refresh visual indicators."""
        self._update_git_status()
        self.stats_panel.update_iteration(iteration)

    def _on_file_changed(self, filepath: str, diff: str):
        self.code_panel.add_changed_file(filepath)
        if diff:
            self.code_panel.show_diff(filepath, diff, "Applied by CODER — SUPERVISOR approved")
        if self.project_path:
            self.code_panel.load_project_tree(self.project_path)
        # Refresh Git status after file changes
        self._update_git_status()

    def _on_exec_result(self, exit_code: int, stdout: str, stderr: str):
        if stdout:
            self.sim_panel.show_terminal_output(stdout)
        status = "✓ Success" if exit_code == 0 else f"✗ Exit code {exit_code}"
        parts = [f"Execution: {status}"]
        if stdout:
            parts.append(f"STDOUT:\n{stdout[:500]}")
        if stderr:
            parts.append(f"STDERR:\n{stderr[:500]}")
        self.chat_panel.add_message("SYSTEM", "\n".join(parts), "system")

    def _on_vision_report(self, report: dict):
        if report.get("screenshot_path") and os.path.isfile(report["screenshot_path"]):
            self.sim_panel.add_frame(report["screenshot_path"])

    def _on_stats_update(self, stats: dict):
        self.stats_panel.update_stats(stats)
        per_agent = stats.get("per_agent", {})
        self.agent_panel.update_all(per_agent)

    def _on_plan_update(self, plan: list, current_step: int):
        self.stats_panel.update_plan(plan, current_step)

    def _on_complete(self, reason: str):
        self.chat_panel.add_message(
            "SYSTEM", f"🏁 FORGE loop completed: {reason}", "system"
        )
        self.steering_bar.set_running(False)
        self.rec_indicator.pack_forget()
        self.chat_panel.set_live(False)
        self._update_git_status()

    def _on_error(self, error_msg: str):
        self.chat_panel.add_message("SYSTEM", f"❌ Error: {error_msg}", "system")

    def _on_file_change(self, event_type: str, filepath: str):
        """Handle external file changes (from file watcher)."""
        self.root.after(0, lambda: self.code_panel.load_project_tree(self.project_path))

    # ── Recording indicator ───────────────────────────────────────────────────────

    def _pulse_rec(self):
        """Animate the recording indicator."""
        if not self.agent_manager or not self.agent_manager.running:
            return
        current = self.rec_indicator.cget("text_color")
        if current == config.THEME["error"]:
            self.rec_indicator.configure(text_color=config.THEME["bg_tertiary"])
        else:
            self.rec_indicator.configure(text_color=config.THEME["error"])
        self.root.after(800, self._pulse_rec)

    # ── Dialogs ───────────────────────────────────────────────────────────────────

    def _open_diagnostics(self):
        """Open the system diagnostics dialog."""
        DiagnosticsDialog(self.root)

    def _open_settings(self):
        """Open the full FORGE settings dialog (tabbed)."""
        settings_win = ctk.CTkToplevel(self.root)
        settings_win.title("FORGE — Settings")
        settings_win.geometry("560x500")
        settings_win.configure(fg_color=config.THEME["bg_secondary"])
        settings_win.transient(self.root)
        settings_win.grab_set()
        settings_win.resizable(True, True)

        # Header
        ctk.CTkLabel(
            settings_win, text="⚙️  FORGE Settings",
            font=config.FONTS["heading"],
            text_color=config.THEME["text_primary"],
        ).pack(padx=20, pady=(16, 8), anchor="w")

        tabview = ctk.CTkTabview(
            settings_win,
            fg_color=config.THEME["bg_primary"],
            segmented_button_fg_color=config.THEME["bg_tertiary"],
            segmented_button_selected_color=config.THEME["accent"],
            segmented_button_selected_hover_color=config.THEME["accent_hover"],
            segmented_button_unselected_color=config.THEME["bg_tertiary"],
            segmented_button_unselected_hover_color=config.THEME["bg_input"],
            text_color=config.THEME["text_primary"],
        )
        tabview.pack(fill="both", expand=True, padx=16, pady=8)

        # ── Tab 1: Storage Paths ──────────────────────────────────────────────
        tab_storage = tabview.add("💾 Storage")

        storage_items = [
            ("FORGE Home", str(config.FORGE_DIR)),
            ("Models Dir", str(config.MODELS_DIR)),
            ("Projects Dir", str(config.PROJECTS_DIR)),
            ("Sessions / DB", str(config.STORAGE_DIR)),
            ("RAG Docs Dir", str(config.DOCS_DIR)),
            ("HF_HOME", os.environ.get("HF_HOME", "(default)")),
            ("OLLAMA_MODELS", os.environ.get("OLLAMA_MODELS", "(default)")),
            ("Settings File", str(config.USER_SETTINGS_FILE)),
        ]

        scroll_s = ctk.CTkScrollableFrame(tab_storage, fg_color="transparent")
        scroll_s.pack(fill="both", expand=True)

        for lbl, val in storage_items:
            row = ctk.CTkFrame(scroll_s, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=lbl, font=config.FONTS["small"],
                         text_color=config.THEME["text_secondary"],
                         width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val, font=config.FONTS["mono_tiny"],
                         text_color=config.THEME["text_primary"],
                         anchor="w", wraplength=340).pack(side="left", padx=4)

        ctk.CTkButton(
            tab_storage, text="📂  Open Storage Settings...",
            font=config.FONTS["body"],
            fg_color=config.THEME["accent"],
            hover_color=config.THEME["accent_hover"],
            text_color="#FFFFFF",
            height=38, corner_radius=8,
            command=lambda: self._launch_storage_settings(settings_win),
        ).pack(pady=(12, 4), padx=16, fill="x")

        # ── Tab 2: Models ─────────────────────────────────────────────────────
        tab_models = tabview.add("🤖 Models")

        model_items = [
            ("AirLLM Model", config.AIRLLM_MODEL_ID),
            ("Ollama Host", config.OLLAMA_HOST),
            ("Planner (Ollama)", config.OLLAMA_PLANNER_MODEL),
            ("Debugger (Ollama)", config.OLLAMA_DEBUGGER_MODEL),
            ("Vision (Ollama)", config.OLLAMA_VISION_MODEL),
            ("Tester (Ollama)", config.OLLAMA_TESTER_MODEL),
            ("Auditor (Gemini)", config.GEMINI_MODEL),
            ("Gemini Key Set", "Yes ✓" if config.GEMINI_API_KEY else "No ✗"),
        ]

        scroll_m = ctk.CTkScrollableFrame(tab_models, fg_color="transparent")
        scroll_m.pack(fill="both", expand=True)

        for lbl, val in model_items:
            row = ctk.CTkFrame(scroll_m, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=lbl, font=config.FONTS["small"],
                         text_color=config.THEME["text_secondary"],
                         width=150, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val, font=config.FONTS["mono_tiny"],
                         text_color=config.THEME["text_primary"],
                         anchor="w").pack(side="left", padx=4)

        ctk.CTkButton(
            tab_models, text="🤖  Change Models...",
            font=config.FONTS["body"],
            fg_color=config.THEME["accent"],
            hover_color=config.THEME["accent_hover"],
            text_color="#FFFFFF",
            height=38, corner_radius=8,
            command=lambda: self._launch_model_picker(settings_win),
        ).pack(pady=(12, 4), padx=16, fill="x")

        # ── Tab 3: Loop Config ────────────────────────────────────────────────
        tab_loop = tabview.add("🔄 Loop")

        loop_items = [
            ("Max Iterations", str(config.MAX_ITERATIONS)),
            ("Exec Timeout", f"{config.EXEC_TIMEOUT}s"),
            ("TDD Enabled", "Yes ✓" if config.TDD_ENABLED else "No"),
            ("TDD Framework", config.TDD_FRAMEWORK),
            ("Git Auto-commit", "Yes ✓" if config.GIT_AUTO_COMMIT else "No"),
            ("Git Prefix", config.GIT_COMMIT_PREFIX),
            ("RAG Enabled", "Yes ✓" if config.RAG_ENABLED else "No"),
            ("RAG Top-K", str(config.RAG_TOP_K)),
            ("AST Indexer", "Yes ✓" if config.AST_ENABLED else "No"),
            ("Auditor Trigger", config.AUDITOR_TRIGGER),
            ("Auditor Every N", str(config.AUDITOR_EVERY_N)),
            ("Canvas Steering", "Yes ✓" if config.CANVAS_STEERING_ENABLED else "No"),
            ("Context Prune", f"{int(config.CONTEXT_PRUNE_THRESHOLD*100)}%"),
            ("Backup Versions", str(config.BACKUP_VERSIONS_KEPT)),
        ]

        scroll_l = ctk.CTkScrollableFrame(tab_loop, fg_color="transparent")
        scroll_l.pack(fill="both", expand=True)

        for lbl, val in loop_items:
            row = ctk.CTkFrame(scroll_l, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=lbl, font=config.FONTS["small"],
                         text_color=config.THEME["text_secondary"],
                         width=160, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val, font=config.FONTS["mono_small"],
                         text_color=config.THEME["text_primary"],
                         anchor="w").pack(side="left", padx=4)

        # Close button
        ctk.CTkButton(
            settings_win, text="Close",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_primary"],
            width=100, height=36, corner_radius=8,
            command=settings_win.destroy,
        ).pack(pady=(0, 14))

    def _launch_storage_settings(self, parent_win=None):
        """Open the Storage Path Settings dialog."""
        from gui.dialogs.storage_settings import StorageSettingsDialog
        w = parent_win or self.root
        StorageSettingsDialog(w)

    def _launch_model_picker(self, parent_win=None):
        """Open the Model Picker dialog."""
        from gui.dialogs.model_picker import ModelPickerDialog
        w = parent_win or self.root
        ModelPickerDialog(w)
