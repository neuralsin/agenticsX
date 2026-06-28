# FORGE — Multi-Agent AI Development Studio
## Complete Implementation Specification

> A desktop GUI application that runs a team of 5 specialized local AI agents
> to autonomously plan, code, debug, visually verify, and refine any software project.
> Built for: 12GB RAM · RTX 4050 6GB VRAM · i5-12450HX
> Runtime: AirLLM (layer-sliced inference) + Ollama (small/vision models)
> Framework: Python + CustomTkinter (native desktop, no browser)

---

## 0. Hardware Reality & Model Assignment

### Constraint Profile
- VRAM: 6GB (RTX 4050) — cannot hold any 7B+ model fully in GPU RAM
- System RAM: 12GB — AirLLM uses this as extended VRAM via layer slicing
- AirLLM principle: loads model layer-by-layer from disk → GPU → inference → unload
  This means one model runs at a time. Models are NOT concurrent.
- Disk: models stored in ~/.cache/airllm/ (or configurable path)

### Agent → Model Mapping

| Agent       | Role                        | Model                        | Load Method | Est. RAM  | Speed      |
|-------------|-----------------------------|-----------------------------|-------------|-----------|------------|
| SUPERVISOR  | Routes tasks, final review  | Qwen3.6:27B (Q4_K_M)        | AirLLM      | ~8GB RAM  | ~3-5 tok/s |
| PLANNER     | Breaks goals into steps     | DeepSeek-R1:8B (Q4_K_M)     | Ollama      | ~5GB RAM  | ~15 tok/s  |
| CODER       | Writes/edits code           | Qwen3.6:27B (Q4_K_M)        | AirLLM      | ~8GB RAM  | ~3-5 tok/s |
| DEBUGGER    | Analyzes errors, fixes bugs | DeepSeek-R1:8B (Q4_K_M)     | Ollama      | ~5GB RAM  | ~12 tok/s  |
| VISION      | Reads screenshots/renders   | Qwen2.5-VL:7B               | Ollama      | ~5GB RAM  | ~8 tok/s   |

### Why This Split
- SUPERVISOR + CODER share the same 27B model (AirLLM) — loaded once, reused
- PLANNER + DEBUGGER use DeepSeek-R1:8B via Ollama — fast, reasoning-optimized, fits in RAM
- VISION uses Qwen2.5-VL:7B via Ollama — only model with multimodal capability
- Never load AirLLM and Ollama large models simultaneously
- Ollama 8B models can stay resident; AirLLM 27B loads on-demand

### Model Queue System
Since only one large model runs at a time, FORGE uses a task queue:
- If AirLLM is busy → queue SUPERVISOR/CODER tasks, show pending status
- Ollama agents (PLANNER, DEBUGGER, VISION) can run while AirLLM is between loads
- User sees live status of which agent is active

---

## 1. Application Architecture

```
forge/
├── main.py                      # Entry point, launches GUI
├── config.py                    # All user settings, paths, model config
├── requirements.txt
│
├── core/
│   ├── agent_manager.py         # Orchestrates all 5 agents, task queue
│   ├── context_manager.py       # Disk-backed context store (SQLite)
│   ├── file_watcher.py          # Watches project dir for changes
│   ├── executor.py              # Sandboxed code runner, subprocess mgmt
│   ├── diff_engine.py           # Applies patches, git-style diffs
│   └── token_counter.py         # Tiktoken-based usage tracker
│
├── agents/
│   ├── base_agent.py            # Abstract base: system prompt, memory, call()
│   ├── supervisor.py            # Agent: SUPERVISOR (AirLLM Qwen3.6 27B)
│   ├── planner.py               # Agent: PLANNER (Ollama DeepSeek-R1 8B)
│   ├── coder.py                 # Agent: CODER (AirLLM Qwen3.6 27B)
│   ├── debugger.py              # Agent: DEBUGGER (Ollama DeepSeek-R1 8B)
│   └── vision.py                # Agent: VISION (Ollama Qwen2.5-VL 7B)
│
├── simulator/
│   ├── renderer.py              # Pygame window: renders project output
│   ├── esp32_sim.py             # ESP32/ILI9341 specific renderer (240x320)
│   ├── web_sim.py               # HTML/CSS preview via CEF or webview
│   └── terminal_sim.py          # Terminal output capture + display
│
├── storage/
│   ├── context.db               # SQLite: all agent messages, project state
│   ├── sessions/                # Per-session JSON snapshots
│   └── projects/                # Project metadata index
│
└── gui/
    ├── app.py                   # Main CustomTkinter window
    ├── panels/
    │   ├── agent_team.py        # Left panel: 5 agent cards with live status
    │   ├── chat_hub.py          # Center panel: multi-agent conversation feed
    │   ├── code_editor.py       # Right panel: Monaco-style code view + diff
    │   ├── simulator_panel.py   # Bottom-right: project render/preview
    │   ├── context_stats.py     # Bottom bar: token usage, RAM, VRAM meters
    │   └── steering_bar.py      # Bottom input: user injection / steering
    └── widgets/
        ├── token_meter.py       # Animated token counter widget
        ├── agent_badge.py       # Agent status pill (thinking/idle/error)
        ├── diff_view.py         # Red/green diff display widget
        └── log_stream.py        # Scrolling log with color coding
```

---

## 2. Context Management System (Disk-as-Memory)

### Why This Matters
12GB RAM limits in-memory context. FORGE solves this by treating SQLite on disk
as the primary context store. Agents never hold full history in RAM.

### SQLite Schema (`storage/context.db`)

```sql
-- Core message store
CREATE TABLE messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    agent_name  TEXT NOT NULL,          -- 'SUPERVISOR'|'PLANNER'|'CODER'|'DEBUGGER'|'VISION'|'USER'
    role        TEXT NOT NULL,          -- 'system'|'user'|'assistant'
    content     TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    timestamp   REAL NOT NULL,
    iteration   INTEGER DEFAULT 0,
    importance  INTEGER DEFAULT 5       -- 1-10, used for pruning
);

-- Project file snapshots (compressed)
CREATE TABLE file_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    filepath    TEXT NOT NULL,
    content     BLOB NOT NULL,          -- zlib compressed
    token_count INTEGER DEFAULT 0,
    iteration   INTEGER DEFAULT 0,
    timestamp   REAL NOT NULL
);

-- Per-agent context windows (what each agent currently sees)
CREATE TABLE agent_contexts (
    agent_name  TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    token_budget  INTEGER DEFAULT 8192,
    tokens_used   INTEGER DEFAULT 0,
    last_updated  REAL NOT NULL
);

-- Execution results
CREATE TABLE exec_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    iteration   INTEGER NOT NULL,
    exit_code   INTEGER,
    stdout      TEXT,
    stderr      TEXT,
    duration_ms INTEGER,
    timestamp   REAL NOT NULL
);

-- Vision feedback records
CREATE TABLE vision_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    iteration   INTEGER NOT NULL,
    screenshot_path TEXT,
    feedback    TEXT,
    issues_found INTEGER DEFAULT 0,
    timestamp   REAL NOT NULL
);

-- User steering injections
CREATE TABLE steering_inputs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    iteration   INTEGER NOT NULL,
    content     TEXT NOT NULL,
    applied     INTEGER DEFAULT 0,
    timestamp   REAL NOT NULL
);

CREATE INDEX idx_messages_session ON messages(session_id, timestamp);
CREATE INDEX idx_messages_agent ON messages(session_id, agent_name);
CREATE INDEX idx_files_session ON file_snapshots(session_id, filepath);
```

### Context Budget Per Agent (tokens)

| Agent      | System Prompt | Codebase Slice | History | Vision Data | Total Budget |
|------------|---------------|----------------|---------|-------------|--------------|
| SUPERVISOR | 800           | 2000           | 1500    | 500         | 4800         |
| PLANNER    | 600           | 1000           | 2000    | 0           | 3600         |
| CODER      | 1000          | 6000           | 1000    | 200         | 8200         |
| DEBUGGER   | 600           | 3000           | 1500    | 300         | 5400         |
| VISION     | 400           | 0              | 500     | image       | 900 + img    |

### Smart Context Retrieval (`core/context_manager.py`)

```python
class ContextManager:
    """
    Never loads full history into RAM.
    Retrieves only what each agent needs for the current task.
    """

    def get_agent_context(self, agent_name: str, session_id: str, 
                           current_task: str) -> list[dict]:
        """
        Builds the message list for an agent call using:
        1. Agent's system prompt (always included)
        2. Most recent N messages from this agent (recency)
        3. Top-K messages by importance score (relevance)
        4. Current codebase slice (only files relevant to task)
        5. Latest execution result
        6. Latest vision report (if applicable)
        7. Any pending user steering inputs
        """
        budget = self._get_budget(agent_name)
        messages = []
        tokens_used = 0

        # 1. System prompt (always)
        sys_prompt = self._get_system_prompt(agent_name)
        messages.append({"role": "system", "content": sys_prompt})
        tokens_used += count_tokens(sys_prompt)

        # 2. Pending steering inputs (highest priority after system)
        steering = self._get_pending_steering(session_id)
        if steering and tokens_used + count_tokens(steering) < budget * 0.2:
            messages.append({
                "role": "user", 
                "content": f"[USER STEERING]\n{steering}"
            })
            tokens_used += count_tokens(steering)

        # 3. Recent agent-specific history (last 5 exchanges)
        history = self._get_recent_history(agent_name, session_id, limit=5)
        for msg in history:
            t = count_tokens(msg["content"])
            if tokens_used + t < budget * 0.6:
                messages.append(msg)
                tokens_used += t

        # 4. Relevant codebase slice
        code_slice = self._get_relevant_files(session_id, current_task, 
                                               token_limit=budget - tokens_used - 1000)
        if code_slice:
            messages.append({"role": "user", "content": code_slice})
            tokens_used += count_tokens(code_slice)

        # 5. Latest exec result
        exec_result = self._get_latest_exec(session_id)
        if exec_result:
            messages.append({"role": "user", "content": exec_result})
            tokens_used += count_tokens(exec_result)

        return messages, tokens_used

    def _get_relevant_files(self, session_id, task, token_limit):
        """
        Use TF-IDF keyword matching between task description 
        and filenames/content to select most relevant files.
        Returns compressed representation if over limit.
        """
        # ... implementation
        pass

    def compress_old_history(self, session_id: str, keep_recent: int = 10):
        """
        Summarizes old messages in-DB using PLANNER model.
        Replaces N old messages with 1 summary message.
        Runs automatically when any agent exceeds 80% token budget.
        """
        pass
```

---

## 3. Agent Implementations

### Base Agent (`agents/base_agent.py`)

```python
from abc import ABC, abstractmethod
from core.context_manager import ContextManager
from core.token_counter import count_tokens
import time

class BaseAgent(ABC):
    name: str
    model: str
    load_method: str  # 'airllm' | 'ollama'
    color: str        # UI accent color hex

    def __init__(self, context_manager: ContextManager, session_id: str):
        self.ctx = context_manager
        self.session_id = session_id
        self.status = "idle"         # idle | thinking | error | waiting
        self.last_tokens_in = 0
        self.last_tokens_out = 0
        self.total_tokens = 0
        self.call_count = 0
        self.status_callbacks = []   # GUI binds here

    def call(self, task: str, extra_context: dict = None) -> str:
        self._set_status("thinking")
        messages, tokens_in = self.ctx.get_agent_context(
            self.name, self.session_id, task
        )
        # Add current task
        messages.append({"role": "user", "content": task})
        tokens_in += count_tokens(task)

        t0 = time.time()
        response = self._inference(messages)
        elapsed = time.time() - t0

        tokens_out = count_tokens(response)
        self.last_tokens_in = tokens_in
        self.last_tokens_out = tokens_out
        self.total_tokens += tokens_in + tokens_out
        self.call_count += 1

        # Persist to DB
        self.ctx.save_message(self.session_id, self.name, "user", task, tokens_in)
        self.ctx.save_message(self.session_id, self.name, "assistant", response, tokens_out)

        self._set_status("idle")
        return response

    @abstractmethod
    def _inference(self, messages: list[dict]) -> str:
        pass

    def _set_status(self, status: str):
        self.status = status
        for cb in self.status_callbacks:
            cb(self.name, status)
```

### SUPERVISOR Agent (`agents/supervisor.py`)

```python
"""
SUPERVISOR — Qwen3.6 27B via AirLLM
Role: Overall project awareness, task decomposition, routing decisions,
      quality gate on CODER output before it gets written to disk,
      decides when goal is achieved or needs another iteration.
"""

SUPERVISOR_SYSTEM = """You are SUPERVISOR — the lead architect of a multi-agent AI development team.

Your team:
- PLANNER: breaks goals into ordered steps
- CODER: writes and modifies code files
- DEBUGGER: analyzes runtime errors and proposes fixes
- VISION: analyzes screenshots of running output

Your responsibilities:
1. Receive the user's project goal
2. Delegate to PLANNER for step breakdown
3. After each CODER edit, review the proposed change for correctness
4. After each VISION report, decide: iterate more, change approach, or mark done
5. Inject user steering into the team's workflow at the right moment
6. Declare when the goal is achieved

Output format for routing decisions:
ROUTE_TO: <PLANNER|CODER|DEBUGGER|VISION|DONE>
REASON: <one line>
TASK: <specific instruction for the target agent>

Output format for code review:
REVIEW: APPROVE|REJECT
ISSUES: <list any problems, or "none">
NEXT: <what should happen after>
"""

class SupervisorAgent(AirLLMAgent):
    name = "SUPERVISOR"
    color = "#7C3AED"  # violet

    def route(self, situation: str) -> dict:
        """Decide which agent acts next and what their task is."""
        response = self.call(f"Current situation:\n{situation}\n\nWhat should happen next?")
        return self._parse_routing(response)

    def review_code(self, filename: str, new_code: str, change_description: str) -> dict:
        """Quality gate before any file write."""
        task = f"""Review this proposed change:
FILE: {filename}
DESCRIPTION: {change_description}

```
{new_code[:3000]}  
```

Is this safe to apply? Check for: syntax issues, logic errors, breaking changes."""
        response = self.call(task)
        return self._parse_review(response)
```

### PLANNER Agent (`agents/planner.py`)

```python
"""
PLANNER — DeepSeek-R1 8B via Ollama
Role: Receives a high-level goal, outputs a numbered step-by-step execution plan.
      Uses chain-of-thought reasoning to think through dependencies and order.
      Re-plans when SUPERVISOR signals a direction change.
"""

PLANNER_SYSTEM = """You are PLANNER — a senior software architect specializing in breaking 
down complex development goals into precise, ordered implementation steps.

You think step by step using <think>...</think> tags before outputting the plan.
Your plans are concrete, file-specific, and actionable — not vague.

Output format:
<think>
[your reasoning about the goal, dependencies, risks]
</think>

PLAN:
1. [ACTION] [FILE: path/to/file.py] — [exact description of change]
2. [ACTION] [FILE: path/to/file.py] — [exact description of change]
...

Actions: CREATE | MODIFY | DELETE | RUN | TEST | VERIFY

After each step in the plan, note:
DEPENDS_ON: [step numbers this depends on, or "none"]
VERIFY_BY: [how to know this step succeeded]
"""

class PlannerAgent(OllamaAgent):
    name = "PLANNER"
    color = "#0891B2"  # cyan

    def create_plan(self, goal: str, project_structure: str) -> list[dict]:
        task = f"""Goal: {goal}

Project structure:
{project_structure}

Create a detailed implementation plan."""
        response = self.call(task)
        return self._parse_plan(response)

    def replan(self, original_plan: str, completed_steps: list, 
               blocker: str) -> list[dict]:
        """Called when SUPERVISOR detects the plan needs revision."""
        task = f"""Original plan:
{original_plan}

Completed steps: {completed_steps}
Blocker encountered: {blocker}

Revise the plan to work around this blocker."""
        response = self.call(task)
        return self._parse_plan(response)
```

### CODER Agent (`agents/coder.py`)

```python
"""
CODER — Qwen3.6 27B via AirLLM
Role: Receives specific file-level tasks from SUPERVISOR/PLANNER.
      Outputs complete file contents or precise diffs.
      One file change per call for safety and reviewability.
      Must always output in parseable format.
"""

CODER_SYSTEM = """You are CODER — an expert software engineer who writes precise, working code.

You receive a specific coding task and the current state of relevant files.
You output EXACTLY ONE file change per response.

ALWAYS use this output format:

### FILE: relative/path/from/project/root.py
### ACTION: CREATE|MODIFY|DELETE
### DESCRIPTION: one line describing what changed and why
```python
<complete file contents — never partial, always the full file>
```
### END

Rules:
- Output the COMPLETE file, not snippets or diffs
- Never truncate with "# rest of code here" 
- If the file is long, still output it in full
- Only change what the task requires, keep everything else identical
- Add a comment on any line you changed: # FORGE: <reason>
"""

class CoderAgent(AirLLMAgent):
    name = "CODER"
    color = "#059669"  # green

    def implement(self, task: str, current_file_content: str, 
                  filename: str) -> dict:
        full_task = f"""Task: {task}

Current file ({filename}):
```
{current_file_content}
```

Implement the task. Output the complete modified file."""
        response = self.call(full_task)
        return self._parse_file_output(response)

    def create_file(self, task: str, filename: str, 
                    related_files: dict) -> dict:
        ctx = "\n\n".join(
            f"Related file {k}:\n```\n{v[:1000]}\n```" 
            for k, v in related_files.items()
        )
        full_task = f"""Task: Create new file {filename}
{task}

Related files for context:
{ctx}"""
        response = self.call(full_task)
        return self._parse_file_output(response)
```

### DEBUGGER Agent (`agents/debugger.py`)

```python
"""
DEBUGGER — DeepSeek-R1 8B via Ollama  
Role: Receives stderr/stdout + the code that caused it.
      Uses R1's chain-of-thought to trace the error root cause.
      Outputs a specific fix instruction for CODER.
      Can also do static analysis (no execution needed).
"""

DEBUGGER_SYSTEM = """You are DEBUGGER — an expert at diagnosing software bugs.

You receive: error output, the file(s) involved, and iteration context.
You use systematic reasoning to find root causes, not surface symptoms.

Think through:
<think>
1. What is the error type and message?
2. Which line/function is the source?
3. What state led to this? (trace backward)
4. What is the minimal fix?
5. Are there related issues this fix might expose?
</think>

Output format:

ROOT_CAUSE: [one sentence]
AFFECTED_FILE: [path]
AFFECTED_LINE: [line number or range]
FIX_DESCRIPTION: [exact instruction for CODER]
FIX_CONFIDENCE: HIGH|MEDIUM|LOW
SIDE_EFFECTS: [any other files/behavior this fix might impact]
CODER_TASK: [copy-pasteable task description for CODER agent]
"""

class DebuggerAgent(OllamaAgent):
    name = "DEBUGGER"
    color = "#DC2626"  # red

    def analyze_error(self, stderr: str, stdout: str, 
                      file_contents: dict, iteration: int) -> dict:
        task = f"""Iteration {iteration} execution failed.

STDERR:
{stderr[:2000]}

STDOUT:
{stdout[:500]}

Files involved:
{self._format_files(file_contents)}

Find the root cause and tell CODER exactly how to fix it."""
        response = self.call(task)
        return self._parse_debug_report(response)

    def static_analysis(self, file_contents: dict) -> list[dict]:
        """Proactive bug detection before execution."""
        task = f"""Perform static analysis on these files. 
Find bugs, type errors, logic issues, missing imports, undefined variables.

{self._format_files(file_contents)}

List all issues found, ordered by severity."""
        response = self.call(task)
        return self._parse_issues(response)
```

### VISION Agent (`agents/vision.py`)

```python
"""
VISION — Qwen2.5-VL 7B via Ollama
Role: Receives a screenshot of the running project output.
      Reports what it sees vs what was expected.
      Identifies UI/visual bugs, layout issues, missing elements.
      Generates a structured report for SUPERVISOR.
"""

VISION_SYSTEM = """You are VISION — a QA engineer who analyzes screenshots of running software.

You receive: a screenshot + the expected behavior description.
You report exactly what you see and what differs from expectation.

Output format:

WHAT_I_SEE: [describe the screenshot content literally]
EXPECTED: [what should be showing]
MATCHES: YES|PARTIAL|NO
ISSUES:
- [specific issue 1]
- [specific issue 2]
SEVERITY: CRITICAL|MAJOR|MINOR|NONE
RECOMMENDATION: [specific instruction — what CODER/DEBUGGER should fix]
ITERATION_VERDICT: CONTINUE|DONE|CHANGE_APPROACH
"""

class VisionAgent(OllamaAgent):
    name = "VISION"
    color = "#D97706"  # amber

    def analyze_frame(self, screenshot_path: str, expected: str,
                      iteration: int) -> dict:
        with open(screenshot_path, "rb") as f:
            import base64
            img_b64 = base64.b64encode(f.read()).decode()

        task = f"""Iteration {iteration}.
Expected behavior: {expected}
Analyze this screenshot and report what you see."""

        response = self._inference_with_image(task, img_b64)
        return self._parse_vision_report(response)

    def compare_frames(self, before_path: str, after_path: str, 
                       change_description: str) -> str:
        """Compare two frames to verify a change had visible effect."""
        # Encode both images
        images = []
        for path in [before_path, after_path]:
            with open(path, "rb") as f:
                import base64
                images.append(base64.b64encode(f.read()).decode())

        task = f"""Compare BEFORE (first image) and AFTER (second image).
Change that was made: {change_description}
Did the change have the expected visual effect? What's different?"""

        return self._inference_with_images(task, images)
```

---

## 4. Agent Orchestration Loop (`core/agent_manager.py`)

```python
class AgentManager:
    """
    The main coordination engine.
    Runs in a background thread. GUI subscribes to events via callbacks.
    """

    def __init__(self, ctx_manager, project_path, session_id):
        self.ctx = ctx_manager
        self.project_path = project_path
        self.session_id = session_id
        self.iteration = 0
        self.max_iterations = 50
        self.paused = False
        self.stopped = False
        self.current_plan = []
        self.current_step = 0

        # Agents
        self.supervisor = SupervisorAgent(ctx_manager, session_id)
        self.planner = PlannerAgent(ctx_manager, session_id)
        self.coder = CoderAgent(ctx_manager, session_id)
        self.debugger = DebuggerAgent(ctx_manager, session_id)
        self.vision = VisionAgent(ctx_manager, session_id)
        self.all_agents = [self.supervisor, self.planner, 
                           self.coder, self.debugger, self.vision]

        # Event callbacks (GUI binds these)
        self.on_agent_status = None    # (agent_name, status) -> None
        self.on_message = None         # (agent_name, content, role) -> None
        self.on_file_changed = None    # (filepath, diff) -> None
        self.on_exec_result = None     # (exit_code, stdout, stderr) -> None
        self.on_vision_report = None   # (report_dict) -> None
        self.on_stats_update = None    # (stats_dict) -> None
        self.on_plan_update = None     # (plan_list, current_step) -> None

        # Wire up agent status callbacks
        for agent in self.all_agents:
            agent.status_callbacks.append(self._agent_status_changed)

    def run(self, goal: str):
        """Main loop. Called in background thread."""
        self._emit("on_message", "SUPERVISOR", f"Starting on goal: {goal}", "system")

        # Phase 1: Planning
        project_structure = self._scan_project()
        plan = self.planner.create_plan(goal, project_structure)
        self.current_plan = plan
        self._emit("on_plan_update", plan, 0)

        # Phase 2: Supervisor reviews plan
        supervisor_ok = self.supervisor.call(
            f"PLANNER produced this plan for goal: {goal}\n\n"
            f"{self._format_plan(plan)}\n\n"
            f"Review and approve or revise."
        )
        self._emit("on_message", "SUPERVISOR", supervisor_ok, "assistant")

        # Phase 3: Execute loop
        while self.iteration < self.max_iterations and not self.stopped:
            if self.paused:
                time.sleep(0.5)
                continue

            self.iteration += 1
            self._emit_stats()

            # Check for user steering
            steering = self.ctx.get_pending_steering(self.session_id)
            if steering:
                self._emit("on_message", "USER", f"[STEERING] {steering}", "user")
                # Supervisor decides how to incorporate
                routing = self.supervisor.route(
                    f"User steering received: {steering}\n"
                    f"Current plan step: {self.current_step}/{len(self.current_plan)}\n"
                    f"How should we adjust?"
                )
                if routing.get("action") == "REPLAN":
                    plan = self.planner.replan(
                        self._format_plan(self.current_plan),
                        list(range(self.current_step)),
                        steering
                    )
                    self.current_plan = plan
                    self._emit("on_plan_update", plan, self.current_step)

            # Get current step
            if self.current_step >= len(self.current_plan):
                self._emit("on_message", "SUPERVISOR", "All plan steps completed.", "system")
                break

            step = self.current_plan[self.current_step]
            self._emit("on_message", "SUPERVISOR", 
                       f"Iteration {self.iteration}: Step {self.current_step+1} — {step['description']}", 
                       "system")

            # Route to appropriate agent
            if step["action"] in ("CREATE", "MODIFY"):
                # CODER implements
                current_content = self._read_file(step["file"]) or ""
                result = self.coder.implement(step["description"], current_content, step["file"])

                # SUPERVISOR reviews before writing
                review = self.supervisor.review_code(
                    step["file"], result["code"], result["description"]
                )
                self._emit("on_message", "SUPERVISOR", 
                           f"Code review: {review['verdict']} — {review['issues']}", "assistant")

                if review["verdict"] == "APPROVE":
                    # DEBUGGER does static analysis first
                    static_issues = self.debugger.static_analysis({step["file"]: result["code"]})
                    if static_issues:
                        self._emit("on_message", "DEBUGGER", 
                                   f"Static analysis found {len(static_issues)} issues", "assistant")
                        # Loop back to CODER with debugger feedback
                        continue

                    # Write file
                    self._write_file(step["file"], result["code"])
                    self._emit("on_file_changed", step["file"], result["diff"])

            elif step["action"] == "RUN":
                # Execute and handle result
                ok, stdout, stderr = self._run_project()
                self._emit("on_exec_result", ok, stdout, stderr)

                if not ok:
                    # DEBUGGER analyzes
                    relevant_files = self._get_error_files(stderr)
                    debug_report = self.debugger.analyze_error(
                        stderr, stdout, relevant_files, self.iteration
                    )
                    self._emit("on_message", "DEBUGGER", 
                               f"Root cause: {debug_report['root_cause']}", "assistant")

                    # Inject fix as next step
                    fix_step = {
                        "action": "MODIFY",
                        "file": debug_report["affected_file"],
                        "description": debug_report["coder_task"],
                        "depends_on": [],
                        "verify_by": "no runtime error"
                    }
                    self.current_plan.insert(self.current_step + 1, fix_step)
                    self._emit("on_plan_update", self.current_plan, self.current_step)
                    continue

            elif step["action"] == "VERIFY":
                # VISION analyzes current render
                screenshot = self._take_screenshot()
                report = self.vision.analyze_frame(screenshot, step["description"], self.iteration)
                self._emit("on_vision_report", report)
                self._emit("on_message", "VISION", 
                           f"Verdict: {report['iteration_verdict']} — {report['recommendation']}", 
                           "assistant")

                if report["iteration_verdict"] == "DONE":
                    self._emit("on_message", "SUPERVISOR", 
                               "VISION confirms goal achieved. Done.", "system")
                    break
                elif report["iteration_verdict"] == "CHANGE_APPROACH":
                    # Replan
                    new_plan = self.planner.replan(
                        self._format_plan(self.current_plan),
                        list(range(self.current_step)),
                        report["recommendation"]
                    )
                    self.current_plan = new_plan
                    self.current_step = 0
                    self._emit("on_plan_update", new_plan, 0)
                    continue

            self.current_step += 1
            self._emit("on_plan_update", self.current_plan, self.current_step)
            self._emit_stats()

    def _emit_stats(self):
        stats = {
            "iteration": self.iteration,
            "total_tokens": sum(a.total_tokens for a in self.all_agents),
            "per_agent": {a.name: {
                "tokens_total": a.total_tokens,
                "tokens_last_in": a.last_tokens_in,
                "tokens_last_out": a.last_tokens_out,
                "calls": a.call_count,
                "status": a.status,
            } for a in self.all_agents},
            "db_size_mb": self._get_db_size(),
            "context_entries": self.ctx.count_messages(self.session_id),
        }
        if self.on_stats_update:
            self.on_stats_update(stats)
```

---

## 5. AirLLM Integration (`agents/airllm_agent.py`)

```python
from airllm import AutoModel
import torch

class AirLLMAgent(BaseAgent):
    """
    Uses AirLLM to run Qwen3.6 27B on 6GB VRAM via layer splitting.
    Loads model from disk, runs inference, results returned.
    Only one AirLLM model active at a time (enforced by AgentManager).
    """
    
    MODEL_PATH = "~/.cache/airllm/qwen3.6-27b-q4"
    _model_instance = None  # Class-level singleton

    @classmethod
    def load_model(cls):
        if cls._model_instance is None:
            cls._model_instance = AutoModel.from_pretrained(
                "Qwen/Qwen3.6-27B-Instruct",
                compression="4bit",
                profiling_mode=False,
            )
        return cls._model_instance

    def _inference(self, messages: list[dict]) -> str:
        model = self.load_model()
        
        # Format as chat template
        prompt = self._format_chat(messages)
        tokens = model.tokenizer(prompt, return_tensors="pt")
        
        input_ids = tokens["input_ids"]
        
        generation_config = {
            "max_new_tokens": 2048,
            "temperature": 0.2,
            "do_sample": True,
            "repetition_penalty": 1.1,
        }
        
        with torch.no_grad():
            output = model.generate(input_ids, **generation_config)
        
        new_tokens = output[0][input_ids.shape[1]:]
        return model.tokenizer.decode(new_tokens, skip_special_tokens=True)

    def _format_chat(self, messages: list[dict]) -> str:
        """Convert messages list to Qwen chat format."""
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"<|im_start|>system\n{content}<|im_end|>")
            elif role == "user":
                parts.append(f"<|im_start|>user\n{content}<|im_end|>")
            elif role == "assistant":
                parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)
```

---

## 6. Simulator / Renderer (`simulator/renderer.py`)

```python
"""
Project output renderer. Supports multiple render modes:
- ESP32/ILI9341: 240x320 pygame window
- Terminal: subprocess stdout capture
- Web: embedded webview (pywebview)
- Desktop app: subprocess with screenshot capture
"""

import pygame
import subprocess
import threading
import pywebview  # pip install pywebview
from PIL import Image
import os

class ProjectRenderer:
    
    MODES = ["esp32", "terminal", "web", "desktop", "none"]

    def __init__(self, project_path: str, mode: str = "terminal"):
        self.project_path = project_path
        self.mode = mode
        self.screenshot_dir = os.path.join(project_path, ".forge", "frames")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.frame_count = 0
        self._process = None
        self._pygame_win = None

    def start(self):
        if self.mode == "esp32":
            self._start_esp32_sim()
        elif self.mode == "terminal":
            self._start_terminal_capture()
        elif self.mode == "web":
            self._start_web_preview()

    def _start_esp32_sim(self):
        pygame.init()
        self._pygame_win = pygame.display.set_mode((240 * 3, 320 * 3))
        pygame.display.set_caption("FORGE — ESP32 ILI9341 Simulator")

    def render_esp32_frame(self, draw_callback):
        """draw_callback(surface: pygame.Surface) — draws on 240x320 surface"""
        surface = pygame.Surface((240, 320))
        surface.fill((0, 0, 0))
        draw_callback(surface)
        scaled = pygame.transform.scale(surface, (720, 960))
        self._pygame_win.blit(scaled, (0, 0))
        pygame.display.flip()

    def screenshot(self, label: str = "") -> str:
        self.frame_count += 1
        path = os.path.join(
            self.screenshot_dir, 
            f"frame_{self.frame_count:04d}_{label}.png"
        )
        if self.mode == "esp32" and self._pygame_win:
            pygame.image.save(self._pygame_win, path)
        elif self.mode in ("terminal", "desktop"):
            self._screenshot_subprocess_window(path)
        elif self.mode == "web":
            self._screenshot_webview(path)
        return path

    def run_project(self, entry_file: str, timeout: int = 15) -> tuple[bool, str, str]:
        """Run the project entry point, capture output."""
        env = {**os.environ, "FORGE_SIM": "1", "PYTHONPATH": self.project_path}
        try:
            result = subprocess.run(
                ["python", entry_file],
                capture_output=True, text=True, timeout=timeout,
                cwd=self.project_path, env=env
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "TIMEOUT: process ran over limit"
        except Exception as e:
            return False, "", str(e)

    def _start_web_preview(self):
        def run():
            window = pywebview.create_window(
                "FORGE Web Preview",
                url="http://localhost:5000",
                width=800, height=600
            )
            pywebview.start()
        threading.Thread(target=run, daemon=True).start()
```

---

## 7. GUI Layout (`gui/app.py`)

### Layout Blueprint

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  FORGE  [Project: CompanionOS ▾]  [Session: 2026-06-28 #3 ▾]  [●REC] [⚙ SETTINGS]│
├────────────────┬───────────────────────────────────┬───────────────────────────┤
│  AGENT TEAM    │         CONVERSATION HUB           │      CODE EDITOR          │
│                │                                   │                           │
│ ◉ SUPERVISOR   │  [SUPERVISOR] Reviewing plan...   │  📄 main.py               │
│   Qwen3.6 27B  │                                   │  ┌─────────────────────┐  │
│   ● thinking   │  [PLANNER] Step 1: Create         │  │ - old line (red)    │  │
│   12.4K tokens │  display_driver.py with...        │  │ + new line (green)  │  │
│                │                                   │  │   unchanged line    │  │
│ ◉ PLANNER      │  [USER STEERING]                  │  └─────────────────────┘  │
│   R1 8B        │  > I want the eyes to be green    │                           │
│   ○ idle       │                                   │  [APPLY] [REJECT] [EDIT]  │
│   3.2K tokens  │  [CODER] Writing display_driver   │                           │
│                │  ████████░░░░ generating...       │  CHANGED FILES            │
│ ◉ CODER        │                                   │  • display_driver.py ✏️   │
│   Qwen3.6 27B  │  [DEBUGGER] Static analysis:      │  • main.py ✏️             │
│   ○ waiting    │  ⚠ Line 47: undefined 'tft'       │  • config.py              │
│   8.1K tokens  │                                   │                           │
│                │  [VISION] Screenshot analyzed:    ├───────────────────────────┤
│ ◉ DEBUGGER     │  👁 Eyes are visible but offset   │   PROJECT RENDER          │
│   R1 8B        │  by ~20px to the right            │                           │
│   ○ idle       │                                   │  ┌───────────────────┐    │
│   1.8K tokens  │  ─────────────────────────────── │  │                   │    │
│                │  [Step 3/7] Applying CODER edit   │  │  [ESP32 240x320]  │    │
│ ◉ VISION       │                                   │  │     (^_^)         │    │
│   VL 7B        │                                   │  │                   │    │
│   ○ idle       │                                   │  └───────────────────┘    │
│   2.1K tokens  │                                   │  [MODE: esp32 ▾] [📸 CAP]│
├────────────────┴───────────────────────────────────┴───────────────────────────┤
│  PLAN PROGRESS  [████████░░░░░░░░]  Step 3 of 7  ✓✓✓○○○○                       │
├───────────────────────────────────────────────────────────────────────────────│
│  CONTEXT USAGE                                                                 │
│  SUPERVISOR [████████░░] 4.8K/6K  PLANNER [████░░░░] 3.6K/4K  CODER [██░░] 2K  │
│  DEBUGGER [███░░░] 2.1K/5K  VISION [█░░░░░] 0.9K/2K  DB: 2.4MB  Iter: 7/50    │
├───────────────────────────────────────────────────────────────────────────────│
│  STEER  [▶ RUNNING ‖PAUSE ■STOP]  [Type to inject steering... (Shift+Enter)]   │
└───────────────────────────────────────────────────────────────────────────────┘
```

### GUI Panel Breakdown

#### Left Panel — Agent Team (`gui/panels/agent_team.py`)
- 5 agent cards, each showing:
  - Name + model name
  - Status dot: ● thinking (animated pulse), ○ idle, ✗ error, ⏳ waiting
  - Token counters: last_in / last_out / total (live updating)
  - Mini sparkline of tokens per call (last 10 calls)
  - Click to expand: full system prompt, last message, call history
- AirLLM model load progress bar (shows % layers loaded when Qwen 27B is loading)

#### Center Panel — Conversation Hub (`gui/panels/chat_hub.py`)
- Chronological feed of all agent messages
- Each message has colored left border (agent's color)
- Role tag: [AGENT_NAME] role
- Streaming text display (updates char-by-char as model generates)
- Special message types:
  - `[PLAN]` — collapsible step list
  - `[CODE]` — syntax-highlighted code block with copy button
  - `[DEBUG]` — red border, root cause highlighted
  - `[VISION]` — thumbnail of screenshot + report text
  - `[USER STEERING]` — highlighted in white, timestamped
- Filter buttons: show only specific agent(s)
- Search bar across all messages

#### Right Panel Top — Code Editor (`gui/panels/code_editor.py`)
- File tree of project (left)
- Diff view (right): green additions, red deletions, unchanged lines dimmed
- Current edit source: "Proposed by CODER — pending SUPERVISOR review"
- Action buttons: [APPLY] [REJECT] [EDIT MANUALLY]
- If user clicks EDIT MANUALLY: opens inline editor, changes get attributed to USER
- Status: "2 files changed this iteration"

#### Right Panel Bottom — Project Render (`gui/panels/simulator_panel.py`)
- Mode selector: ESP32 | Terminal | Web | Desktop | None
- Live render window (pygame embedded or webview)
- For ESP32 mode: 240x320 display at 3x scale with bezel
- Screenshot capture button + auto-capture on each iteration
- Frame history: thumbnail strip of last 10 frames
- Click frame: loads in VISION panel for analysis

#### Bottom Bar — Context Stats (`gui/panels/context_stats.py`)
- Per-agent token meters (colored bars, fills to budget limit)
- Turns orange at 80%, red at 95%
- DB size counter (MB)
- RAM usage (psutil)
- VRAM usage (pynvml)
- Iteration counter: "Iter 7 / 50"
- Total tokens used this session
- Estimated cost (even at $0 since local, shows "0.00 — Local Model")

#### Bottom Input — Steering Bar (`gui/panels/steering_bar.py`)
- Text input: "Type to inject steering... (Shift+Enter to send)"
- [▶ RUNNING] [‖ PAUSE] [■ STOP] buttons
- Steering goes into DB as `steering_inputs` record
- SUPERVISOR picks it up on next iteration
- Steering history: click to see all past injections
- Quick presets: [🔄 Replan] [⏩ Skip Step] [🔁 Retry] [💬 Ask Agent]
  - "Ask Agent": pause loop, pick agent, have direct conversation, resume

---

## 8. Project Setup & New Project Flow

### New Project Dialog
When user opens FORGE with no project:

```
┌──────────────────────────────────────┐
│  FORGE — New Project                 │
├──────────────────────────────────────┤
│  Project Name: [________________]    │
│  Location:     [Browse...       ]    │
│                                      │
│  Project Type:                       │
│  ○ ESP32 / Embedded (Python bridge)  │
│  ○ Python Desktop App                │
│  ○ Python Web App (Flask/FastAPI)    │
│  ○ Existing Codebase (point to dir)  │
│  ○ Custom (describe below)           │
│                                      │
│  Render Mode:                        │
│  ○ ESP32 ILI9341 (240x320)          │
│  ○ Terminal output                   │
│  ○ Web browser preview               │
│  ○ Screenshot (desktop app)          │
│  ○ None (code-only)                  │
│                                      │
│  Entry file: [main.py          ]     │
│                                      │
│  [CANCEL]              [CREATE →]    │
└──────────────────────────────────────┘
```

After creation: drops into FORGE main window with project loaded.
User types their goal in steering bar and hits [▶ START].

---

## 9. Installation & Dependencies

### `requirements.txt`
```
# Core
customtkinter>=5.2.0
airllm>=0.5.0
transformers>=4.45.0
torch>=2.3.0
ollama>=0.3.0

# Context / Storage
tiktoken>=0.7.0
sqlite3  # stdlib

# Simulator
pygame>=2.5.0
pywebview>=5.0.0
Pillow>=10.0.0
psutil>=5.9.0
pynvml>=11.5.0

# Code tools
ast  # stdlib
pygments>=2.18.0   # syntax highlighting in diff view

# Utilities
python-dotenv>=1.0.0
watchdog>=4.0.0    # file system watching
zlib  # stdlib
```

### Installation Script (`install.sh`)
```bash
#!/bin/bash
echo "Installing FORGE dependencies..."
pip install -r requirements.txt

echo "Pulling Ollama models..."
ollama pull deepseek-r1:8b
ollama pull qwen2.5-vl:7b

echo "Downloading Qwen3.6 27B for AirLLM (this will take a while)..."
python -c "
from airllm import AutoModel
model = AutoModel.from_pretrained('Qwen/Qwen3.6-27B-Instruct', compression='4bit')
print('AirLLM model cached.')
"

echo "FORGE ready. Run: python main.py"
```

---

## 10. Key Implementation Notes for the Builder

### Threading Model
- GUI runs on main thread (CustomTkinter requirement)
- AgentManager.run() runs on a daemon thread
- All GUI updates from agent thread must use `root.after(0, callback)` 
- Never call tkinter from agent thread directly — use event queue

### AirLLM Gotchas on This Hardware
- Layer loading from disk takes 20-40s for first call on 27B model
- Subsequent calls with same model are faster (layers partially cached)
- If RAM pressure hits: `torch.cuda.empty_cache()` between agent calls
- Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` in env

### Context Pruning Trigger
- When any agent hits 85% of its token budget:
  1. PLANNER is asked to summarize the last 10 messages of that agent
  2. Summary saved as a single "SUMMARY" role message
  3. Original 10 messages marked `importance=1` (still in DB but deprioritized)
  4. Token count drops, loop continues

### Diff Application Safety
- Never overwrite a file without writing backup to `.forge/backups/`
- Keep last 5 versions of every file
- [REJECT] button in GUI restores last backup
- Git integration optional: `git add -A && git commit -m "FORGE iter {n}"`

### Steering Injection Timing
- Steering is checked at start of each iteration (not mid-inference)
- If user sends steering while model is generating: queued, applied next iteration
- If user hits PAUSE: finishes current agent call, then pauses before next

### Multiple Projects
- Each project gets its own SQLite file: `storage/projects/{name}.db`
- Sessions within project: `session_id = f"{project_name}_{timestamp}"`
- Session switcher in top bar loads different DB

---

## 11. File: `main.py` (Entry Point)

```python
import customtkinter as ctk
from gui.app import ForgeApp

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    
    root = ctk.CTk()
    root.title("FORGE — Multi-Agent AI Studio")
    root.geometry("1600x900")
    root.minsize(1200, 700)
    
    app = ForgeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
```

---

## 12. Config (`config.py`)

```python
import os
from pathlib import Path

# Paths
FORGE_DIR = Path.home() / ".forge"
MODELS_DIR = FORGE_DIR / "models"
PROJECTS_DIR = FORGE_DIR / "projects"
LOGS_DIR = FORGE_DIR / "logs"

for d in [FORGE_DIR, MODELS_DIR, PROJECTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# AirLLM
AIRLLM_MODEL_ID = "Qwen/Qwen3.6-27B-Instruct"
AIRLLM_COMPRESSION = "4bit"
AIRLLM_MAX_NEW_TOKENS = 2048

# Ollama
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_PLANNER_MODEL = "deepseek-r1:8b"
OLLAMA_DEBUGGER_MODEL = "deepseek-r1:8b"
OLLAMA_VISION_MODEL = "qwen2.5-vl:7b"

# Context budgets (tokens per agent per call)
CONTEXT_BUDGETS = {
    "SUPERVISOR": 4800,
    "PLANNER": 3600,
    "CODER": 8200,
    "DEBUGGER": 5400,
    "VISION": 900,
}

# Loop limits
MAX_ITERATIONS = 50
CONTEXT_PRUNE_THRESHOLD = 0.85  # prune when agent hits 85% of budget
BACKUP_VERSIONS_KEPT = 5

# Agent colors (hex)
AGENT_COLORS = {
    "SUPERVISOR": "#7C3AED",
    "PLANNER":    "#0891B2",
    "CODER":      "#059669",
    "DEBUGGER":   "#DC2626",
    "VISION":     "#D97706",
}

# Hardware
TORCH_DEVICE = "cuda"  # falls back to cpu if unavailable
```

---

## 13. What to Tell the AI Building This

Hand this entire document to the AI. Then add:

> Build FORGE exactly as specified. Start with:
> 1. `core/context_manager.py` — SQLite schema + all methods
> 2. `agents/base_agent.py` + `agents/airllm_agent.py` + `agents/ollama_agent.py`
> 3. All 5 agent files
> 4. `core/agent_manager.py` — the main loop
> 5. `gui/app.py` + all panels
> 6. `simulator/renderer.py`
> 7. `main.py` + `config.py` + `requirements.txt`
> 
> Use CustomTkinter for all GUI. No web frameworks. No Flask. No browser.
> Every panel is a CTkFrame. The conversation hub streams text.
> Build file by file, complete implementations, no stubs.
> After each file, confirm it integrates with the previous ones.

---
---
---
---
---
---
---
---
---
---
---
---
---
---
---

## 14. Build Log — Antigravity Agent Sessions

All changes implemented and verified below in chronological order.

---

### Session A — Initial Build (v1 Foundation)

| # | File | Status | Notes |
|---|------|--------|-------|
| 1 | `config.py` | ✅ Complete | Full v1 config — paths, models, theme, fonts, render modes |
| 2 | `main.py` | ✅ Complete | CustomTkinter entry point with icon support |
| 3 | `agents/base_agent.py` | ✅ Complete | Abstract base with `call()`, token tracking, context retrieval |
| 4 | `agents/airllm_agent.py` | ✅ Complete | AirLLM layer-sliced inference, singleton model, load progress |
| 5 | `agents/ollama_agent.py` | ✅ Complete | Ollama SDK integration with auto-pull on missing model |
| 6 | `agents/supervisor.py` | ✅ Complete | Routing decisions, code review gate |
| 7 | `agents/planner.py` | ✅ Complete | DeepSeek-R1 chain-of-thought planning, re-planning |
| 8 | `agents/coder.py` | ✅ Complete | Structured file output parser, full file mode |
| 9 | `agents/debugger.py` | ✅ Complete | Error analysis, stack trace parsing, fix proposals |
| 10 | `agents/vision.py` | ✅ Complete | Qwen2.5-VL multimodal screenshot analysis |
| 11 | `core/context_manager.py` | ✅ Complete | SQLite WAL, token budgets, file snapshots, exec results, steering |
| 12 | `core/agent_manager.py` | ✅ Complete | Orchestration loop, diff engine, pause/resume/skip/retry |
| 13 | `core/file_watcher.py` | ✅ Complete | Watchdog-based live file tree refresh |
| 14 | `gui/app.py` | ✅ Complete | Full 3-column layout, all callbacks wired |
| 15 | `gui/panels/agent_team.py` | ✅ Complete | 7 agent cards with sparklines and expand |
| 16 | `gui/panels/chat_hub.py` | ✅ Complete | Streaming conversation hub with agent color coding |
| 17 | `gui/panels/code_editor.py` | ✅ Complete | File tree, diff viewer, syntax highlighting |
| 18 | `gui/panels/simulator_panel.py` | ✅ Complete | Render canvas, frame history, canvas steering bounding box |
| 19 | `gui/panels/context_stats.py` | ✅ Complete | 7 token meters, RAM/VRAM, timeline button |
| 20 | `gui/panels/steering_bar.py` | ✅ Complete | Goal input, run/pause/stop/replan/skip/retry controls |
| 21 | `gui/widgets/agent_badge.py` | ✅ Complete | Animated status badge with colour states |
| 22 | `gui/widgets/token_meter.py` | ✅ Complete | Segmented token usage bar |
| 23 | `gui/dialogs/new_project.py` | ✅ Complete | Project name/location/type/render/entry/Stitch ID |
| 24 | `gui/dialogs/diagnostics.py` | ✅ Complete | System checks: CUDA, Ollama, AirLLM, Gemini API |
| 25 | `requirements.txt` | ✅ Complete | All dependencies including `google-generativeai`, `pytest` |

---

### Session B — v2 Feature Upgrade

| # | File | Status | Notes |
|---|------|--------|-------|
| 1 | `config.py` (v2) | ✅ Complete | Added AUDITOR, TESTER, DEFAULT_AGENT_MODELS, Git, TDD, RAG, AST, Stitch, Canvas Steering |
| 2 | `agents/auditor.py` | ✅ Complete | Gemini 2.5 Flash API agent — audit loop on disagreements or every N iters |
| 3 | `agents/tester.py` | ✅ Complete | TDD test generator, pytest output parser |
| 4 | `core/git_manager.py` | ✅ Complete | GitPython wrapper — auto-commit after each approved write, timeline, revert |
| 5 | `core/ast_indexer.py` | ✅ Complete | AST-based symbol map for Python/.js/etc, relevant symbol extraction |
| 6 | `core/rag_librarian.py` | ✅ Complete | TF-IDF doc search over FORGE_DIR/docs, context injection |
| 7 | `core/stitch_bridge.py` | ✅ Complete | Stitch MCP project data cache and context formatter |
| 8 | `core/model_registry.py` | ✅ Complete | JSON-backed persistent model registry |
| 9 | `core/agent_manager.py` (v2) | ✅ Complete | Integrated AUDITOR, TESTER, GitManager, AST context, TDD loop |
| 10 | `core/context_manager.py` (v2) | ✅ Complete | AST-aware file retrieval, export/import session, fixed steering |
| 11 | `gui/app.py` (v2) | ✅ Complete | Full rewrite — diagnostics, timeline, canvas steer, Stitch injection, safe file watcher |
| 12 | `gui/panels/agent_team.py` (v2) | ✅ Complete | All 7 agents shown with correct display_name + speed |
| 13 | `gui/panels/context_stats.py` (v2) | ✅ Complete | 7 token meters + timeline button |
| 14 | `gui/panels/simulator_panel.py` (v2) | ✅ Complete | Canvas bounding-box steering with coordinate mapping |
| 15 | `gui/dialogs/new_project.py` (v2) | ✅ Complete | Stitch Project ID field added |

---

### v2 Architecture Summary

```
main.py
  └── ForgeApp (gui/app.py)
        ├── AgentTeamPanel      — 7 agent cards (left)
        ├── ChatHubPanel        — streaming conversation (center)
        ├── CodeEditorPanel     — file tree + diff viewer (right top)
        ├── SimulatorPanel      — render canvas + canvas steering (right bottom)
        ├── ContextStatsPanel   — 7 token meters + timeline (bottom)
        └── SteeringBar         — goal input + controls (bottom)

AgentManager (core/agent_manager.py)
  ├── SUPERVISOR  (AirLLM  — Qwen3.6 27B)    routing, review gate
  ├── PLANNER     (Ollama  — DeepSeek-R1 8B) step planning
  ├── CODER       (AirLLM  — Qwen3.6 27B)    code generation
  ├── DEBUGGER    (Ollama  — DeepSeek-R1 8B) error analysis
  ├── VISION      (Ollama  — Qwen2.5-VL 7B)  screenshot analysis
  ├── AUDITOR     (Gemini  — 2.5 Flash API)   quality audits
  └── TESTER      (Ollama  — DeepSeek-R1 8B) TDD test generation

Support modules:
  ContextManager   — SQLite WAL storage, token budgets, steering
  GitManager       — auto-commit, timeline, revert
  ASTIndexer       — symbol maps for code context
  RAGLibrarian     — document search injection
  StitchBridge     — design system context loading
  FileWatcher      — live project tree refresh
```

