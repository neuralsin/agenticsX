"""
SUPERVISOR — Qwen3.6 27B via AirLLM
Role: Overall project awareness, task decomposition, routing decisions,
      quality gate on CODER output before it gets written to disk,
      decides when goal is achieved or needs another iteration.
"""

import re
from agents.airllm_agent import AirLLMAgent
import config


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
    """
    SUPERVISOR agent — lead architect, routes tasks, reviews code.
    Uses Qwen3.6 27B via AirLLM for deep reasoning.
    """
    
    name = "SUPERVISOR"

    color = config.AGENT_COLORS["SUPERVISOR"]

    def __init__(self, context_manager, session_id):
        super().__init__(context_manager, session_id)
        # Register system prompt in DB
        self.ctx.set_system_prompt(self.name, session_id, SUPERVISOR_SYSTEM,
                                   config.CONTEXT_BUDGETS["SUPERVISOR"])

    def route(self, situation: str) -> dict:
        """Decide which agent acts next and what their task is."""
        response = self.call(
            f"Current situation:\n{situation}\n\nWhat should happen next?"
        )
        return self._parse_routing(response)

    def review_code(self, filename: str, new_code: str,
                    change_description: str,
                    team_context: list = None) -> dict:
        """Quality gate before any file write. Gets team bus context."""
        # Truncate code to keep within context budget
        code_preview = new_code[:3000]
        task = f"""Review this proposed change:
FILE: {filename}
DESCRIPTION: {change_description}

```
{code_preview}
```

Is this safe to apply? Check for: syntax issues, logic errors, breaking changes."""
        response = self.call(task, team_context=team_context)
        return self._parse_review(response)

    def _parse_routing(self, response: str) -> dict:
        """Parse a routing decision from SUPERVISOR response."""
        result = {
            "action": "CODER",
            "reason": "",
            "task": "",
            "raw": response,
        }

        # Parse ROUTE_TO
        route_match = re.search(
            r'ROUTE_TO:\s*(PLANNER|CODER|DEBUGGER|VISION|DONE|REPLAN)',
            response, re.IGNORECASE
        )
        if route_match:
            result["action"] = route_match.group(1).upper()

        # Parse REASON
        reason_match = re.search(r'REASON:\s*(.+?)(?:\n|$)', response)
        if reason_match:
            result["reason"] = reason_match.group(1).strip()

        # Parse TASK
        task_match = re.search(r'TASK:\s*(.+?)(?:\n\n|\n[A-Z]|$)', 
                               response, re.DOTALL)
        if task_match:
            result["task"] = task_match.group(1).strip()

        return result

    def _parse_review(self, response: str) -> dict:
        """Parse a code review decision from SUPERVISOR response."""
        result = {
            "verdict": "APPROVE",
            "issues": "none",
            "next": "",
            "raw": response,
        }

        # Parse REVIEW verdict
        review_match = re.search(r'REVIEW:\s*(APPROVE|REJECT)', 
                                 response, re.IGNORECASE)
        if review_match:
            result["verdict"] = review_match.group(1).upper()

        # Parse ISSUES
        issues_match = re.search(r'ISSUES:\s*(.+?)(?:\n[A-Z]|\n\n|$)', 
                                 response, re.DOTALL)
        if issues_match:
            result["issues"] = issues_match.group(1).strip()

        # Parse NEXT
        next_match = re.search(r'NEXT:\s*(.+?)(?:\n\n|$)', response, re.DOTALL)
        if next_match:
            result["next"] = next_match.group(1).strip()

        return result
