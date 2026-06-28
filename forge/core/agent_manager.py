"""
FORGE Agent Manager — Main coordination engine.
Orchestrates all 5 agents, runs in a background thread.
GUI subscribes to events via callbacks.
Implements the full loop from spec Section 4.
"""

import time
import os
import threading
import uuid
from pathlib import Path

from core.context_manager import ContextManager
from core.diff_engine import DiffEngine
from core.executor import Executor
from core.file_watcher import FileWatcher
from core.token_counter import count_tokens

from agents.supervisor import SupervisorAgent
from agents.planner import PlannerAgent
from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.vision import VisionAgent
from agents.auditor import AuditorAgent
from agents.tester import TesterAgent
from core.git_manager import GitManager

import config


class AgentManager:
    """
    The main coordination engine.
    Runs in a background thread. GUI subscribes to events via callbacks.
    Manages the plan → code → review → debug → vision loop.
    """

    def __init__(self, ctx_manager: ContextManager, project_path: str,
                 session_id: str = None):
        self.ctx = ctx_manager
        self.project_path = project_path
        self.session_id = session_id or f"session_{int(time.time())}"
        self.iteration = 0
        self.max_iterations = config.MAX_ITERATIONS
        self.paused = False
        self.stopped = False
        self.running = False
        self.current_plan = []
        self.current_step = 0
        self.current_goal = ""

        # Shared team message bus — all agents can see recent peer outputs
        self.team_bus: list[dict] = []   # [{agent, content, iteration}]
        self._BUS_MAX = 20               # keep last N messages on the bus

        # Tools
        self.diff_engine = DiffEngine(project_path)
        self.executor = Executor(project_path)

        # Agents
        self.supervisor = SupervisorAgent(ctx_manager, self.session_id)
        self.planner = PlannerAgent(ctx_manager, self.session_id)
        self.coder = CoderAgent(ctx_manager, self.session_id)
        self.debugger = DebuggerAgent(ctx_manager, self.session_id)
        self.vision = VisionAgent(ctx_manager, self.session_id)
        self.auditor = AuditorAgent(ctx_manager, self.session_id)
        self.tester = TesterAgent(ctx_manager, self.session_id)
        self.all_agents = [
            self.supervisor, self.planner,
            self.coder, self.debugger, self.vision,
            self.auditor, self.tester
        ]

        # Git Manager for time travel
        self.git_manager = GitManager(project_path)
        if config.GIT_AUTO_COMMIT:
            self.git_manager.init_repo()

        # Event callbacks (GUI binds these)
        self.on_agent_status = None     # (agent_name, status) -> None
        self.on_message = None          # (agent_name, content, role) -> None
        self.on_file_changed = None     # (filepath, diff) -> None
        self.on_exec_result = None      # (exit_code, stdout, stderr) -> None
        self.on_vision_report = None    # (report_dict) -> None
        self.on_stats_update = None     # (stats_dict) -> None
        self.on_plan_update = None      # (plan_list, current_step) -> None
        self.on_iteration_start = None  # (iteration_num) -> None
        self.on_complete = None         # (reason) -> None
        self.on_error = None            # (error_msg) -> None

        # Wire up agent status callbacks
        for agent in self.all_agents:
            agent.status_callbacks.append(self._agent_status_changed)

        # Background thread
        self._thread = None

    def start(self, goal: str):
        """Start the agent loop in a background thread."""
        if self.running:
            return
        
        self.current_goal = goal
        self.stopped = False
        self.paused = False
        self.running = True
        self.iteration = 0
        self.current_step = 0
        
        self._thread = threading.Thread(
            target=self._run_loop, args=(goal,), daemon=True
        )
        self._thread.start()

    def pause(self):
        """Pause the loop after current agent call finishes."""
        self.paused = True
        self._emit("on_message", "SYSTEM", "Loop paused by user.", "system")

    def resume(self):
        """Resume the paused loop."""
        self.paused = False
        self._emit("on_message", "SYSTEM", "Loop resumed.", "system")

    def stop(self):
        """Stop the loop after current agent call finishes."""
        self.stopped = True
        self.running = False
        self._emit("on_message", "SYSTEM", "Loop stopped by user.", "system")

    def inject_steering(self, content: str):
        """Add a user steering injection for the next iteration."""
        self.ctx.add_steering(self.session_id, content, self.iteration)
        self._emit("on_message", "USER", f"[STEERING] {content}", "user")

    def skip_step(self):
        """Skip the current plan step."""
        self.current_step += 1
        self._emit("on_message", "SYSTEM", 
                   f"Skipped to step {self.current_step + 1}", "system")
        self._emit("on_plan_update", self.current_plan, self.current_step)

    def retry_step(self):
        """Retry the current plan step."""
        self._emit("on_message", "SYSTEM", 
                   f"Retrying step {self.current_step + 1}", "system")

    def _run_loop(self, goal: str):
        """Main loop. Runs in background thread."""
        try:
            self._emit("on_message", "SUPERVISOR", 
                       f"Starting on goal: {goal}", "system")

            # Phase 1: Planning
            self._emit("on_message", "SYSTEM",
                       "Phase 1: Creating implementation plan...", "system")
            project_structure = self._scan_project()
            plan = self.planner.create_plan(goal, project_structure)
            self.current_plan = plan
            self._emit("on_plan_update", plan, 0)
            self._emit("on_message", "PLANNER",
                       self._format_plan(plan), "assistant")

            # Phase 2: SUPERVISOR reviews the plan (sees PLANNER's output via team bus)
            self._emit("on_message", "SYSTEM",
                       "Phase 2: SUPERVISOR reviewing plan...", "system")
            supervisor_ok = self._agent_call(
                self.supervisor,
                f"PLANNER produced this plan for goal: {goal}\n\n"
                f"{self._format_plan(plan)}\n\n"
                f"Review and approve or revise. Reply with APPROVE or suggest specific changes."
            )
            self._emit("on_message", "SUPERVISOR", supervisor_ok, "assistant")

            # Phase 3: Execute loop
            self._emit("on_message", "SYSTEM",
                       "Phase 3: Executing plan...", "system")
            
            while self.iteration < self.max_iterations and not self.stopped:
                if self.paused:
                    time.sleep(0.5)
                    continue

                self.iteration += 1
                self._emit("on_iteration_start", self.iteration)
                self._emit_stats()

                # Auditor periodic check (wrapped — missing key must not crash loop)
                if self.auditor.should_trigger(self.iteration, False):
                    try:
                        self._emit("on_message", "SYSTEM",
                                   "AUDITOR performing periodic review...", "system")
                        proj_summary = self._scan_project()
                        audit_res = self.auditor.periodic_review(
                            proj_summary, "Periodic quality check", self.iteration
                        )
                        self._emit("on_message", "AUDITOR",
                                   f"Verdict: {audit_res['verdict']}\n"
                                   f"Summary: {audit_res['summary']}",
                                   "assistant")
                        if audit_res["verdict"] == "INDEPENDENT_FIX":
                            self.ctx.add_steering(
                                self.session_id,
                                f"AUDITOR SUGGESTS: {audit_res['fix_suggestion']}",
                                self.iteration,
                            )
                    except Exception as audit_err:
                        self._emit("on_message", "AUDITOR",
                                   f"[Skipped — {audit_err}]", "system")

                # Check for user steering
                steering = self.ctx.get_pending_steering(self.session_id)
                if steering:
                    self._emit("on_message", "USER",
                              f"[STEERING] {steering}", "user")
                    # Supervisor decides how to incorporate steering
                    routing = self._agent_call(
                        self.supervisor,
                        f"User steering received: {steering}\n"
                        f"Current plan step: {self.current_step}/{len(self.current_plan)}\n"
                        f"How should we adjust? Your team's recent activity is in context."
                    )
                    routing_parsed = self.supervisor._parse_routing(routing)
                    self._emit("on_message", "SUPERVISOR",
                              f"Routing decision: {routing_parsed['action']} — {routing_parsed['reason']}",
                              "assistant")

                    if routing_parsed.get("action") == "REPLAN":
                        new_plan = self.planner.replan(
                            self._format_plan(self.current_plan),
                            list(range(self.current_step)),
                            steering
                        )
                        self.current_plan = new_plan
                        self._emit("on_plan_update", new_plan, self.current_step)

                # Check if plan is complete
                if self.current_step >= len(self.current_plan):
                    self._emit("on_message", "SUPERVISOR",
                              "All plan steps completed.", "system")
                    self._emit("on_complete", "Plan completed successfully")
                    break

                step = self.current_plan[self.current_step]
                self._emit("on_message", "SUPERVISOR",
                    f"Iteration {self.iteration}: Step {self.current_step + 1} "
                    f"— {step.get('description', 'No description')}",
                    "system")

                # Route to appropriate agent based on step action
                action = step.get("action", "").upper()
                
                if action in ("CREATE", "MODIFY"):
                    self._handle_code_step(step)
                elif action == "DELETE":
                    self._handle_delete_step(step)
                elif action == "RUN":
                    should_continue = self._handle_run_step(step)
                    if not should_continue:
                        continue  # Fix step was injected
                elif action in ("TEST", "VERIFY"):
                    self._handle_verify_step(step)
                else:
                    # Unknown action — let supervisor decide
                    self._emit("on_message", "SUPERVISOR",
                              f"Unknown action: {action}. Skipping.", "system")

                self.current_step += 1
                self._emit("on_plan_update", self.current_plan, self.current_step)
                self._emit_stats()

            if self.iteration >= self.max_iterations:
                self._emit("on_message", "SUPERVISOR",
                          f"Maximum iterations ({self.max_iterations}) reached.",
                          "system")
                self._emit("on_complete", "Max iterations reached")

        except Exception as e:
            self._emit("on_error", str(e))
            self._emit("on_message", "SYSTEM",
                       f"Error in agent loop: {str(e)}", "system")
        finally:
            self.running = False

    def _handle_code_step(self, step: dict):
        """Handle a CREATE or MODIFY step. Includes TDD test generation."""
        filename = step.get("file", "")
        description = step.get("description", "")
        
        test_context = ""
        if config.TDD_ENABLED:
            self._emit("on_message", "SYSTEM", "TESTER generating tests...", "system")
            current_content = self._read_file(filename) or ""
            proj_struct = self._scan_project()
            tests = self.tester.generate_tests(description, filename, current_content, proj_struct)
            
            self._emit("on_message", "TESTER", 
                       f"Generated {tests.get('test_count', 0)} tests in {tests.get('test_file')}\n"
                       f"Description: {tests.get('description')}", "assistant")
            
            if tests.get("test_code"):
                # Write test file
                success, diff = self.diff_engine.write_file_safe(tests["test_file"], tests["test_code"])
                if success:
                    self._emit("on_file_changed", tests["test_file"], diff)
                    test_context = f"\nTests to pass:\n{tests['test_code']}"

        # Combine description with tests
        full_desc = description + test_context

        if step["action"] == "CREATE":
            # Create new file
            result = self.coder.create_file(full_desc, filename)
        else:
            # Modify existing file
            current_content = self._read_file(filename) or ""
            result = self.coder.implement(full_desc, current_content, filename)

        self._emit("on_message", "CODER",
                  f"File: {result['filename']}\n"
                  f"Action: {result['action']}\n"
                  f"Description: {result['description']}",
                  "assistant")

        # SUPERVISOR reviews before writing (sees CODER + TESTER via team bus)
        if result["code"]:
            review = self.supervisor.review_code(
                result["filename"], result["code"], result["description"],
                team_context=self._get_bus(8),
            )
            self._emit("on_message", "SUPERVISOR",
                       f"Code review: {review['verdict']} — {review['issues']}",
                       "assistant")

            if review["verdict"] == "APPROVE":
                # DEBUGGER does static analysis
                static_issues = self.debugger.static_analysis(
                    {result["filename"]: result["code"]}
                )
                if static_issues:
                    self._emit("on_message", "DEBUGGER",
                        f"Static analysis found {len(static_issues)} issues:\n" +
                        "\n".join(f"  • {i['description']}" for i in static_issues[:5]),
                        "assistant")

                # Write file regardless (issues are informational)
                success, diff = self.diff_engine.write_file_safe(
                    result["filename"], result["code"]
                )
                if success:
                    # Save snapshot to DB
                    self.ctx.save_file_snapshot(
                        self.session_id, result["filename"],
                        result["code"], self.iteration
                    )
                    self._emit("on_file_changed", result["filename"], diff)
                    
                    if config.GIT_AUTO_COMMIT:
                        self.git_manager.commit_iteration(self.iteration, description, [result["filename"]])
                else:
                    self._emit("on_message", "SYSTEM",
                              f"Failed to write file: {diff}", "system")
            else:
                self._emit("on_message", "SUPERVISOR",
                          f"Code rejected. Issues: {review['issues']}",
                          "system")
                
                # AUDITOR check on disagreement
                if self.auditor.should_trigger(self.iteration, True):
                    self._emit("on_message", "SYSTEM", "AUDITOR reviewing disagreement...", "system")
                    audit_res = self.auditor.audit_code(
                        result["filename"], result["code"], review['verdict'], result["description"]
                    )
                    self._emit("on_message", "AUDITOR", 
                               f"Verdict: {audit_res['verdict']}\n"
                               f"Suggestion: {audit_res['fix_suggestion']}", 
                               "assistant")
                    if audit_res['verdict'] == "AGREE_WITH_CODER":
                        self._emit("on_message", "SYSTEM", "AUDITOR overrules SUPERVISOR. Applying code.", "system")
                        success, diff = self.diff_engine.write_file_safe(result["filename"], result["code"])
                        if success:
                            self.ctx.save_file_snapshot(self.session_id, result["filename"], result["code"], self.iteration)
                            self._emit("on_file_changed", result["filename"], diff)
                            if config.GIT_AUTO_COMMIT:
                                self.git_manager.commit_iteration(self.iteration, description, [result["filename"]])

    def _handle_delete_step(self, step: dict):
        """Handle a DELETE step."""
        filename = step.get("file", "")
        filepath = os.path.join(self.project_path, filename)
        
        if os.path.exists(filepath):
            self.diff_engine.backup_file(filename)
            try:
                os.remove(filepath)
                self._emit("on_message", "CODER",
                          f"Deleted: {filename}", "assistant")
                self._emit("on_file_changed", filename, f"DELETED: {filename}")
            except OSError as e:
                self._emit("on_message", "SYSTEM",
                          f"Failed to delete {filename}: {e}", "system")

    def _handle_run_step(self, step: dict) -> bool:
        """
        Handle a RUN step. Returns True if execution succeeded,
        False if a fix step was injected.
        """
        entry_file = step.get("file", "main.py")
        
        self._emit("on_message", "SYSTEM",
                   f"Running: {entry_file}...", "system")
        
        success, stdout, stderr, duration_ms = self.executor.run(entry_file)
        
        # Save to DB
        self.ctx.save_exec_result(
            self.session_id, self.iteration,
            0 if success else 1, stdout, stderr, duration_ms
        )
        
        self._emit("on_exec_result", 0 if success else 1, stdout, stderr)
        
        if success:
            self._emit("on_message", "SYSTEM",
                       f"Execution succeeded ({duration_ms}ms)", "system")
            return True
        else:
            self._emit("on_message", "SYSTEM",
                       f"Execution failed ({duration_ms}ms)", "system")
            
            # DEBUGGER analyzes the error
            relevant_files = self._get_error_files(stderr)
            debug_report = self.debugger.analyze_error(
                stderr, stdout, relevant_files, self.iteration
            )
            self._emit("on_message", "DEBUGGER",
                       f"Root cause: {debug_report['root_cause']}\n"
                       f"Fix: {debug_report['fix_description']}",
                       "assistant")

            # Inject fix as next step
            fix_step = {
                "step": self.current_step + 1,
                "action": "MODIFY",
                "file": debug_report.get("affected_file", ""),
                "description": debug_report.get("coder_task", 
                               debug_report.get("fix_description", "")),
                "depends_on": [],
                "verify_by": "no runtime error",
            }
            self.current_plan.insert(self.current_step + 1, fix_step)
            self._emit("on_plan_update", self.current_plan, self.current_step)
            return False

    def _handle_verify_step(self, step: dict):
        """Handle a VERIFY/TEST step using VISION agent."""
        screenshot_path = self._take_screenshot()
        if screenshot_path:
            report = self.vision.analyze_frame(
                screenshot_path,
                step.get("description", "Expected behavior"),
                self.iteration
            )
            self._emit("on_vision_report", report)
            self._emit("on_message", "VISION",
                       f"Verdict: {report.get('iteration_verdict', 'CONTINUE')}\n"
                       f"Matches: {report.get('matches', 'N/A')}\n"
                       f"Recommendation: {report.get('recommendation', 'N/A')}",
                       "assistant")

            verdict = report.get("iteration_verdict", "CONTINUE")
            if verdict == "DONE":
                self._emit("on_message", "SUPERVISOR",
                          "VISION confirms goal achieved. Done.", "system")
                self.stopped = True
            elif verdict == "CHANGE_APPROACH":
                # Replan
                new_plan = self.planner.replan(
                    self._format_plan(self.current_plan),
                    list(range(self.current_step)),
                    report.get("recommendation", "Change approach")
                )
                self.current_plan = new_plan
                self.current_step = 0
                self._emit("on_plan_update", new_plan, 0)
        else:
            self._emit("on_message", "VISION",
                       "No screenshot available for verification.", "system")

    def _scan_project(self) -> str:
        """Scan project directory and return structure as text."""
        result = []
        try:
            for root, dirs, files in os.walk(self.project_path):
                # Skip ignored directories
                dirs[:] = [d for d in dirs if d not in {
                    ".forge", "__pycache__", ".git", ".venv", "venv",
                    "node_modules", ".pytest_cache"
                }]
                
                level = root.replace(self.project_path, "").count(os.sep)
                indent = "  " * level
                folder_name = os.path.basename(root)
                result.append(f"{indent}{folder_name}/")
                
                sub_indent = "  " * (level + 1)
                for f in sorted(files):
                    size = os.path.getsize(os.path.join(root, f))
                    result.append(f"{sub_indent}{f} ({size}B)")
        except OSError:
            result.append("(empty project)")
        
        return "\n".join(result) if result else "(empty project)"

    def _read_file(self, filepath: str) -> str:
        """Read a file from the project directory."""
        abs_path = filepath
        if not os.path.isabs(filepath):
            abs_path = os.path.join(self.project_path, filepath)
        
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _get_error_files(self, stderr: str) -> dict:
        """Extract file paths mentioned in error output and load them."""
        import re
        files = {}
        # Find Python traceback file references
        file_refs = re.findall(r'File "([^"]+)"', stderr)
        for ref in file_refs:
            if self.project_path in ref or not os.path.isabs(ref):
                content = self._read_file(ref)
                if content:
                    rel = os.path.relpath(ref, self.project_path) \
                        if os.path.isabs(ref) else ref
                    files[rel] = content
        return files

    def _take_screenshot(self) -> str:
        """Take a screenshot of the current project render."""
        frames_dir = os.path.join(self.project_path, ".forge", "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # For now, try to capture desktop screenshot using PIL
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            path = os.path.join(
                frames_dir,
                f"frame_{self.iteration:04d}.png"
            )
            screenshot.save(path)
            return path
        except Exception:
            return ""

    def _format_plan(self, plan: list[dict]) -> str:
        """Format a plan as readable text."""
        lines = ["PLAN:"]
        for i, step in enumerate(plan):
            status = "✓" if i < self.current_step else \
                     "→" if i == self.current_step else "○"
            lines.append(
                f"  {status} {i+1}. [{step.get('action', '?')}] "
                f"{step.get('file', '')} — {step.get('description', '')}"
            )
        return "\n".join(lines)

    # ── Team Bus ──────────────────────────────────────────────────────────────

    def _post_to_bus(self, agent_name: str, content: str):
        """Post an agent message to the shared team bus."""
        if agent_name in ("SYSTEM", "USER"):
            return  # Only agent outputs go on the bus
        self.team_bus.append({
            "agent": agent_name,
            "content": content,
            "iteration": self.iteration,
        })
        if len(self.team_bus) > self._BUS_MAX:
            self.team_bus.pop(0)

    def _get_bus(self, n: int = 8) -> list:
        """Get the last n messages from the team bus."""
        return self.team_bus[-n:] if self.team_bus else []

    def _agent_call(self, agent, task: str, extra_context: dict = None) -> str:
        """Call an agent with current team bus context injected."""
        return agent.call(
            task,
            extra_context=extra_context,
            team_context=self._get_bus(8),
        )

    def _emit(self, event_name: str, *args):
        """Emit an event to the GUI callback."""
        # If it's a message event, also post to team bus
        if event_name == "on_message" and len(args) >= 2:
            self._post_to_bus(args[0], args[1])

        callback = getattr(self, event_name, None)
        if callback:
            try:
                callback(*args)
            except Exception as e:
                import traceback
                print(f"[EMIT ERROR] {event_name}: {e}")

    def _emit_stats(self):
        """Emit comprehensive stats update."""
        stats = {
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "current_step": self.current_step,
            "total_steps": len(self.current_plan),
            "total_tokens": sum(a.total_tokens for a in self.all_agents),
            "per_agent": {
                a.name: {
                    "tokens_total": a.total_tokens,
                    "tokens_last_in": a.last_tokens_in,
                    "tokens_last_out": a.last_tokens_out,
                    "calls": a.call_count,
                    "status": a.status,
                } for a in self.all_agents
            },
            "db_size_mb": self.ctx.get_db_size_mb(),
            "context_entries": self.ctx.count_messages(self.session_id),
            "paused": self.paused,
            "stopped": self.stopped,
            "running": self.running,
        }
        self._emit("on_stats_update", stats)

    def _agent_status_changed(self, agent_name: str, status: str):
        """Called by agents when their status changes."""
        self._emit("on_agent_status", agent_name, status)

    def get_stats(self) -> dict:
        """Get current stats (thread-safe)."""
        return {
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "current_step": self.current_step,
            "total_steps": len(self.current_plan),
            "total_tokens": sum(a.total_tokens for a in self.all_agents),
            "running": self.running,
            "paused": self.paused,
            "per_agent": {a.name: a.get_stats() for a in self.all_agents},
            "db_size_mb": self.ctx.get_db_size_mb(),
        }
