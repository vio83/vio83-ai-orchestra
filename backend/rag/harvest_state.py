# ============================================================
# VIO 83 AI ORCHESTRA — Copyright (c) 2026 Viorica Porcu (vio83)
# DUAL LICENSE: Proprietary + AGPL-3.0 — See LICENSE files
# ALL RIGHTS RESERVED — https://github.com/vio83/vio83-ai-orchestra
# ============================================================
"""
VIO 83 AI ORCHESTRA — Harvest State Manager
=============================================
Gestisce lo stato di harvesting per resume capability.
Salva cursori, offset, contatori in SQLite per poter
interrompere e riprendere senza perdere progresso.

Funzionalità:
- Salva posizione cursor (OpenAlex) / offset (Crossref) / page (Wikipedia)
- Traccia documenti scaricati per fonte
- Calcola ETA e velocità
- Recovery automatico da crash
- Log file per diagnostica
"""

import os
import time
import json
import sqlite3
import logging
from typing import Optional, Any
from dataclasses import dataclass, field
from contextlib import contextmanager

# ============================================================
# CONFIGURAZIONE PATHS
# ============================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
STATE_DB = os.path.join(DATA_DIR, "harvest_state.db")
LOG_DIR = os.path.join(DATA_DIR, "logs")


# ============================================================
# LOGGER
# ============================================================

def setup_logger(name: str = "harvest", log_file: str = "") -> logging.Logger:
    """Configura logger con output su file e console."""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    if not log_file:
        log_file = os.path.join(LOG_DIR, f"harvest_{time.strftime('%Y%m%d')}.log")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ============================================================
# PROGRESS TRACKER
# ============================================================

@dataclass
class HarvestProgress:
    """Stato di avanzamento per una fonte."""
    source: str = ""
    cursor: str = "*"           # OpenAlex cursor
    offset: int = 0             # Crossref/Wikipedia offset
    total_fetched: int = 0      # Documenti scaricati
    total_inserted: int = 0     # Documenti inseriti (nuovi)
    total_errors: int = 0       # Errori
    target: int = 0             # Target documenti
    started_at: float = 0.0     # Timestamp inizio
    last_batch_at: float = 0.0  # Timestamp ultimo batch
    last_batch_size: int = 0    # Dimensione ultimo batch
    speed_docs_sec: float = 0.0 # Velocità media docs/sec
    eta_seconds: float = 0.0    # Stima tempo rimanente
    status: str = "idle"        # idle, running, paused, completed, error
    extra: str = ""             # JSON per dati extra (es. wiki_lang, query)

    def update_speed(self):
        """Aggiorna velocità e ETA."""
        if self.started_at > 0 and self.total_fetched > 0:
            elapsed = time.time() - self.started_at
            self.speed_docs_sec = self.total_fetched / max(elapsed, 1)
            remaining = self.target - self.total_fetched
            if self.speed_docs_sec > 0:
                self.eta_seconds = remaining / self.speed_docs_sec
            else:
                self.eta_seconds = 0

    def eta_human(self) -> str:
        """ETA in formato leggibile."""
        self.update_speed()
        s = int(self.eta_seconds)
        if s < 60:
            return f"{s}s"
        elif s < 3600:
            return f"{s // 60}m {s % 60}s"
        elif s < 86400:
            return f"{s // 3600}h {(s % 3600) // 60}m"
        else:
            return f"{s // 86400}g {(s % 86400) // 3600}h"

    def progress_pct(self) -> float:
        """Percentuale di avanzamento."""
        if self.target <= 0:
            return 0.0
        return min(100.0, (self.total_fetched / self.target) * 100)

    def summary(self) -> str:
        """Sommario in una riga."""
        pct = self.progress_pct()
        eta = self.eta_human()
        return (
            f"[{self.source}] {self.total_fetched:,}/{self.target:,} "
            f"({pct:.1f}%) | {self.speed_docs_sec:.1f} docs/s | "
            f"ETA: {eta} | inseriti: {self.total_inserted:,} | "
            f"errori: {self.total_errors}"
        )


# ============================================================
# STATE DATABASE
# ============================================================

class HarvestStateDB:
    """
    Database SQLite per persistere lo stato di harvesting.
    Permette resume dopo interruzione o crash.
    """

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or STATE_DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS harvest_progress (
                    source TEXT PRIMARY KEY,
                    cursor TEXT DEFAULT '*',
                    offset_val INTEGER DEFAULT 0,
                    total_fetched INTEGER DEFAULT 0,
                    total_inserted INTEGER DEFAULT 0,
                    total_errors INTEGER DEFAULT 0,
                    target INTEGER DEFAULT 0,
                    started_at REAL DEFAULT 0,
                    last_batch_at REAL DEFAULT 0,
                    last_batch_size INTEGER DEFAULT 0,
                    speed_docs_sec REAL DEFAULT 0,
                    eta_seconds REAL DEFAULT 0,
                    status TEXT DEFAULT 'idle',
                    extra TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS harvest_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    source TEXT,
                    event TEXT,
                    details TEXT DEFAULT '',
                    docs_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS local_scan_state (
                    scan_id TEXT PRIMARY KEY,
                    base_path TEXT,
                    files_scanned INTEGER DEFAULT 0,
                    files_indexed INTEGER DEFAULT 0,
                    bytes_original INTEGER DEFAULT 0,
                    bytes_compressed INTEGER DEFAULT 0,
                    last_file TEXT DEFAULT '',
                    status TEXT DEFAULT 'idle',
                    started_at REAL DEFAULT 0,
                    updated_at REAL DEFAULT 0
                )
            """)

    # --- Progress CRUD ---

    def save_progress(self, p: HarvestProgress):
        """Salva o aggiorna il progresso."""
        p.update_speed()
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO harvest_progress
                (source, cursor, offset_val, total_fetched, total_inserted,
                 total_errors, target, started_at, last_batch_at,
                 last_batch_size, speed_docs_sec, eta_seconds, status, extra)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                p.source, p.cursor, p.offset, p.total_fetched,
                p.total_inserted, p.total_errors, p.target,
                p.started_at, p.last_batch_at, p.last_batch_size,
                p.speed_docs_sec, p.eta_seconds, p.status, p.extra,
            ))

    def load_progress(self, source: str) -> Optional[HarvestProgress]:
        """Carica il progresso per una fonte."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM harvest_progress WHERE source = ?", (source,)
            ).fetchone()
            if not row:
                return None
            return HarvestProgress(
                source=row["source"],
                cursor=row["cursor"],
                offset=row["offset_val"],
                total_fetched=row["total_fetched"],
                total_inserted=row["total_inserted"],
                total_errors=row["total_errors"],
                target=row["target"],
                started_at=row["started_at"],
                last_batch_at=row["last_batch_at"],
                last_batch_size=row["last_batch_size"],
                speed_docs_sec=row["speed_docs_sec"],
                eta_seconds=row["eta_seconds"],
                status=row["status"],
                extra=row["extra"],
            )

    def load_all_progress(self) -> list[HarvestProgress]:
        """Carica tutti i progressi."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM harvest_progress").fetchall()
            results = []
            for row in rows:
                results.append(HarvestProgress(
                    source=row["source"],
                    cursor=row["cursor"],
                    offset=row["offset_val"],
                    total_fetched=row["total_fetched"],
                    total_inserted=row["total_inserted"],
                    total_errors=row["total_errors"],
                    target=row["target"],
                    started_at=row["started_at"],
                    last_batch_at=row["last_batch_at"],
                    last_batch_size=row["last_batch_size"],
                    speed_docs_sec=row["speed_docs_sec"],
                    eta_seconds=row["eta_seconds"],
                    status=row["status"],
                    extra=row["extra"],
                ))
            return results

    def reset_progress(self, source: str):
        """Reset completo per una fonte."""
        with self._conn() as conn:
            conn.execute("DELETE FROM harvest_progress WHERE source = ?", (source,))

    # --- Log ---

    def log_event(self, source: str, event: str, details: str = "", docs: int = 0):
        """Logga un evento nel database."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO harvest_log (timestamp, source, event, details, docs_count) "
                "VALUES (?,?,?,?,?)",
                (time.time(), source, event, details, docs)
            )

    def get_recent_logs(self, source: str = "", limit: int = 50) -> list[dict]:
        """Ultimi log."""
        with self._conn() as conn:
            if source:
                rows = conn.execute(
                    "SELECT * FROM harvest_log WHERE source = ? "
                    "ORDER BY timestamp DESC LIMIT ?", (source, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM harvest_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    # --- Local Scan State ---

    def save_scan_state(self, scan_id: str, base_path: str,
                        files_scanned: int, files_indexed: int,
                        bytes_original: int, bytes_compressed: int,
                        last_file: str, status: str):
        """Salva stato scansione locale."""
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO local_scan_state
                (scan_id, base_path, files_scanned, files_indexed,
                 bytes_original, bytes_compressed, last_file, status,
                 started_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,
                    COALESCE((SELECT started_at FROM local_scan_state WHERE scan_id=?), ?),
                    ?)
            """, (
                scan_id, base_path, files_scanned, files_indexed,
                bytes_original, bytes_compressed, last_file, status,
                scan_id, time.time(), time.time(),
            ))

    def load_scan_state(self, scan_id: str) -> Optional[dict]:
        """Carica stato scansione locale."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM local_scan_state WHERE scan_id = ?",
                (scan_id,)
            ).fetchone()
            return dict(row) if row else None

    # --- Statistiche globali ---

    def global_stats(self) -> dict:
        """Statistiche globali di harvesting."""
        with self._conn() as conn:
            progs = conn.execute(
                "SELECT source, total_fetched, total_inserted, status FROM harvest_progress"
            ).fetchall()
            total_fetched = sum(r["total_fetched"] for r in progs)
            total_inserted = sum(r["total_inserted"] for r in progs)
            return {
                "total_fetched": total_fetched,
                "total_inserted": total_inserted,
                "sources": {r["source"]: {
                    "fetched": r["total_fetched"],
                    "inserted": r["total_inserted"],
                    "status": r["status"],
                } for r in progs},
            }
