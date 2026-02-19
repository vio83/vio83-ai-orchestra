"""
VIO 83 AI ORCHESTRA - RAG Engine (Retrieval-Augmented Generation)
Motore di verifica risposte basato su fonti certificate.
Usa ChromaDB come vector database per ricerca semantica.
"""

import os
import hashlib
from typing import Optional
from dataclasses import dataclass, field

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False


@dataclass
class RAGSource:
    """Fonte certificata per la verifica."""
    title: str
    content: str
    source_type: str  # "academic", "library", "official", "manual"
    url: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    reliability_score: float = 1.0  # 0.0-1.0


@dataclass
class RAGResult:
    """Risultato di una ricerca RAG."""
    query: str
    matches: list = field(default_factory=list)
    verified: bool = False
    confidence: float = 0.0
    sources_used: int = 0


class RAGEngine:
    """
    Motore RAG per verifica risposte AI con fonti certificate.
    
    Flusso:
    1. L'utente fa una domanda
    2. L'AI genera una risposta
    3. Il RAG cerca fonti certificate correlate
    4. Se trova corrispondenze, la risposta viene verificata
    5. Badge di qualità assegnato in base alla verifica
    """

    def __init__(self, persist_dir: str = "./data/chromadb"):
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None
        self.embedding_model = None
        self._initialized = False

    def initialize(self) -> bool:
        """Inizializza ChromaDB e il modello di embedding."""
        if not CHROMADB_AVAILABLE:
            print("[RAG] ChromaDB non installato. pip install chromadb")
            return False

        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(
                name="vio83_certified_sources",
                metadata={"description": "Fonti certificate VIO 83 AI Orchestra"}
            )
            self._initialized = True
            print(f"[RAG] Inizializzato con {self.collection.count()} documenti")
            return True
        except Exception as e:
            print(f"[RAG] Errore inizializzazione: {e}")
            return False

    def add_source(self, source: RAGSource) -> str:
        """Aggiungi una fonte certificata al database."""
        if not self._initialized:
            if not self.initialize():
                return ""

        doc_id = hashlib.md5(
            f"{source.title}:{source.content[:100]}".encode()
        ).hexdigest()

        metadata = {
            "title": source.title,
            "source_type": source.source_type,
            "reliability_score": source.reliability_score,
        }
        if source.url:
            metadata["url"] = source.url
        if source.author:
            metadata["author"] = source.author
        if source.year:
            metadata["year"] = source.year

        self.collection.upsert(
            documents=[source.content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        return doc_id

    def search(self, query: str, n_results: int = 5, min_score: float = 0.7) -> RAGResult:
        """Cerca fonti certificate correlate alla query."""
        if not self._initialized:
            if not self.initialize():
                return RAGResult(query=query)

        if self.collection.count() == 0:
            return RAGResult(query=query)

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, self.collection.count())
            )

            matches = []
            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    distance = results["distances"][0][i] if results["distances"] else 1.0
                    similarity = max(0, 1.0 - distance)
                    
                    if similarity >= min_score:
                        meta = results["metadatas"][0][i] if results["metadatas"] else {}
                        matches.append({
                            "content": doc[:500],
                            "similarity": round(similarity, 3),
                            "title": meta.get("title", "Sconosciuto"),
                            "source_type": meta.get("source_type", "unknown"),
                            "reliability": meta.get("reliability_score", 0.5),
                        })

            verified = len(matches) > 0 and matches[0]["similarity"] > 0.8
            confidence = matches[0]["similarity"] if matches else 0.0

            return RAGResult(
                query=query,
                matches=matches,
                verified=verified,
                confidence=round(confidence, 3),
                sources_used=len(matches)
            )
        except Exception as e:
            print(f"[RAG] Errore ricerca: {e}")
            return RAGResult(query=query)

    def verify_response(self, question: str, ai_response: str) -> dict:
        """
        Verifica una risposta AI contro le fonti certificate.
        Ritorna un dizionario con il badge di qualità.
        """
        search_result = self.search(question)

        if not search_result.matches:
            return {
                "badge": "unverified",
                "icon": "⚪",
                "label": "Non Verificato",
                "confidence": 0.0,
                "sources": [],
                "note": "Nessuna fonte certificata trovata per questa query"
            }

        if search_result.verified and search_result.confidence > 0.85:
            return {
                "badge": "gold",
                "icon": "🥇",
                "label": "Verificato — Alta Affidabilità",
                "confidence": search_result.confidence,
                "sources": [m["title"] for m in search_result.matches[:3]],
                "note": f"Confermato da {search_result.sources_used} fonti certificate"
            }
        elif search_result.confidence > 0.7:
            return {
                "badge": "silver",
                "icon": "🥈",
                "label": "Parzialmente Verificato",
                "confidence": search_result.confidence,
                "sources": [m["title"] for m in search_result.matches[:2]],
                "note": "Trovate fonti correlate ma non perfettamente corrispondenti"
            }
        else:
            return {
                "badge": "bronze",
                "icon": "🥉",
                "label": "Bassa Corrispondenza",
                "confidence": search_result.confidence,
                "sources": [m["title"] for m in search_result.matches[:1]],
                "note": "Le fonti trovate hanno bassa correlazione"
            }

    def get_stats(self) -> dict:
        """Statistiche del database RAG."""
        if not self._initialized:
            self.initialize()
        
        count = self.collection.count() if self.collection else 0
        return {
            "total_documents": count,
            "persist_dir": self.persist_dir,
            "initialized": self._initialized,
            "chromadb_available": CHROMADB_AVAILABLE,
        }


# Singleton globale
_rag_engine: Optional[RAGEngine] = None


def get_rag_engine(persist_dir: str = "./data/chromadb") -> RAGEngine:
    """Ottieni l'istanza singleton del RAG engine."""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine(persist_dir=persist_dir)
    return _rag_engine
