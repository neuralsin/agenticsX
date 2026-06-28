"""
FORGE Ollama Agent — Uses Ollama Python SDK for local inference.
Supports text-only (PLANNER, DEBUGGER) and multimodal (VISION) agents.
"""

import base64

from agents.base_agent import BaseAgent
import config


class OllamaAgent(BaseAgent):
    """
    Base class for agents that use Ollama for inference.
    Supports DeepSeek-R1 8B (text) and Qwen2.5-VL 7B (vision).
    """

    load_method = "ollama"
    ollama_model: str = ""  # Set by subclass

    def _inference(self, messages: list[dict]) -> str:
        """Run inference via Ollama chat API."""
        try:
            import ollama

            response = ollama.chat(
                model=self.ollama_model,
                messages=messages,
                options={
                    "temperature": 0.3,
                    "num_predict": 2048,
                    "top_p": 0.9,
                }
            )
            return response["message"]["content"]

        except ImportError:
            return (
                "[OLLAMA NOT INSTALLED] Install the ollama package:\n"
                "  pip install ollama\n"
                "Then start Ollama: ollama serve"
            )
        except Exception as e:
            # Check if it's a connection error
            error_str = str(e).lower()
            if "connection" in error_str or "refused" in error_str:
                return (
                    f"[OLLAMA CONNECTION ERROR] Cannot connect to Ollama at "
                    f"{config.OLLAMA_HOST}. Please ensure Ollama is running.\n"
                    f"Start Ollama with: ollama serve\n"
                    f"Error: {str(e)}"
                )
            return f"[OLLAMA ERROR] {str(e)}"

    def _inference_with_image(self, task: str, image_b64: str) -> str:
        """
        Run inference with an image input (for VISION agent).
        Uses Ollama's multimodal API.
        """
        try:
            import ollama

            response = ollama.chat(
                model=self.ollama_model,
                messages=[
                    {
                        "role": "user",
                        "content": task,
                        "images": [image_b64],
                    }
                ],
                options={
                    "temperature": 0.2,
                    "num_predict": 1024,
                }
            )
            return response["message"]["content"]

        except ImportError:
            return "[OLLAMA NOT INSTALLED] pip install ollama"
        except Exception as e:
            return f"[OLLAMA VISION ERROR] {str(e)}"

    def _inference_with_images(self, task: str, images_b64: list[str]) -> str:
        """
        Run inference with multiple images (for frame comparison).
        """
        try:
            import ollama

            response = ollama.chat(
                model=self.ollama_model,
                messages=[
                    {
                        "role": "user",
                        "content": task,
                        "images": images_b64,
                    }
                ],
                options={
                    "temperature": 0.2,
                    "num_predict": 1024,
                }
            )
            return response["message"]["content"]

        except ImportError:
            return "[OLLAMA NOT INSTALLED] pip install ollama"
        except Exception as e:
            return f"[OLLAMA MULTI-IMAGE ERROR] {str(e)}"

    def _handle_model_not_found(self, model_name: str) -> str:
        """
        Handle model not found — attempt auto-pull if configured,
        otherwise return actionable error message.
        """
        # Try to auto-pull the model
        try:
            import ollama
            ollama.pull(model_name)
            return ""  # Success — caller should retry
        except Exception as pull_error:
            return (
                f"[OLLAMA MODEL NOT FOUND] Model '{model_name}' is not available.\n"
                f"Auto-pull failed: {str(pull_error)}\n"
                f"Manual fix: Run 'ollama pull {model_name}' in terminal.\n"
                f"Or change the model in Settings > Model Config."
            )

    @staticmethod
    def check_ollama_available() -> tuple[bool, str]:
        """Check if Ollama is running and accessible."""
        try:
            import ollama
            models = ollama.list()
            model_count = len(models.get("models", []))
            return True, f"Ollama running — {model_count} models available"
        except ImportError:
            return False, "ollama package not installed. Run: pip install ollama"
        except Exception as e:
            error_str = str(e).lower()
            if "connection" in error_str or "refused" in error_str:
                return False, "Ollama not running. Start with: ollama serve"
            return False, f"Ollama error: {str(e)}"

    @staticmethod
    def check_model_available(model_name: str) -> tuple[bool, str]:
        """Check if a specific model is available in Ollama."""
        try:
            import ollama
            models = ollama.list()
            model_names = [m.get("name", "") for m in models.get("models", [])]
            if any(model_name in name for name in model_names):
                return True, f"Model '{model_name}' available"
            return False, (
                f"Model '{model_name}' not found. "
                f"Run: ollama pull {model_name}"
            )
        except ImportError:
            return False, "ollama package not installed"
        except Exception as e:
            return False, f"Check failed: {str(e)}"

    @staticmethod
    def list_available_models() -> list[str]:
        """List all available Ollama models."""
        try:
            import ollama
            models = ollama.list()
            return [
                m.get("name", "") or m.get("model", "")
                for m in models.get("models", [])
            ]
        except Exception:
            return []

