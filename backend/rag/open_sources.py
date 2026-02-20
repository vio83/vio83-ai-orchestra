"""
VIO 83 AI ORCHESTRA — Open Sources Connector
=============================================
Sistema automatizzato per scaricare e distillare conoscenza
da fonti gratuite e open access, senza costi di abbonamento.

FONTI SUPPORTATE (tutte gratuite):
┌──────────────────────────────────────────────────────────────────┐
│ Fonte                    │ Documenti │ Tipo                      │
├──────────────────────────┼───────────┼───────────────────────────┤
│ OpenAlex API             │   250M+   │ Metadati + abstract       │
│ Crossref API             │   140M+   │ Metadati DOI              │
│ Semantic Scholar API     │   220M+   │ Metadati + abstract + cit │
│ arXiv API                │   2.5M    │ Paper full-text (PDF)     │
│ PubMed/PMC API           │   8M      │ Articoli medici           │
│ Project Gutenberg        │   70K     │ Libri full-text           │
│ Wikipedia API            │   62M     │ Articoli enciclopedici    │
│ Wikidata SPARQL          │   110M    │ Knowledge graph           │
│ CORE API                 │   36M     │ Articoli open access      │
│ DOAJ API                 │   9.5M    │ Journal open access       │
│ Europeana API            │   58M     │ Patrimonio culturale      │
└──────────────────────────┴───────────┴───────────────────────────┘

STRATEGIA DI DOWNLOAD:
1. Per PRIMO scarica i metadati (Livello 1) — velocissimo, ~100K/sec
2. Poi arricchisci con abstract (Livello 3) dove disponibili
3. Per i top documenti, scarica full-text e distilla tutti i livelli
4. Tutto incrementale: puo' essere interrotto e ripreso

RATE LIMITING: rispetta i limiti di ogni API
"""

import os
import re
import json
import time
import hashlib
from typing import Optional, Generator
from dataclasses import dataclass

# httpx per HTTP async-friendly
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# urllib come fallback
import urllib.request
import urllib.parse

from backend.rag.knowledge_distiller import (
    Level1_Metadata,
    DistilledKnowledgeDB,
    get_distilled_db,
)


# ============================================================
# HTTP CLIENT con rate limiting
# ============================================================

class RateLimitedClient:
    """Client HTTP con rate limiting e retry automatico."""

    # User-Agent OBBLIGATORIO per Wikipedia e buona pratica per tutte le API
    USER_AGENT = "VIO83-AI-Orchestra/2.0 (https://github.com/vio83/vio83-ai-orchestra; mailto:research@vio83.ai) Python/3"

    def __init__(self, requests_per_second: float = 10.0):
        self.min_interval = 1.0 / requests_per_second
        self._last_request = 0.0
        self._client = None
        if HTTPX_AVAILABLE:
            try:
                self._client = httpx.Client(
                    timeout=30.0,
                    follow_redirects=True,
                    headers={"User-Agent": self.USER_AGENT},
                )
            except (ImportError, Exception):
                self._client = None

    def get_json(self, url: str, params: Optional[dict] = None) -> Optional[dict]:
        """GET request che ritorna JSON, con rate limiting."""
        # Rate limit
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request = time.time()

        try:
            if self._client:
                resp = self._client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            else:
                # Fallback urllib
                if params:
                    url = url + "?" + urllib.parse.urlencode(params)
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": self.USER_AGENT}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[OpenSources] Errore GET {url}: {e}")
            return None

    def close(self):
        if self._client:
            self._client.close()


# ============================================================
# CLASSIFICATORE AUTOMATICO (da metadati a categoria)
# ============================================================

# Mappa dei concept/topic OpenAlex → categorie VIO83
OPENALEX_TOPIC_MAP = {
    "mathematics": "matematica",
    "physics": "fisica",
    "chemistry": "chimica",
    "biology": "biologia",
    "earth science": "scienze_terra",
    "geology": "scienze_terra",
    "astronomy": "astronomia",
    "space science": "astronomia",
    "medicine": "medicina",
    "clinical medicine": "medicina",
    "surgery": "medicina",
    "pharmacology": "farmacia_farmacologia",
    "toxicology": "farmacia_farmacologia",
    "psychology": "psicologia",
    "nursing": "scienze_infermieristiche",
    "veterinary": "veterinaria",
    "history": "storia",
    "philosophy": "filosofia",
    "linguistics": "linguistica",
    "language": "linguistica",
    "sociology": "sociologia_antropologia",
    "anthropology": "sociologia_antropologia",
    "political science": "scienze_politiche",
    "law": "diritto",
    "education": "pedagogia",
    "theology": "religioni_teologia",
    "religion": "religioni_teologia",
    "economics": "economia",
    "business": "management_business",
    "management": "management_business",
    "finance": "contabilita_finanza",
    "accounting": "contabilita_finanza",
    "computer science": "informatica",
    "engineering": "ingegneria",
    "electrical engineering": "telecomunicazioni",
    "materials science": "ingegneria",
    "biotechnology": "biotecnologia_nanotecnologia",
    "nanotechnology": "biotecnologia_nanotecnologia",
    "art": "arti_visive_performative",
    "music": "musica",
    "film": "cinema_media",
    "media": "cinema_media",
    "communication": "cinema_media",
    "design": "design_moda_architettura",
    "architecture": "design_moda_architettura",
    "agriculture": "agraria_alimentare",
    "food science": "agraria_alimentare",
    "environmental science": "scienze_ambientali",
    "sports science": "scienze_motorie_sport",
    "tourism": "turismo_ospitalita",
    "criminology": "criminologia_forensi",
    "forensic": "criminologia_forensi",
    "library science": "biblioteconomia_archivistica",
    "gender studies": "studi_genere_interculturali",
}


def classify_from_topics(topics: list[str]) -> str:
    """Classifica un documento dalle sue topic labels."""
    for topic in topics:
        topic_lower = topic.lower()
        for key, cat in OPENALEX_TOPIC_MAP.items():
            if key in topic_lower:
                return cat
    return "libri"  # default


# ============================================================
# CONNETTORI PER FONTI SPECIFICHE
# ============================================================

class OpenAlexConnector:
    """
    OpenAlex API — La piu grande fonte gratuita di metadati accademici.
    250M+ documenti, aggiornamento continuo, nessuna API key necessaria.
    https://docs.openalex.org/
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: str = "research@vio83.ai"):
        self.client = RateLimitedClient(requests_per_second=10)
        self.email = email  # polite pool = 10 req/sec con email

    def fetch_works(
        self,
        query: Optional[str] = None,
        categoria: Optional[str] = None,
        anno_da: Optional[int] = None,
        anno_a: Optional[int] = None,
        per_page: int = 200,
        cursor: str = "*",
    ) -> tuple[list[Level1_Metadata], Optional[str]]:
        """
        Scarica batch di documenti da OpenAlex.
        Ritorna (lista_metadati, next_cursor).
        """
        params = {
            "mailto": self.email,
            "per_page": per_page,
            "cursor": cursor,
            "select": "id,title,authorships,publication_year,language,type,"
                      "doi,topics,primary_topic,cited_by_count,"
                      "is_oa",
        }

        filters = []
        if query:
            params["search"] = query
        if anno_da:
            filters.append(f"publication_year:>{anno_da - 1}")
        if anno_a:
            filters.append(f"publication_year:<{anno_a + 1}")
        if filters:
            params["filter"] = ",".join(filters)

        data = self.client.get_json(f"{self.BASE_URL}/works", params=params)
        if not data or "results" not in data:
            return [], None

        results = []
        for work in data["results"]:
            # Estrai autore principale
            authors = work.get("authorships", [])
            autore = ""
            if authors:
                au = authors[0].get("author", {})
                autore = au.get("display_name", "")

            # Estrai topics per classificazione
            topics = []
            primary = work.get("primary_topic")
            if primary:
                topics.append(primary.get("display_name", ""))
            for t in work.get("topics", [])[:3]:
                topics.append(t.get("display_name", ""))

            # Classifica
            cat = classify_from_topics(topics)

            # Tipo fonte
            work_type = work.get("type", "article")
            tipo_map = {
                "article": "article", "book": "book", "book-chapter": "book",
                "dissertation": "thesis", "preprint": "preprint",
                "review": "article", "dataset": "online",
            }
            fonte_tipo = tipo_map.get(work_type, "article")

            # DOI
            doi = work.get("doi", "") or ""
            if doi.startswith("https://doi.org/"):
                doi = doi[16:]

            meta = Level1_Metadata(
                doc_id=hashlib.md5(str(work.get("id", "")).encode()).hexdigest()[:16],
                titolo=(work.get("title") or "")[:200],
                autore=autore[:100],
                anno=work.get("publication_year") or 0,
                lingua=work.get("language") or "en",
                categoria=cat,
                fonte_tipo=fonte_tipo,
                doi=doi,
                parole_chiave=",".join(topics[:5]),
                affidabilita=min(1.0, 0.5 + (work.get("cited_by_count", 0) / 1000)),
                peer_reviewed=not work.get("is_oa", False) or fonte_tipo == "article",
                fonte_origine="openalex",
                url_fonte=work.get("id", ""),
            )
            results.append(meta)

        # Next cursor per paginazione
        next_cursor = data.get("meta", {}).get("next_cursor")
        return results, next_cursor

    def close(self):
        self.client.close()


class CrossrefConnector:
    """
    Crossref API — 140M+ metadati DOI.
    Nessuna API key necessaria (polite pool con email).
    """

    BASE_URL = "https://api.crossref.org"

    def __init__(self, email: str = "research@vio83.ai"):
        self.client = RateLimitedClient(requests_per_second=5)
        self.email = email

    def fetch_works(
        self,
        query: Optional[str] = None,
        rows: int = 100,
        offset: int = 0,
        cursor: Optional[str] = None,
    ) -> tuple[list[Level1_Metadata], Optional[str]]:
        """
        Scarica batch di documenti da Crossref.
        USA CURSOR per deep paging (offset max = 10,000 nell'API).
        Ritorna (lista_metadati, next_cursor).
        """
        params = {
            "mailto": self.email,
            "rows": rows,
        }
        if cursor:
            # Cursor-based paging: nessun limite di profondità
            params["cursor"] = cursor
        elif offset > 0:
            # Offset-based: LIMITATO a 10,000 dall'API
            params["offset"] = min(offset, 9999)
        else:
            # Prima richiesta: inizia con cursor=*
            params["cursor"] = "*"

        if query:
            params["query"] = query

        data = self.client.get_json(f"{self.BASE_URL}/works", params=params)
        if not data or "message" not in data:
            return [], None

        # Estrai next-cursor per deep paging
        next_cursor = data["message"].get("next-cursor")

        results = []
        for item in data["message"].get("items", []):
            # Titolo
            titles = item.get("title", [])
            titolo = titles[0] if titles else ""

            # Autore
            authors = item.get("author", [])
            autore = ""
            if authors:
                a = authors[0]
                autore = f"{a.get('family', '')} {a.get('given', '')}".strip()

            # Anno
            published = item.get("published-print") or item.get("published-online") or {}
            date_parts = published.get("date-parts", [[0]])
            anno = date_parts[0][0] if date_parts and date_parts[0] else 0

            # Subject per classificazione
            subjects = item.get("subject", [])
            cat = classify_from_topics(subjects)

            meta = Level1_Metadata(
                doc_id=hashlib.md5(item.get("DOI", "").encode()).hexdigest()[:16],
                titolo=titolo[:200],
                autore=autore[:100],
                anno=anno,
                lingua="en",
                categoria=cat,
                fonte_tipo=item.get("type", "journal-article"),
                doi=item.get("DOI", ""),
                issn=",".join(item.get("ISSN", [])[:2]),
                editore=item.get("publisher", "")[:100],
                parole_chiave=",".join(subjects[:5]),
                affidabilita=min(1.0, 0.5 + (item.get("is-referenced-by-count", 0) / 500)),
                peer_reviewed=True,
                fonte_origine="crossref",
                url_fonte=f"https://doi.org/{item.get('DOI', '')}",
            )
            results.append(meta)

        return results, next_cursor

    def close(self):
        self.client.close()


class WikipediaConnector:
    """
    Wikipedia API — 62M+ articoli in tutte le lingue.
    Completamente gratuita, ottima per conoscenza enciclopedica.
    """

    def __init__(self, lang: str = "it"):
        self.lang = lang
        self.base_url = f"https://{lang}.wikipedia.org/w/api.php"
        self.client = RateLimitedClient(requests_per_second=10)

    def search_articles(self, query: str, limit: int = 20) -> list[Level1_Metadata]:
        """Cerca articoli Wikipedia."""
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srprop": "snippet|titlesnippet|wordcount|timestamp",
        }

        data = self.client.get_json(self.base_url, params=params)
        if not data or "query" not in data:
            return []

        results = []
        for item in data["query"].get("search", []):
            title = item.get("title", "")
            snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))

            meta = Level1_Metadata(
                doc_id=hashlib.md5(f"wiki:{self.lang}:{title}".encode()).hexdigest()[:16],
                titolo=title[:200],
                autore="Wikipedia",
                anno=int(item.get("timestamp", "2024")[:4]) if item.get("timestamp") else 2024,
                lingua=self.lang,
                categoria="fonti_online",
                fonte_tipo="online",
                parole_chiave=title.replace(" ", ",").lower(),
                affidabilita=0.7,
                peer_reviewed=False,
                fonte_origine="wikipedia",
                url_fonte=f"https://{self.lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}",
            )
            results.append(meta)

        return results

    def close(self):
        self.client.close()


# ============================================================
# ORCHESTRATORE DI DOWNLOAD
# ============================================================

class OpenSourceOrchestrator:
    """
    Orchestratore che coordina il download da tutte le fonti
    e la distillazione nel database locale.

    Uso tipico:
        orchestrator = OpenSourceOrchestrator()
        stats = orchestrator.run_harvest(
            target_docs=1_000_000,  # quanti documenti scaricare
            sources=["openalex", "crossref", "wikipedia"],
        )
    """

    def __init__(self, db_path: str = ""):
        self.db = get_distilled_db(db_path)
        self._connectors = {}

    def _get_connector(self, source: str):
        """Lazy-init dei connettori."""
        if source not in self._connectors:
            if source == "openalex":
                self._connectors[source] = OpenAlexConnector()
            elif source == "crossref":
                self._connectors[source] = CrossrefConnector()
            elif source == "wikipedia":
                self._connectors[source] = WikipediaConnector("it")
            elif source == "wikipedia_en":
                self._connectors[source] = WikipediaConnector("en")
        return self._connectors.get(source)

    def harvest_openalex(
        self,
        max_docs: int = 10000,
        query: Optional[str] = None,
        anno_da: Optional[int] = None,
        anno_a: Optional[int] = None,
    ) -> dict:
        """
        Scarica documenti da OpenAlex.
        Con paginazione cursor-based, puo' scaricare milioni di docs.
        """
        conn = self._get_connector("openalex")
        if not conn:
            return {"error": "OpenAlex connector non disponibile"}

        total = 0
        cursor = "*"
        batch_size = 200  # max di OpenAlex

        print(f"[OpenSources] Avvio harvest OpenAlex (target: {max_docs:,})")

        while total < max_docs and cursor:
            batch, cursor = conn.fetch_works(
                query=query,
                anno_da=anno_da,
                anno_a=anno_a,
                per_page=min(batch_size, max_docs - total),
                cursor=cursor,
            )

            if not batch:
                break

            inserted = self.db.distill_batch_metadata(batch)
            total += inserted

            if total % 1000 == 0:
                print(f"[OpenSources] OpenAlex: {total:,} / {max_docs:,} documenti")

        print(f"[OpenSources] OpenAlex completato: {total:,} documenti")
        return {"source": "openalex", "documents": total}

    def harvest_crossref(self, max_docs: int = 10000) -> dict:
        """Scarica documenti da Crossref con cursor-based deep paging."""
        conn = self._get_connector("crossref")
        if not conn:
            return {"error": "Crossref connector non disponibile"}

        total = 0
        cursor = "*"  # Cursor-based: nessun limite di profondità!
        batch_size = 100

        print(f"[OpenSources] Avvio harvest Crossref (target: {max_docs:,}) — cursor-based")

        while total < max_docs and cursor:
            batch, cursor = conn.fetch_works(rows=batch_size, cursor=cursor)
            if not batch:
                break

            inserted = self.db.distill_batch_metadata(batch)
            total += inserted

            if total % 1000 == 0:
                print(f"[OpenSources] Crossref: {total:,} / {max_docs:,} documenti")

        print(f"[OpenSources] Crossref completato: {total:,} documenti")
        return {"source": "crossref", "documents": total}

    def harvest_wikipedia(self, queries: list[str], lang: str = "it") -> dict:
        """Scarica articoli Wikipedia per lista di query."""
        source_key = f"wikipedia{'_' + lang if lang != 'it' else ''}"
        conn = self._get_connector(source_key)
        if not conn:
            return {"error": f"Wikipedia {lang} connector non disponibile"}

        total = 0
        for q in queries:
            batch = conn.search_articles(q, limit=20)
            if batch:
                inserted = self.db.distill_batch_metadata(batch)
                total += inserted

        print(f"[OpenSources] Wikipedia ({lang}): {total} articoli")
        return {"source": f"wikipedia_{lang}", "documents": total}

    def run_harvest(
        self,
        target_docs: int = 10000,
        sources: Optional[list[str]] = None,
    ) -> dict:
        """
        Esegue un harvest completo da piu fonti.
        Distribuisce il target equamente tra le fonti.
        """
        if sources is None:
            sources = ["openalex", "crossref"]

        results = {}
        per_source = target_docs // len(sources)

        for source in sources:
            if source == "openalex":
                results[source] = self.harvest_openalex(max_docs=per_source)
            elif source == "crossref":
                results[source] = self.harvest_crossref(max_docs=per_source)
            elif source.startswith("wikipedia"):
                lang = source.split("_")[1] if "_" in source else "it"
                # Query di base per le 42 categorie
                base_queries = [
                    "matematica", "fisica", "chimica", "biologia", "medicina",
                    "informatica", "storia", "filosofia", "diritto", "economia",
                    "psicologia", "astronomia", "ingegneria", "arte",
                ]
                results[source] = self.harvest_wikipedia(base_queries, lang)

        # Statistiche finali
        total = sum(r.get("documents", 0) for r in results.values())
        stats = self.db.stats()

        return {
            "totale_scaricati": total,
            "risultati_per_fonte": results,
            "stato_database": stats,
        }

    def close(self):
        for conn in self._connectors.values():
            if hasattr(conn, "close"):
                conn.close()
        self._connectors.clear()
