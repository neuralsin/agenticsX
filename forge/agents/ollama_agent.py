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
            return self._simulate_response(messages)
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
            return self._simulate_response([{"role": "user", "content": task}])
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
            return self._simulate_response([{"role": "user", "content": task}])
        except Exception as e:
            return f"[OLLAMA MULTI-IMAGE ERROR] {str(e)}"

    def _simulate_response(self, messages: list[dict]) -> str:
        """
        Simulation mode response when Ollama is not available.
        Used for GUI development and testing without models.
        """
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"][:200]
                break

        return (
            f"[SIMULATION MODE — Ollama not connected]\n"
            f"Agent: {self.name}\n"
            f"Model: {self.ollama_model}\n"
            f"Received task: {last_user_msg}\n"
            f"This is a simulated response. Start Ollama and pull "
            f"the required model to enable real inference."
        )

    @staticmethod
    def check_ollama_available() -> bool:
        """Check if Ollama is running and accessible."""
        try:
            import ollama
            ollama.list()
            return True
        except Exception:
            return False

    @staticmethod
    def check_model_available(model_name: str) -> bool:
        """Check if a specific model is available in Ollama."""
        try:
            import ollama
            models = ollama.list()
            model_names = [m.get("name", "") for m in models.get("models", [])]
            return any(model_name in name for name in model_names)
        except Exception:
            return False
