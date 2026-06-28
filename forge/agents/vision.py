"""
VISION — Qwen2.5-VL 7B via Ollama
Role: Receives a screenshot of the running project output.
      Reports what it sees vs what was expected.
      Identifies UI/visual bugs, layout issues, missing elements.
      Generates a structured report for SUPERVISOR.
"""

import re
import base64
from agents.ollama_agent import OllamaAgent
import config


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
    """
    VISION agent — analyzes screenshots and provides visual QA.
    Uses Qwen2.5-VL 7B for multimodal (text + image) analysis.
    """

    name = "VISION"

    color = config.AGENT_COLORS["VISION"]
    ollama_model = config.OLLAMA_VISION_MODEL

    def __init__(self, context_manager, session_id):
        super().__init__(context_manager, session_id)
        self.ctx.set_system_prompt(self.name, session_id, VISION_SYSTEM,
                                   config.CONTEXT_BUDGETS["VISION"])

    def analyze_frame(self, screenshot_path: str, expected: str,
                      iteration: int) -> dict:
        """Analyze a screenshot against expected behavior."""
        try:
            with open(screenshot_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
        except Exception as e:
            return {
                "what_i_see": f"[ERROR] Could not load screenshot: {e}",
                "expected": expected,
                "matches": "NO",
                "issues": [f"Screenshot load failed: {str(e)}"],
                "severity": "CRITICAL",
                "recommendation": "Check screenshot capture system",
                "iteration_verdict": "CONTINUE",
                "raw": "",
            }

        task = f"""Iteration {iteration}.
Expected behavior: {expected}
Analyze this screenshot and report what you see."""

        response = self._inference_with_image(task, img_b64)
        
        # Save to DB
        report = self._parse_vision_report(response)
        self.ctx.save_vision_report(
            self.session_id, iteration, screenshot_path,
            response, len(report.get("issues", []))
        )
        
        return report

    def compare_frames(self, before_path: str, after_path: str,
                       change_description: str) -> str:
        """Compare two frames to verify a change had visible effect."""
        images = []
        for path in [before_path, after_path]:
            try:
                with open(path, "rb") as f:
                    images.append(base64.b64encode(f.read()).decode())
            except Exception as e:
                return f"[ERROR] Could not load image {path}: {e}"

        task = f"""Compare BEFORE (first image) and AFTER (second image).
Change that was made: {change_description}
Did the change have the expected visual effect? What's different?"""

        return self._inference_with_images(task, images)

    def _parse_vision_report(self, response: str) -> dict:
        """Parse a structured vision report from VISION response."""
        result = {
            "what_i_see": "",
            "expected": "",
            "matches": "NO",
            "issues": [],
            "severity": "MINOR",
            "recommendation": "",
            "iteration_verdict": "CONTINUE",
            "raw": response,
        }

        patterns = {
            "what_i_see": r'WHAT_I_SEE:\s*(.+?)(?:\nEXPECTED|\n\n|$)',
            "expected": r'EXPECTED:\s*(.+?)(?:\nMATCHES|\n\n|$)',
            "matches": r'MATCHES:\s*(YES|PARTIAL|NO)',
            "severity": r'SEVERITY:\s*(CRITICAL|MAJOR|MINOR|NONE)',
            "recommendation": r'RECOMMENDATION:\s*(.+?)(?:\nITERATION|\n\n|$)',
            "iteration_verdict": r'ITERATION_VERDICT:\s*(CONTINUE|DONE|CHANGE_APPROACH)',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
            if match:
                result[key] = match.group(1).strip()

        # Parse ISSUES (bullet list)
        issues_match = re.search(
            r'ISSUES:\s*\n((?:\s*[-•]\s*.+\n?)+)',
            response, re.IGNORECASE
        )
        if issues_match:
            issues_text = issues_match.group(1)
            result["issues"] = [
                line.strip().lstrip("-•").strip()
                for line in issues_text.strip().split("\n")
                if line.strip()
            ]

        return result
