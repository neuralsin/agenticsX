"""
FORGE Model Registry — Persistent, per-agent model configuration.
Stores model assignments in ~/.forge/model_config.json.
Supports hot-swapping models without code changes.
Auto-discovers available Ollama models.
"""

import json
import os
import copy
from pathlib import Path

import config


class ModelRegistry:
    """
    Central registry for agent → model assignments.
    Loads from disk, falls back to defaults, saves changes persistently.
    """

    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(config.CONFIG_FILE)
        self._registry = {}
        self._available_ollama = []
        self._load()

    def _load(self):
        """Load model config from disk, or initialize with defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Merge with defaults (add any new agents from defaults)
                self._registry = copy.deepcopy(config.DEFAULT_AGENT_MODELS)
                for agent, model_cfg in saved.items():
                    if agent in self._registry:
                        self._registry[agent].update(model_cfg)
                    else:
                        self._registry[agent] = model_cfg
            except (json.JSONDecodeError, IOError):
                self._registry = copy.deepcopy(config.DEFAULT_AGENT_MODELS)
        else:
            self._registry = copy.deepcopy(config.DEFAULT_AGENT_MODELS)

    def save(self):
        """Persist the current registry to disk."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._registry, f, indent=2)

    def get_agent_model(self, agent_name: str) -> dict:
        """Get model config for an agent."""
        return self._registry.get(agent_name,
                                  config.DEFAULT_AGENT_MODELS.get(agent_name, {}))

    def get_provider(self, agent_name: str) -> str:
        """Get the inference provider for an agent."""
        return self.get_agent_model(agent_name).get("provider", "ollama")

    def get_model_id(self, agent_name: str) -> str:
        """Get the model ID for an agent."""
        return self.get_agent_model(agent_name).get("model_id", "")

    def get_display_name(self, agent_name: str) -> str:
        """Get the display name for an agent's model."""
        return self.get_agent_model(agent_name).get("display_name", "Unknown")

    def set_agent_model(self, agent_name: str, provider: str, model_id: str,
                        display_name: str = "", speed: str = ""):
        """Update an agent's model assignment."""
        if agent_name not in self._registry:
            self._registry[agent_name] = {}
        self._registry[agent_name].update({
            "provider": provider,
            "model_id": model_id,
            "display_name": display_name or model_id,
            "speed": speed or "unknown",
        })
        self.save()

    def get_all(self) -> dict:
        """Get the full registry."""
        return copy.deepcopy(self._registry)

    def get_agents(self) -> list[str]:
        """Get list of all agent names."""
        return list(self._registry.keys())

    def reset_to_defaults(self):
        """Reset all agents to default model assignments."""
        self._registry = copy.deepcopy(config.DEFAULT_AGENT_MODELS)
        self.save()

    def discover_ollama_models(self) -> list[str]:
        """
        Auto-discover available models from the running Ollama instance.
        Returns list of model name strings.
        """
        try:
            import ollama
            response = ollama.list()
            models = response.get("models", [])
            self._available_ollama = []
            for m in models:
                name = m.get("name", "") or m.get("model", "")
                if name:
                    self._available_ollama.append(name)
            return self._available_ollama
        except Exception:
            return self._available_ollama

    def get_available_ollama(self) -> list[str]:
        """Get cached list of available Ollama models."""
        if not self._available_ollama:
            self.discover_ollama_models()
        return self._available_ollama

    def get_available_providers(self) -> list[str]:
        """Get list of supported inference providers."""
        return ["ollama", "airllm", "gemini"]

    def get_provider_models(self, provider: str) -> list[str]:
        """Get available models for a specific provider."""
        if provider == "ollama":
            return self.get_available_ollama()
        elif provider == "airllm":
            return [
                "Qwen/Qwen3.6-27B-Instruct",
                "Qwen/Qwen2.5-7B-Instruct",
                "meta-llama/Llama-3-8B-Instruct",
                "mistralai/Mistral-7B-Instruct-v0.2",
            ]
        elif provider == "gemini":
            return [
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
                "gemini-1.5-pro",
            ]
        return []

    def validate_agent_model(self, agent_name: str) -> tuple[bool, str]:
        """
        Check if an agent's assigned model is actually available.
        Returns (is_valid, error_message).
        """
        model_cfg = self.get_agent_model(agent_name)
        provider = model_cfg.get("provider", "")
        model_id = model_cfg.get("model_id", "")

        if not provider or not model_id:
            return False, f"No model configured for {agent_name}"

        if provider == "ollama":
            available = self.get_available_ollama()
            if available and not any(model_id in m for m in available):
                return False, (
                    f"Model '{model_id}' not found in Ollama. "
                    f"Run: ollama pull {model_id}"
                )
        elif provider == "gemini":
            if not config.GEMINI_API_KEY:
                return False, (
                    "Gemini API key not set. Set GEMINI_API_KEY env var "
                    "or enter it in Settings."
                )
        elif provider == "airllm":
            try:
                import torch
                if not torch.cuda.is_available():
                    return False, "CUDA not available — AirLLM requires GPU"
            except ImportError:
                return False, "PyTorch not installed — required for AirLLM"

        return True, "OK"


# Global singleton
_registry = None

def get_registry() -> ModelRegistry:
    """Get the global model registry singleton."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
