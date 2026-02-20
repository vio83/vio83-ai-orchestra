"""
VIO 83 AI ORCHESTRA — Knowledge Base Engine
Sistema avanzato di knowledge base che:
- Gestisce embedding vettoriali con ChromaDB o SQLite-FTS fallback
- Supporta modelli di embedding locali (sentence-transformers) o Ollama embedding
- Retrieval semantico con reranking per massima precisione
- Classificazione per dominio disciplinare (scienze, medicina, diritto, etc.)
- Verifica incrociata delle fonti con punteggio di affidabilità
- Distinzione terminologica per campo di studio

ARCHITETTURA:
┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Document Ingest │────▸│  Preprocessing   │────▸│  Embedding +     │
│  (multi-format)  │     │  Pipeline        │     │  Indexing         │
└──────────────────┘     └─────────────────┘     └──────────────────┘
                                                          │
┌──────────────────┐     ┌─────────────────┐              │
│  RAG Response    │◂────│  Reranker +      │◂────────────┘
│  + Verification  │     │  Retrieval       │
└──────────────────┘     └─────────────────┘
"""

import os
import re
import json
import time
import sqlite3
import hashlib
from typing import Optional
from dataclasses import dataclass, field, asdict

from backend.rag.preprocessing import ProcessedChunk, PreprocessingPipeline
from backend.rag.ingestion import IngestionEngine, IngestedDocument

# ChromaDB (opzionale — fallback a SQLite FTS)
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# Sentence-transformers per embedding locali (opzionale)
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# httpx per embedding via Ollama API
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# ============================================================
# DOMAIN CLASSIFIER — Classificazione per disciplina
# ============================================================

DOMAIN_KEYWORDS = {
    "matematica": ["algebra", "calcolo", "teorema", "dimostrazione", "integrale", "derivata",
                   "equazione", "matrice", "vettore", "topologia", "gruppo", "anello", "campo",
                   "funzione", "limite", "convergenza", "serie", "probabilità", "statistica"],
    "fisica": ["forza", "energia", "quantistica", "relatività", "onda", "particella", "campo",
               "termodinamica", "entropia", "momento", "impulso", "spin", "bosone", "fermione",
               "gravitazione", "elettromagnetismo", "meccanica", "ottica", "acustica"],
    "chimica": ["molecola", "atomo", "reazione", "legame", "orbitale", "catalisi", "pH",
                "ossidazione", "riduzione", "polimero", "enzima", "solvente", "cristallo",
                "spettroscopia", "cromatografia", "stechiometria"],
    "biologia": ["cellula", "DNA", "RNA", "proteina", "gene", "mutazione", "evoluzione",
                 "specie", "ecosistema", "fotosintesi", "mitosi", "meiosi", "genoma",
                 "metabolismo", "enzima", "organismo", "tessuto", "organo"],
    "medicina": ["diagnosi", "terapia", "farmaco", "sintomo", "patologia", "chirurgia",
                 "anamnesi", "prognosi", "eziologia", "epidemiologia", "dosaggio",
                 "controindicazione", "effetto collaterale", "screening", "biopsia"],
    "informatica": ["algoritmo", "complessità", "database", "rete", "protocollo", "compilatore",
                    "thread", "stack", "heap", "hash", "cache", "API", "framework", "container",
                    "crittografia", "machine learning", "neurale", "deep learning"],
    "diritto": ["articolo", "comma", "decreto", "legge", "codice", "giurisprudenza", "sentenza",
                "tribunale", "reato", "sanzione", "contratto", "responsabilità", "procedura",
                "costituzione", "diritto", "norma", "regolamento"],
    "economia": ["PIL", "inflazione", "mercato", "domanda", "offerta", "capitale", "interesse",
                 "investimento", "bilancio", "fiscale", "monetaria", "microeconomia",
                 "macroeconomia", "econometria", "finanza", "rendimento"],
    "storia": ["secolo", "epoca", "dinastia", "impero", "guerra", "rivoluzione", "trattato",
               "monarchia", "repubblica", "colonia", "feudalesimo", "rinascimento",
               "illuminismo", "industrializzazione", "civilizzazione"],
    "filosofia": ["ontologia", "epistemologia", "etica", "metafisica", "fenomenologia",
                  "dialettica", "ermeneutica", "esistenzialismo", "pragmatismo", "logica",
                  "sillogismo", "a priori", "a posteriori", "trascendentale"],
    "linguistica": ["fonema", "morfema", "sintassi", "semantica", "pragmatica", "lessema",
                    "fonetica", "fonologia", "morfologia", "coniugazione", "declinazione",
                    "etimologia", "sociolinguistica", "psicolinguistica"],
    "astronomia": ["stella", "pianeta", "galassia", "nebulosa", "supernova", "buco nero",
                   "pulsar", "quasar", "redshift", "magnitudine", "parsec", "anno luce",
                   "cosmologia", "esopianeta", "asteroide", "cometa"],
    "psicologia": ["cognizione", "comportamento", "percezione", "memoria", "apprendimento",
                   "motivazione", "emozione", "personalità", "disturbo", "terapia",
                   "inconscio", "condizionamento", "rinforzo", "attaccamento"],
}


def classify_domain(text: str) -> list[tuple[str, float]]:
    """
    Classifica il testo nei domini disciplinari.
    Ritorna lista di (dominio, score) ordinata per rilevanza.
    """
    text_lower = text.lower()
    words = set(text_lower.split())
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > 0:
            scores[domain] = count / len(keywords)
    sorted_domains = sorted(scores.items(), key=lambda x: -x[1])
    return sorted_domains[:5]  # Top 5 domini


# ============================================================
# EMBEDDING ENGINE — Generazione vettori
# ============================================================

class EmbeddingEngine:
    """
    Genera embedding vettoriali per testo.
    Supporta:
    1. sentence-transformers (locale, offline) — preferito
    2. Ollama embedding API (locale, richiede Ollama attivo)
    3. Fallback: nessun embedding (solo FTS)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", ollama_host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.ollama_host = ollama_host
        self._st_model = None
        self._mode = "none"
        self._initialize()

    def _initialize(self):
        """Inizializza il miglior backend disponibile."""
        # 1. Prova sentence-transformers
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self._st_model = SentenceTransformer(self.model_name)
                self._mode = "sentence_transformers"
                print(f"[Embedding] Inizializzato sentence-transformers: {self.model_name}")
                return
            except Exception as e:
                print(f"[Embedding] sentence-transformers fallito: {e}")

        # 2. Prova Ollama embedding
        if HTTPX_AVAILABLE:
            try:
                resp = httpx.post(
                    f"{self.ollama_host}/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": "test"},
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    self._mode = "ollama"
                    print("[Embedding] Inizializzato Ollama embedding: nomic-embed-text")
                    return
            except Exception:
                pass

        self._mode = "none"
        print("[Embedding] Nessun backend embedding disponibile. Solo FTS attivo.")

    def embed(self, texts: list[str]) -> Optional[list[list[float]]]:
        """Genera embedding per una lista di testi."""
        if self._mode == "sentence_transformers" and self._st_model:
            embeddings = self._st_model.encode(texts, show_progress_bar=False)
            return embeddings.tolist()

        elif self._mode == "ollama":
            embeddings = []
            for text in texts:
                try:
                    resp = httpx.post(
                        f"{self.ollama_host}/api/embeddings",
                        json={"model": "nomic-embed-text", "prompt": text[:8000]},
                        timeout=30.0,
                    )
                    if resp.status_code == 200:
                        embeddings.append(resp.json().get("embedding", []))
                    else:
                        return None
                except Exception:
                    return None
            return embeddings if len(embeddings) == len(texts) else None

        return None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def dimension(self) -> int:
        if self._mode == "sentence_transformers" and self._st_model:
            return self._st_model.get_sentence_embedding_dimension()
        elif self._mode == "ollama":
            return 768  # nomic-embed-text default
        return 0


# ============================================================
# SQLITE FTS5 FALLBACK — Full-Text Search quando ChromaDB non c'è
# ============================================================

class SQLiteFTSIndex:
    """
    Indice Full-Text Search con SQLite FTS5.
    Fallback quando ChromaDB non è disponibile.
    Supporta ricerca testuale con ranking BM25.
    """

    def __init__(self, db_path: str = "./data/vio83_knowledge.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_tables()

    def _init_tables(self):
        """Crea tabelle FTS5."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                chunk_id, content, title, author, domain, source_type,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_meta (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT,
                filename TEXT,
                language TEXT,
                year INTEGER,
                reliability REAL DEFAULT 1.0,
                word_count INTEGER,
                chunk_index INTEGER,
                total_chunks INTEGER,
                section_title TEXT,
                metadata_json TEXT,
                created_at REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meta_doc ON knowledge_meta(doc_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meta_domain ON knowledge_meta(chunk_id)")
        conn.commit()
        conn.close()

    def add(self, chunk: ProcessedChunk, domain: str = "", source_type: str = "book",
            title: str = "", author: str = "", reliability: float = 1.0):
        """Aggiungi un chunk all'indice FTS."""
        conn = sqlite3.connect(self.db_path)
        try:
            # FTS5
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_fts(chunk_id, content, title, author, domain, source_type) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (chunk.chunk_id, chunk.content, title, author, domain, source_type)
            )
            # Metadati
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_meta "
                "(chunk_id, doc_id, filename, language, year, reliability, word_count, "
                "chunk_index, total_chunks, section_title, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (chunk.chunk_id, chunk.source_doc_id,
                 chunk.metadata.get("filename", ""), chunk.language,
                 chunk.metadata.get("year"), reliability, chunk.word_count,
                 chunk.chunk_index, chunk.total_chunks, chunk.section_title,
                 json.dumps(chunk.metadata, ensure_ascii=False), time.time())
            )
            conn.commit()
        finally:
            conn.close()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Cerca con FTS5 + BM25 ranking."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Sanitizza query per FTS5
            safe_query = re.sub(r'[^\w\s]', ' ', query)
            safe_query = " OR ".join(w for w in safe_query.split() if len(w) > 2)
            if not safe_query:
                return []

            rows = conn.execute(
                "SELECT chunk_id, content, title, author, domain, source_type, "
                "bm25(knowledge_fts) as score "
                "FROM knowledge_fts WHERE knowledge_fts MATCH ? "
                "ORDER BY bm25(knowledge_fts) LIMIT ?",
                (safe_query, limit)
            ).fetchall()

            results = []
            for row in rows:
                meta_row = conn.execute(
                    "SELECT * FROM knowledge_meta WHERE chunk_id = ?",
                    (row["chunk_id"],)
                ).fetchone()

                results.append({
                    "chunk_id": row["chunk_id"],
                    "content": row["content"],
                    "title": row["title"],
                    "author": row["author"],
                    "domain": row["domain"],
                    "source_type": row["source_type"],
                    "score": abs(row["score"]),  # BM25 ritorna valori negativi
                    "reliability": meta_row["reliability"] if meta_row else 1.0,
                    "language": meta_row["language"] if meta_row else "unknown",
                    "year": meta_row["year"] if meta_row else None,
                })
            return results
        except Exception as e:
            print(f"[FTS] Errore ricerca: {e}")
            return []
        finally:
            conn.close()

    def count(self) -> int:
        """Conta i documenti nell'indice."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM knowledge_meta").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()


# ============================================================
# KNOWLEDGE BASE — Engine principale
# ============================================================

class KnowledgeBase:
    """
    Knowledge Base Engine completo.
    Unifica:
    - ChromaDB (embedding vettoriali) o SQLite FTS5 (fallback)
    - Embedding Engine (sentence-transformers / Ollama / none)
    - Ingestion Engine (multi-formato)
    - Preprocessing Pipeline
    - Domain Classification
    - Reranking per precisione
    - Verifica fonti con punteggio affidabilità
    """

    def __init__(
        self,
        data_dir: str = "./data",
        max_tokens_per_chunk: int = 512,
        overlap_tokens: int = 64,
        embedding_model: str = "all-MiniLM-L6-v2",
        ollama_host: str = "http://localhost:11434",
    ):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # Componenti
        self.ingestion = IngestionEngine(
            max_tokens_per_chunk=max_tokens_per_chunk,
            overlap_tokens=overlap_tokens,
        )
        self.embedder = EmbeddingEngine(
            model_name=embedding_model,
            ollama_host=ollama_host,
        )

        # Indici
        self._chromadb_client = None
        self._chromadb_collection = None
        self._fts_index = None
        self._use_chromadb = False

        self._init_indices()

    def _init_indices(self):
        """Inizializza gli indici di ricerca."""
        # Prova ChromaDB
        if CHROMADB_AVAILABLE:
            try:
                persist_path = os.path.join(self.data_dir, "chromadb")
                os.makedirs(persist_path, exist_ok=True)
                self._chromadb_client = chromadb.PersistentClient(path=persist_path)
                self._chromadb_collection = self._chromadb_client.get_or_create_collection(
                    name="vio83_knowledge_base",
                    metadata={
                        "description": "VIO 83 AI Orchestra — Knowledge Base completa",
                        "hnsw:space": "cosine",
                    }
                )
                self._use_chromadb = True
                print(f"[KB] ChromaDB inizializzato: {self._chromadb_collection.count()} chunk indicizzati")
            except Exception as e:
                print(f"[KB] ChromaDB fallito: {e}. Uso SQLite FTS5.")

        # SQLite FTS5 (sempre attivo come fallback o complemento)
        fts_path = os.path.join(self.data_dir, "vio83_knowledge.db")
        self._fts_index = SQLiteFTSIndex(db_path=fts_path)
        fts_count = self._fts_index.count()
        print(f"[KB] SQLite FTS5 inizializzato: {fts_count} chunk indicizzati")

    # ========================================================
    # INGEST — Aggiungi documenti alla knowledge base
    # ========================================================

    def ingest_file(
        self,
        filepath: str,
        source_type: str = "book",
        reliability: float = 1.0,
        extra_metadata: Optional[dict] = None,
    ) -> IngestedDocument:
        """Ingesci un singolo file nella knowledge base."""
        meta = extra_metadata or {}
        meta["source_type"] = source_type
        meta["reliability"] = reliability

        doc = self.ingestion.ingest_file(filepath, extra_metadata=meta)

        if doc.status == "success" and doc.chunks:
            self._index_chunks(
                doc.chunks,
                title=doc.title,
                author=doc.author,
                source_type=source_type,
                reliability=reliability,
            )
            print(f"[KB] Indicizzato: {doc.filename} → {doc.chunk_count} chunk")

        return doc

    def ingest_directory(
        self,
        directory: str,
        recursive: bool = True,
        source_type: str = "book",
        reliability: float = 1.0,
    ) -> list[IngestedDocument]:
        """Ingesci tutti i file da una directory."""
        docs = self.ingestion.ingest_directory(directory, recursive=recursive)

        for doc in docs:
            if doc.status == "success" and doc.chunks:
                self._index_chunks(
                    doc.chunks,
                    title=doc.title,
                    author=doc.author,
                    source_type=source_type,
                    reliability=reliability,
                )

        return docs

    def ingest_text(
        self,
        text: str,
        title: str = "",
        author: str = "",
        source_type: str = "manual",
        reliability: float = 1.0,
        metadata: Optional[dict] = None,
    ) -> int:
        """Ingesci testo grezzo direttamente (senza file)."""
        pipeline = self.ingestion.pipeline
        doc_id = hashlib.md5(text[:200].encode()).hexdigest()[:12]

        chunks = pipeline.process(
            text=text,
            doc_id=doc_id,
            extra_metadata=metadata,
        )

        if chunks:
            self._index_chunks(
                chunks,
                title=title,
                author=author,
                source_type=source_type,
                reliability=reliability,
            )

        return len(chunks)

    def _index_chunks(
        self,
        chunks: list[ProcessedChunk],
        title: str = "",
        author: str = "",
        source_type: str = "book",
        reliability: float = 1.0,
    ):
        """Indicizza i chunk nel vector DB e/o FTS."""
        # Classifica dominio per il primo chunk (rappresentativo)
        if chunks:
            domains = classify_domain(chunks[0].content)
            primary_domain = domains[0][0] if domains else "generale"
        else:
            primary_domain = "generale"

        # === ChromaDB ===
        if self._use_chromadb and self._chromadb_collection:
            ids = [c.chunk_id for c in chunks]
            documents = [c.content for c in chunks]
            metadatas = [
                {
                    "title": title or c.metadata.get("title", ""),
                    "author": author or c.metadata.get("author", ""),
                    "domain": primary_domain,
                    "source_type": source_type,
                    "reliability": reliability,
                    "language": c.language,
                    "doc_id": c.source_doc_id,
                    "chunk_index": c.chunk_index,
                    "section_title": c.section_title,
                }
                for c in chunks
            ]

            # Genera embedding se disponibili
            embeddings = self.embedder.embed(documents)

            try:
                if embeddings:
                    self._chromadb_collection.upsert(
                        ids=ids, documents=documents,
                        metadatas=metadatas, embeddings=embeddings,
                    )
                else:
                    self._chromadb_collection.upsert(
                        ids=ids, documents=documents, metadatas=metadatas,
                    )
            except Exception as e:
                print(f"[KB] Errore ChromaDB upsert: {e}")

        # === SQLite FTS5 (sempre) ===
        if self._fts_index:
            for chunk in chunks:
                self._fts_index.add(
                    chunk, domain=primary_domain,
                    source_type=source_type,
                    title=title, author=author,
                    reliability=reliability,
                )

    # ========================================================
    # QUERY — Ricerca semantica + reranking
    # ========================================================

    def query(
        self,
        question: str,
        n_results: int = 10,
        min_reliability: float = 0.5,
        domain_filter: Optional[str] = None,
        rerank: bool = True,
    ) -> list[dict]:
        """
        Ricerca nella knowledge base con retrieval semantico e reranking.

        Strategia:
        1. Se ChromaDB disponibile: ricerca vettoriale (embedding similarity)
        2. Sempre: ricerca FTS5 (BM25 keyword match)
        3. Merge e dedup dei risultati
        4. Reranking basato su: similarity + reliability + domain match + freshness
        """
        results = []

        # 1. ChromaDB — Ricerca semantica
        if self._use_chromadb and self._chromadb_collection and self._chromadb_collection.count() > 0:
            try:
                query_embedding = self.embedder.embed([question])
                chromadb_params = {
                    "query_texts": [question],
                    "n_results": min(n_results * 2, self._chromadb_collection.count()),
                }
                if query_embedding:
                    chromadb_params["query_embeddings"] = query_embedding

                chroma_results = self._chromadb_collection.query(**chromadb_params)

                if chroma_results and chroma_results["documents"] and chroma_results["documents"][0]:
                    for i, doc in enumerate(chroma_results["documents"][0]):
                        distance = chroma_results["distances"][0][i] if chroma_results["distances"] else 1.0
                        similarity = max(0, 1.0 - distance)
                        meta = chroma_results["metadatas"][0][i] if chroma_results["metadatas"] else {}
                        chunk_id = chroma_results["ids"][0][i] if chroma_results["ids"] else ""

                        results.append({
                            "chunk_id": chunk_id,
                            "content": doc[:2000],
                            "similarity": round(similarity, 4),
                            "source": "vector",
                            "title": meta.get("title", ""),
                            "author": meta.get("author", ""),
                            "domain": meta.get("domain", ""),
                            "source_type": meta.get("source_type", ""),
                            "reliability": meta.get("reliability", 1.0),
                            "language": meta.get("language", ""),
                        })
            except Exception as e:
                print(f"[KB] Errore ChromaDB query: {e}")

        # 2. SQLite FTS5 — Ricerca keyword
        if self._fts_index:
            fts_results = self._fts_index.search(question, limit=n_results * 2)
            for fr in fts_results:
                # Evita duplicati (stessi chunk già da ChromaDB)
                if not any(r["chunk_id"] == fr["chunk_id"] for r in results):
                    results.append({
                        "chunk_id": fr["chunk_id"],
                        "content": fr["content"][:2000],
                        "similarity": min(1.0, fr["score"] / 20.0),  # Normalizza BM25
                        "source": "fts",
                        "title": fr.get("title", ""),
                        "author": fr.get("author", ""),
                        "domain": fr.get("domain", ""),
                        "source_type": fr.get("source_type", ""),
                        "reliability": fr.get("reliability", 1.0),
                        "language": fr.get("language", ""),
                    })

        # 3. Filtro affidabilità minima
        results = [r for r in results if r.get("reliability", 0) >= min_reliability]

        # 4. Filtro dominio (opzionale)
        if domain_filter:
            domain_results = [r for r in results if r.get("domain") == domain_filter]
            if domain_results:
                results = domain_results

        # 5. Reranking
        if rerank:
            results = self._rerank(question, results)

        return results[:n_results]

    def _rerank(self, query: str, results: list[dict]) -> list[dict]:
        """
        Reranking multi-fattore:
        - 50% similarity score (semantico o BM25)
        - 25% reliability score (affidabilità fonte)
        - 15% domain match (dominio della query vs dominio del chunk)
        - 10% source preference (vector > fts)
        """
        query_domains = classify_domain(query)
        query_primary = query_domains[0][0] if query_domains else ""

        for r in results:
            sim_score = r.get("similarity", 0)
            rel_score = r.get("reliability", 1.0)
            domain_match = 1.0 if r.get("domain") == query_primary else 0.3
            source_bonus = 1.0 if r.get("source") == "vector" else 0.7

            r["final_score"] = (
                0.50 * sim_score +
                0.25 * rel_score +
                0.15 * domain_match +
                0.10 * source_bonus
            )

        results.sort(key=lambda x: -x.get("final_score", 0))
        return results

    # ========================================================
    # RAG CONTEXT — Prepara contesto per il modello AI
    # ========================================================

    def build_rag_context(
        self,
        question: str,
        max_context_tokens: int = 2000,
        n_results: int = 5,
    ) -> dict:
        """
        Costruisce il contesto RAG da iniettare nel system prompt.
        Ritorna: {context_text, sources, domain, confidence}
        """
        results = self.query(question, n_results=n_results)

        if not results:
            return {
                "context_text": "",
                "sources": [],
                "domain": "generale",
                "confidence": 0.0,
                "has_context": False,
            }

        # Costruisci testo contesto
        context_parts = []
        sources = []
        total_tokens = 0

        for r in results:
            content = r["content"]
            tokens_est = len(content) // 4
            if total_tokens + tokens_est > max_context_tokens:
                break

            source_label = f"{r.get('title', 'Fonte')} ({r.get('author', 'N/A')})"
            context_parts.append(f"[Fonte: {source_label}]\n{content}")
            sources.append({
                "title": r.get("title", ""),
                "author": r.get("author", ""),
                "domain": r.get("domain", ""),
                "reliability": r.get("reliability", 1.0),
                "similarity": r.get("similarity", 0),
            })
            total_tokens += tokens_est

        context_text = "\n\n---\n\n".join(context_parts)
        avg_confidence = sum(r.get("final_score", r.get("similarity", 0)) for r in results[:len(sources)]) / max(len(sources), 1)
        primary_domain = results[0].get("domain", "generale") if results else "generale"

        return {
            "context_text": context_text,
            "sources": sources,
            "domain": primary_domain,
            "confidence": round(avg_confidence, 3),
            "has_context": True,
        }

    # ========================================================
    # STATS
    # ========================================================

    def get_stats(self) -> dict:
        """Statistiche della knowledge base."""
        chroma_count = 0
        if self._use_chromadb and self._chromadb_collection:
            try:
                chroma_count = self._chromadb_collection.count()
            except Exception:
                pass

        fts_count = self._fts_index.count() if self._fts_index else 0

        return {
            "chromadb_available": self._use_chromadb,
            "chromadb_chunks": chroma_count,
            "fts_chunks": fts_count,
            "embedding_mode": self.embedder.mode,
            "embedding_dimension": self.embedder.dimension,
            "ingestion_stats": self.ingestion.get_stats(),
            "data_dir": self.data_dir,
        }


# ============================================================
# SINGLETON
# ============================================================

_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base(data_dir: str = "./data") -> KnowledgeBase:
    """Ottieni l'istanza singleton della Knowledge Base."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase(data_dir=data_dir)
    return _knowledge_base
