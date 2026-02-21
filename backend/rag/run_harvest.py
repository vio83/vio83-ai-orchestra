#!/usr/bin/env python3
# ============================================================
# VIO 83 AI ORCHESTRA — Copyright (c) 2026 Viorica Porcu (vio83)
# DUAL LICENSE: Proprietary + AGPL-3.0 — See LICENSE files
# ALL RIGHTS RESERVED — https://github.com/vio83/vio83-ai-orchestra
# ============================================================
"""
VIO 83 AI ORCHESTRA — HARVEST & DISTILL
========================================
Script REALE per scaricare conoscenza e distillare dati locali.
Lanciare dal Mac e lasciare in esecuzione per settimane.

MODALITÀ:
  1. harvest   — Scarica metadati da OpenAlex, Crossref, Wikipedia
  2. local     — Scansiona e distilla file locali del Mac
  3. all       — Entrambi in sequenza
  4. status    — Mostra progresso corrente
  5. resume    — Riprende da dove si era interrotto

USO:
  cd /Users/padronavio/Projects/vio83-ai-orchestra
  python3 -m backend.rag.run_harvest harvest --target 1000000
  python3 -m backend.rag.run_harvest local --path ~/Documents
  python3 -m backend.rag.run_harvest all --target 1000000
  python3 -m backend.rag.run_harvest status
  python3 -m backend.rag.run_harvest resume

INTERRUPT: Ctrl+C per interrompere — riprende automaticamente con 'resume'
"""

import os
import sys
import re
import json
import time
import signal
import hashlib
import argparse
import mimetypes
from pathlib import Path
from typing import Optional

# Aggiungi il progetto al path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.rag.harvest_state import (
    HarvestStateDB, HarvestProgress, setup_logger, DATA_DIR
)
from backend.rag.knowledge_distiller import (
    Level1_Metadata, DistilledKnowledgeDB, get_distilled_db,
)
from backend.rag.open_sources import (
    RateLimitedClient, OpenAlexConnector, CrossrefConnector,
    WikipediaConnector, classify_from_topics,
)

# ============================================================
# CONFIGURAZIONE GLOBALE
# ============================================================

logger = setup_logger("harvest")
SHUTDOWN_REQUESTED = False


def signal_handler(sig, frame):
    """Gestione Ctrl+C — salva stato e esce pulito."""
    global SHUTDOWN_REQUESTED
    if SHUTDOWN_REQUESTED:
        logger.warning("Secondo Ctrl+C — uscita forzata!")
        sys.exit(1)
    SHUTDOWN_REQUESTED = True
    logger.info("🛑 Shutdown richiesto — salvo stato e chiudo...")


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ============================================================
# HARVESTER REALE CON RESUME
# ============================================================

class ProductionHarvester:
    """
    Harvester production-grade con:
    - Resume capability (cursori/offset salvati in SQLite)
    - Exponential backoff su errori
    - Logging dettagliato su file
    - Velocità e ETA in tempo reale
    - Wikipedia bulk enumeration (allpages, non solo search)
    """

    def __init__(self, db_path: str = "", state_path: str = ""):
        self.db = get_distilled_db(db_path)
        self.state = HarvestStateDB(state_path)
        self._max_retries = 5
        self._base_backoff = 2.0

    # ----------------------------------------------------------
    # EXPONENTIAL BACKOFF
    # ----------------------------------------------------------

    def _retry_with_backoff(self, func, *args, max_retries: int = 0, **kwargs):
        """Esegue func con retry ed exponential backoff."""
        retries = max_retries or self._max_retries
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                wait = self._base_backoff * (2 ** attempt)
                logger.warning(
                    f"Errore (tentativo {attempt + 1}/{retries}): {e} "
                    f"— riprovo tra {wait:.0f}s"
                )
                if attempt < retries - 1:
                    time.sleep(wait)
                else:
                    logger.error(f"Fallito dopo {retries} tentativi: {e}")
                    raise

    # ----------------------------------------------------------
    # OPENALEX HARVEST (cursor-based, fino a 250M docs)
    # ----------------------------------------------------------

    def harvest_openalex(self, target: int = 100_000, resume: bool = True):
        """
        Scarica metadati da OpenAlex con paginazione cursor-based.
        Resume automatico dal cursor salvato.
        """
        global SHUTDOWN_REQUESTED
        source = "openalex"

        # Carica o crea progress
        prog = self.state.load_progress(source) if resume else None
        if prog and prog.status in ("running", "paused"):
            logger.info(f"▶ RESUME OpenAlex da {prog.total_fetched:,} docs, cursor={prog.cursor[:20]}...")
        else:
            prog = HarvestProgress(
                source=source,
                cursor="*",
                target=target,
                started_at=time.time(),
                status="running",
            )
        prog.target = target
        prog.status = "running"
        self.state.save_progress(prog)
        self.state.log_event(source, "start", f"target={target}, resume={resume}")

        conn = OpenAlexConnector()
        batch_count = 0

        try:
            while prog.total_fetched < target and not SHUTDOWN_REQUESTED:
                # Fetch con retry
                try:
                    batch, next_cursor = self._retry_with_backoff(
                        conn.fetch_works,
                        per_page=200,
                        cursor=prog.cursor,
                    )
                except Exception as e:
                    prog.total_errors += 1
                    self.state.save_progress(prog)
                    logger.error(f"OpenAlex: errore critico — {e}")
                    break

                if not batch:
                    logger.info("OpenAlex: nessun altro risultato — fine dati")
                    break

                # Inserisci nel DB
                inserted = self.db.distill_batch_metadata(batch)

                # Aggiorna progress
                prog.total_fetched += len(batch)
                prog.total_inserted += inserted
                prog.cursor = next_cursor or ""
                prog.last_batch_at = time.time()
                prog.last_batch_size = len(batch)
                batch_count += 1

                # Salva stato ogni 5 batch (= 1000 docs)
                if batch_count % 5 == 0:
                    self.state.save_progress(prog)

                # Log ogni 2000 docs
                if prog.total_fetched % 2000 < 200:
                    logger.info(prog.summary())

                # Se il cursor è vuoto, fine dati
                if not next_cursor:
                    logger.info("OpenAlex: cursor esaurito — fine dati")
                    break

        finally:
            prog.status = "completed" if prog.total_fetched >= target else "paused"
            if SHUTDOWN_REQUESTED:
                prog.status = "paused"
            self.state.save_progress(prog)
            self.state.log_event(
                source, "stop",
                f"fetched={prog.total_fetched}, inserted={prog.total_inserted}",
                prog.total_fetched,
            )
            conn.close()
            logger.info(f"OpenAlex terminato: {prog.summary()}")

        return prog

    # ----------------------------------------------------------
    # CROSSREF HARVEST (cursor-based deep paging — NESSUN LIMITE)
    # ----------------------------------------------------------

    def harvest_crossref(self, target: int = 50_000, resume: bool = True):
        """
        Scarica metadati da Crossref con cursor-based deep paging.
        NESSUN LIMITE di profondità (offset era limitato a 10,000).
        """
        global SHUTDOWN_REQUESTED
        source = "crossref"

        prog = self.state.load_progress(source) if resume else None
        if prog and prog.status in ("running", "paused"):
            logger.info(f"▶ RESUME Crossref da {prog.total_fetched:,} docs, cursor={prog.cursor[:30] if prog.cursor else 'N/A'}...")
        else:
            prog = HarvestProgress(
                source=source,
                cursor="*",  # Cursor-based: inizia con *
                target=target,
                started_at=time.time(),
                status="running",
            )
        prog.target = target
        prog.status = "running"
        self.state.save_progress(prog)

        conn = CrossrefConnector()
        batch_count = 0

        try:
            while prog.total_fetched < target and not SHUTDOWN_REQUESTED:
                try:
                    batch, next_cursor = self._retry_with_backoff(
                        conn.fetch_works,
                        rows=100,
                        cursor=prog.cursor or "*",
                    )
                except Exception as e:
                    prog.total_errors += 1
                    self.state.save_progress(prog)
                    logger.error(f"Crossref: errore critico — {e}")
                    break

                if not batch:
                    logger.info("Crossref: nessun altro risultato")
                    break

                inserted = self.db.distill_batch_metadata(batch)
                prog.total_fetched += len(batch)
                prog.total_inserted += inserted
                prog.cursor = next_cursor or ""
                prog.last_batch_at = time.time()
                prog.last_batch_size = len(batch)
                batch_count += 1

                if batch_count % 10 == 0:
                    self.state.save_progress(prog)

                if prog.total_fetched % 1000 < 100:
                    logger.info(prog.summary())

                # Se cursor esaurito, fine dati
                if not next_cursor:
                    logger.info("Crossref: cursor esaurito — fine catalogo")
                    break

        finally:
            prog.status = "completed" if prog.total_fetched >= target else "paused"
            if SHUTDOWN_REQUESTED:
                prog.status = "paused"
            self.state.save_progress(prog)
            conn.close()
            logger.info(f"Crossref terminato: {prog.summary()}")

        return prog

    # ----------------------------------------------------------
    # WIKIPEDIA HARVEST (allpages enumeration — BULK)
    # ----------------------------------------------------------

    def harvest_wikipedia(self, target: int = 50_000, langs: list = None,
                          resume: bool = True):
        """
        Scarica articoli Wikipedia BULK usando API allpages.
        Non usa search — enumera tutte le pagine sistematicamente.
        """
        global SHUTDOWN_REQUESTED
        if langs is None:
            langs = ["it", "en"]

        for lang in langs:
            if SHUTDOWN_REQUESTED:
                break

            source = f"wikipedia_{lang}"
            prog = self.state.load_progress(source) if resume else None

            if prog and prog.status in ("running", "paused"):
                logger.info(f"▶ RESUME Wikipedia {lang} da {prog.total_fetched:,} docs")
                apcontinue = prog.cursor if prog.cursor != "*" else ""
            else:
                apcontinue = ""
                prog = HarvestProgress(
                    source=source,
                    cursor="",
                    target=target // len(langs),
                    started_at=time.time(),
                    status="running",
                    extra=json.dumps({"lang": lang}),
                )

            prog.status = "running"
            self.state.save_progress(prog)

            client = RateLimitedClient(requests_per_second=10)
            base_url = f"https://{lang}.wikipedia.org/w/api.php"
            per_lang_target = target // len(langs)

            try:
                while prog.total_fetched < per_lang_target and not SHUTDOWN_REQUESTED:
                    # Usa allpages per enumerazione bulk
                    params = {
                        "action": "query",
                        "format": "json",
                        "list": "allpages",
                        "aplimit": 50,  # max 500 per bot, 50 per utente
                        "apnamespace": 0,  # solo articoli
                        "apfilterredir": "nonredirects",
                    }
                    if apcontinue:
                        params["apcontinue"] = apcontinue

                    try:
                        data = self._retry_with_backoff(
                            client.get_json, base_url, params
                        )
                    except Exception as e:
                        prog.total_errors += 1
                        self.state.save_progress(prog)
                        logger.error(f"Wikipedia {lang}: errore — {e}")
                        break

                    if not data or "query" not in data:
                        break

                    pages = data["query"].get("allpages", [])
                    if not pages:
                        break

                    # Converti in Level1_Metadata
                    batch = []
                    for page in pages:
                        title = page.get("title", "")
                        page_id = page.get("pageid", 0)

                        meta = Level1_Metadata(
                            doc_id=hashlib.md5(
                                f"wiki:{lang}:{page_id}".encode()
                            ).hexdigest()[:16],
                            titolo=title[:200],
                            autore="Wikipedia",
                            anno=2025,
                            lingua=lang,
                            categoria="fonti_online",
                            fonte_tipo="online",
                            parole_chiave=title.lower().replace(" ", ",")[:100],
                            affidabilita=0.7,
                            peer_reviewed=False,
                            fonte_origine="wikipedia",
                            url_fonte=f"https://{lang}.wikipedia.org/wiki/{page_id}",
                        )
                        batch.append(meta)

                    inserted = self.db.distill_batch_metadata(batch)
                    prog.total_fetched += len(batch)
                    prog.total_inserted += inserted
                    prog.last_batch_at = time.time()
                    prog.last_batch_size = len(batch)

                    # Paginazione
                    cont = data.get("continue", {})
                    apcontinue = cont.get("apcontinue", "")
                    prog.cursor = apcontinue

                    if not apcontinue:
                        logger.info(f"Wikipedia {lang}: fine pagine")
                        break

                    # Salva ogni 10 batch
                    if prog.total_fetched % 500 < 50:
                        self.state.save_progress(prog)
                        logger.info(prog.summary())

            finally:
                prog.status = "completed" if prog.total_fetched >= per_lang_target else "paused"
                if SHUTDOWN_REQUESTED:
                    prog.status = "paused"
                self.state.save_progress(prog)
                client.close()
                logger.info(f"Wikipedia {lang} terminato: {prog.summary()}")

    # ----------------------------------------------------------
    # HARVEST COMPLETO (tutte le fonti)
    # ----------------------------------------------------------

    def harvest_all(self, target: int = 100_000, resume: bool = True):
        """
        Esegue harvest da tutte le fonti in sequenza.
        Distribuzione: OpenAlex 70%, Wikipedia 20%, Crossref 10%
        """
        logger.info("=" * 60)
        logger.info(f"HARVEST COMPLETO — Target: {target:,} documenti")
        logger.info("=" * 60)

        t_openalex = int(target * 0.70)
        t_wikipedia = int(target * 0.20)
        t_crossref = int(target * 0.10)

        logger.info(f"  OpenAlex:  {t_openalex:,}")
        logger.info(f"  Wikipedia: {t_wikipedia:,}")
        logger.info(f"  Crossref:  {t_crossref:,}")
        logger.info("=" * 60)

        results = []

        if not SHUTDOWN_REQUESTED:
            results.append(self.harvest_openalex(t_openalex, resume))
        if not SHUTDOWN_REQUESTED:
            results.append(self.harvest_crossref(t_crossref, resume))
        if not SHUTDOWN_REQUESTED:
            self.harvest_wikipedia(t_wikipedia, ["it", "en"], resume)

        # Statistiche finali
        stats = self.db.stats()
        logger.info("=" * 60)
        logger.info("HARVEST COMPLETATO")
        logger.info(f"  Documenti nel DB: {stats['livello_1_metadati']:,}")
        logger.info(f"  DB size: {stats['db_size_MB']:.1f} MB")
        logger.info("=" * 60)

        return stats


# ============================================================
# LOCAL MAC DATA SCANNER & DISTILLER
# ============================================================

class LocalMacDistiller:
    """
    Scansiona file locali del Mac e li distilla nel database.
    Supporta: PDF, TXT, DOCX, MD, HTML, CSV, JSON, XML, EPUB.
    Crea metadati Level1 per ogni file trovato.

    Compressione effettiva:
    - Un documento di 1MB → ~1.5KB di metadati
    - Rapporto: ~670x
    """

    # Tipi file supportati per distillazione
    SUPPORTED_EXTENSIONS = {
        ".txt", ".md", ".rst", ".tex", ".csv", ".tsv",
        ".json", ".xml", ".yaml", ".yml",
        ".html", ".htm",
        ".pdf",
        ".doc", ".docx",
        ".epub",
        ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h",
        ".rb", ".go", ".rs", ".swift", ".kt",
        ".sh", ".bash", ".zsh",
        ".sql", ".r", ".m",
        ".ipynb",
        ".log",
    }

    # Categorie per estensione
    EXT_CATEGORY = {
        ".pdf": "documenti",
        ".doc": "documenti", ".docx": "documenti",
        ".txt": "documenti", ".md": "documenti", ".rst": "documenti",
        ".epub": "libri",
        ".html": "fonti_online", ".htm": "fonti_online",
        ".py": "informatica", ".js": "informatica", ".ts": "informatica",
        ".java": "informatica", ".cpp": "informatica", ".c": "informatica",
        ".rb": "informatica", ".go": "informatica", ".rs": "informatica",
        ".swift": "informatica", ".kt": "informatica",
        ".sh": "informatica", ".bash": "informatica",
        ".sql": "informatica", ".r": "informatica",
        ".ipynb": "informatica",
        ".json": "dati", ".xml": "dati", ".csv": "dati",
        ".yaml": "dati", ".yml": "dati",
        ".tex": "documenti",
        ".log": "dati",
    }

    # Directory da escludere
    EXCLUDE_DIRS = {
        ".git", ".svn", "node_modules", "__pycache__",
        ".Trash", ".Spotlight-V100", ".fseventsd",
        "Library", ".cache", ".npm", ".yarn",
        "venv", ".venv", "env", ".env",
        ".DS_Store", "Caches", "DerivedData",
    }

    def __init__(self, db_path: str = "", state_path: str = ""):
        self.db = get_distilled_db(db_path)
        self.state = HarvestStateDB(state_path)

    def scan_and_distill(self, base_path: str, scan_id: str = ""):
        """
        Scansiona ricorsivamente una directory del Mac
        e distilla tutti i file supportati nel database.
        """
        global SHUTDOWN_REQUESTED

        base_path = os.path.expanduser(base_path)
        if not os.path.isdir(base_path):
            logger.error(f"Directory non trovata: {base_path}")
            return

        scan_id = scan_id or hashlib.md5(base_path.encode()).hexdigest()[:12]

        # Carica stato precedente per resume
        prev_state = self.state.load_scan_state(scan_id)
        last_file = prev_state.get("last_file", "") if prev_state else ""
        files_scanned = prev_state.get("files_scanned", 0) if prev_state else 0
        files_indexed = prev_state.get("files_indexed", 0) if prev_state else 0
        bytes_original = prev_state.get("bytes_original", 0) if prev_state else 0
        bytes_compressed = prev_state.get("bytes_compressed", 0) if prev_state else 0
        past_resume_point = not bool(last_file)

        logger.info(f"📁 Scansione locale: {base_path}")
        if last_file:
            logger.info(f"   Resume da: {last_file}")

        start_time = time.time()
        batch = []
        batch_size = 100

        for root, dirs, files in os.walk(base_path, topdown=True):
            # Escludi directory di sistema
            dirs[:] = [
                d for d in dirs
                if d not in self.EXCLUDE_DIRS and not d.startswith(".")
            ]

            if SHUTDOWN_REQUESTED:
                break

            for fname in sorted(files):
                if SHUTDOWN_REQUESTED:
                    break

                fpath = os.path.join(root, fname)

                # Skip se stiamo facendo resume e non abbiamo ancora raggiunto
                if not past_resume_point:
                    if fpath == last_file:
                        past_resume_point = True
                    continue

                ext = os.path.splitext(fname)[1].lower()
                if ext not in self.SUPPORTED_EXTENSIONS:
                    continue

                try:
                    stat = os.stat(fpath)
                    if stat.st_size == 0 or stat.st_size > 100_000_000:  # skip >100MB
                        continue

                    files_scanned += 1
                    bytes_original += stat.st_size

                    # Crea metadati
                    rel_path = os.path.relpath(fpath, base_path)
                    doc_id = hashlib.md5(fpath.encode()).hexdigest()[:16]

                    # Estrai info dal percorso e nome file
                    parts = rel_path.split(os.sep)
                    parent_dir = parts[-2] if len(parts) > 1 else ""

                    meta = Level1_Metadata(
                        doc_id=doc_id,
                        titolo=os.path.splitext(fname)[0][:200],
                        autore=os.path.basename(base_path),
                        anno=int(time.strftime("%Y", time.localtime(stat.st_mtime))),
                        lingua="it",  # default, verrà aggiornato
                        categoria=self.EXT_CATEGORY.get(ext, "documenti"),
                        sotto_disciplina=parent_dir[:50],
                        fonte_tipo=ext.lstrip("."),
                        parole_chiave=",".join(parts[:-1])[:100],
                        affidabilita=0.5,
                        peer_reviewed=False,
                        fonte_origine="local_mac",
                        url_fonte=fpath,
                    )
                    batch.append(meta)
                    bytes_compressed += 400  # ~400 bytes per metadato L1

                    # Flush batch
                    if len(batch) >= batch_size:
                        inserted = self.db.distill_batch_metadata(batch)
                        files_indexed += inserted
                        batch.clear()

                        # Salva stato
                        self.state.save_scan_state(
                            scan_id, base_path, files_scanned,
                            files_indexed, bytes_original, bytes_compressed,
                            fpath, "running",
                        )

                        if files_scanned % 1000 == 0:
                            ratio = bytes_original / max(bytes_compressed, 1)
                            elapsed = time.time() - start_time
                            speed = files_scanned / max(elapsed, 1)
                            logger.info(
                                f"📁 Scan: {files_scanned:,} files | "
                                f"{files_indexed:,} indicizzati | "
                                f"compressione: {ratio:.0f}x | "
                                f"{speed:.0f} files/s"
                            )

                except (PermissionError, OSError):
                    continue  # Skip file non accessibili

        # Flush ultimo batch
        if batch:
            inserted = self.db.distill_batch_metadata(batch)
            files_indexed += inserted

        # Stato finale
        status = "completed" if not SHUTDOWN_REQUESTED else "paused"
        self.state.save_scan_state(
            scan_id, base_path, files_scanned, files_indexed,
            bytes_original, bytes_compressed, "", status,
        )

        elapsed = time.time() - start_time
        ratio = bytes_original / max(bytes_compressed, 1)

        logger.info("=" * 60)
        logger.info("📁 SCANSIONE LOCALE COMPLETATA")
        logger.info(f"   File scansionati:  {files_scanned:,}")
        logger.info(f"   File indicizzati:  {files_indexed:,}")
        logger.info(f"   Dati originali:    {bytes_original / (1024**2):.1f} MB")
        logger.info(f"   Metadati salvati:  {bytes_compressed / (1024**2):.3f} MB")
        logger.info(f"   Rapporto:          {ratio:.0f}x")
        logger.info(f"   Tempo:             {elapsed:.0f}s")
        logger.info("=" * 60)


# ============================================================
# CLI — INTERFACCIA LINEA DI COMANDO
# ============================================================

def cmd_harvest(args):
    """Comando harvest: scarica da API."""
    harvester = ProductionHarvester()
    target = args.target

    if args.source == "all":
        harvester.harvest_all(target, resume=not args.fresh)
    elif args.source == "openalex":
        harvester.harvest_openalex(target, resume=not args.fresh)
    elif args.source == "crossref":
        harvester.harvest_crossref(target, resume=not args.fresh)
    elif args.source == "wikipedia":
        harvester.harvest_wikipedia(target, resume=not args.fresh)
    else:
        logger.error(f"Fonte sconosciuta: {args.source}")


def cmd_local(args):
    """Comando local: scansiona e distilla file Mac."""
    distiller = LocalMacDistiller()
    path = args.path or os.path.expanduser("~/Documents")
    distiller.scan_and_distill(path)


def cmd_all(args):
    """Comando all: harvest + local."""
    cmd_harvest(args)
    if not SHUTDOWN_REQUESTED:
        cmd_local(args)


def cmd_status(args):
    """Mostra stato corrente."""
    state = HarvestStateDB()
    db = get_distilled_db()

    print("\n" + "=" * 60)
    print("VIO 83 AI ORCHESTRA — STATO HARVEST")
    print("=" * 60)

    # Progresso per fonte
    progs = state.load_all_progress()
    if progs:
        print("\n📡 FONTI REMOTE:")
        for p in progs:
            p.update_speed()
            print(f"  {p.summary()}")
    else:
        print("\n📡 Nessun harvest in corso")

    # Database
    stats = db.stats()
    print(f"\n📊 DATABASE:")
    print(f"  Documenti totali:   {stats['livello_1_metadati']:,}")
    print(f"  Con embedding:      {stats['livello_2_embedding']:,}")
    print(f"  Con riassunto:      {stats['livello_3_riassunti']:,}")
    print(f"  Con knowledge graph: {stats['livello_4_knowledge_graph']:,}")
    print(f"  Con full-text:      {stats['livello_5_testo_completo']:,}")
    print(f"  Dimensione DB:      {stats['db_size_MB']:.1f} MB")

    if stats.get("per_fonte"):
        print(f"\n  Per fonte:")
        for fonte, n in sorted(stats["per_fonte"].items(), key=lambda x: -x[1]):
            print(f"    {fonte}: {n:,}")

    if stats.get("per_categoria"):
        print(f"\n  Per categoria (top 10):")
        for cat, n in sorted(stats["per_categoria"].items(), key=lambda x: -x[1])[:10]:
            print(f"    {cat}: {n:,}")

    print("\n" + "=" * 60)


def cmd_resume(args):
    """Riprende harvest interrotto."""
    state = HarvestStateDB()
    progs = state.load_all_progress()
    paused = [p for p in progs if p.status == "paused"]

    if not paused:
        print("Nessun harvest da riprendere. Usa 'harvest' per iniziare.")
        return

    print(f"\n▶ Riprendo {len(paused)} harvest interrotti:")
    for p in paused:
        print(f"  {p.source}: {p.total_fetched:,}/{p.target:,}")

    harvester = ProductionHarvester()

    for p in paused:
        if SHUTDOWN_REQUESTED:
            break
        if p.source == "openalex":
            harvester.harvest_openalex(p.target, resume=True)
        elif p.source == "crossref":
            harvester.harvest_crossref(p.target, resume=True)
        elif p.source.startswith("wikipedia"):
            lang = p.source.split("_")[1] if "_" in p.source else "it"
            harvester.harvest_wikipedia(p.target, [lang], resume=True)


def main():
    parser = argparse.ArgumentParser(
        description="VIO 83 AI ORCHESTRA — Harvest & Distill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python3 -m backend.rag.run_harvest harvest --target 10000
  python3 -m backend.rag.run_harvest harvest --source openalex --target 1000000
  python3 -m backend.rag.run_harvest local --path ~/Documents
  python3 -m backend.rag.run_harvest all --target 100000
  python3 -m backend.rag.run_harvest status
  python3 -m backend.rag.run_harvest resume
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # harvest
    p_harvest = subparsers.add_parser("harvest", help="Scarica da fonti remote")
    p_harvest.add_argument("--target", type=int, default=100_000,
                           help="Target documenti (default: 100000)")
    p_harvest.add_argument("--source", default="all",
                           choices=["all", "openalex", "crossref", "wikipedia"],
                           help="Fonte specifica (default: all)")
    p_harvest.add_argument("--fresh", action="store_true",
                           help="Ricomincia da zero (ignora progresso)")
    p_harvest.set_defaults(func=cmd_harvest)

    # local
    p_local = subparsers.add_parser("local", help="Scansiona file locali del Mac")
    p_local.add_argument("--path", default="",
                         help="Directory da scansionare (default: ~/Documents)")
    p_local.set_defaults(func=cmd_local)

    # all
    p_all = subparsers.add_parser("all", help="Harvest + local")
    p_all.add_argument("--target", type=int, default=100_000,
                        help="Target documenti remoti")
    p_all.add_argument("--source", default="all")
    p_all.add_argument("--fresh", action="store_true")
    p_all.add_argument("--path", default="")
    p_all.set_defaults(func=cmd_all)

    # status
    p_status = subparsers.add_parser("status", help="Mostra stato corrente")
    p_status.set_defaults(func=cmd_status)

    # resume
    p_resume = subparsers.add_parser("resume", help="Riprendi harvest interrotto")
    p_resume.set_defaults(func=cmd_resume)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Crea directory data se non esiste
    os.makedirs(DATA_DIR, exist_ok=True)

    logger.info("=" * 60)
    logger.info("VIO 83 AI ORCHESTRA — Harvest & Distill")
    logger.info(f"Comando: {args.command}")
    logger.info(f"Data dir: {DATA_DIR}")
    logger.info("=" * 60)

    args.func(args)


if __name__ == "__main__":
    main()
