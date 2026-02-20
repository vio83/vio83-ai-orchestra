"""
VIO 83 AI ORCHESTRA — Biblioteca Digitale Universale
=====================================================
Database strutturato che rappresenta il corpus umano scritto nei libri
dalla nascita dell'essere umano fino al 20 febbraio 2026.

CATEGORIE (13):
1.  Libri — tutte le lingue (inglese, francese, tedesco, italiano, cinese, araba, etc.)
2.  Articoli accademici e scientifici — peer-reviewed, riviste, giornali
3.  Documenti storici e archivistici — archivi, biblioteche, musei
4.  Fonti online — Wikipedia, enciclopedie, siti di conoscenza
5.  Ricerche e studi universitari — tesi, dissertazioni, pubblicazioni
6.  Scienze — fisica, chimica, biologia, medicina, etc.
7.  Storia — documenti storici per ogni epoca e civiltà
8.  Filosofia — testi filosofici dalla Grecia antica a oggi
9.  Linguistica — grammatiche, dizionari, testi letterari, fonologia
10. Economia — articoli, report, studi di mercato, econometria
11. Sociologia e Antropologia — studi di caso, report etnografici
12. Tecnologia e Ingegneria — brevetti, manuali, standard, specifiche
13. Arti e Comunicazione — arti visive, musica, cinema, giornalismo

STRUTTURA:
- Database SQLite relazionale con tabelle dedicate per ogni categoria
- Full-Text Search (FTS5) per ricerca semantica
- Indici per autore, anno, lingua, dominio, affidabilità
- Metadati completi: ISBN, DOI, ISSN, classificazione Dewey/LOC
- Punteggio di affidabilità per ogni fonte (0.0 — 1.0)
- Integrazione con Knowledge Base Engine per embedding e retrieval
"""

import os
import re
import sqlite3
import json
import uuid
import time
from typing import Optional
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager


# ============================================================
# CONFIGURAZIONE
# ============================================================

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
BIBLIOTECA_DB = os.path.join(DB_DIR, "biblioteca_digitale.db")


# ============================================================
# CATEGORIE DELLA BIBLIOTECA
# ============================================================

CATEGORIE = {
    "libri": {
        "nome": "Libri",
        "descrizione": "Tutti i libri scritti in varie lingue dalla nascita della civiltà al 2026",
        "tabella": "libri",
    },
    "articoli_accademici": {
        "nome": "Articoli Accademici e Scientifici",
        "descrizione": "Articoli peer-reviewed pubblicati su riviste e giornali scientifici",
        "tabella": "articoli_accademici",
    },
    "documenti_storici": {
        "nome": "Documenti Storici e Archivistici",
        "descrizione": "Documenti storici da archivi, biblioteche e musei",
        "tabella": "documenti_storici",
    },
    "fonti_online": {
        "nome": "Fonti Online",
        "descrizione": "Wikipedia, enciclopedie, siti di conoscenza certificati",
        "tabella": "fonti_online",
    },
    "ricerche_universitarie": {
        "nome": "Ricerche e Studi Universitari",
        "descrizione": "Tesi, dissertazioni, pubblicazioni universitarie",
        "tabella": "ricerche_universitarie",
    },
    "scienze": {
        "nome": "Scienze",
        "descrizione": "Fisica, chimica, biologia, medicina, astronomia, geologia",
        "tabella": "scienze",
    },
    "storia": {
        "nome": "Storia",
        "descrizione": "Documenti storici per ogni epoca, civiltà e area geografica",
        "tabella": "storia",
    },
    "filosofia": {
        "nome": "Filosofia",
        "descrizione": "Testi filosofici dalla Grecia antica a oggi",
        "tabella": "filosofia",
    },
    "linguistica": {
        "nome": "Linguistica",
        "descrizione": "Grammatiche, dizionari, testi letterari, studi fonetici",
        "tabella": "linguistica",
    },
    "economia": {
        "nome": "Economia",
        "descrizione": "Articoli, report, studi di mercato, econometria",
        "tabella": "economia",
    },
    "sociologia_antropologia": {
        "nome": "Sociologia e Antropologia",
        "descrizione": "Studi di caso, report etnografici, ricerca sociale",
        "tabella": "sociologia_antropologia",
    },
    "tecnologia_ingegneria": {
        "nome": "Tecnologia e Ingegneria",
        "descrizione": "Brevetti, manuali tecnici, standard, specifiche ingegneristiche",
        "tabella": "tecnologia_ingegneria",
    },
    "arti_comunicazione": {
        "nome": "Arti e Comunicazione",
        "descrizione": "Arti visive, musica, cinema, design, giornalismo, semiotica",
        "tabella": "arti_comunicazione",
    },
}


# ============================================================
# SOTTO-DISCIPLINE PER CATEGORIA
# ============================================================

SOTTO_DISCIPLINE = {
    "scienze": [
        "fisica_classica", "fisica_quantistica", "relativita", "termodinamica",
        "elettromagnetismo", "ottica", "acustica", "astrofisica", "cosmologia",
        "chimica_generale", "chimica_organica", "chimica_inorganica", "biochimica",
        "chimica_fisica", "chimica_analitica", "elettrochimica", "fotochimica",
        "biologia_cellulare", "biologia_molecolare", "genetica", "genomica",
        "microbiologia", "virologia", "immunologia", "ecologia", "evoluzione",
        "neurobiologia", "bioinformatica", "epigenetica",
        "medicina_interna", "cardiologia", "oncologia", "neurologia", "psichiatria",
        "chirurgia", "farmacologia", "epidemiologia", "radiologia", "pediatria",
        "ginecologia", "ortopedia", "dermatologia", "oftalmologia",
        "matematica_pura", "algebra", "analisi", "geometria", "topologia",
        "statistica", "probabilita", "logica_matematica",
        "geologia", "meteorologia", "oceanografia", "paleontologia", "sismologia",
        "astronomia_osservativa", "planetologia", "astrobiologia",
    ],
    "storia": [
        "preistoria", "storia_antica", "egitto", "mesopotamia", "grecia", "roma",
        "storia_medievale", "storia_moderna", "storia_contemporanea",
        "storia_dell_arte", "storia_della_scienza", "storia_della_filosofia",
        "storia_del_diritto", "storia_economica", "storia_militare",
        "storia_delle_religioni", "storia_sociale", "storia_culturale",
        "civilta_cinese", "civilta_indiana", "civilta_islamica",
        "civilta_precolombiane", "civilta_africane", "civilta_giapponese",
    ],
    "filosofia": [
        "metafisica", "ontologia", "epistemologia", "logica", "etica",
        "estetica", "filosofia_della_mente", "filosofia_del_linguaggio",
        "filosofia_della_scienza", "filosofia_politica", "ermeneutica",
        "fenomenologia", "esistenzialismo", "pragmatismo", "filosofia_analitica",
        "filosofia_orientale", "filosofia_antica", "filosofia_medievale",
        "filosofia_moderna", "filosofia_contemporanea",
    ],
    "linguistica": [
        "fonetica", "fonologia", "morfologia", "sintassi", "semantica",
        "pragmatica", "sociolinguistica", "psicolinguistica", "neurolinguistica",
        "linguistica_computazionale", "tipologia_linguistica",
        "linguistica_storica", "dialettologia", "lessicografia", "traduttologia",
    ],
    "economia": [
        "microeconomia", "macroeconomia", "econometria", "economia_dello_sviluppo",
        "economia_internazionale", "economia_monetaria", "economia_pubblica",
        "economia_del_lavoro", "economia_industriale", "economia_comportamentale",
        "finanza", "contabilita", "management", "marketing",
    ],
    "tecnologia_ingegneria": [
        "informatica", "algoritmi", "intelligenza_artificiale", "machine_learning",
        "deep_learning", "nlp", "computer_vision", "cybersecurity", "crittografia",
        "ingegneria_civile", "ingegneria_meccanica", "ingegneria_elettrica",
        "ingegneria_chimica", "ingegneria_aerospaziale", "ingegneria_biomedica",
        "ingegneria_nucleare", "telecomunicazioni", "robotica", "meccatronica",
    ],
}


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class DocumentoBase:
    """Struttura base per ogni documento nella biblioteca."""
    id: str = ""
    titolo: str = ""
    autore: str = ""
    contenuto: str = ""
    lingua: str = "it"
    anno: Optional[int] = None
    categoria: str = ""
    sotto_disciplina: str = ""
    fonte_tipo: str = ""           # book, article, thesis, archive, online, patent
    isbn: str = ""
    doi: str = ""
    issn: str = ""
    editore: str = ""
    rivista: str = ""
    url: str = ""
    classificazione_dewey: str = ""
    classificazione_loc: str = ""  # Library of Congress
    affidabilita: float = 1.0      # 0.0 — 1.0
    peer_reviewed: bool = False
    parole_chiave: str = ""        # Comma-separated
    abstract: str = ""
    note: str = ""
    data_inserimento: float = 0.0


# ============================================================
# DATABASE MANAGER
# ============================================================

class BibliotecaDigitale:
    """
    Biblioteca Digitale Universale — Database relazionale strutturato
    con 13 categorie, FTS5 per ricerca testuale, indici ottimizzati.
    """

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or BIBLIOTECA_DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_database()

    @contextmanager
    def _conn(self):
        """Context manager per connessione thread-safe."""
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Crea tutte le tabelle della biblioteca digitale."""
        with self._conn() as conn:
            # ── TABELLA PRINCIPALE: documenti (unificata) ──
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documenti (
                    id TEXT PRIMARY KEY,
                    titolo TEXT NOT NULL,
                    autore TEXT NOT NULL DEFAULT '',
                    contenuto TEXT NOT NULL DEFAULT '',
                    lingua TEXT DEFAULT 'it',
                    anno INTEGER,
                    categoria TEXT NOT NULL,
                    sotto_disciplina TEXT DEFAULT '',
                    fonte_tipo TEXT DEFAULT 'book',
                    isbn TEXT DEFAULT '',
                    doi TEXT DEFAULT '',
                    issn TEXT DEFAULT '',
                    editore TEXT DEFAULT '',
                    rivista TEXT DEFAULT '',
                    url TEXT DEFAULT '',
                    classificazione_dewey TEXT DEFAULT '',
                    classificazione_loc TEXT DEFAULT '',
                    affidabilita REAL DEFAULT 1.0,
                    peer_reviewed INTEGER DEFAULT 0,
                    parole_chiave TEXT DEFAULT '',
                    abstract TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    data_inserimento REAL DEFAULT 0,
                    word_count INTEGER DEFAULT 0,
                    char_count INTEGER DEFAULT 0
                )
            """)

            # ── TABELLE PER CATEGORIA (viste + tabelle specializzate) ──

            # Libri — dettagli editoriali
            conn.execute("""
                CREATE TABLE IF NOT EXISTS libri_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    edizione TEXT DEFAULT '',
                    numero_pagine INTEGER,
                    collana TEXT DEFAULT '',
                    traduttore TEXT DEFAULT '',
                    lingua_originale TEXT DEFAULT '',
                    genere_letterario TEXT DEFAULT ''
                )
            """)

            # Articoli accademici — dettagli pubblicazione
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articoli_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    volume TEXT DEFAULT '',
                    numero TEXT DEFAULT '',
                    pagine TEXT DEFAULT '',
                    impact_factor REAL,
                    citazioni INTEGER DEFAULT 0,
                    tipo_articolo TEXT DEFAULT ''
                )
            """)

            # Documenti storici — dettagli archivistici
            conn.execute("""
                CREATE TABLE IF NOT EXISTS storici_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    epoca TEXT DEFAULT '',
                    civilta TEXT DEFAULT '',
                    area_geografica TEXT DEFAULT '',
                    tipo_documento TEXT DEFAULT '',
                    archivio_provenienza TEXT DEFAULT '',
                    stato_conservazione TEXT DEFAULT ''
                )
            """)

            # Fonti online — dettagli web
            conn.execute("""
                CREATE TABLE IF NOT EXISTS online_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    nome_sito TEXT DEFAULT '',
                    tipo_contenuto TEXT DEFAULT '',
                    data_ultimo_accesso TEXT DEFAULT '',
                    licenza TEXT DEFAULT '',
                    verificato INTEGER DEFAULT 0
                )
            """)

            # Ricerche universitarie — dettagli accademici
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ricerche_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    universita TEXT DEFAULT '',
                    dipartimento TEXT DEFAULT '',
                    tipo_tesi TEXT DEFAULT '',
                    relatore TEXT DEFAULT '',
                    anno_accademico TEXT DEFAULT ''
                )
            """)

            # ── TABELLA AUTORI (normalizzata) ──
            conn.execute("""
                CREATE TABLE IF NOT EXISTS autori (
                    id TEXT PRIMARY KEY,
                    nome TEXT NOT NULL,
                    cognome TEXT NOT NULL DEFAULT '',
                    nazionalita TEXT DEFAULT '',
                    anno_nascita INTEGER,
                    anno_morte INTEGER,
                    specializzazione TEXT DEFAULT '',
                    istituzione TEXT DEFAULT '',
                    h_index INTEGER,
                    orcid TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS documento_autore (
                    doc_id TEXT REFERENCES documenti(id),
                    autore_id TEXT REFERENCES autori(id),
                    ruolo TEXT DEFAULT 'autore',
                    PRIMARY KEY (doc_id, autore_id)
                )
            """)

            # ── FTS5 per ricerca full-text ──
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documenti_fts USING fts5(
                    id, titolo, autore, contenuto, abstract, parole_chiave,
                    categoria, sotto_disciplina, lingua,
                    tokenize='unicode61 remove_diacritics 2'
                )
            """)

            # ── INDICI per performance ──
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_categoria ON documenti(categoria)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_sotto ON documenti(sotto_disciplina)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_lingua ON documenti(lingua)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_anno ON documenti(anno)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_autore ON documenti(autore)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_affid ON documenti(affidabilita)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_isbn ON documenti(isbn)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_doi ON documenti(doi)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_tipo ON documenti(fonte_tipo)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_peer ON documenti(peer_reviewed)")

            # ── STATISTICHE ──
            conn.execute("""
                CREATE TABLE IF NOT EXISTS statistiche_biblioteca (
                    chiave TEXT PRIMARY KEY,
                    valore TEXT,
                    aggiornato_il REAL
                )
            """)

    # ========================================================
    # INSERIMENTO DOCUMENTI
    # ========================================================

    def aggiungi_documento(self, doc: DocumentoBase) -> str:
        """Aggiungi un documento alla biblioteca."""
        if not doc.id:
            doc.id = str(uuid.uuid4())[:16]
        if not doc.data_inserimento:
            doc.data_inserimento = time.time()

        word_count = len(doc.contenuto.split())
        char_count = len(doc.contenuto)

        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO documenti
                (id, titolo, autore, contenuto, lingua, anno, categoria,
                 sotto_disciplina, fonte_tipo, isbn, doi, issn, editore,
                 rivista, url, classificazione_dewey, classificazione_loc,
                 affidabilita, peer_reviewed, parole_chiave, abstract, note,
                 data_inserimento, word_count, char_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc.id, doc.titolo, doc.autore, doc.contenuto, doc.lingua,
                doc.anno, doc.categoria, doc.sotto_disciplina, doc.fonte_tipo,
                doc.isbn, doc.doi, doc.issn, doc.editore, doc.rivista, doc.url,
                doc.classificazione_dewey, doc.classificazione_loc,
                doc.affidabilita, 1 if doc.peer_reviewed else 0,
                doc.parole_chiave, doc.abstract, doc.note,
                doc.data_inserimento, word_count, char_count,
            ))

            # Aggiorna FTS
            conn.execute(
                "INSERT OR REPLACE INTO documenti_fts "
                "(id, titolo, autore, contenuto, abstract, parole_chiave, "
                "categoria, sotto_disciplina, lingua) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc.id, doc.titolo, doc.autore, doc.contenuto,
                 doc.abstract, doc.parole_chiave, doc.categoria,
                 doc.sotto_disciplina, doc.lingua)
            )

        return doc.id

    def aggiungi_batch(self, documenti: list[DocumentoBase]) -> int:
        """Aggiungi batch di documenti (ottimizzato)."""
        count = 0
        with self._conn() as conn:
            for doc in documenti:
                if not doc.id:
                    doc.id = str(uuid.uuid4())[:16]
                if not doc.data_inserimento:
                    doc.data_inserimento = time.time()

                word_count = len(doc.contenuto.split())
                char_count = len(doc.contenuto)

                conn.execute("""
                    INSERT OR REPLACE INTO documenti
                    (id, titolo, autore, contenuto, lingua, anno, categoria,
                     sotto_disciplina, fonte_tipo, isbn, doi, issn, editore,
                     rivista, url, classificazione_dewey, classificazione_loc,
                     affidabilita, peer_reviewed, parole_chiave, abstract, note,
                     data_inserimento, word_count, char_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc.id, doc.titolo, doc.autore, doc.contenuto, doc.lingua,
                    doc.anno, doc.categoria, doc.sotto_disciplina, doc.fonte_tipo,
                    doc.isbn, doc.doi, doc.issn, doc.editore, doc.rivista, doc.url,
                    doc.classificazione_dewey, doc.classificazione_loc,
                    doc.affidabilita, 1 if doc.peer_reviewed else 0,
                    doc.parole_chiave, doc.abstract, doc.note,
                    doc.data_inserimento, word_count, char_count,
                ))

                conn.execute(
                    "INSERT OR REPLACE INTO documenti_fts "
                    "(id, titolo, autore, contenuto, abstract, parole_chiave, "
                    "categoria, sotto_disciplina, lingua) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (doc.id, doc.titolo, doc.autore, doc.contenuto,
                     doc.abstract, doc.parole_chiave, doc.categoria,
                     doc.sotto_disciplina, doc.lingua)
                )
                count += 1

        return count

    # ========================================================
    # RICERCA
    # ========================================================

    def cerca(
        self,
        query: str,
        categoria: Optional[str] = None,
        sotto_disciplina: Optional[str] = None,
        lingua: Optional[str] = None,
        anno_da: Optional[int] = None,
        anno_a: Optional[int] = None,
        min_affidabilita: float = 0.0,
        solo_peer_reviewed: bool = False,
        limite: int = 20,
    ) -> list[dict]:
        """
        Ricerca avanzata nella biblioteca con FTS5 + filtri.
        """
        with self._conn() as conn:
            # Sanitizza query per FTS5
            safe_query = re.sub(r'[^\w\s]', ' ', query)
            terms = [w for w in safe_query.split() if len(w) > 2]
            if not terms:
                return []
            fts_query = " OR ".join(terms)

            # Base query FTS5
            sql = """
                SELECT d.*, bm25(documenti_fts) as score
                FROM documenti_fts f
                JOIN documenti d ON d.id = f.id
                WHERE documenti_fts MATCH ?
            """
            params = [fts_query]

            # Filtri opzionali
            if categoria:
                sql += " AND d.categoria = ?"
                params.append(categoria)
            if sotto_disciplina:
                sql += " AND d.sotto_disciplina = ?"
                params.append(sotto_disciplina)
            if lingua:
                sql += " AND d.lingua = ?"
                params.append(lingua)
            if anno_da:
                sql += " AND d.anno >= ?"
                params.append(anno_da)
            if anno_a:
                sql += " AND d.anno <= ?"
                params.append(anno_a)
            if min_affidabilita > 0:
                sql += " AND d.affidabilita >= ?"
                params.append(min_affidabilita)
            if solo_peer_reviewed:
                sql += " AND d.peer_reviewed = 1"

            sql += " ORDER BY bm25(documenti_fts) LIMIT ?"
            params.append(limite)

            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def cerca_per_autore(self, autore: str, limite: int = 50) -> list[dict]:
        """Cerca documenti per autore."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM documenti WHERE autore LIKE ? ORDER BY anno DESC LIMIT ?",
                (f"%{autore}%", limite)
            ).fetchall()
            return [dict(row) for row in rows]

    def cerca_per_isbn(self, isbn: str) -> Optional[dict]:
        """Cerca documento per ISBN."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM documenti WHERE isbn = ?", (isbn.replace("-", ""),)
            ).fetchone()
            return dict(row) if row else None

    def cerca_per_doi(self, doi: str) -> Optional[dict]:
        """Cerca documento per DOI."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM documenti WHERE doi = ?", (doi,)).fetchone()
            return dict(row) if row else None

    # ========================================================
    # STATISTICHE
    # ========================================================

    def statistiche(self) -> dict:
        """Statistiche complete della biblioteca."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM documenti").fetchone()[0]

            # Per categoria
            cats = conn.execute(
                "SELECT categoria, COUNT(*) as n FROM documenti GROUP BY categoria ORDER BY n DESC"
            ).fetchall()

            # Per lingua
            lingue = conn.execute(
                "SELECT lingua, COUNT(*) as n FROM documenti GROUP BY lingua ORDER BY n DESC"
            ).fetchall()

            # Per tipo fonte
            tipi = conn.execute(
                "SELECT fonte_tipo, COUNT(*) as n FROM documenti GROUP BY fonte_tipo ORDER BY n DESC"
            ).fetchall()

            # Parole totali
            words = conn.execute("SELECT SUM(word_count) FROM documenti").fetchone()[0] or 0

            # Range anni
            anni = conn.execute(
                "SELECT MIN(anno), MAX(anno) FROM documenti WHERE anno IS NOT NULL"
            ).fetchone()

            return {
                "totale_documenti": total,
                "totale_parole": words,
                "per_categoria": {row[0]: row[1] for row in cats},
                "per_lingua": {row[0]: row[1] for row in lingue},
                "per_tipo_fonte": {row[0]: row[1] for row in tipi},
                "anno_piu_antico": anni[0] if anni else None,
                "anno_piu_recente": anni[1] if anni else None,
                "categorie_disponibili": list(CATEGORIE.keys()),
            }

    def lista_categorie(self) -> list[dict]:
        """Lista tutte le categorie con descrizione e conteggi."""
        with self._conn() as conn:
            result = []
            for key, info in CATEGORIE.items():
                count = conn.execute(
                    "SELECT COUNT(*) FROM documenti WHERE categoria = ?", (key,)
                ).fetchone()[0]
                result.append({
                    "chiave": key,
                    "nome": info["nome"],
                    "descrizione": info["descrizione"],
                    "documenti": count,
                    "sotto_discipline": SOTTO_DISCIPLINE.get(key, []),
                })
            return result


# ============================================================
# SINGLETON
# ============================================================

_biblioteca: Optional[BibliotecaDigitale] = None


def get_biblioteca(db_path: str = "") -> BibliotecaDigitale:
    """Ottieni l'istanza singleton della Biblioteca Digitale."""
    global _biblioteca
    if _biblioteca is None:
        _biblioteca = BibliotecaDigitale(db_path=db_path)
    return _biblioteca
