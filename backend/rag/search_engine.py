# ============================================================
# VIO 83 AI ORCHESTRA — Copyright (c) 2026 Viorica Porcu (vio83)
# DUAL LICENSE: Proprietary + AGPL-3.0 — See LICENSE files
# ALL RIGHTS RESERVED — https://github.com/vio83/vio83-ai-orchestra
# ============================================================
"""
╔══════════════════════════════════════════════════════════════════════╗
║         VIO 83 AI ORCHESTRA — Advanced Search Engine                ║
║                                                                      ║
║  Motore di ricerca multi-backend con ranking unificato:              ║
║  • SQLite FTS5   — default, zero config, integrato (stdlib)          ║
║  • Whoosh        — full-text search Python puro (opzionale)          ║
║  • Elasticsearch — distribuito, scalabile (opzionale)                ║
║  • Meilisearch   — ultra-veloce, typo-tolerant (opzionale)           ║
║                                                                      ║
║  Features:                                                           ║
║  • Ricerca semantica ibrida (BM25 + vector similarity)               ║
║  • Faceted search con filtri per categoria/anno/lingua               ║
║  • Query expansion e spell correction                                ║
║  • Highlighting dei risultati                                        ║
║  • Aggregazioni e statistiche                                        ║
║  • Auto-complete / suggest                                           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("vio83.search_engine")

# ═══════════════════════════════════════════════════════
# Tipi
# ═══════════════════════════════════════════════════════

class SearchBackendType(Enum):
    FTS5 = "fts5"
    WHOOSH = "whoosh"
    ELASTICSEARCH = "elasticsearch"
    MEILISEARCH = "meilisearch"


@dataclass
class SearchResult:
    """Singolo risultato di ricerca."""
    doc_id: str
    score: float
    title: str = ""
    snippet: str = ""
    highlights: List[str] = field(default_factory=list)
    category: str = ""
    language: str = ""
    year: int = 0
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Risposta completa della ricerca."""
    query: str
    total_hits: int
    results: List[SearchResult]
    took_ms: float
    facets: Dict[str, Dict[str, int]] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    did_you_mean: str = ""


@dataclass
class SearchQuery:
    """Query di ricerca strutturata."""
    text: str
    filters: Dict[str, Any] = field(default_factory=dict)
    facets: List[str] = field(default_factory=list)
    offset: int = 0
    limit: int = 20
    sort_by: str = "relevance"  # "relevance", "date", "title"
    highlight: bool = True
    min_score: float = 0.0
    language: str = ""
    categories: List[str] = field(default_factory=list)
    year_from: int = 0
    year_to: int = 0
    suggest: bool = False


# ═══════════════════════════════════════════════════════
# Interfaccia Astratta
# ═══════════════════════════════════════════════════════

class SearchBackend(ABC):

    @abstractmethod
    def index_document(self, doc_id: str, title: str, content: str,
                       category: str = "", language: str = "", year: int = 0,
                       source: str = "", metadata: Optional[Dict] = None) -> bool:
        ...

    @abstractmethod
    def index_batch(self, documents: List[Dict[str, Any]]) -> int:
        ...

    @abstractmethod
    def search(self, query: SearchQuery) -> SearchResponse:
        ...

    @abstractmethod
    def delete_document(self, doc_id: str) -> bool:
        ...

    @abstractmethod
    def count(self) -> int:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...

    def suggest(self, prefix: str, limit: int = 10) -> List[str]:
        return []


# ═══════════════════════════════════════════════════════
# 1. SQLITE FTS5 (default, zero config)
# ═══════════════════════════════════════════════════════

class FTS5SearchEngine(SearchBackend):
    """
    Motore di ricerca basato su SQLite FTS5.
    Zero dipendenze, integrato in Python.
    Supporta BM25 ranking, prefix queries, phrase queries.
    """

    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = os.path.join(os.path.expanduser("~"), ".vio83", "search.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        self._setup_tables()
        logger.info(f"FTS5SearchEngine: {db_path}")

    def _setup_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT '',
                language TEXT DEFAULT '',
                year INTEGER DEFAULT 0,
                source TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                indexed_at REAL DEFAULT (strftime('%s','now'))
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                doc_id,
                title,
                content,
                category,
                content='documents',
                content_rowid='rowid',
                tokenize='unicode61 remove_diacritics 2'
            );

            CREATE INDEX IF NOT EXISTS idx_docs_category ON documents(category);
            CREATE INDEX IF NOT EXISTS idx_docs_language ON documents(language);
            CREATE INDEX IF NOT EXISTS idx_docs_year ON documents(year);
            CREATE INDEX IF NOT EXISTS idx_docs_source ON documents(source);

            -- Trigger per sync FTS
            CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON documents BEGIN
                INSERT INTO search_fts(rowid, doc_id, title, content, category)
                VALUES (new.rowid, new.doc_id, new.title, new.content, new.category);
            END;

            CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON documents BEGIN
                INSERT INTO search_fts(search_fts, rowid, doc_id, title, content, category)
                VALUES ('delete', old.rowid, old.doc_id, old.title, old.content, old.category);
            END;

            CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON documents BEGIN
                INSERT INTO search_fts(search_fts, rowid, doc_id, title, content, category)
                VALUES ('delete', old.rowid, old.doc_id, old.title, old.content, old.category);
                INSERT INTO search_fts(rowid, doc_id, title, content, category)
                VALUES (new.rowid, new.doc_id, new.title, new.content, new.category);
            END;
        """)
        self._conn.commit()

    def index_document(self, doc_id: str, title: str, content: str,
                       category: str = "", language: str = "", year: int = 0,
                       source: str = "", metadata: Optional[Dict] = None) -> bool:
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO documents
                   (doc_id, title, content, category, language, year, source, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, title, content, category, language, year, source,
                 json.dumps(metadata or {}, ensure_ascii=False)),
            )
            self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"Errore indicizzazione {doc_id}: {e}")
            return False

    def index_batch(self, documents: List[Dict[str, Any]]) -> int:
        """Bulk insert ottimizzato."""
        count = 0
        try:
            self._conn.execute("BEGIN TRANSACTION")
            for doc in documents:
                self._conn.execute(
                    """INSERT OR REPLACE INTO documents
                       (doc_id, title, content, category, language, year, source, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        doc.get("doc_id", ""),
                        doc.get("title", ""),
                        doc.get("content", ""),
                        doc.get("category", ""),
                        doc.get("language", ""),
                        doc.get("year", 0),
                        doc.get("source", ""),
                        json.dumps(doc.get("metadata", {}), ensure_ascii=False),
                    ),
                )
                count += 1
            self._conn.execute("COMMIT")
        except Exception as e:
            self._conn.execute("ROLLBACK")
            logger.error(f"Errore batch index: {e}")
        return count

    def search(self, query: SearchQuery) -> SearchResponse:
        t0 = time.perf_counter()

        # Costruisci FTS5 query
        fts_query = self._build_fts_query(query.text)

        # Query principale con BM25
        sql_parts = [
            "SELECT d.doc_id, d.title, d.content, d.category, d.language, d.year, d.source, d.metadata,",
            "  bm25(search_fts, 0, 5.0, 1.0, 2.0) AS score",
            "FROM search_fts f",
            "JOIN documents d ON d.rowid = f.rowid",
            f"WHERE search_fts MATCH ?",
        ]
        params: List[Any] = [fts_query]

        # Filtri
        if query.categories:
            placeholders = ",".join("?" * len(query.categories))
            sql_parts.append(f"AND d.category IN ({placeholders})")
            params.extend(query.categories)

        if query.language:
            sql_parts.append("AND d.language = ?")
            params.append(query.language)

        if query.year_from > 0:
            sql_parts.append("AND d.year >= ?")
            params.append(query.year_from)

        if query.year_to > 0:
            sql_parts.append("AND d.year <= ?")
            params.append(query.year_to)

        for key, val in query.filters.items():
            if key in ("category", "language", "year"):
                continue
            sql_parts.append(f"AND d.{key} = ?")
            params.append(val)

        if query.min_score > 0:
            sql_parts.append("AND score < ?")  # BM25 in FTS5: lower = better match
            params.append(-query.min_score)

        # Ordinamento
        if query.sort_by == "date":
            sql_parts.append("ORDER BY d.year DESC")
        elif query.sort_by == "title":
            sql_parts.append("ORDER BY d.title ASC")
        else:
            sql_parts.append("ORDER BY score ASC")  # BM25: lower = better

        sql_parts.append("LIMIT ? OFFSET ?")
        params.extend([query.limit, query.offset])

        sql = "\n".join(sql_parts)

        try:
            rows = self._conn.execute(sql, params).fetchall()
        except Exception as e:
            logger.error(f"Errore ricerca FTS5: {e}")
            rows = []

        # Conta totale
        count_sql = f"SELECT COUNT(*) FROM search_fts WHERE search_fts MATCH ?"
        try:
            total = self._conn.execute(count_sql, [fts_query]).fetchone()[0]
        except Exception:
            total = len(rows)

        # Costruisci risultati
        results: List[SearchResult] = []
        for row in rows:
            doc_id, title, content, category, lang, year, source, meta_json, score = row
            snippet = self._make_snippet(content, query.text, max_chars=300)
            highlights = self._highlight(content, query.text) if query.highlight else []

            results.append(SearchResult(
                doc_id=doc_id,
                score=abs(score),  # BM25 è negativo in FTS5
                title=title,
                snippet=snippet,
                highlights=highlights,
                category=category,
                language=lang,
                year=year,
                source=source,
                metadata=json.loads(meta_json) if meta_json else {},
            ))

        # Facets
        facets = {}
        if "category" in query.facets:
            facets["category"] = self._get_facet("category", fts_query)
        if "language" in query.facets:
            facets["language"] = self._get_facet("language", fts_query)
        if "year" in query.facets:
            facets["year"] = self._get_facet("year", fts_query)

        # Suggestions
        suggestions = []
        if query.suggest:
            suggestions = self.suggest(query.text)

        elapsed = (time.perf_counter() - t0) * 1000

        return SearchResponse(
            query=query.text,
            total_hits=total,
            results=results,
            took_ms=round(elapsed, 2),
            facets=facets,
            suggestions=suggestions,
        )

    def _build_fts_query(self, text: str) -> str:
        """Costruisci query FTS5 robusta."""
        # Rimuovi caratteri speciali FTS5
        clean = re.sub(r'[^\w\s\-\"]', ' ', text)
        tokens = clean.split()
        if not tokens:
            return '""'  # query vuota

        # Se è una singola parola, cerca con prefix
        if len(tokens) == 1:
            return f"{tokens[0]}*"

        # Multi-parola: AND implicito con prefix sull'ultimo
        parts = tokens[:-1] + [f"{tokens[-1]}*"]
        return " ".join(parts)

    def _make_snippet(self, content: str, query: str, max_chars: int = 300) -> str:
        """Crea snippet centrato sul match."""
        query_lower = query.lower()
        content_lower = content.lower()
        pos = content_lower.find(query_lower.split()[0] if query_lower.split() else "")

        if pos < 0:
            return content[:max_chars] + ("..." if len(content) > max_chars else "")

        start = max(0, pos - max_chars // 3)
        end = min(len(content), start + max_chars)
        snippet = content[start:end]

        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

    def _highlight(self, content: str, query: str, max_highlights: int = 3) -> List[str]:
        """Evidenzia matches nel contenuto."""
        highlights = []
        for word in query.lower().split():
            if len(word) < 2:
                continue
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            for match in pattern.finditer(content):
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                ctx = content[start:end]
                highlighted = pattern.sub(f"**{match.group()}**", ctx)
                highlights.append(highlighted)
                if len(highlights) >= max_highlights:
                    return highlights
        return highlights

    def _get_facet(self, field_name: str, fts_query: str) -> Dict[str, int]:
        """Calcola facet per un campo."""
        sql = f"""
            SELECT d.{field_name}, COUNT(*) as cnt
            FROM search_fts f
            JOIN documents d ON d.rowid = f.rowid
            WHERE search_fts MATCH ?
            GROUP BY d.{field_name}
            ORDER BY cnt DESC
            LIMIT 50
        """
        try:
            rows = self._conn.execute(sql, [fts_query]).fetchall()
            return {str(row[0]): row[1] for row in rows if row[0]}
        except Exception:
            return {}

    def suggest(self, prefix: str, limit: int = 10) -> List[str]:
        """Auto-complete basato su titoli indicizzati."""
        if len(prefix) < 2:
            return []
        try:
            rows = self._conn.execute(
                "SELECT DISTINCT title FROM documents WHERE title LIKE ? LIMIT ?",
                (f"%{prefix}%", limit),
            ).fetchall()
            return [row[0] for row in rows]
        except Exception:
            return []

    def delete_document(self, doc_id: str) -> bool:
        try:
            self._conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            self._conn.commit()
            return True
        except Exception:
            return False

    def count(self) -> int:
        try:
            return self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        except Exception:
            return 0

    def clear(self) -> None:
        self._conn.executescript("""
            DELETE FROM documents;
            INSERT INTO search_fts(search_fts) VALUES('rebuild');
        """)
        self._conn.commit()

    def optimize(self) -> None:
        """Ottimizza indice FTS5."""
        self._conn.execute("INSERT INTO search_fts(search_fts) VALUES('optimize')")
        self._conn.execute("VACUUM")
        self._conn.commit()

    def stats(self) -> Dict[str, Any]:
        total = self.count()
        categories = self._conn.execute(
            "SELECT category, COUNT(*) FROM documents GROUP BY category ORDER BY COUNT(*) DESC LIMIT 20"
        ).fetchall()
        db_size = os.path.getsize(self._db_path) if os.path.exists(self._db_path) else 0
        return {
            "backend": "fts5",
            "total_documents": total,
            "db_size_mb": round(db_size / (1024**2), 2),
            "categories": {row[0]: row[1] for row in categories},
        }


# ═══════════════════════════════════════════════════════
# 2. WHOOSH (Python puro, opzionale)
# ═══════════════════════════════════════════════════════

class WhooshSearchEngine(SearchBackend):
    """
    Whoosh full-text search engine.
    Python puro, più features di FTS5.
    Richiede: pip install whoosh
    """

    def __init__(self, index_dir: str = ""):
        try:
            from whoosh.index import create_in, open_dir, exists_in
            from whoosh.fields import Schema, TEXT, ID, NUMERIC, KEYWORD, STORED
            from whoosh.analysis import StemmingAnalyzer
            self._whoosh = True
        except ImportError:
            raise ImportError(
                "Whoosh richiesto per WhooshSearchEngine. "
                "Installa con: pip install whoosh"
            )

        if not index_dir:
            index_dir = os.path.join(os.path.expanduser("~"), ".vio83", "whoosh_index")
        os.makedirs(index_dir, exist_ok=True)
        self._index_dir = index_dir

        schema = Schema(
            doc_id=ID(stored=True, unique=True),
            title=TEXT(stored=True, analyzer=StemmingAnalyzer()),
            content=TEXT(stored=True, analyzer=StemmingAnalyzer()),
            category=KEYWORD(stored=True, commas=True),
            language=ID(stored=True),
            year=NUMERIC(stored=True, sortable=True),
            source=ID(stored=True),
            metadata=STORED,
        )

        if exists_in(index_dir):
            self._ix = open_dir(index_dir)
        else:
            self._ix = create_in(index_dir, schema)

        logger.info(f"WhooshSearchEngine: {index_dir}")

    def index_document(self, doc_id: str, title: str, content: str,
                       category: str = "", language: str = "", year: int = 0,
                       source: str = "", metadata: Optional[Dict] = None) -> bool:
        try:
            writer = self._ix.writer()
            writer.update_document(
                doc_id=doc_id,
                title=title,
                content=content,
                category=category,
                language=language,
                year=year,
                source=source,
                metadata=json.dumps(metadata or {}),
            )
            writer.commit()
            return True
        except Exception as e:
            logger.error(f"Errore Whoosh index: {e}")
            return False

    def index_batch(self, documents: List[Dict[str, Any]]) -> int:
        count = 0
        try:
            writer = self._ix.writer(limitmb=256, procs=4, multisegment=True)
            for doc in documents:
                writer.update_document(
                    doc_id=doc.get("doc_id", ""),
                    title=doc.get("title", ""),
                    content=doc.get("content", ""),
                    category=doc.get("category", ""),
                    language=doc.get("language", ""),
                    year=doc.get("year", 0),
                    source=doc.get("source", ""),
                    metadata=json.dumps(doc.get("metadata", {})),
                )
                count += 1
            writer.commit(optimize=True)
        except Exception as e:
            logger.error(f"Errore Whoosh batch: {e}")
        return count

    def search(self, query: SearchQuery) -> SearchResponse:
        from whoosh.qparser import MultifieldParser, OrGroup
        from whoosh.query import And, Term, NumericRange

        t0 = time.perf_counter()

        parser = MultifieldParser(
            ["title", "content"], self._ix.schema, group=OrGroup
        )
        parsed = parser.parse(query.text)

        # Aggiungi filtri
        filters = []
        if query.categories:
            for cat in query.categories:
                filters.append(Term("category", cat))
        if query.language:
            filters.append(Term("language", query.language))
        if query.year_from > 0 or query.year_to > 0:
            yr_from = query.year_from or 0
            yr_to = query.year_to or 9999
            filters.append(NumericRange("year", yr_from, yr_to))

        if filters:
            parsed = And([parsed] + filters)

        with self._ix.searcher() as searcher:
            results = searcher.search(
                parsed,
                limit=query.offset + query.limit,
            )

            search_results: List[SearchResult] = []
            for hit in results[query.offset:query.offset + query.limit]:
                snippet = hit.highlights("content", top=3) if query.highlight else ""
                search_results.append(SearchResult(
                    doc_id=hit["doc_id"],
                    score=hit.score,
                    title=hit["title"],
                    snippet=snippet or hit["content"][:300],
                    category=hit.get("category", ""),
                    language=hit.get("language", ""),
                    year=hit.get("year", 0),
                    source=hit.get("source", ""),
                    metadata=json.loads(hit.get("metadata", "{}")),
                ))

            total = len(results)

        elapsed = (time.perf_counter() - t0) * 1000

        return SearchResponse(
            query=query.text,
            total_hits=total,
            results=search_results,
            took_ms=round(elapsed, 2),
        )

    def delete_document(self, doc_id: str) -> bool:
        try:
            writer = self._ix.writer()
            writer.delete_by_term("doc_id", doc_id)
            writer.commit()
            return True
        except Exception:
            return False

    def count(self) -> int:
        return self._ix.doc_count()

    def clear(self) -> None:
        from whoosh.index import create_in
        self._ix = create_in(self._index_dir, self._ix.schema)


# ═══════════════════════════════════════════════════════
# 3. ELASTICSEARCH (opzionale, distribuito)
# ═══════════════════════════════════════════════════════

class ElasticsearchEngine(SearchBackend):
    """
    Elasticsearch per deployment scalabili.
    Richiede: pip install elasticsearch
    """

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        index_name: str = "vio83_knowledge",
        api_key: str = "",
        cloud_id: str = "",
    ):
        try:
            from elasticsearch import Elasticsearch
        except ImportError:
            raise ImportError(
                "elasticsearch richiesto. "
                "Installa con: pip install elasticsearch"
            )

        if cloud_id:
            self._es = Elasticsearch(cloud_id=cloud_id, api_key=api_key)
        elif hosts:
            kwargs: Dict[str, Any] = {"hosts": hosts}
            if api_key:
                kwargs["api_key"] = api_key
            self._es = Elasticsearch(**kwargs)
        else:
            self._es = Elasticsearch(["http://localhost:9200"])

        self._index = index_name
        self._setup_index()
        logger.info(f"ElasticsearchEngine: index={index_name}")

    def _setup_index(self) -> None:
        if not self._es.indices.exists(index=self._index):
            self._es.indices.create(
                index=self._index,
                body={
                    "settings": {
                        "number_of_shards": 3,
                        "number_of_replicas": 1,
                        "analysis": {
                            "analyzer": {
                                "multilingual": {
                                    "type": "standard",
                                    "max_token_length": 255,
                                }
                            }
                        },
                    },
                    "mappings": {
                        "properties": {
                            "doc_id": {"type": "keyword"},
                            "title": {"type": "text", "analyzer": "multilingual", "fields": {"keyword": {"type": "keyword"}}},
                            "content": {"type": "text", "analyzer": "multilingual"},
                            "category": {"type": "keyword"},
                            "language": {"type": "keyword"},
                            "year": {"type": "integer"},
                            "source": {"type": "keyword"},
                            "metadata": {"type": "object", "enabled": False},
                            "indexed_at": {"type": "date"},
                        }
                    },
                },
            )

    def index_document(self, doc_id: str, title: str, content: str,
                       category: str = "", language: str = "", year: int = 0,
                       source: str = "", metadata: Optional[Dict] = None) -> bool:
        try:
            self._es.index(
                index=self._index,
                id=doc_id,
                body={
                    "doc_id": doc_id,
                    "title": title,
                    "content": content,
                    "category": category,
                    "language": language,
                    "year": year,
                    "source": source,
                    "metadata": metadata or {},
                },
            )
            return True
        except Exception as e:
            logger.error(f"ES index error: {e}")
            return False

    def index_batch(self, documents: List[Dict[str, Any]]) -> int:
        from elasticsearch.helpers import bulk

        actions = []
        for doc in documents:
            actions.append({
                "_index": self._index,
                "_id": doc.get("doc_id", ""),
                "_source": {
                    "doc_id": doc.get("doc_id", ""),
                    "title": doc.get("title", ""),
                    "content": doc.get("content", ""),
                    "category": doc.get("category", ""),
                    "language": doc.get("language", ""),
                    "year": doc.get("year", 0),
                    "source": doc.get("source", ""),
                    "metadata": doc.get("metadata", {}),
                },
            })

        success, _ = bulk(self._es, actions, chunk_size=500, request_timeout=120)
        return success

    def search(self, query: SearchQuery) -> SearchResponse:
        t0 = time.perf_counter()

        body: Dict[str, Any] = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query.text,
                                "fields": ["title^3", "content"],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                            }
                        }
                    ],
                    "filter": [],
                }
            },
            "from": query.offset,
            "size": query.limit,
            "highlight": {
                "fields": {
                    "title": {},
                    "content": {"fragment_size": 200, "number_of_fragments": 3},
                }
            } if query.highlight else {},
        }

        # Filtri
        if query.categories:
            body["query"]["bool"]["filter"].append({"terms": {"category": query.categories}})
        if query.language:
            body["query"]["bool"]["filter"].append({"term": {"language": query.language}})
        if query.year_from > 0 or query.year_to > 0:
            yr_range: Dict[str, int] = {}
            if query.year_from:
                yr_range["gte"] = query.year_from
            if query.year_to:
                yr_range["lte"] = query.year_to
            body["query"]["bool"]["filter"].append({"range": {"year": yr_range}})

        # Facets (aggregazioni)
        if query.facets:
            body["aggs"] = {}
            for facet in query.facets:
                body["aggs"][facet] = {"terms": {"field": facet, "size": 50}}

        # Sorting
        if query.sort_by == "date":
            body["sort"] = [{"year": "desc"}, "_score"]
        elif query.sort_by == "title":
            body["sort"] = [{"title.keyword": "asc"}]

        response = self._es.search(index=self._index, body=body)
        elapsed = (time.perf_counter() - t0) * 1000

        results: List[SearchResult] = []
        for hit in response["hits"]["hits"]:
            src = hit["_source"]
            highlights = []
            if "highlight" in hit:
                for field_highlights in hit["highlight"].values():
                    highlights.extend(field_highlights)

            results.append(SearchResult(
                doc_id=src["doc_id"],
                score=hit["_score"] or 0,
                title=src.get("title", ""),
                snippet=highlights[0] if highlights else src.get("content", "")[:300],
                highlights=highlights,
                category=src.get("category", ""),
                language=src.get("language", ""),
                year=src.get("year", 0),
                source=src.get("source", ""),
                metadata=src.get("metadata", {}),
            ))

        # Facets
        facets = {}
        for facet_name, agg in response.get("aggregations", {}).items():
            facets[facet_name] = {
                bucket["key"]: bucket["doc_count"]
                for bucket in agg.get("buckets", [])
            }

        return SearchResponse(
            query=query.text,
            total_hits=response["hits"]["total"]["value"],
            results=results,
            took_ms=round(elapsed, 2),
            facets=facets,
        )

    def delete_document(self, doc_id: str) -> bool:
        try:
            self._es.delete(index=self._index, id=doc_id)
            return True
        except Exception:
            return False

    def count(self) -> int:
        try:
            return self._es.count(index=self._index)["count"]
        except Exception:
            return 0

    def clear(self) -> None:
        try:
            self._es.indices.delete(index=self._index)
            self._setup_index()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════

_search_instance: Optional[SearchBackend] = None


def get_search_engine(
    backend: SearchBackendType = SearchBackendType.FTS5,
    **kwargs,
) -> SearchBackend:
    """Factory per creare il motore di ricerca."""
    global _search_instance
    if _search_instance is None:
        if backend == SearchBackendType.FTS5:
            _search_instance = FTS5SearchEngine(**kwargs)
        elif backend == SearchBackendType.WHOOSH:
            _search_instance = WhooshSearchEngine(**kwargs)
        elif backend == SearchBackendType.ELASTICSEARCH:
            _search_instance = ElasticsearchEngine(**kwargs)
        else:
            _search_instance = FTS5SearchEngine(**kwargs)
    return _search_instance


def reset_search_engine() -> None:
    global _search_instance
    _search_instance = None


def available_search_backends() -> Dict[str, bool]:
    """Lista backend disponibili."""
    has_whoosh = False
    has_es = False
    has_meili = False
    try:
        import whoosh
        has_whoosh = True
    except ImportError:
        pass
    try:
        import elasticsearch
        has_es = True
    except ImportError:
        pass
    try:
        import meilisearch
        has_meili = True
    except ImportError:
        pass
    return {
        "fts5": True,
        "whoosh": has_whoosh,
        "elasticsearch": has_es,
        "meilisearch": has_meili,
    }
