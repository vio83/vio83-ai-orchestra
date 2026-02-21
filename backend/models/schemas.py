# ============================================================
# VIO 83 AI ORCHESTRA — Copyright (c) 2026 Viorica Porcu (vio83)
# DUAL LICENSE: Proprietary + AGPL-3.0 — See LICENSE files
# ALL RIGHTS RESERVED — https://github.com/vio83/vio83-ai-orchestra
# ============================================================
"""
VIO 83 AI ORCHESTRA - Pydantic Schemas
Definizione modelli dati per API e validazione.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# === Request Models ===

class ChatRequest(BaseModel):
    """Richiesta chat dall'utente."""
    message: str = Field(..., min_length=1, max_length=50000)
    conversation_id: Optional[str] = None
    mode: Literal["cloud", "local"] = "local"
    provider: Optional[str] = None
    model: Optional[str] = None
    enable_cross_check: bool = False
    enable_rag: bool = True
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=128000)
    system_prompt: Optional[str] = None


class ClassifyRequest(BaseModel):
    """Richiesta classificazione tipo di query."""
    message: str = Field(..., min_length=1)


class RAGAddRequest(BaseModel):
    """Richiesta aggiunta fonte certificata."""
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=10)
    source_type: Literal["academic", "library", "official", "manual"] = "official"
    url: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    reliability_score: float = Field(1.0, ge=0.0, le=1.0)


class RAGSearchRequest(BaseModel):
    """Richiesta ricerca RAG."""
    query: str = Field(..., min_length=1)
    n_results: int = Field(5, ge=1, le=20)
    min_score: float = Field(0.7, ge=0.0, le=1.0)


class APIKeyUpdate(BaseModel):
    """Aggiornamento chiave API."""
    provider: str
    api_key: str = Field(..., min_length=5)


class ProviderConfig(BaseModel):
    """Configurazione provider AI."""
    provider: str
    enabled: bool = True
    model: Optional[str] = None
    priority: int = Field(1, ge=1, le=10)
    max_tokens: int = 4096
    temperature: float = 0.7


# === Response Models ===

class ChatResponse(BaseModel):
    """Risposta chat dalla AI."""
    content: str
    provider: str
    model: str
    tokens_used: int = 0
    latency_ms: int = 0
    request_type: Optional[str] = None
    cross_check: Optional[dict] = None
    rag_verification: Optional[dict] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ClassifyResponse(BaseModel):
    """Risposta classificazione."""
    request_type: str
    suggested_provider: str
    confidence: float


class HealthResponse(BaseModel):
    """Stato di salute del sistema."""
    status: str = "ok"
    version: str = "0.1.0"
    providers: dict = {}
    rag_stats: dict = {}
    uptime_seconds: float = 0.0


class ProviderStatus(BaseModel):
    """Stato di un provider AI."""
    name: str
    available: bool
    model: str
    mode: Literal["cloud", "local"]
    latency_ms: Optional[int] = None


class ErrorResponse(BaseModel):
    """Risposta errore."""
    error: str
    detail: Optional[str] = None
    code: int = 500
