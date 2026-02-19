"""
VIO 83 AI ORCHESTRA - Backend Orchestrator con LiteLLM
Gestisce il routing intelligente tra provider AI cloud e locale.
"""

import os
import time
import litellm
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Configurazione LiteLLM - silenzio log verbosi
litellm.set_verbose = False

# Mapping modelli per provider
CLOUD_MODELS = {
    "claude": "anthropic/claude-sonnet-4-20250514",
    "gpt4": "openai/gpt-4o",
    "grok": "xai/grok-2",
    "mistral": "mistral/mistral-large-latest",
    "deepseek": "deepseek/deepseek-chat",
}

# Classificazione richieste per routing intelligente
KEYWORDS = {
    "code": ["codice", "code", "funzione", "function", "bug", "debug", "api",
             "database", "sql", "python", "javascript", "typescript", "react"],
    "creative": ["scrivi", "write", "storia", "story", "poesia", "poem",
                 "creativo", "creative", "articolo", "blog"],
    "analysis": ["analiz", "analy", "dati", "data", "grafico", "chart",
                 "statistic", "csv", "excel"],
    "realtime": ["oggi", "today", "attual", "current", "news", "notizie",
                 "ultimo", "latest"],
    "reasoning": ["spiega", "explain", "perché", "why", "come funziona",
                  "how does", "ragion", "logic", "matematica", "math"],
}

# Mapping tipo richiesta -> provider ottimale
ROUTING_MAP = {
    "code": "claude",
    "creative": "gpt4",
    "analysis": "claude",
    "realtime": "grok",
    "reasoning": "claude",
    "conversation": "claude",
}


def classify_request(message: str) -> str:
    """Classifica il tipo di richiesta per il routing intelligente."""
    lower = message.lower()
    for req_type, keywords in KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return req_type
    return "conversation"


def route_to_provider(request_type: str, mode: str = "cloud") -> str:
    """Determina il provider ottimale basato sul tipo di richiesta."""
    if mode == "local":
        return "ollama"
    return ROUTING_MAP.get(request_type, "claude")


async def call_ai(
    messages: list[dict],
    provider: str = "claude",
    mode: str = "cloud",
    ollama_model: str = "qwen2.5-coder:3b",
    ollama_host: str = "http://localhost:11434",
    auto_routing: bool = True,
    fallback_providers: list[str] = None,
    cross_check: bool = False,
) -> dict:
    """
    Funzione principale: invia messaggio all'orchestra AI.
    
    Returns:
        dict con: content, provider, model, tokens_used, latency_ms, cross_check_result
    """
    if fallback_providers is None:
        fallback_providers = ["gpt4", "ollama"]

    # Routing intelligente
    if auto_routing and mode == "cloud":
        last_msg = messages[-1]["content"] if messages else ""
        request_type = classify_request(last_msg)
        provider = route_to_provider(request_type, mode)
        print(f"[Orchestra] Tipo: {request_type} → Provider: {provider}")

    # Determina il modello
    if mode == "local" or provider == "ollama":
        model = f"ollama/{ollama_model}"
        litellm.api_base = ollama_host
    else:
        model = CLOUD_MODELS.get(provider, CLOUD_MODELS["claude"])

    start = time.time()
    result = {"provider": provider, "model": model}

    try:
        # Chiamata principale via LiteLLM
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            max_tokens=4096,
        )

        result["content"] = response.choices[0].message.content
        result["tokens_used"] = response.usage.total_tokens if response.usage else 0
        result["latency_ms"] = int((time.time() - start) * 1000)

        # Cross-check opzionale
        if cross_check and mode == "cloud" and fallback_providers:
            result["cross_check_result"] = await _cross_check(
                messages, result["content"], fallback_providers[0]
            )

        return result

    except Exception as e:
        print(f"[Orchestra] Provider {provider} fallito: {e}")

        # Fallback
        for fb_provider in fallback_providers:
            try:
                if fb_provider == "ollama":
                    fb_model = f"ollama/{ollama_model}"
                else:
                    fb_model = CLOUD_MODELS.get(fb_provider)
                    if not fb_model:
                        continue

                response = await litellm.acompletion(
                    model=fb_model,
                    messages=messages,
                    max_tokens=4096,
                )

                return {
                    "content": response.choices[0].message.content,
                    "provider": fb_provider,
                    "model": fb_model,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "latency_ms": int((time.time() - start) * 1000),
                }
            except Exception as fb_error:
                print(f"[Orchestra] Fallback {fb_provider} fallito: {fb_error}")
                continue

        raise Exception(f"Tutti i provider hanno fallito. Ultimo errore: {e}")


async def _cross_check(
    original_messages: list[dict],
    first_response: str,
    check_provider: str,
) -> dict:
    """Verifica incrociata della risposta con un secondo provider."""
    try:
        check_model = CLOUD_MODELS.get(check_provider)
        if not check_model:
            return {"concordance": None, "error": "Provider non disponibile"}

        check_messages = original_messages + [
            {"role": "assistant", "content": first_response},
            {
                "role": "user",
                "content": (
                    "Verifica se la risposta precedente è accurata e corretta. "
                    "Rispondi SOLO con 'CONFERMATO' se è corretta, "
                    "o spiega brevemente gli errori trovati."
                ),
            },
        ]

        response = await litellm.acompletion(
            model=check_model,
            messages=check_messages,
            max_tokens=500,
        )

        check_content = response.choices[0].message.content
        return {
            "concordance": "CONFERMATO" in check_content.upper(),
            "second_provider": check_provider,
            "second_response": check_content,
        }
    except Exception as e:
        return {"concordance": None, "error": str(e)}
