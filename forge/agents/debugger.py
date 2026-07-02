"""
DEBUGGER — Qwen3.6 27B via AirLLM (layer-sliced, fits 6GB VRAM)
Role: Receives stderr/stdout + the code that caused it.
      Uses chain-of-thought reasoning to trace the error root cause.
      Outputs a specific fix instruction for CODER.
      Can also do static analysis (no execution needed).
"""

import re
from agents.airllm_agent import AirLLMAgent
import config


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


class DebuggerAgent(AirLLMAgent):
    """
    DEBUGGER agent — diagnoses bugs and generates fix instructions.
    Uses Qwen3.6 27B via AirLLM (layer-sliced, 6GB VRAM safe).
    """

    name = "DEBUGGER"

    color = config.AGENT_COLORS["DEBUGGER"]

    def __init__(self, context_manager, session_id):
        super().__init__(context_manager, session_id)
        self.ctx.set_system_prompt(self.name, session_id, DEBUGGER_SYSTEM,
                                   config.CONTEXT_BUDGETS["DEBUGGER"])

    def analyze_error(self, stderr: str, stdout: str,
                      file_contents: dict, iteration: int) -> dict:
        """Analyze a runtime error and produce a fix instruction."""
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

    def _format_files(self, file_contents: dict) -> str:
        """Format file contents for the prompt."""
        parts = []
        for filepath, content in file_contents.items():
            # Truncate large files
            truncated = content[:2000] if len(content) > 2000 else content
            parts.append(f"--- {filepath} ---\n```\n{truncated}\n```")
        return "\n\n".join(parts)

    def _parse_debug_report(self, response: str) -> dict:
        """Parse a debug report from DEBUGGER response."""
        result = {
            "root_cause": "",
            "affected_file": "",
            "affected_line": "",
            "fix_description": "",
            "fix_confidence": "MEDIUM",
            "side_effects": "",
            "coder_task": "",
            "raw": response,
        }

        # Remove <think>...</think> blocks for parsing
        clean = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)

        patterns = {
            "root_cause": r'ROOT_CAUSE:\s*(.+?)(?:\n[A-Z]|\n\n|$)',
            "affected_file": r'AFFECTED_FILE:\s*(.+?)(?:\n|$)',
            "affected_line": r'AFFECTED_LINE:\s*(.+?)(?:\n|$)',
            "fix_description": r'FIX_DESCRIPTION:\s*(.+?)(?:\n[A-Z]|\n\n|$)',
            "fix_confidence": r'FIX_CONFIDENCE:\s*(HIGH|MEDIUM|LOW)',
            "side_effects": r'SIDE_EFFECTS:\s*(.+?)(?:\n[A-Z]|\n\n|$)',
            "coder_task": r'CODER_TASK:\s*(.+?)(?:\n\n|$)',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, clean, re.IGNORECASE | re.DOTALL)
            if match:
                result[key] = match.group(1).strip()

        return result

    def _parse_issues(self, response: str) -> list[dict]:
        """Parse static analysis issues from DEBUGGER response."""
        issues = []
        
        # Remove <think> blocks
        clean = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        
        # Look for numbered issues or bullet points
        issue_pattern = re.compile(
            r'(?:\d+[\.\)]\s*|[-•]\s*)(.+?)(?=\n\d+[\.\)]|\n[-•]|\n\n|$)',
            re.DOTALL
        )
        
        for match in issue_pattern.finditer(clean):
            issue_text = match.group(1).strip()
            if len(issue_text) > 10:  # Filter out noise
                severity = "MEDIUM"
                if any(w in issue_text.lower() for w in ["critical", "crash", "fatal"]):
                    severity = "HIGH"
                elif any(w in issue_text.lower() for w in ["minor", "style", "warning"]):
                    severity = "LOW"
                
                issues.append({
                    "description": issue_text,
                    "severity": severity,
                })

        return issues
