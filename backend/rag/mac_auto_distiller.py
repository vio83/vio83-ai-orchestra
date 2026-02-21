#!/usr/bin/env python3
# ============================================================
# VIO 83 AI ORCHESTRA — Copyright (c) 2026 Viorica Porcu (vio83)
# DUAL LICENSE: Proprietary + AGPL-3.0 — See LICENSE files
# ALL RIGHTS RESERVED — https://github.com/vio83/vio83-ai-orchestra
# ============================================================
"""
VIO 83 AI ORCHESTRA — Mac Auto-Distiller Daemon
=================================================
Daemon PERMANENTE che gira in background sul Mac e:

1. MONITORA IL FILESYSTEM IN TEMPO REALE (FSEvents/watchdog)
   - Ogni file nuovo o modificato viene automaticamente distillato
   - Metadati Level1 estratti e indicizzati nel database
   - Trasparente: i file rimangono esattamente dove sono

2. MONITORA PROCESSI E APP
   - Traccia quali app girano, quando, per quanto tempo
   - Registra sessioni di lavoro come metadati

3. COMPRESSIONE TRASPARENTE
   - Il Mac funziona identico a prima
   - In background, tutto viene indicizzato nel knowledge DB
   - Ricerca full-text su TUTTO il Mac in millisecondi

PRINCIPIO FONDAMENTALE:
  - I file ORIGINALI non vengono MAI toccati, spostati o modificati
  - Il daemon crea SOLO metadati compressi nel database
  - Il Mac funziona esattamente come prima, ma ora ha un
    indice di ricerca globale e knowledge graph di tutto

INSTALLAZIONE:
  python3 -m backend.rag.mac_auto_distiller install
  python3 -m backend.rag.mac_auto_distiller start
  python3 -m backend.rag.mac_auto_distiller stop
  python3 -m backend.rag.mac_auto_distiller status
  python3 -m backend.rag.mac_auto_distiller uninstall
"""

import os
import sys
import time
import json
import signal
import hashlib
import sqlite3
import logging
import argparse
import subprocess
import platform
from pathlib import Path
from typing import Optional
from datetime import datetime
from contextlib import contextmanager

# ============================================================
# PATH SETUP
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.rag.harvest_state import (
    HarvestStateDB, HarvestProgress, setup_logger, DATA_DIR, LOG_DIR
)
from backend.rag.knowledge_distiller import (
    Level1_Metadata, DistilledKnowledgeDB, get_distilled_db,
)

# ============================================================
# CONFIGURAZIONE
# ============================================================

DAEMON_NAME = "ai.vio83.orchestra.autodistiller"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{DAEMON_NAME}.plist")
PID_FILE = os.path.join(DATA_DIR, "autodistiller.pid")
CONFIG_FILE = os.path.join(DATA_DIR, "autodistiller_config.json")

# Directory da monitorare di default
DEFAULT_WATCH_DIRS = [
    "~/Documents",
    "~/Desktop",
    "~/Downloads",
    "~/Pictures",
    "~/Movies",
    "~/Music",
    "~/Projects",
]

# Directory SEMPRE escluse
EXCLUDE_DIRS = {
    ".git", ".svn", "node_modules", "__pycache__", ".cache",
    ".Trash", ".Spotlight-V100", ".fseventsd", ".DocumentRevisions-V100",
    "Library", "DerivedData", ".npm", ".yarn", ".pip", ".conda",
    "venv", ".venv", "env", ".env", ".tox", ".mypy_cache",
    "Caches", "CacheStorage", "Cache", "GPUCache", "ShaderCache",
    "com.apple.bird", "CloudStorage", ".Trashes",
}

# Estensioni supportate per indicizzazione
SUPPORTED_EXTENSIONS = {
    # Documenti
    ".txt", ".md", ".rst", ".tex", ".rtf",
    ".pdf", ".doc", ".docx", ".odt",
    ".epub", ".mobi",
    # Web
    ".html", ".htm", ".xml", ".xhtml",
    # Dati
    ".json", ".csv", ".tsv", ".yaml", ".yml", ".toml",
    ".sql", ".sqlite", ".db",
    # Codice
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".cpp", ".c", ".h", ".hpp",
    ".rb", ".go", ".rs", ".swift", ".kt", ".kts",
    ".sh", ".bash", ".zsh", ".fish",
    ".r", ".m", ".jl", ".lua", ".php",
    ".css", ".scss", ".less",
    ".ipynb",
    # Config
    ".ini", ".cfg", ".conf", ".env",
    ".plist", ".properties",
    # Media metadata (solo nome file)
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".mp3", ".wav", ".flac", ".aac", ".m4a",
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    # Archivi (solo nome)
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    # Presentazioni / Fogli
    ".pptx", ".ppt", ".odp",
    ".xlsx", ".xls", ".ods",
    # Log
    ".log",
}

# Categorie per estensione
EXT_CATEGORIES = {
    ".pdf": "documenti", ".doc": "documenti", ".docx": "documenti",
    ".txt": "documenti", ".md": "documenti", ".rst": "documenti",
    ".rtf": "documenti", ".odt": "documenti", ".tex": "documenti",
    ".epub": "libri", ".mobi": "libri",
    ".html": "fonti_online", ".htm": "fonti_online",
    ".py": "informatica", ".js": "informatica", ".ts": "informatica",
    ".jsx": "informatica", ".tsx": "informatica",
    ".java": "informatica", ".cpp": "informatica", ".c": "informatica",
    ".h": "informatica", ".hpp": "informatica",
    ".rb": "informatica", ".go": "informatica", ".rs": "informatica",
    ".swift": "informatica", ".kt": "informatica",
    ".sh": "informatica", ".bash": "informatica", ".zsh": "informatica",
    ".sql": "informatica", ".r": "informatica", ".ipynb": "informatica",
    ".css": "informatica", ".scss": "informatica",
    ".json": "dati", ".csv": "dati", ".tsv": "dati",
    ".xml": "dati", ".yaml": "dati", ".yml": "dati",
    ".pptx": "documenti", ".ppt": "documenti",
    ".xlsx": "dati", ".xls": "dati",
    ".png": "media", ".jpg": "media", ".jpeg": "media",
    ".gif": "media", ".svg": "media", ".webp": "media",
    ".mp3": "media", ".wav": "media", ".flac": "media",
    ".mp4": "media", ".mov": "media", ".avi": "media", ".mkv": "media",
    ".zip": "archivi", ".tar": "archivi", ".gz": "archivi",
    ".bz2": "archivi", ".7z": "archivi", ".rar": "archivi",
    ".log": "dati", ".toml": "dati", ".ini": "dati",
    ".cfg": "dati", ".conf": "dati", ".env": "dati",
    ".plist": "dati", ".properties": "dati",
    ".rtf": "documenti", ".odt": "documenti",
    ".mobi": "libri", ".xhtml": "fonti_online",
    ".odp": "documenti", ".ods": "dati",
    ".less": "informatica", ".fish": "informatica",
    ".jl": "informatica", ".lua": "informatica", ".php": "informatica",
    ".kts": "informatica", ".hpp": "informatica",
    ".m4a": "media", ".aac": "media",
    ".webm": "media", ".flac": "media",
    ".sqlite": "dati", ".db": "dati",
    ".tsx": "informatica", ".jsx": "informatica",
}


# ============================================================
# FILESYSTEM WATCHER (compatibile macOS senza dipendenze)
# ============================================================

class FSEventsWatcher:
    """
    File system watcher nativo macOS usando polling efficiente.
    Fallback universale che funziona su qualsiasi sistema.
    Se watchdog è installato, usa FSEvents nativo (più efficiente).
    """

    def __init__(self, watch_dirs: list[str], callback, interval: float = 5.0):
        self.watch_dirs = [os.path.expanduser(d) for d in watch_dirs]
        self.callback = callback
        self.interval = interval
        self._running = False
        self._known_files: dict[str, float] = {}  # path → mtime
        self._watchdog_observer = None

    def _should_skip_dir(self, dirpath: str) -> bool:
        """Verifica se una directory deve essere esclusa."""
        parts = dirpath.split(os.sep)
        return any(p in EXCLUDE_DIRS or p.startswith(".") for p in parts)

    def _should_index_file(self, filepath: str) -> bool:
        """Verifica se un file deve essere indicizzato."""
        ext = os.path.splitext(filepath)[1].lower()
        return ext in SUPPORTED_EXTENSIONS

    def _scan_directory(self, base_dir: str) -> dict[str, float]:
        """Scansione rapida di una directory."""
        files = {}
        try:
            for root, dirs, fnames in os.walk(base_dir, topdown=True):
                # Filtra directory
                dirs[:] = [
                    d for d in dirs
                    if d not in EXCLUDE_DIRS and not d.startswith(".")
                ]
                for fname in fnames:
                    fpath = os.path.join(root, fname)
                    if self._should_index_file(fpath):
                        try:
                            st = os.stat(fpath)
                            if 0 < st.st_size < 500_000_000:  # 0 < size < 500MB
                                files[fpath] = st.st_mtime
                        except (OSError, PermissionError):
                            pass
        except (OSError, PermissionError):
            pass
        return files

    def _try_watchdog(self) -> bool:
        """Prova a usare watchdog per FSEvents nativi (più efficiente)."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class Handler(FileSystemEventHandler):
                def __init__(self, watcher):
                    self.watcher = watcher

                def on_created(self, event):
                    if not event.is_directory and self.watcher._should_index_file(event.src_path):
                        self.watcher.callback([event.src_path], [])

                def on_modified(self, event):
                    if not event.is_directory and self.watcher._should_index_file(event.src_path):
                        self.watcher.callback([], [event.src_path])

            observer = Observer()
            handler = Handler(self)
            for d in self.watch_dirs:
                if os.path.isdir(d):
                    observer.schedule(handler, d, recursive=True)

            observer.start()
            self._watchdog_observer = observer
            return True
        except ImportError:
            return False

    def start(self):
        """Avvia il monitoraggio."""
        self._running = True

        # Tentativo watchdog (FSEvents nativi)
        if self._try_watchdog():
            logger = logging.getLogger("autodistiller")
            logger.info("✅ Watchdog FSEvents attivo (monitoraggio nativo macOS)")
            # Con watchdog, polling di backup ogni 60 secondi
            while self._running:
                time.sleep(60)
            return

        # Fallback: polling
        logger = logging.getLogger("autodistiller")
        logger.info("📂 Modalità polling (installa 'watchdog' per FSEvents nativi)")

        # Prima scansione completa
        for d in self.watch_dirs:
            if os.path.isdir(d):
                scanned = self._scan_directory(d)
                self._known_files.update(scanned)
        logger.info(f"   Scansione iniziale: {len(self._known_files):,} file monitorati")

        # Loop di polling
        while self._running:
            time.sleep(self.interval)
            new_files = []
            modified_files = []

            for d in self.watch_dirs:
                if not os.path.isdir(d):
                    continue

                current = self._scan_directory(d)

                for fpath, mtime in current.items():
                    if fpath not in self._known_files:
                        new_files.append(fpath)
                    elif mtime > self._known_files.get(fpath, 0):
                        modified_files.append(fpath)

                self._known_files.update(current)

            if new_files or modified_files:
                self.callback(new_files, modified_files)

    def stop(self):
        """Ferma il monitoraggio."""
        self._running = False
        if self._watchdog_observer:
            self._watchdog_observer.stop()
            self._watchdog_observer.join(timeout=5)


# ============================================================
# PROCESS MONITOR
# ============================================================

class ProcessMonitor:
    """
    Monitora i processi del Mac e registra sessioni di lavoro.
    Traccia app aperte, tempo di utilizzo, focus app.
    """

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or os.path.join(DATA_DIR, "process_log.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
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
                CREATE TABLE IF NOT EXISTS process_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    pid INTEGER,
                    name TEXT,
                    cpu_pct REAL DEFAULT 0,
                    mem_mb REAL DEFAULT 0,
                    status TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_name TEXT,
                    started_at REAL,
                    ended_at REAL DEFAULT 0,
                    duration_sec REAL DEFAULT 0,
                    category TEXT DEFAULT ''
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ps_ts ON process_snapshots(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_as_app ON app_sessions(app_name)"
            )

    def snapshot_processes(self):
        """Cattura uno snapshot dei processi correnti."""
        try:
            # Usa ps nativo macOS
            result = subprocess.run(
                ["ps", "-eo", "pid,pcpu,pmem,comm"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return

            now = time.time()
            rows = []
            for line in result.stdout.strip().split("\n")[1:]:  # skip header
                parts = line.split(None, 3)
                if len(parts) < 4:
                    continue
                try:
                    pid = int(parts[0])
                    cpu = float(parts[1])
                    mem = float(parts[2])
                    name = parts[3].strip()
                    # Solo processi significativi (>0.1% CPU o >0.5% MEM)
                    if cpu > 0.1 or mem > 0.5:
                        rows.append((now, pid, os.path.basename(name), cpu, mem, "running"))
                except (ValueError, IndexError):
                    continue

            if rows:
                with self._conn() as conn:
                    conn.executemany(
                        "INSERT INTO process_snapshots "
                        "(timestamp, pid, name, cpu_pct, mem_mb, status) "
                        "VALUES (?,?,?,?,?,?)", rows
                    )

        except (subprocess.TimeoutExpired, OSError):
            pass

    def get_top_apps(self, hours: int = 24) -> list[dict]:
        """Top app per CPU negli ultimi N ore."""
        cutoff = time.time() - (hours * 3600)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT name, AVG(cpu_pct) as avg_cpu, COUNT(*) as samples "
                "FROM process_snapshots WHERE timestamp > ? "
                "GROUP BY name ORDER BY avg_cpu DESC LIMIT 20",
                (cutoff,)
            ).fetchall()
            return [dict(r) for r in rows]

    def stats(self) -> dict:
        """Statistiche del monitor processi."""
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM process_snapshots"
            ).fetchone()[0]
            unique = conn.execute(
                "SELECT COUNT(DISTINCT name) FROM process_snapshots"
            ).fetchone()[0]
            return {
                "total_snapshots": total,
                "unique_processes": unique,
            }


# ============================================================
# AUTO-DISTILLER DAEMON
# ============================================================

class AutoDistillerDaemon:
    """
    Daemon principale che orchestra:
    - Monitoraggio filesystem in tempo reale
    - Indicizzazione automatica nuovi file
    - Monitoraggio processi
    - Tutto in background, trasparente, permanente
    """

    def __init__(self):
        self.logger = setup_logger("autodistiller",
                                    os.path.join(LOG_DIR, "autodistiller.log"))
        self.db = get_distilled_db()
        self.state = HarvestStateDB()
        self.process_monitor = ProcessMonitor()
        self._running = False
        self._config = self._load_config()
        self._stats = {
            "files_indexed": 0,
            "files_updated": 0,
            "errors": 0,
            "started_at": 0,
        }

    def _load_config(self) -> dict:
        """Carica configurazione."""
        default = {
            "watch_dirs": DEFAULT_WATCH_DIRS,
            "poll_interval": 5.0,
            "process_interval": 60.0,
            "exclude_dirs": list(EXCLUDE_DIRS),
            "max_file_size_mb": 500,
            "auto_harvest": False,
            "harvest_target": 100000,
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    saved = json.load(f)
                default.update(saved)
            except (json.JSONDecodeError, OSError):
                pass
        return default

    def _save_config(self):
        """Salva configurazione."""
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._config, f, indent=2)

    def _on_files_changed(self, new_files: list[str], modified_files: list[str]):
        """Callback chiamato quando file cambiano."""
        batch = []

        for fpath in new_files + modified_files:
            try:
                stat = os.stat(fpath)
                if stat.st_size == 0:
                    continue

                ext = os.path.splitext(fpath)[1].lower()
                fname = os.path.basename(fpath)
                doc_id = hashlib.md5(fpath.encode()).hexdigest()[:16]

                # Trova la directory di contesto
                parts = fpath.split(os.sep)
                parent = parts[-2] if len(parts) > 1 else ""

                meta = Level1_Metadata(
                    doc_id=doc_id,
                    titolo=os.path.splitext(fname)[0][:200],
                    autore=os.path.expanduser("~").split(os.sep)[-1],
                    anno=int(datetime.fromtimestamp(stat.st_mtime).strftime("%Y")),
                    lingua="it",
                    categoria=EXT_CATEGORIES.get(ext, "documenti"),
                    sotto_disciplina=parent[:50],
                    fonte_tipo=ext.lstrip("."),
                    parole_chiave=",".join(parts[-3:-1])[:100] if len(parts) > 2 else "",
                    affidabilita=0.5,
                    peer_reviewed=False,
                    fonte_origine="mac_auto",
                    url_fonte=fpath,
                )
                batch.append(meta)

            except (OSError, PermissionError):
                self._stats["errors"] += 1

        if batch:
            try:
                inserted = self.db.distill_batch_metadata(batch)
                self._stats["files_indexed"] += len([f for f in new_files if f])
                self._stats["files_updated"] += len([f for f in modified_files if f])

                if len(batch) >= 5:
                    self.logger.info(
                        f"📄 Indicizzati {len(batch)} file "
                        f"({len(new_files)} nuovi, {len(modified_files)} modificati)"
                    )
            except Exception as e:
                self.logger.error(f"Errore indicizzazione batch: {e}")
                self._stats["errors"] += 1

    def run(self):
        """Avvia il daemon."""
        self._running = True
        self._stats["started_at"] = time.time()

        # Scrivi PID
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))

        self.logger.info("=" * 60)
        self.logger.info("VIO 83 AI ORCHESTRA — Auto-Distiller Daemon AVVIATO")
        self.logger.info(f"  PID: {os.getpid()}")
        self.logger.info(f"  Directory monitorate: {len(self._config['watch_dirs'])}")
        for d in self._config["watch_dirs"]:
            expanded = os.path.expanduser(d)
            exists = "✅" if os.path.isdir(expanded) else "⚠️ non trovata"
            self.logger.info(f"    {d} {exists}")
        self.logger.info(f"  Intervallo polling: {self._config['poll_interval']}s")
        self.logger.info(f"  Intervallo processi: {self._config['process_interval']}s")
        self.logger.info("=" * 60)

        # Signal handlers
        def shutdown(sig, frame):
            self.logger.info("🛑 Shutdown richiesto...")
            self._running = False

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        # Avvia filesystem watcher in thread separato
        import threading

        watcher = FSEventsWatcher(
            self._config["watch_dirs"],
            self._on_files_changed,
            interval=self._config["poll_interval"],
        )

        watcher_thread = threading.Thread(target=watcher.start, daemon=True)
        watcher_thread.start()

        # Loop principale: process monitor + statistiche
        last_process_check = 0
        last_status_log = 0

        try:
            while self._running:
                now = time.time()

                # Snapshot processi ogni N secondi
                if now - last_process_check >= self._config["process_interval"]:
                    try:
                        self.process_monitor.snapshot_processes()
                    except Exception as e:
                        self.logger.error(f"Errore process monitor: {e}")
                    last_process_check = now

                # Log statistiche ogni 5 minuti
                if now - last_status_log >= 300:
                    elapsed = now - self._stats["started_at"]
                    hours = elapsed / 3600
                    db_stats = self.db.stats()
                    self.logger.info(
                        f"📊 Stato: {db_stats['livello_1_metadati']:,} docs in DB | "
                        f"{self._stats['files_indexed']} nuovi | "
                        f"{self._stats['files_updated']} aggiornati | "
                        f"{self._stats['errors']} errori | "
                        f"uptime: {hours:.1f}h"
                    )
                    last_status_log = now

                time.sleep(1)

        finally:
            watcher.stop()
            # Rimuovi PID file
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)

            self.logger.info("=" * 60)
            self.logger.info("Auto-Distiller Daemon FERMATO")
            self.logger.info(f"  File indicizzati: {self._stats['files_indexed']}")
            self.logger.info(f"  File aggiornati: {self._stats['files_updated']}")
            self.logger.info(f"  Errori: {self._stats['errors']}")
            self.logger.info("=" * 60)


# ============================================================
# LAUNCHAGENT MANAGER
# ============================================================

def generate_plist() -> str:
    """Genera il file plist per LaunchAgent macOS."""
    python_path = sys.executable
    script_path = os.path.abspath(__file__)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{DAEMON_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
        <string>run</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>{os.path.join(LOG_DIR, "autodistiller_stdout.log")}</string>

    <key>StandardErrorPath</key>
    <string>{os.path.join(LOG_DIR, "autodistiller_stderr.log")}</string>

    <key>WorkingDirectory</key>
    <string>{PROJECT_ROOT}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>PYTHONPATH</key>
        <string>{PROJECT_ROOT}</string>
    </dict>

    <key>ProcessType</key>
    <string>Background</string>

    <key>LowPriorityIO</key>
    <true/>

    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>"""


def install_daemon():
    """Installa il LaunchAgent."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)

    plist_content = generate_plist()
    with open(PLIST_PATH, "w") as f:
        f.write(plist_content)

    # Salva config di default
    daemon = AutoDistillerDaemon()
    daemon._save_config()

    print(f"✅ LaunchAgent installato: {PLIST_PATH}")
    print(f"   Config: {CONFIG_FILE}")
    print(f"   Log: {LOG_DIR}")
    print(f"\n   Per avviare: python3 -m backend.rag.mac_auto_distiller start")
    print(f"   Oppure: launchctl load {PLIST_PATH}")
    print(f"\n   Si avvierà automaticamente ad ogni login!")


def uninstall_daemon():
    """Rimuove il LaunchAgent."""
    # Ferma se in esecuzione
    stop_daemon()

    if os.path.exists(PLIST_PATH):
        try:
            subprocess.run(["launchctl", "unload", PLIST_PATH],
                           capture_output=True, timeout=10)
        except Exception:
            pass
        os.remove(PLIST_PATH)
        print(f"✅ LaunchAgent rimosso: {PLIST_PATH}")
    else:
        print("ℹ️  LaunchAgent non trovato")


def start_daemon():
    """Avvia il daemon."""
    if not os.path.exists(PLIST_PATH):
        print("⚠️  LaunchAgent non installato. Esegui prima 'install'")
        return

    # Controlla se già in esecuzione
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)
            print(f"ℹ️  Daemon già in esecuzione (PID: {pid})")
            return
        except OSError:
            os.remove(PID_FILE)

    result = subprocess.run(
        ["launchctl", "load", PLIST_PATH],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        time.sleep(1)
        if os.path.exists(PID_FILE):
            with open(PID_FILE) as f:
                pid = f.read().strip()
            print(f"✅ Daemon avviato (PID: {pid})")
        else:
            print("✅ Daemon avviato (launchctl)")
    else:
        print(f"❌ Errore avvio: {result.stderr}")


def stop_daemon():
    """Ferma il daemon."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            print(f"✅ Daemon fermato (PID: {pid})")
        except (OSError, ValueError):
            pass
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

    if os.path.exists(PLIST_PATH):
        try:
            subprocess.run(["launchctl", "unload", PLIST_PATH],
                           capture_output=True, timeout=10)
        except Exception:
            pass


def show_status():
    """Mostra stato del daemon."""
    print("\n" + "=" * 60)
    print("VIO 83 AI ORCHESTRA — Auto-Distiller Status")
    print("=" * 60)

    # Stato daemon
    running = False
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            running = True
            print(f"\n🟢 Daemon ATTIVO (PID: {pid})")
        except (OSError, ValueError):
            print("\n🔴 Daemon NON attivo (PID file stale)")
    else:
        print("\n🔴 Daemon NON attivo")

    # LaunchAgent
    if os.path.exists(PLIST_PATH):
        print(f"✅ LaunchAgent installato: {PLIST_PATH}")
    else:
        print("⚠️  LaunchAgent NON installato")

    # Database
    try:
        db = get_distilled_db()
        stats = db.stats()
        print(f"\n📊 Database Knowledge:")
        print(f"   Documenti totali:   {stats['livello_1_metadati']:,}")
        print(f"   Con embedding:      {stats['livello_2_embedding']:,}")
        print(f"   Con riassunto:      {stats['livello_3_riassunti']:,}")
        print(f"   Dimensione DB:      {stats['db_size_MB']:.1f} MB")

        if stats.get("per_fonte"):
            print(f"\n   Per fonte:")
            for fonte, n in sorted(stats["per_fonte"].items(), key=lambda x: -x[1]):
                print(f"     {fonte}: {n:,}")

        if stats.get("per_categoria"):
            print(f"\n   Per categoria:")
            for cat, n in sorted(stats["per_categoria"].items(), key=lambda x: -x[1])[:10]:
                print(f"     {cat}: {n:,}")
    except Exception as e:
        print(f"\n⚠️  Database non accessibile: {e}")

    # Process monitor
    try:
        pm = ProcessMonitor()
        pm_stats = pm.stats()
        print(f"\n📡 Process Monitor:")
        print(f"   Snapshot totali:    {pm_stats['total_snapshots']:,}")
        print(f"   Processi unici:     {pm_stats['unique_processes']:,}")

        top = pm.get_top_apps(24)
        if top:
            print(f"\n   Top app (ultime 24h):")
            for app in top[:5]:
                print(f"     {app['name']}: {app['avg_cpu']:.1f}% CPU ({app['samples']} samples)")
    except Exception:
        pass

    # Config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            print(f"\n⚙️  Configurazione:")
            print(f"   Directory monitorate: {len(config.get('watch_dirs', []))}")
            for d in config.get("watch_dirs", []):
                print(f"     {d}")
            print(f"   Intervallo polling: {config.get('poll_interval', 5)}s")
        except Exception:
            pass

    # Log recenti
    log_file = os.path.join(LOG_DIR, "autodistiller.log")
    if os.path.exists(log_file):
        try:
            with open(log_file) as f:
                lines = f.readlines()
            last_lines = lines[-5:] if len(lines) > 5 else lines
            print(f"\n📋 Ultimi log:")
            for line in last_lines:
                print(f"   {line.rstrip()}")
        except Exception:
            pass

    print("\n" + "=" * 60)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="VIO 83 AI Orchestra — Auto-Distiller Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comandi:
  install   Installa il LaunchAgent (auto-start al login)
  uninstall Rimuovi il LaunchAgent
  start     Avvia il daemon
  stop      Ferma il daemon
  status    Mostra stato corrente
  run       Esegui in foreground (per debug)

Esempio:
  python3 -m backend.rag.mac_auto_distiller install
  python3 -m backend.rag.mac_auto_distiller start
  python3 -m backend.rag.mac_auto_distiller status
        """,
    )

    parser.add_argument("command", nargs="?", default="status",
                        choices=["install", "uninstall", "start", "stop",
                                "status", "run"],
                        help="Comando da eseguire")
    parser.add_argument("--dirs", nargs="*",
                        help="Directory da monitorare (override config)")

    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    if args.command == "install":
        install_daemon()
    elif args.command == "uninstall":
        uninstall_daemon()
    elif args.command == "start":
        start_daemon()
    elif args.command == "stop":
        stop_daemon()
    elif args.command == "status":
        show_status()
    elif args.command == "run":
        # Esecuzione in foreground
        if args.dirs:
            daemon = AutoDistillerDaemon()
            daemon._config["watch_dirs"] = args.dirs
        else:
            daemon = AutoDistillerDaemon()
        daemon.run()


if __name__ == "__main__":
    main()
