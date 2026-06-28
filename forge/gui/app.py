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
import uuid
from datetime import datetime

from gui.panels.agent_team import AgentTeamPanel
from gui.panels.chat_hub import ChatHubPanel
from gui.panels.code_editor import CodeEditorPanel
from gui.panels.simulator_panel import SimulatorPanel
from gui.panels.context_stats import ContextStatsPanel
from gui.panels.steering_bar import SteeringBar
from gui.dialogs.new_project import NewProjectDialog

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
        self.render_mode = "terminal"
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
        
        # Right side: recording + settings
        ctk.CTkButton(
            self.top_bar, text="⚙ SETTINGS",
            font=config.FONTS["tiny"],
            fg_color="transparent",
            hover_color=config.THEME["bg_input"],
            text_color=config.THEME["text_secondary"],
            width=80, height=24, corner_radius=4,
            command=self._open_settings,
        ).pack(side="right", padx=8, pady=7)
        
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
        sep1 = ctk.CTkFrame(
            main_content, fg_color=config.THEME["border"],
            width=1, corner_radius=0,
        )
        sep1.grid(row=0, column=0, sticky="nse")
        
        # ── Center Panel: Conversation Hub ───────────────────────
        self.chat_panel = ChatHubPanel(main_content)
        self.chat_panel.grid(row=0, column=1, sticky="nsew")
        
        # Separator
        sep2 = ctk.CTkFrame(
            main_content, fg_color=config.THEME["border"],
            width=1, corner_radius=0,
        )
        sep2.grid(row=0, column=1, sticky="nse")
        
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
        sep3 = ctk.CTkFrame(
            right_panel, fg_color=config.THEME["border"],
            height=1, corner_radius=0,
        )
        sep3.grid(row=0, column=0, sticky="sew")
        
        # Simulator (bottom half)
        self.sim_panel = SimulatorPanel(right_panel)
        self.sim_panel.grid(row=1, column=0, sticky="nsew")
        
        # ── Bottom Section ───────────────────────────────────────
        
        # Context stats bar
        self.stats_panel = ContextStatsPanel(self.root)
        self.stats_panel.pack(fill="x")
        
        # Separator
        ctk.CTkFrame(
            self.root, fg_color=config.THEME["border"],
            height=1, corner_radius=0,
        ).pack(fill="x")
        
        # Steering bar (bottom input)
        self.steering_bar = SteeringBar(self.root)
        self.steering_bar.pack(fill="x")
        
        # ── Wire up callbacks ────────────────────────────────────
        self.steering_bar.on_start = self._on_start_goal
        self.steering_bar.on_pause = self._on_pause
        self.steering_bar.on_resume = self._on_resume
        self.steering_bar.on_stop = self._on_stop
        self.steering_bar.on_steering = self._on_steering_input
        self.steering_bar.on_replan = self._on_replan
        self.steering_bar.on_skip = self._on_skip
        self.steering_bar.on_retry = self._on_retry

    def _check_initial_project(self):
        """Check if a project is loaded; if not, show new project dialog."""
        if self.project_path is None:
            self._open_project_dialog()

    def _open_project_dialog(self):
        """Open the new project dialog."""
        dialog = NewProjectDialog(self.root)
        self.root.wait_window(dialog)
        
        result = dialog.get_result()
        if result:
            self._load_project(result)

    def _load_project(self, project_config: dict):
        """Load a project from config dict."""
        self.project_name = project_config["name"]
        self.project_path = project_config["path"]
        self.render_mode = project_config.get("render_mode", "terminal")
        self.entry_file = project_config.get("entry_file", "main.py")
        
        # Create new session
        self._new_session()
        
        # Update UI
        self.project_label.configure(text=f"{self.project_name} ▾")
        
        # Load file tree
        self.code_panel.load_project_tree(self.project_path)
        
        # Set render mode
        self.sim_panel.mode_var.set(self.render_mode)
        
        # Initialize file watcher
        if self.file_watcher:
            self.file_watcher.stop()
        self.file_watcher = FileWatcher(
            self.project_path, 
            callback=self._on_file_change
        )
        self.file_watcher.start()
        
        # Add system message
        self.chat_panel.add_message(
            "SYSTEM",
            f"Project '{self.project_name}' loaded.\n"
            f"Path: {self.project_path}\n"
            f"Type: {project_config.get('type', 'custom')}\n"
            f"Render: {self.render_mode}\n"
            f"Enter your goal and press ▶ START.",
            "system"
        )

    def _new_session(self):
        """Create a new session for the current project."""
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        name = self.project_name or "forge"
        self.session_id = f"{name}_{ts}"
        
        # Initialize context manager
        if self.project_path:
            db_path = os.path.join(
                self.project_path, ".forge", "context.db"
            )
        else:
            db_path = str(config.STORAGE_DIR / "context.db")
        
        self.ctx_manager = ContextManager(db_path)
        
        # Update session label
        display_ts = datetime.now().strftime("%Y-%m-%d #1")
        self.session_label.configure(text=f"Session: {display_ts} ▾")

    def _on_start_goal(self, goal: str):
        """Start the agent loop with a goal."""
        if not self.project_path:
            self.chat_panel.add_message(
                "SYSTEM",
                "No project loaded. Create or open a project first.",
                "system"
            )
            return
        
        if not self.ctx_manager:
            self._new_session()
        
        # Create agent manager
        self.agent_manager = AgentManager(
            self.ctx_manager, self.project_path, self.session_id
        )
        
        # Wire up callbacks (thread-safe via root.after)
        self.agent_manager.on_message = lambda *args: self.root.after(
            0, self._on_agent_message, *args
        )
        self.agent_manager.on_agent_status = lambda *args: self.root.after(
            0, self._on_agent_status_change, *args
        )
        self.agent_manager.on_file_changed = lambda *args: self.root.after(
            0, self._on_file_changed, *args
        )
        self.agent_manager.on_exec_result = lambda *args: self.root.after(
            0, self._on_exec_result, *args
        )
        self.agent_manager.on_vision_report = lambda *args: self.root.after(
            0, self._on_vision_report, *args
        )
        self.agent_manager.on_stats_update = lambda *args: self.root.after(
            0, self._on_stats_update, *args
        )
        self.agent_manager.on_plan_update = lambda *args: self.root.after(
            0, self._on_plan_update, *args
        )
        self.agent_manager.on_complete = lambda *args: self.root.after(
            0, self._on_complete, *args
        )
        self.agent_manager.on_error = lambda *args: self.root.after(
            0, self._on_error, *args
        )
        
        # Show recording indicator
        self.rec_indicator.pack(side="right", padx=4, pady=7)
        self._pulse_rec()
        
        # Start
        self.agent_manager.start(goal)
        self.steering_bar.set_running(True)

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

    def _on_steering_input(self, text: str):
        """Handle user steering injection."""
        if self.agent_manager:
            self.agent_manager.inject_steering(text)
        self.chat_panel.add_message("USER", f"[STEERING] {text}", "user")

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

    # ── Agent Manager Callbacks (run on main thread via root.after) ──

    def _on_agent_message(self, agent_name: str, content: str, role: str):
        """Handle new message from an agent."""
        self.chat_panel.add_message(agent_name, content, role)

    def _on_agent_status_change(self, agent_name: str, status: str):
        """Handle agent status change."""
        self.agent_panel.set_agent_status(agent_name, status)

    def _on_file_changed(self, filepath: str, diff: str):
        """Handle file change."""
        self.code_panel.add_changed_file(filepath)
        if diff:
            self.code_panel.show_diff(filepath, diff,
                                      "Applied by CODER — SUPERVISOR approved")
        # Refresh file tree
        if self.project_path:
            self.code_panel.load_project_tree(self.project_path)

    def _on_exec_result(self, exit_code: int, stdout: str, stderr: str):
        """Handle execution result."""
        if stdout:
            self.sim_panel.show_terminal_output(stdout)
        status = "✓ Success" if exit_code == 0 else f"✗ Failed (code {exit_code})"
        self.chat_panel.add_message(
            "SYSTEM",
            f"Execution: {status}\n"
            + (f"STDOUT:\n{stdout[:500]}\n" if stdout else "")
            + (f"STDERR:\n{stderr[:500]}" if stderr else ""),
            "system"
        )

    def _on_vision_report(self, report: dict):
        """Handle vision analysis report."""
        # Try to display the screenshot
        if "screenshot_path" in report and report.get("screenshot_path"):
            self.sim_panel.add_frame(report["screenshot_path"])

    def _on_stats_update(self, stats: dict):
        """Handle stats update from agent manager."""
        self.stats_panel.update_stats(stats)
        
        # Update agent cards
        per_agent = stats.get("per_agent", {})
        self.agent_panel.update_all(per_agent)

    def _on_plan_update(self, plan: list, current_step: int):
        """Handle plan update."""
        self.stats_panel.update_plan(plan, current_step)

    def _on_complete(self, reason: str):
        """Handle loop completion."""
        self.chat_panel.add_message(
            "SYSTEM",
            f"🏁 FORGE loop completed: {reason}",
            "system"
        )
        self.steering_bar.set_running(False)
        self.rec_indicator.pack_forget()

    def _on_error(self, error_msg: str):
        """Handle agent loop error."""
        self.chat_panel.add_message(
            "SYSTEM",
            f"❌ Error: {error_msg}",
            "system"
        )

    def _on_file_change(self, event_type: str, filepath: str):
        """Handle external file changes (from file watcher)."""
        # Thread-safe GUI update
        self.root.after(0, lambda: self.code_panel.load_project_tree(
            self.project_path
        ))

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

    def _open_settings(self):
        """Open settings dialog."""
        settings = ctk.CTkToplevel(self.root)
        settings.title("FORGE — Settings")
        settings.geometry("500x400")
        settings.configure(fg_color=config.THEME["bg_secondary"])
        settings.transient(self.root)
        settings.grab_set()
        
        # Header
        ctk.CTkLabel(
            settings, text="⚙️ Settings",
            font=config.FONTS["heading"],
            text_color=config.THEME["text_primary"],
        ).pack(padx=20, pady=(16, 8), anchor="w")
        
        scroll = ctk.CTkScrollableFrame(
            settings, fg_color="transparent",
        )
        scroll.pack(fill="both", expand=True, padx=16, pady=8)
        
        # Model settings
        ctk.CTkLabel(
            scroll, text="Model Configuration",
            font=config.FONTS["subheading"],
            text_color=config.THEME["accent"],
        ).pack(anchor="w", pady=(0, 4))
        
        settings_items = [
            ("AirLLM Model", config.AIRLLM_MODEL_ID),
            ("Ollama Host", config.OLLAMA_HOST),
            ("Planner Model", config.OLLAMA_PLANNER_MODEL),
            ("Debugger Model", config.OLLAMA_DEBUGGER_MODEL),
            ("Vision Model", config.OLLAMA_VISION_MODEL),
            ("Max Iterations", str(config.MAX_ITERATIONS)),
            ("Execution Timeout", f"{config.EXEC_TIMEOUT}s"),
        ]
        
        for label, value in settings_items:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=label,
                font=config.FONTS["small"],
                text_color=config.THEME["text_secondary"],
                width=140, anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=value,
                font=config.FONTS["mono_small"],
                text_color=config.THEME["text_primary"],
                anchor="w",
            ).pack(side="left", padx=8)
        
        # Close button
        ctk.CTkButton(
            settings, text="Close",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_primary"],
            width=100, height=36,
            corner_radius=8,
            command=settings.destroy,
        ).pack(pady=(0, 16))
