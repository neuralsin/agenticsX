"""
FORGE TESTER Agent — TDD test generation agent.
Generates pytest test cases BEFORE the CODER writes implementation.
The CODER then writes code to pass these tests.
Uses Qwen3.6 27B via AirLLM (layer-sliced, fits 6GB VRAM).
"""

import re

from agents.airllm_agent import AirLLMAgent
import config


TESTER_SYSTEM = """You are TESTER — the test-driven development specialist in a multi-agent AI team.

Your role:
1. Before CODER writes implementation, YOU write the failing tests
2. Your tests define the expected behavior precisely
3. Tests must be runnable with pytest
4. Focus on: edge cases, error handling, type correctness, boundary conditions

Output format:
TEST_FILE: <relative path, e.g. tests/test_main.py>
TEST_DESCRIPTION: <what these tests verify>
TEST_CODE:
```python
<complete, runnable pytest code>
```

Rules:
- Always include necessary imports
- Use descriptive test function names: test_<what>_<when>_<expected>
- Include at least 3 test cases per function being tested
- Include one edge case test and one error handling test
- Use pytest.raises for expected exceptions
- Keep tests independent — no shared mutable state
- Add brief docstrings explaining what each test verifies
"""


class TesterAgent(AirLLMAgent):
    """
    TESTER agent — generates pytest tests before implementation.
    Uses Qwen3.6 27B via AirLLM (layer-sliced, 6GB VRAM safe).
    Part of the TDD loop: TESTER → CODER → RUN → DEBUGGER.
    """

    name = "TESTER"
    color = "#06B6D4"  # electric-cyan

    def __init__(self, context_manager, session_id: str):
        super().__init__(context_manager, session_id)

    def generate_tests(self, step_description: str,
                       filename: str,
                       existing_code: str = "",
                       project_structure: str = "") -> dict:
        """
        Generate pytest test cases for a planned implementation step.
        Called BEFORE CODER writes the actual code.
        """
        task = f"""Generate pytest tests for this implementation task:

TASK: {step_description}
TARGET FILE: {filename}

{"EXISTING CODE:" if existing_code else ""}
{existing_code[:2000] if existing_code else "(new file — no existing code)"}

{"PROJECT STRUCTURE:" if project_structure else ""}
{project_structure[:500] if project_structure else ""}

Write comprehensive tests that the implementation must pass.
Follow the output format exactly."""

        response = self.call(task)
        return self._parse_test_output(response)

    def generate_regression_tests(self, changed_files: dict,
                                  error_history: str = "") -> dict:
        """
        Generate regression tests after a bug fix.
        Ensures the same bug doesn't recur.
        """
        files_summary = "\n".join(
            f"FILE: {f}\n{c[:500]}" for f, c in changed_files.items()
        )

        task = f"""Generate regression tests for these recently fixed files:

{files_summary}

{"PREVIOUS ERRORS:" if error_history else ""}
{error_history[:1000] if error_history else ""}

Write tests that specifically prevent these bugs from recurring.
Focus on the exact error conditions that were fixed."""

        response = self.call(task)
        return self._parse_test_output(response)

    def _parse_test_output(self, response: str) -> dict:
        """Parse the TESTER's structured response."""
        result = {
            "test_file": "tests/test_generated.py",
            "description": "",
            "test_code": "",
            "raw": response,
            "test_count": 0,
        }

        # Parse TEST_FILE
        file_match = re.search(
            r'TEST_FILE:\s*(.+)', response, re.IGNORECASE
        )
        if file_match:
            result["test_file"] = file_match.group(1).strip()

        # Parse TEST_DESCRIPTION
        desc_match = re.search(
            r'TEST_DESCRIPTION:\s*(.+)', response, re.IGNORECASE
        )
        if desc_match:
            result["description"] = desc_match.group(1).strip()

        # Parse TEST_CODE from code block
        code_match = re.search(
            r'```python\s*\n(.+?)```',
            response, re.DOTALL
        )
        if code_match:
            result["test_code"] = code_match.group(1).strip()
        else:
            # Try to find code after TEST_CODE:
            code_section = re.search(
                r'TEST_CODE:\s*\n(.+)',
                response, re.DOTALL | re.IGNORECASE
            )
            if code_section:
                code = code_section.group(1).strip()
                # Remove markdown fences if present
                code = re.sub(r'^```\w*\n?', '', code)
                code = re.sub(r'\n?```$', '', code)
                result["test_code"] = code.strip()

        # Count test functions
        if result["test_code"]:
            result["test_count"] = len(
                re.findall(r'def test_\w+', result["test_code"])
            )

        return result

    @staticmethod
    def check_pytest_available() -> tuple[bool, str]:
        """Check if pytest is available."""
        try:
            import pytest
            return True, f"pytest {pytest.__version__}"
        except ImportError:
            return False, (
                "pytest not installed. "
                "Run: pip install pytest"
            )
