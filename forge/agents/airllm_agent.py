"""
FORGE AirLLM Agent — Uses AirLLM to run Qwen3.6 27B on 6GB VRAM via layer splitting.
Loads model from disk, runs inference, results returned.
Only one AirLLM model active at a time (enforced by AgentManager).

When AirLLM / CUDA is unavailable, silently falls back to qwen3.6:27b via Ollama
so all 7 agents keep working without any errors.
"""

import threading

from agents.base_agent import BaseAgent
import config


class AirLLMAgent(BaseAgent):
    """
    Base class for agents that use AirLLM (layer-sliced inference).
    Supports Qwen3.6 27B on 6GB VRAM by loading model layer-by-layer.
    Class-level singleton ensures only one model instance exists.

    When AirLLM is not available (no CUDA / model not downloaded),
    automatically falls back to Ollama qwen3.6:27b so agents keep working.
    """

    load_method = "airllm"

    _model_instance = None
    _model_lock = threading.Lock()
    _loading = False
    _load_progress = 0.0  # 0.0 to 1.0, for GUI progress bar
    _load_callbacks = []  # GUI binds here for load progress

    @classmethod
    def load_model(cls):
        """
        Load the AirLLM model (singleton).
        Layer loading from disk takes 20-40s for first call on 27B model.
        Returns None silently if CUDA / AirLLM not available.
        """
        with cls._model_lock:
            if cls._model_instance is not None:
                return cls._model_instance

            cls._loading = True
            cls._load_progress = 0.0
            cls._notify_load_progress(0.0, "Loading AirLLM model...")

            try:
                from airllm import AutoModel
                import torch

                cls._notify_load_progress(0.1, "Initializing model from pretrained...")

                cls._model_instance = AutoModel.from_pretrained(
                    config.AIRLLM_MODEL_ID,
                    compression=config.AIRLLM_COMPRESSION,
                    profiling_mode=False,
                )

                cls._notify_load_progress(1.0, "Model loaded successfully")
                return cls._model_instance

            except ImportError:
                cls._notify_load_progress(1.0, "AirLLM not available — using Ollama fallback")
                cls._model_instance = None
                return None
            except Exception as e:
                import traceback
                traceback.print_exc()
                cls._notify_load_progress(1.0, f"AirLLM unavailable ({e}) — using Ollama fallback")
                cls._model_instance = None
                return None
            finally:
                cls._loading = False

    @classmethod
    def unload_model(cls):
        """Unload the model and free VRAM."""
        with cls._model_lock:
            if cls._model_instance is not None:
                try:
                    import torch
                    del cls._model_instance
                    cls._model_instance = None
                    torch.cuda.empty_cache()
                except Exception:
                    cls._model_instance = None

    @classmethod
    def _notify_load_progress(cls, progress: float, message: str):
        """Notify GUI callbacks about model loading progress."""
        cls._load_progress = progress
        for cb in cls._load_callbacks:
            try:
                cb(progress, message)
            except Exception:
                pass

    def _inference(self, messages: list[dict]) -> str:
        """Run inference using AirLLM with Qwen chat template.
        If AirLLM is not available, transparently falls back to Ollama."""
        model = self.load_model()

        if model is None:
            # ── Transparent Ollama fallback ──────────────────────────────────
            # AirLLM requires CUDA + large disk space (~15GB). When unavailable,
            # silently route inference through Ollama qwen3.6:27b instead.
            return self._ollama_fallback(messages)

        try:
            import torch

            # Format as Qwen chat template
            prompt = self._format_chat(messages)
            tokens = model.tokenizer(prompt, return_tensors="pt")
            input_ids = tokens["input_ids"]

            generation_config = {
                "max_new_tokens": config.AIRLLM_MAX_NEW_TOKENS,
                "temperature": config.AIRLLM_TEMPERATURE,
                "do_sample": True,
                "repetition_penalty": config.AIRLLM_REPETITION_PENALTY,
            }

            with torch.no_grad():
                output = model.generate(input_ids, **generation_config)

            new_tokens = output[0][input_ids.shape[1]:]
            return model.tokenizer.decode(new_tokens, skip_special_tokens=True)

        except Exception:
            # Any runtime error — also fall back to Ollama
            return self._ollama_fallback(messages)

    def _ollama_fallback(self, messages: list[dict]) -> str:
        """
        Silent fallback: when AirLLM is unavailable (no CUDA, no model),
        route the inference request through Ollama qwen3.6:27b instead.
        This keeps SUPERVISOR and CODER fully operational at all times.
        """
        try:
            import ollama
            response = ollama.chat(
                model=config.OLLAMA_PLANNER_MODEL,  # qwen3.6:27b
                messages=messages,
                options={
                    "temperature": config.AIRLLM_TEMPERATURE,
                    "num_predict": config.AIRLLM_MAX_NEW_TOKENS,
                    "top_p": 0.9,
                },
            )
            # Handle both new SDK object and old dict response formats
            if isinstance(response, dict):
                return response["message"]["content"]
            return response.message.content
        except Exception as e:
            error_str = str(e).lower()
            if "connection" in error_str or "refused" in error_str:
                return (
                    "[OFFLINE] Cannot reach Ollama. Make sure Ollama is running.\n"
                    "Run: ollama serve\n"
                    "Or launch FORGE via Launch FORGE.bat (it starts Ollama automatically)."
                )
            return f"[FALLBACK ERROR] Both AirLLM and Ollama failed: {str(e)}"

    def _format_chat(self, messages: list[dict]) -> str:
        """Convert messages list to Qwen chat format with im_start/im_end tags."""
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"<|im_start|>system\n{content}<|im_end|>")
            elif role == "user":
                parts.append(f"<|im_start|>user\n{content}<|im_end|>")
            elif role == "assistant":
                parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)
