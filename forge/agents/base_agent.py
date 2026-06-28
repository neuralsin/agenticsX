"""
FORGE Base Agent — Abstract base class for all agents.
Defines the interface: system prompt, memory, call(), status management.
All 5 agents inherit from this.
"""

from abc import ABC, abstractmethod
import time
import threading

from core.context_manager import ContextManager
from core.token_counter import count_tokens


class BaseAgent(ABC):
    """
    Abstract base agent. Every FORGE agent inherits from this.
    Provides: status management, token tracking, context integration,
    and GUI callback wiring.
    """

    name: str = "BASE"
    model: str = "unknown"
    load_method: str = "none"  # 'airllm' | 'ollama'
    color: str = "#FFFFFF"

    def __init__(self, context_manager: ContextManager, session_id: str):
        self.ctx = context_manager
        self.session_id = session_id
        self.status = "idle"  # idle | thinking | error | waiting
        self.last_tokens_in = 0
        self.last_tokens_out = 0
        self.total_tokens = 0
        self.call_count = 0
        self.tokens_history = []  # Last N token counts for sparkline
        self.last_response_time = 0.0
        self.last_error = ""
        self.status_callbacks = []  # GUI binds here
        self._lock = threading.Lock()

    def call(self, task: str, extra_context: dict = None) -> str:
        """
        Main entry point for agent inference.
        1. Sets status to 'thinking'
        2. Builds context from DB
        3. Runs model inference
        4. Tracks tokens
        5. Persists to DB
        6. Returns response text
        """
        self._set_status("thinking")
        
        try:
            # Build context from DB
            messages, tokens_in = self.ctx.get_agent_context(
                self.name, self.session_id, task
            )
            
            # Add current task
            messages.append({"role": "user", "content": task})
            tokens_in += count_tokens(task)

            # Add extra context if provided
            if extra_context:
                for key, value in extra_context.items():
                    ctx_msg = f"[{key}]\n{value}"
                    messages.append({"role": "user", "content": ctx_msg})
                    tokens_in += count_tokens(ctx_msg)

            # Run inference
            t0 = time.time()
            response = self._inference(messages)
            elapsed = time.time() - t0
            self.last_response_time = elapsed

            # Track tokens
            tokens_out = count_tokens(response)
            with self._lock:
                self.last_tokens_in = tokens_in
                self.last_tokens_out = tokens_out
                self.total_tokens += tokens_in + tokens_out
                self.call_count += 1
                self.tokens_history.append(tokens_in + tokens_out)
                if len(self.tokens_history) > 10:
                    self.tokens_history.pop(0)

            # Persist to DB
            self.ctx.save_message(
                self.session_id, self.name, "user", task, tokens_in
            )
            self.ctx.save_message(
                self.session_id, self.name, "assistant", response, tokens_out
            )

            self._set_status("idle")
            return response

        except Exception as e:
            self.last_error = str(e)
            self._set_status("error")
            return f"[AGENT ERROR: {self.name}] {str(e)}"

    @abstractmethod
    def _inference(self, messages: list[dict]) -> str:
        """
        Run model inference. Implemented by subclasses
        (AirLLMAgent, OllamaAgent).
        """
        pass

    def _set_status(self, status: str):
        """Update agent status and notify all GUI callbacks."""
        self.status = status
        for cb in self.status_callbacks:
            try:
                cb(self.name, status)
            except Exception:
                pass  # Don't crash on callback errors

    def get_stats(self) -> dict:
        """Get agent statistics for GUI display."""
        with self._lock:
            return {
                "name": self.name,
                "model": self.model,
                "load_method": self.load_method,
                "color": self.color,
                "status": self.status,
                "tokens_total": self.total_tokens,
                "tokens_last_in": self.last_tokens_in,
                "tokens_last_out": self.last_tokens_out,
                "calls": self.call_count,
                "last_response_time": self.last_response_time,
                "last_error": self.last_error,
                "tokens_history": list(self.tokens_history),
            }

    def reset_stats(self):
        """Reset all statistics."""
        with self._lock:
            self.last_tokens_in = 0
            self.last_tokens_out = 0
            self.total_tokens = 0
            self.call_count = 0
            self.tokens_history = []
            self.last_response_time = 0.0
            self.last_error = ""
