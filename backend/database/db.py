"""
VIO 83 AI ORCHESTRA - Database SQLite per Conversazioni
Gestisce persistenza conversazioni, messaggi, metriche provider.
Funziona interamente in locale — zero dati trasmessi.
"""

import sqlite3
import json
import uuid
import time
import os
from contextlib import contextmanager
from typing import Optional

# Path database nella cartella del progetto
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "vio83_orchestra.db")


def get_db_path() -> str:
    """Ritorna il path del database, creando la directory se necessario."""
    os.makedirs(DB_DIR, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection():
    """Context manager per connessione SQLite thread-safe."""
    conn = sqlite3.connect(get_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Inizializza tutte le tabelle del database."""
    with get_connection() as conn:
        conn.executescript("""
            -- Conversazioni
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'Nuova conversazione',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                mode TEXT NOT NULL DEFAULT 'local',
                primary_provider TEXT DEFAULT 'ollama',
                message_count INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                archived INTEGER DEFAULT 0
            );

            -- Messaggi
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                provider TEXT,
                model TEXT,
                tokens_used INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                verified INTEGER,
                quality_score REAL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            -- Metriche provider (per analytics)
            CREATE TABLE IF NOT EXISTS provider_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                request_type TEXT,
                tokens_used INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 1,
                error_message TEXT,
                timestamp REAL NOT NULL
            );

            -- API Keys criptate (solo per backend, non esposte)
            CREATE TABLE IF NOT EXISTS api_keys (
                provider TEXT PRIMARY KEY,
                encrypted_key TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_used REAL
            );

            -- Impostazioni utente
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            -- Indici per performance
            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_metrics_provider ON provider_metrics(provider);
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON provider_metrics(timestamp);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
        """)
    print(f"📦 Database inizializzato: {get_db_path()}")


# === CONVERSAZIONI ===

def create_conversation(title: str = "Nuova conversazione", mode: str = "local",
                        provider: str = "ollama") -> dict:
    """Crea una nuova conversazione."""
    conv_id = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, mode, primary_provider) VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, title, now, now, mode, provider)
        )
    return {"id": conv_id, "title": title, "created_at": now, "mode": mode}


def list_conversations(limit: int = 50, offset: int = 0, include_archived: bool = False) -> list[dict]:
    """Lista conversazioni ordinate per ultimo aggiornamento."""
    with get_connection() as conn:
        query = "SELECT * FROM conversations"
        if not include_archived:
            query += " WHERE archived = 0"
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        rows = conn.execute(query, (limit, offset)).fetchall()
        return [dict(r) for r in rows]


def get_conversation(conv_id: str) -> Optional[dict]:
    """Ottieni una conversazione con tutti i messaggi."""
    with get_connection() as conn:
        conv = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        if not conv:
            return None
        messages = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
            (conv_id,)
        ).fetchall()
        result = dict(conv)
        result["messages"] = [dict(m) for m in messages]
        return result


def update_conversation_title(conv_id: str, title: str):
    """Aggiorna il titolo di una conversazione."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, time.time(), conv_id)
        )


def delete_conversation(conv_id: str):
    """Elimina una conversazione e tutti i suoi messaggi."""
    with get_connection() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))


def archive_conversation(conv_id: str):
    """Archivia una conversazione."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE conversations SET archived = 1, updated_at = ? WHERE id = ?",
            (time.time(), conv_id)
        )


# === MESSAGGI ===

def add_message(conversation_id: str, role: str, content: str,
                provider: str = None, model: str = None,
                tokens_used: int = 0, latency_ms: int = 0,
                verified: bool = None, quality_score: float = None) -> dict:
    """Aggiungi un messaggio a una conversazione."""
    msg_id = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO messages (id, conversation_id, role, content, provider, model,
               tokens_used, latency_ms, verified, quality_score, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, conversation_id, role, content, provider, model,
             tokens_used, latency_ms, 1 if verified else (0 if verified is not None else None),
             quality_score, now)
        )
        # Aggiorna conversazione
        conn.execute(
            """UPDATE conversations SET
               updated_at = ?,
               message_count = message_count + 1,
               total_tokens = total_tokens + ?
               WHERE id = ?""",
            (now, tokens_used, conversation_id)
        )
    return {"id": msg_id, "role": role, "content": content, "timestamp": now}


# === METRICHE ===

def log_metric(provider: str, model: str, request_type: str = None,
               tokens_used: int = 0, latency_ms: int = 0,
               success: bool = True, error_message: str = None):
    """Registra una metrica per analytics."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO provider_metrics (provider, model, request_type,
               tokens_used, latency_ms, success, error_message, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (provider, model, request_type, tokens_used, latency_ms,
             1 if success else 0, error_message, time.time())
        )


def get_metrics_summary(days: int = 30) -> dict:
    """Ottieni un sommario delle metriche degli ultimi N giorni."""
    since = time.time() - (days * 86400)
    with get_connection() as conn:
        # Totali per provider
        rows = conn.execute("""
            SELECT provider,
                   COUNT(*) as total_calls,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                   SUM(tokens_used) as total_tokens,
                   AVG(latency_ms) as avg_latency,
                   MIN(latency_ms) as min_latency,
                   MAX(latency_ms) as max_latency
            FROM provider_metrics
            WHERE timestamp > ?
            GROUP BY provider
            ORDER BY total_calls DESC
        """, (since,)).fetchall()

        providers = {}
        for r in rows:
            d = dict(r)
            d["success_rate"] = round(d["successful"] / d["total_calls"] * 100, 1) if d["total_calls"] > 0 else 0
            d["avg_latency"] = round(d["avg_latency"] or 0)
            providers[d["provider"]] = d

        # Totali generali
        total = conn.execute("""
            SELECT COUNT(*) as total_calls,
                   SUM(tokens_used) as total_tokens,
                   AVG(latency_ms) as avg_latency
            FROM provider_metrics WHERE timestamp > ?
        """, (since,)).fetchone()

        return {
            "period_days": days,
            "providers": providers,
            "totals": dict(total) if total else {},
            "conversation_count": conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE created_at > ?", (since,)
            ).fetchone()[0],
        }


# === IMPOSTAZIONI ===

def get_setting(key: str, default: str = None) -> Optional[str]:
    """Ottieni un'impostazione."""
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    """Salva un'impostazione."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, time.time())
        )


def get_all_settings() -> dict:
    """Ottieni tutte le impostazioni."""
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


# === AUTO-TITOLO ===

def auto_title_from_message(message: str) -> str:
    """Genera un titolo automatico dal primo messaggio dell'utente."""
    # Prendi le prime parole significative
    clean = message.strip()
    if len(clean) > 60:
        clean = clean[:57] + "..."
    return clean or "Nuova conversazione"
