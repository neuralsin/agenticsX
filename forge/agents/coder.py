"""
CODER — Qwen3.6 27B via AirLLM
Role: Receives specific file-level tasks from SUPERVISOR/PLANNER.
      Outputs complete file contents or precise diffs.
      One file change per call for safety and reviewability.
      Must always output in parseable format.
"""

import re
from agents.airllm_agent import AirLLMAgent
import config


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
    """
    CODER agent — writes and modifies code files.
    One file change per call. Full file output, never partial.
    """

    name = "CODER"

    color = config.AGENT_COLORS["CODER"]

    def __init__(self, context_manager, session_id):
        super().__init__(context_manager, session_id)
        self.ctx.set_system_prompt(self.name, session_id, CODER_SYSTEM,
                                   config.CONTEXT_BUDGETS["CODER"])

    def implement(self, task: str, current_file_content: str,
                  filename: str) -> dict:
        """Implement a task by modifying an existing file."""
        full_task = f"""Task: {task}

Current file ({filename}):
```
{current_file_content}
```

Implement the task. Output the complete modified file."""
        response = self.call(full_task)
        return self._parse_file_output(response, filename)

    def create_file(self, task: str, filename: str,
                    related_files: dict = None) -> dict:
        """Create a new file from scratch."""
        ctx = ""
        if related_files:
            ctx = "\n\n".join(
                f"Related file {k}:\n```\n{v[:1000]}\n```"
                for k, v in related_files.items()
            )
        
        full_task = f"""Task: Create new file {filename}
{task}

Related files for context:
{ctx}"""
        response = self.call(full_task)
        return self._parse_file_output(response, filename)

    def _parse_file_output(self, response: str, default_filename: str = "") -> dict:
        """Parse CODER's structured output into a file change dict."""
        result = {
            "filename": default_filename,
            "action": "CREATE",
            "description": "",
            "code": "",
            "raw": response,
            "diff": "",
        }

        # Parse FILE path
        file_match = re.search(r'###?\s*FILE:\s*(.+?)(?:\n|$)', response)
        if file_match:
            result["filename"] = file_match.group(1).strip()

        # Parse ACTION
        action_match = re.search(
            r'###?\s*ACTION:\s*(CREATE|MODIFY|DELETE)', 
            response, re.IGNORECASE
        )
        if action_match:
            result["action"] = action_match.group(1).upper()

        # Parse DESCRIPTION
        desc_match = re.search(r'###?\s*DESCRIPTION:\s*(.+?)(?:\n|$)', response)
        if desc_match:
            result["description"] = desc_match.group(1).strip()

        # Parse code block — find the largest fenced code block
        code_blocks = re.findall(
            r'```(?:\w+)?\n(.*?)```',
            response, re.DOTALL
        )
        if code_blocks:
            # Use the largest code block (likely the full file)
            result["code"] = max(code_blocks, key=len).strip()
        else:
            # Try to find unformatted code (everything after the headers)
            code_start = 0
            for marker in ["### END", "###END"]:
                idx = response.find(marker)
                if idx > 0:
                    # Find the code between headers and END
                    header_end = response.find("\n```")
                    if header_end > 0:
                        code_section = response[header_end:idx]
                        # Remove the ``` markers
                        code_section = re.sub(r'^```\w*\n?', '', code_section)
                        code_section = re.sub(r'\n?```\s*$', '', code_section)
                        result["code"] = code_section.strip()
                    break

        return result
