"""
VIO 83 AI ORCHESTRA - Direct Orchestrator (senza LiteLLM)
Gestisce chiamate dirette a Ollama e provider cloud via HTTP.
Non dipende da LiteLLM — funziona con Python 3.14.
"""

import os
import time
import json
import asyncio
from typing import Optional, AsyncGenerator
from urllib.request import Request, urlopen
from urllib.error import URLError

# Per chiamate async HTTP usiamo aiohttp se disponibile, altrimenti asyncio
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


# === SYSTEM PROMPT CERTIFICATO VIO 83 ===
# Importato dal modulo dedicato (versione completa con tutti i campi)

from backend.orchestrator.system_prompt import (
    VIO83_MASTER_PROMPT,
    SPECIALIZED_PROMPTS,
    build_system_prompt,
)

# Alias per retrocompatibilità (server.py lo importa come VIO83_SYSTEM_PROMPT)
VIO83_SYSTEM_PROMPT = VIO83_MASTER_PROMPT


# === CLASSIFICAZIONE RICHIESTE ===

KEYWORDS = {
    "code": ["codice", "code", "funzione", "function", "bug", "debug", "api",
             "database", "sql", "python", "javascript", "typescript", "react",
             "script", "algoritmo", "classe", "metodo", "array", "json",
             "html", "css", "endpoint", "backend", "frontend"],
    "creative": ["scrivi", "write", "storia", "story", "poesia", "poem",
                 "creativo", "creative", "articolo", "article", "blog",
                 "racconto", "romanzo", "canzone", "email", "lettera"],
    "analysis": ["analiz", "analy", "dati", "data", "grafico", "chart",
                 "statistic", "csv", "excel", "tabella", "confronta",
                 "compare", "trend", "metrica", "report"],
    "realtime": ["oggi", "today", "attual", "current", "news", "notizie",
                 "ultimo", "latest", "2026", "2025", "tempo reale"],
    "reasoning": ["spiega", "explain", "perché", "why", "come funziona",
                  "how does", "ragion", "reason", "logic", "matematica",
                  "math", "teoria", "filosofia", "dimostrazione"],
}

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
    scores = {}
    for req_type, keywords in KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[req_type] = score
    if scores:
        return max(scores, key=scores.get)
    return "conversation"


def route_to_provider(request_type: str, mode: str = "cloud") -> str:
    """Determina il provider ottimale basato sul tipo di richiesta."""
    if mode == "local":
        return "ollama"
    return ROUTING_MAP.get(request_type, "claude")


# === OLLAMA DIRETTO ===

async def call_ollama(
    messages: list[dict],
    model: str = "qwen2.5-coder:3b",
    host: str = "http://localhost:11434",
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> dict:
    """
    Chiama Ollama direttamente via HTTP.
    Restituisce dict con: content, provider, model, tokens_used, latency_ms
    """
    start = time.time()
    url = f"{host}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,  # Per ora non-streaming dal backend
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    }

    if HAS_HTTPX:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
    elif HAS_AIOHTTP:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                resp.raise_for_status()
                data = await resp.json()
    else:
        # Fallback sincrono (non ideale ma funziona)
        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

    content = data.get("message", {}).get("content", "")
    tokens = (data.get("prompt_eval_count", 0) or 0) + (data.get("eval_count", 0) or 0)

    return {
        "content": content,
        "provider": "ollama",
        "model": model,
        "tokens_used": tokens,
        "latency_ms": int((time.time() - start) * 1000),
    }


async def call_ollama_streaming(
    messages: list[dict],
    model: str = "qwen2.5-coder:3b",
    host: str = "http://localhost:11434",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """
    Streaming Ollama — genera token uno alla volta.
    Usa per Server-Sent Events (SSE) dall'endpoint /chat/stream.
    """
    url = f"{host}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    }

    if HAS_HTTPX:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if data.get("done"):
                                return
                        except json.JSONDecodeError:
                            continue
    elif HAS_AIOHTTP:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                resp.raise_for_status()
                async for line in resp.content:
                    decoded = line.decode("utf-8").strip()
                    if decoded:
                        try:
                            data = json.loads(decoded)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if data.get("done"):
                                return
                        except json.JSONDecodeError:
                            continue
    else:
        # Fallback: non-streaming
        result = await call_ollama(messages, model, host, temperature=temperature, max_tokens=max_tokens)
        yield result["content"]


# === OLLAMA MANAGEMENT ===

async def check_ollama_status(host: str = "http://localhost:11434") -> dict:
    """Verifica stato Ollama e modelli disponibili."""
    result = {"available": False, "models": [], "error": None}

    try:
        if HAS_HTTPX:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check se Ollama è attivo
                resp = await client.get(f"{host}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                result["available"] = True
                result["models"] = [
                    {
                        "name": m["name"],
                        "size_gb": round(m.get("size", 0) / 1e9, 1),
                        "modified_at": m.get("modified_at", ""),
                        "family": m.get("details", {}).get("family", "unknown"),
                        "parameter_size": m.get("details", {}).get("parameter_size", "unknown"),
                        "quantization": m.get("details", {}).get("quantization_level", "unknown"),
                    }
                    for m in data.get("models", [])
                ]
        else:
            import urllib.request
            req = urllib.request.Request(f"{host}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                result["available"] = True
                result["models"] = [
                    {"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)}
                    for m in data.get("models", [])
                ]
    except Exception as e:
        result["error"] = str(e)

    return result


# === ORCHESTRATOR PRINCIPALE ===

async def orchestrate(
    messages: list[dict],
    mode: str = "local",
    provider: str = "ollama",
    model: str = None,
    auto_routing: bool = True,
    ollama_host: str = "http://localhost:11434",
    ollama_model: str = "qwen2.5-coder:3b",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    cross_check: bool = False,
) -> dict:
    """
    Funzione orchestratore principale.
    Per ora supporta solo Ollama (modalità locale).
    Cloud providers verranno aggiunti quando le API keys sono configurate.
    """
    last_msg = messages[-1]["content"] if messages else ""

    # Routing intelligente — classifica PRIMA di costruire il prompt
    request_type = classify_request(last_msg) if auto_routing else "conversation"
    effective_provider = route_to_provider(request_type, mode) if auto_routing else provider

    # Inietta system prompt SPECIALIZZATO per tipo di richiesta
    has_system = any(m.get("role") == "system" for m in messages)
    if not has_system:
        system_prompt = build_system_prompt(request_type)
        messages = [{"role": "system", "content": system_prompt}] + messages

    # In modalità locale, usa sempre Ollama
    if mode == "local" or effective_provider == "ollama":
        effective_model = ollama_model or "llama3.2:3b"
        print(f"[Orchestra] Tipo: {request_type} | Ollama: {effective_model}")

        try:
            result = await call_ollama(
                messages, effective_model, ollama_host,
                temperature=temperature, max_tokens=max_tokens,
            )
            result["request_type"] = request_type
            return result
        except Exception as e:
            # Prova con modello fallback
            fallback_models = ["llama3.2:3b", "qwen2.5-coder:3b", "gemma2:2b"]
            for fb_model in fallback_models:
                if fb_model != effective_model:
                    try:
                        print(f"[Orchestra] Fallback a {fb_model}")
                        result = await call_ollama(
                            messages, fb_model, ollama_host,
                            temperature=temperature, max_tokens=max_tokens,
                        )
                        result["request_type"] = request_type
                        return result
                    except Exception:
                        continue
            raise Exception(f"Ollama non raggiungibile. Errore: {e}\n"
                            "Verifica che Ollama sia attivo con: ollama serve")

    # Cloud mode — per futuro con API keys
    raise Exception(
        f"Provider cloud '{effective_provider}' non ancora implementato nel backend. "
        "Il frontend gestisce le chiamate cloud direttamente."
    )
