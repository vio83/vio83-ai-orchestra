"""
VIO 83 AI ORCHESTRA - FastAPI Server
Server principale che espone le API per il frontend React/Tauri.
Integra: LiteLLM orchestrator, RAG engine, provider management.
"""

import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.models.schemas import (
    ChatRequest, ChatResponse, ClassifyRequest, ClassifyResponse,
    HealthResponse, RAGAddRequest, RAGSearchRequest, ErrorResponse
)
from backend.orchestrator.router import classify_request, call_ai
from backend.rag.engine import get_rag_engine, RAGSource
from backend.config.providers import (
    CLOUD_PROVIDERS, LOCAL_PROVIDERS, get_available_cloud_providers
)

load_dotenv()

START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inizializzazione e shutdown del server."""
    # Startup
    print("🎵 VIO 83 AI ORCHESTRA — Server avviato")
    rag = get_rag_engine()
    rag.initialize()
    print(f"📚 RAG Engine: {rag.get_stats()['total_documents']} documenti")
    available = get_available_cloud_providers()
    print(f"☁️  Provider cloud disponibili: {list(available.keys()) if available else 'nessuno (configura .env)'}")
    yield
    # Shutdown
    print("🎵 VIO 83 AI ORCHESTRA — Server arrestato")


app = FastAPI(
    title="VIO 83 AI ORCHESTRA",
    description="Multi-provider AI orchestration platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:1420", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === HEALTH ===

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Stato di salute del sistema."""
    available = get_available_cloud_providers()
    rag = get_rag_engine()
    
    providers = {}
    for key in CLOUD_PROVIDERS:
        providers[key] = {
            "available": key in available,
            "mode": "cloud",
            "name": CLOUD_PROVIDERS[key]["name"],
        }
    providers["ollama"] = {
        "available": True,
        "mode": "local",
        "name": "Ollama (Locale)",
    }
    
    return HealthResponse(
        status="ok",
        version="0.1.0",
        providers=providers,
        rag_stats=rag.get_stats(),
        uptime_seconds=round(time.time() - START_TIME, 1),
    )


# === CHAT ===

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Endpoint principale chat — instrada la richiesta al provider migliore."""
    try:
        # Classifica la richiesta
        req_type = classify_request(request.message)
        
        # Chiama l'orchestratore
        result = await call_ai(
            message=request.message,
            mode=request.mode,
            provider=request.provider,
            model=request.model,
            request_type=req_type,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_prompt=request.system_prompt,
            enable_cross_check=request.enable_cross_check,
        )
        
        # Verifica RAG (se abilitato)
        rag_verification = None
        if request.enable_rag:
            rag = get_rag_engine()
            rag_verification = rag.verify_response(request.message, result.get("content", ""))
        
        return ChatResponse(
            content=result.get("content", ""),
            provider=result.get("provider", "unknown"),
            model=result.get("model", "unknown"),
            tokens_used=result.get("tokens_used", 0),
            latency_ms=result.get("latency_ms", 0),
            request_type=req_type,
            cross_check=result.get("cross_check"),
            rag_verification=rag_verification,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === CLASSIFY ===

@app.post("/classify", response_model=ClassifyResponse)
async def classify(request: ClassifyRequest):
    """Classifica il tipo di richiesta per il routing intelligente."""
    req_type = classify_request(request.message)
    
    from backend.config.providers import REQUEST_TYPE_ROUTING
    routing = REQUEST_TYPE_ROUTING.get(req_type, {})
    
    return ClassifyResponse(
        request_type=req_type,
        suggested_provider=routing.get("cloud_primary", "claude"),
        confidence=0.85,
    )


# === PROVIDERS ===

@app.get("/providers")
async def list_providers():
    """Lista tutti i provider disponibili."""
    available = get_available_cloud_providers()
    return {
        "cloud": {
            key: {
                "name": CLOUD_PROVIDERS[key]["name"],
                "available": key in available,
                "default_model": CLOUD_PROVIDERS[key]["default_model"],
                "models": list(CLOUD_PROVIDERS[key]["models"].keys()),
            }
            for key in CLOUD_PROVIDERS
        },
        "local": {
            "ollama": {
                "name": "Ollama (Locale)",
                "available": True,
                "default_model": LOCAL_PROVIDERS["ollama"]["default_model"],
                "models": list(LOCAL_PROVIDERS["ollama"]["models"].keys()),
            }
        },
    }


# === RAG ===

@app.post("/rag/add")
async def rag_add_source(request: RAGAddRequest):
    """Aggiungi una fonte certificata al database RAG."""
    rag = get_rag_engine()
    source = RAGSource(
        title=request.title,
        content=request.content,
        source_type=request.source_type,
        url=request.url,
        author=request.author,
        year=request.year,
        reliability_score=request.reliability_score,
    )
    doc_id = rag.add_source(source)
    return {"doc_id": doc_id, "status": "added"}


@app.post("/rag/search")
async def rag_search(request: RAGSearchRequest):
    """Cerca nelle fonti certificate."""
    rag = get_rag_engine()
    result = rag.search(request.query, n_results=request.n_results, min_score=request.min_score)
    return {
        "query": result.query,
        "matches": result.matches,
        "verified": result.verified,
        "confidence": result.confidence,
        "sources_used": result.sources_used,
    }


@app.get("/rag/stats")
async def rag_stats():
    """Statistiche database RAG."""
    rag = get_rag_engine()
    return rag.get_stats()


# === RUN ===

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("LITELLM_PROXY_PORT", 4000))
    print(f"🎵 Avvio VIO 83 AI ORCHESTRA su porta {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
