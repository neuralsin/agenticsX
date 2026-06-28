"""
FORGE AirLLM Agent — Uses AirLLM to run Qwen3.6 27B on 6GB VRAM via layer splitting.
Loads model from disk, runs inference, results returned.
Only one AirLLM model active at a time (enforced by AgentManager).
"""

import threading

from agents.base_agent import BaseAgent
import config


class AirLLMAgent(BaseAgent):
    """
    Base class for agents that use AirLLM (layer-sliced inference).
    Supports Qwen3.6 27B on 6GB VRAM by loading model layer-by-layer.
    Class-level singleton ensures only one model instance exists.
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
                cls._notify_load_progress(1.0, "AirLLM not available — using simulation mode")
                cls._model_instance = None
                return None
            except Exception as e:
                cls._notify_load_progress(1.0, f"Model load failed: {str(e)}")
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
        """Run inference using AirLLM with Qwen chat template."""
        model = self.load_model()

        if model is None:
            return (
                "[AirLLM MODEL NOT LOADED] The AirLLM model could not be loaded.\n"
                "Possible fixes:\n"
                "  1. Install AirLLM: pip install airllm\n"
                "  2. Install PyTorch with CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu121\n"
                "  3. Ensure sufficient disk space for model download (~15GB)\n"
                "  4. Check GPU availability: nvidia-smi\n"
                "  5. Or switch this agent to Ollama in Settings > Model Config"
            )

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

        except Exception as e:
            return f"[AirLLM INFERENCE ERROR] {str(e)}"

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

