"""
PLANNER — Qwen3.6 27B via AirLLM (layer-sliced, fits 6GB VRAM)
Role: Receives a high-level goal, outputs a numbered step-by-step execution plan.
      Uses chain-of-thought reasoning to think through dependencies and order.
      Re-plans when SUPERVISOR signals a direction change.
"""

import re
from agents.airllm_agent import AirLLMAgent
import config


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

MANDATORY RULES:
- Every RUN step MUST be followed immediately by a VERIFY step.
- Every VERIFY step triggers the VISION agent to visually audit the output (screenshot/render).
- If the project produces any visible output (web page, terminal output, GUI, ESP32 display),
  there MUST be at least one VERIFY step at the end of the plan.
- Never end a plan without a final VERIFY step unless action is "none" (code-only project).

After each step in the plan, note:
DEPENDS_ON: [step numbers this depends on, or "none"]
VERIFY_BY: [how to know this step succeeded]
"""


class PlannerAgent(AirLLMAgent):
    """
    PLANNER agent — breaks down goals into ordered implementation steps.
    Uses Qwen3.6 27B via AirLLM (layer-sliced, 6GB VRAM safe).
    """

    name = "PLANNER"

    color = config.AGENT_COLORS["PLANNER"]

    def __init__(self, context_manager, session_id):
        super().__init__(context_manager, session_id)
        self.ctx.set_system_prompt(self.name, session_id, PLANNER_SYSTEM,
                                   config.CONTEXT_BUDGETS["PLANNER"])

    def create_plan(self, goal: str, project_structure: str) -> list[dict]:
        """Create a detailed implementation plan from a goal."""
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

    def summarize_context(self, messages: list[str]) -> str:
        """Summarize old messages for context compression."""
        joined = "\n---\n".join(messages[:10])
        task = f"""Summarize the following conversation history into a concise 
summary that captures the key decisions, code changes, and current state.
Keep it under 200 words.

Messages:
{joined}"""
        return self.call(task)

    def _parse_plan(self, response: str) -> list[dict]:
        """Parse a structured plan from PLANNER response."""
        steps = []
        
        # Remove <think>...</think> blocks
        clean = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        
        # Find numbered plan steps
        # Pattern: number. [ACTION] [FILE: path] — description
        step_pattern = re.compile(
            r'(\d+)\.\s*\[?(CREATE|MODIFY|DELETE|RUN|TEST|VERIFY)\]?\s*'
            r'(?:\[?FILE:\s*([^\]—\n]+)\]?)?\s*[—\-]?\s*(.+?)(?=\n\d+\.|\nDEPENDS|\nVERIFY|\n\n|$)',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in step_pattern.finditer(clean):
            step_num = int(match.group(1))
            action = match.group(2).upper()
            file_path = match.group(3).strip() if match.group(3) else ""
            description = match.group(4).strip()
            
            # Look for DEPENDS_ON after this step
            depends_on = []
            deps_match = re.search(
                rf'(?:DEPENDS_ON|depends_on):\s*(.+?)(?:\n|$)',
                clean[match.end():]
            )
            if deps_match:
                deps_text = deps_match.group(1).strip()
                if deps_text.lower() != "none":
                    depends_on = [int(x) for x in re.findall(r'\d+', deps_text)]

            # Look for VERIFY_BY after this step
            verify_by = ""
            verify_match = re.search(
                rf'(?:VERIFY_BY|verify_by):\s*(.+?)(?:\n|$)',
                clean[match.end():]
            )
            if verify_match:
                verify_by = verify_match.group(1).strip()

            steps.append({
                "step": step_num,
                "action": action,
                "file": file_path,
                "description": description,
                "depends_on": depends_on,
                "verify_by": verify_by,
            })

        # If parsing failed, create a single generic step
        if not steps:
            steps = [{
                "step": 1,
                "action": "CREATE",
                "file": "",
                "description": clean.strip()[:500] or "Execute the plan",
                "depends_on": [],
                "verify_by": "manual review",
            }]

        return steps
