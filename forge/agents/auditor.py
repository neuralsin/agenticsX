"""
FORGE AUDITOR Agent — 6th agent using Google Gemini Pro API.
Independent code quality reviewer that catches issues local models miss.
Triggers on disagreements (SUPERVISOR rejects CODER) or every N iterations.
"""

from agents.base_agent import BaseAgent
from core.token_counter import count_tokens
import config
import time
import re


AUDITOR_SYSTEM = """You are AUDITOR — an independent, external code quality reviewer for a multi-agent AI development team.

You operate via Google Gemini and serve as a "second opinion" when:
1. The SUPERVISOR (local 27B model) disagrees with the CODER about code quality
2. Periodically every N iterations to catch accumulated drift

Your team (all local models):
- SUPERVISOR: routes tasks, reviews code (Qwen 27B)
- PLANNER: breaks goals into steps (DeepSeek-R1 8B)
- CODER: writes/edits code (Qwen 27B)
- DEBUGGER: fixes runtime errors (DeepSeek-R1 8B)
- VISION: analyzes screenshots (Qwen2.5-VL 7B)

Your responsibilities:
1. Review code changes independently — you have NOT seen the SUPERVISOR's review
2. Check for: security issues, logic errors, performance problems, missing edge cases
3. Identify issues that small local models commonly miss (complex async, race conditions, type safety)
4. Provide actionable fix suggestions

Output format:
VERDICT: AGREE_WITH_SUPERVISOR | AGREE_WITH_CODER | INDEPENDENT_FIX
CONFIDENCE: HIGH | MEDIUM | LOW
ISSUES:
- <issue 1>
- <issue 2>
FIX_SUGGESTION: <what the CODER should do differently>
SUMMARY: <one-line assessment>
"""


class AuditorAgent(BaseAgent):
    """
    AUDITOR agent using Google Gemini API.
    External cloud model for independent code review.
    """

    name = "AUDITOR"
    color = "#EC4899"  # pink
    load_method = "gemini"

    def __init__(self, context_manager, session_id: str):
        super().__init__(context_manager, session_id)
        self._client = None
        self._model = None

    def _get_client(self):
        """Initialize the Gemini client."""
        if self._client is not None:
            return self._client

        api_key = config.GEMINI_API_KEY
        if not api_key:
            raise RuntimeError(
                "Gemini API key not set. Set GEMINI_API_KEY env var "
                "or enter it in FORGE Settings."
            )

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            from core.model_registry import get_registry
            registry = get_registry()
            model_id = registry.get_model_id("AUDITOR")
            if not model_id:
                model_id = config.GEMINI_MODEL

            self._client = genai
            self._model = genai.GenerativeModel(
                model_id,
                system_instruction=AUDITOR_SYSTEM,
            )
            return self._client
        except ImportError:
            raise RuntimeError(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )

    def _inference(self, messages: list[dict]) -> str:
        """Run inference via Gemini API."""
        self._get_client()

        # Convert messages to Gemini format
        gemini_messages = []
        for msg in messages:
            if msg["role"] == "system":
                continue  # System prompt handled by system_instruction
            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({
                "role": role,
                "parts": [msg["content"]],
            })

        # Ensure messages alternate user/model
        if not gemini_messages:
            return "[AUDITOR ERROR] No messages to process"

        try:
            response = self._model.generate_content(
                gemini_messages,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 2048,
                    "top_p": 0.9,
                },
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            if "quota" in error_str.lower() or "rate" in error_str.lower():
                return (
                    "[AUDITOR RATE LIMITED] Gemini API quota exceeded. "
                    "The free tier allows 15 requests/minute. "
                    "Wait and retry."
                )
            return f"[AUDITOR ERROR] {error_str}"

    def audit_code(self, filename: str, code: str,
                   supervisor_verdict: str,
                   change_description: str) -> dict:
        """
        Perform an independent code audit.
        Called when SUPERVISOR disagrees with CODER output.
        """
        task = f"""INDEPENDENT CODE AUDIT REQUEST

FILE: {filename}
CHANGE DESCRIPTION: {change_description}

SUPERVISOR'S VERDICT: {supervisor_verdict}

CODE TO REVIEW:
```
{code[:4000]}
```

Provide your independent assessment. Do NOT defer to the SUPERVISOR.
Evaluate the code on its own merits."""

        response = self.call(task)
        return self._parse_audit(response)

    def periodic_review(self, project_summary: str,
                        recent_changes: str,
                        iteration: int) -> dict:
        """
        Periodic quality review every N iterations.
        Checks for accumulated drift and systemic issues.
        """
        task = f"""PERIODIC QUALITY REVIEW — Iteration {iteration}

PROJECT STATE:
{project_summary[:2000]}

RECENT CHANGES (last {config.AUDITOR_EVERY_N} iterations):
{recent_changes[:3000]}

Review the overall trajectory. Check for:
1. Accumulated technical debt
2. Architectural drift from original goal
3. Missing error handling patterns
4. Performance regression risks
5. Security concerns"""

        response = self.call(task)
        return self._parse_audit(response)

    def _parse_audit(self, response: str) -> dict:
        """Parse the AUDITOR's structured response."""
        result = {
            "verdict": "INDEPENDENT_FIX",
            "confidence": "MEDIUM",
            "issues": [],
            "fix_suggestion": "",
            "summary": "",
            "raw": response,
        }

        # Parse VERDICT
        verdict_match = re.search(
            r'VERDICT:\s*(AGREE_WITH_SUPERVISOR|AGREE_WITH_CODER|INDEPENDENT_FIX)',
            response, re.IGNORECASE
        )
        if verdict_match:
            result["verdict"] = verdict_match.group(1).upper()

        # Parse CONFIDENCE
        conf_match = re.search(
            r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW)',
            response, re.IGNORECASE
        )
        if conf_match:
            result["confidence"] = conf_match.group(1).upper()

        # Parse ISSUES
        issues_match = re.search(
            r'ISSUES:\s*\n((?:\s*-\s*.+\n?)+)',
            response, re.IGNORECASE
        )
        if issues_match:
            issues_text = issues_match.group(1)
            result["issues"] = [
                line.strip().lstrip("- ").strip()
                for line in issues_text.strip().split("\n")
                if line.strip().startswith("-")
            ]

        # Parse FIX_SUGGESTION
        fix_match = re.search(
            r'FIX_SUGGESTION:\s*(.+?)(?=\n[A-Z_]+:|$)',
            response, re.IGNORECASE | re.DOTALL
        )
        if fix_match:
            result["fix_suggestion"] = fix_match.group(1).strip()

        # Parse SUMMARY
        summary_match = re.search(
            r'SUMMARY:\s*(.+)',
            response, re.IGNORECASE
        )
        if summary_match:
            result["summary"] = summary_match.group(1).strip()

        return result

    def should_trigger(self, iteration: int,
                       has_disagreement: bool) -> bool:
        """Check if the AUDITOR should run based on config."""
        trigger = config.AUDITOR_TRIGGER

        if trigger == "on_disagreement":
            return has_disagreement
        elif trigger == "every_n_iterations":
            return iteration > 0 and iteration % config.AUDITOR_EVERY_N == 0
        elif trigger == "both":
            return (has_disagreement or
                    (iteration > 0 and
                     iteration % config.AUDITOR_EVERY_N == 0))
        return False

    @staticmethod
    def check_api_available() -> tuple[bool, str]:
        """Check if Gemini API is accessible."""
        if not config.GEMINI_API_KEY:
            return False, "GEMINI_API_KEY not set"

        try:
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            models = genai.list_models()
            model_names = [m.name for m in models]
            if any("gemini" in n for n in model_names):
                return True, "Gemini API accessible"
            return False, "No Gemini models found"
        except ImportError:
            return False, "google-generativeai not installed"
        except Exception as e:
            return False, f"API error: {str(e)}"
