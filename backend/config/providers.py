# ============================================================
# VIO 83 AI ORCHESTRA — Copyright (c) 2026 Viorica Porcu (vio83)
# DUAL LICENSE: Proprietary + AGPL-3.0 — See LICENSE files
# ALL RIGHTS RESERVED — https://github.com/vio83/vio83-ai-orchestra
# ============================================================
"""
VIO 83 AI ORCHESTRA - Configurazione Provider AI
Mappa completa dei provider supportati con modelli e endpoint.
"""

import os
from typing import Optional

# === PROVIDER CLOUD (richiedono API key) ===

CLOUD_PROVIDERS = {
    "claude": {
        "name": "Anthropic Claude",
        "litellm_prefix": "anthropic",
        "models": {
            "claude-sonnet-4-20250514": {
                "name": "Claude Sonnet 4",
                "context_window": 200000,
                "max_output": 8192,
                "strengths": ["code", "analysis", "reasoning", "writing"],
                "cost_per_1m_input": 3.0,
                "cost_per_1m_output": 15.0,
            },
            "claude-opus-4-20250514": {
                "name": "Claude Opus 4",
                "context_window": 200000,
                "max_output": 8192,
                "strengths": ["complex_reasoning", "research", "creative"],
                "cost_per_1m_input": 15.0,
                "cost_per_1m_output": 75.0,
            },
            "claude-haiku-3-5-20241022": {
                "name": "Claude Haiku 3.5",
                "context_window": 200000,
                "max_output": 8192,
                "strengths": ["speed", "simple_tasks", "classification"],
                "cost_per_1m_input": 0.25,
                "cost_per_1m_output": 1.25,
            },
        },
        "env_key": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
    },
    "gpt4": {
        "name": "OpenAI GPT-4",
        "litellm_prefix": "openai",
        "models": {
            "gpt-4o": {
                "name": "GPT-4o",
                "context_window": 128000,
                "max_output": 16384,
                "strengths": ["creative", "multimodal", "general"],
                "cost_per_1m_input": 2.50,
                "cost_per_1m_output": 10.0,
            },
            "gpt-4o-mini": {
                "name": "GPT-4o Mini",
                "context_window": 128000,
                "max_output": 16384,
                "strengths": ["speed", "cost_effective"],
                "cost_per_1m_input": 0.15,
                "cost_per_1m_output": 0.60,
            },
        },
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
    "grok": {
        "name": "xAI Grok",
        "litellm_prefix": "xai",
        "models": {
            "grok-2": {
                "name": "Grok 2",
                "context_window": 131072,
                "max_output": 8192,
                "strengths": ["realtime", "news", "humor", "unfiltered"],
                "cost_per_1m_input": 2.0,
                "cost_per_1m_output": 10.0,
            },
        },
        "env_key": "XAI_API_KEY",
        "default_model": "grok-2",
    },
    "mistral": {
        "name": "Mistral AI",
        "litellm_prefix": "mistral",
        "models": {
            "mistral-large-latest": {
                "name": "Mistral Large",
                "context_window": 128000,
                "max_output": 8192,
                "strengths": ["multilingual", "reasoning", "code"],
                "cost_per_1m_input": 2.0,
                "cost_per_1m_output": 6.0,
            },
            "mistral-small-latest": {
                "name": "Mistral Small",
                "context_window": 128000,
                "max_output": 8192,
                "strengths": ["speed", "cost_effective", "multilingual"],
                "cost_per_1m_input": 0.2,
                "cost_per_1m_output": 0.6,
            },
        },
        "env_key": "MISTRAL_API_KEY",
        "default_model": "mistral-large-latest",
    },
    "deepseek": {
        "name": "DeepSeek",
        "litellm_prefix": "deepseek",
        "models": {
            "deepseek-chat": {
                "name": "DeepSeek Chat V3",
                "context_window": 64000,
                "max_output": 8192,
                "strengths": ["code", "math", "reasoning"],
                "cost_per_1m_input": 0.27,
                "cost_per_1m_output": 1.10,
            },
            "deepseek-reasoner": {
                "name": "DeepSeek R1",
                "context_window": 64000,
                "max_output": 8192,
                "strengths": ["deep_reasoning", "math", "science"],
                "cost_per_1m_input": 0.55,
                "cost_per_1m_output": 2.19,
            },
        },
        "env_key": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
}


# === PROVIDER LOCALI (Ollama, nessuna API key) ===

LOCAL_PROVIDERS = {
    "ollama": {
        "name": "Ollama (Locale)",
        "host": "http://localhost:11434",
        "models": {
            "qwen2.5-coder:3b": {
                "name": "Qwen 2.5 Coder 3B",
                "ram_required_gb": 2.5,
                "strengths": ["code", "fast"],
            },
            "llama3.2:3b": {
                "name": "Llama 3.2 3B",
                "ram_required_gb": 2.5,
                "strengths": ["general", "conversation"],
            },
            "mistral:7b": {
                "name": "Mistral 7B",
                "ram_required_gb": 5.0,
                "strengths": ["reasoning", "multilingual"],
            },
            "phi3:3.8b": {
                "name": "Phi-3 3.8B",
                "ram_required_gb": 3.0,
                "strengths": ["reasoning", "efficient"],
            },
            "deepseek-coder-v2:lite": {
                "name": "DeepSeek Coder V2 Lite",
                "ram_required_gb": 3.5,
                "strengths": ["code", "debugging"],
            },
            "gemma2:2b": {
                "name": "Gemma 2 2B",
                "ram_required_gb": 2.0,
                "strengths": ["lightweight", "fast"],
            },
        },
        "default_model": "qwen2.5-coder:3b",
    }
}


# === ROUTING INTELLIGENTE ===

REQUEST_TYPE_ROUTING = {
    "code": {
        "cloud_primary": "claude",
        "cloud_fallback": "deepseek",
        "local_primary": "qwen2.5-coder:3b",
        "local_fallback": "deepseek-coder-v2:lite",
    },
    "creative": {
        "cloud_primary": "gpt4",
        "cloud_fallback": "claude",
        "local_primary": "llama3.2:3b",
        "local_fallback": "mistral:7b",
    },
    "analysis": {
        "cloud_primary": "claude",
        "cloud_fallback": "mistral",
        "local_primary": "mistral:7b",
        "local_fallback": "phi3:3.8b",
    },
    "realtime": {
        "cloud_primary": "grok",
        "cloud_fallback": "gpt4",
        "local_primary": "llama3.2:3b",
        "local_fallback": "qwen2.5-coder:3b",
    },
    "reasoning": {
        "cloud_primary": "claude",
        "cloud_fallback": "deepseek",
        "local_primary": "phi3:3.8b",
        "local_fallback": "mistral:7b",
    },
    "conversation": {
        "cloud_primary": "claude",
        "cloud_fallback": "gpt4",
        "local_primary": "llama3.2:3b",
        "local_fallback": "gemma2:2b",
    },
}


def get_available_cloud_providers() -> dict:
    """Ritorna solo i provider cloud con API key configurata."""
    available = {}
    for key, provider in CLOUD_PROVIDERS.items():
        env_key = provider["env_key"]
        if os.environ.get(env_key):
            available[key] = provider
    return available


def get_litellm_model_string(provider: str, model: Optional[str] = None) -> str:
    """Costruisci la stringa modello per LiteLLM."""
    if provider in CLOUD_PROVIDERS:
        prefix = CLOUD_PROVIDERS[provider]["litellm_prefix"]
        model_name = model or CLOUD_PROVIDERS[provider]["default_model"]
        return f"{prefix}/{model_name}"
    return model or "ollama/qwen2.5-coder:3b"
