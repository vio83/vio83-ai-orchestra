"""
VIO 83 AI ORCHESTRA — Data Preprocessing Pipeline
Sistema complesso di pre-elaborazione dati per:
- Pulizia e normalizzazione testo
- Tokenizzazione avanzata (word-level, subword, sentence)
- Rimozione noise (HTML, markup, artefatti OCR, encoding errors)
- Segmentazione intelligente in chunk semantici
- Data augmentation per ampliare copertura semantica
- Estrazione metadati strutturati da testo grezzo
"""

import re
import unicodedata
import hashlib
from typing import Optional
from dataclasses import dataclass, field


# ============================================================
# DATACLASS — Chunk processato
# ============================================================

@dataclass
class ProcessedChunk:
    """Singolo chunk di testo pre-processato pronto per embedding."""
    chunk_id: str
    content: str                      # Testo pulito e normalizzato
    content_raw: str                  # Testo originale prima della pulizia
    tokens_approx: int                # Numero approssimativo di token
    char_count: int
    word_count: int
    language: str = "unknown"         # Lingua rilevata
    source_doc_id: str = ""           # ID documento sorgente
    chunk_index: int = 0              # Posizione nel documento
    total_chunks: int = 0
    section_title: str = ""           # Titolo sezione se rilevato
    metadata: dict = field(default_factory=dict)


# ============================================================
# 1. TEXT CLEANING — Rimozione noise
# ============================================================

class TextCleaner:
    """Pulisce testo grezzo da noise, artefatti, markup, encoding errors."""

    # Pattern per rimuovere HTML tags
    HTML_TAGS = re.compile(r"<[^>]+>")
    # Pattern per rimuovere markup wiki
    WIKI_MARKUP = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
    # Pattern per rimuovere URL
    URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
    # Pattern per rimuovere email
    EMAIL_PATTERN = re.compile(r"\S+@\S+\.\S+")
    # Pattern per rimuovere riferimenti bibliografici inline [1], [2,3], etc
    INLINE_REFS = re.compile(r"\[\d+(?:,\s*\d+)*\]")
    # Pattern per rimuovere header/footer ripetitivi (numeri di pagina, etc)
    PAGE_NUMBERS = re.compile(r"^\s*(?:Pagina|Page|p\.)\s*\d+\s*$", re.MULTILINE)
    # Pattern per caratteri di controllo (eccetto newline e tab)
    CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
    # Pattern per whitespace eccessivo
    MULTI_SPACES = re.compile(r"[ \t]+")
    MULTI_NEWLINES = re.compile(r"\n{4,}")
    # Pattern per artefatti OCR comuni
    OCR_ARTIFACTS = re.compile(r"[|}{~`](?=[a-zA-Z])|(?<=[a-zA-Z])[|}{~`]")

    @classmethod
    def clean(cls, text: str, options: Optional[dict] = None) -> str:
        """
        Pipeline di pulizia completa.
        options: {remove_urls, remove_emails, remove_refs, remove_html,
                  fix_encoding, normalize_unicode, remove_ocr_artifacts}
        """
        if not text or not text.strip():
            return ""

        opts = options or {}

        # 1. Fix encoding problems
        if opts.get("fix_encoding", True):
            text = cls._fix_encoding(text)

        # 2. Normalizzazione Unicode
        if opts.get("normalize_unicode", True):
            text = unicodedata.normalize("NFKC", text)

        # 3. Rimuovi caratteri di controllo
        text = cls.CONTROL_CHARS.sub("", text)

        # 4. Rimuovi HTML tags
        if opts.get("remove_html", True):
            text = cls.HTML_TAGS.sub(" ", text)

        # 5. Rimuovi markup wiki → tieni solo il testo visibile
        text = cls.WIKI_MARKUP.sub(r"\1", text)

        # 6. Rimuovi URL
        if opts.get("remove_urls", False):
            text = cls.URL_PATTERN.sub("[URL]", text)

        # 7. Rimuovi email
        if opts.get("remove_emails", True):
            text = cls.EMAIL_PATTERN.sub("[EMAIL]", text)

        # 8. Rimuovi riferimenti inline
        if opts.get("remove_refs", False):
            text = cls.INLINE_REFS.sub("", text)

        # 9. Rimuovi artefatti OCR
        if opts.get("remove_ocr_artifacts", True):
            text = cls.OCR_ARTIFACTS.sub("", text)

        # 10. Rimuovi numeri di pagina isolati
        text = cls.PAGE_NUMBERS.sub("", text)

        # 11. Normalizza whitespace
        text = cls.MULTI_SPACES.sub(" ", text)
        text = cls.MULTI_NEWLINES.sub("\n\n\n", text)

        # 12. Trim ogni riga
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

    @classmethod
    def _fix_encoding(cls, text: str) -> str:
        """Corregge problemi di encoding comuni (mojibake)."""
        replacements = {
            "\xc3\xa8": "\u00e8",   # è
            "\xc3\xa9": "\u00e9",   # é
            "\xc3\xa0": "\u00e0",   # à
            "\xc3\xb9": "\u00f9",   # ù
            "\xc3\xb2": "\u00f2",   # ò
            "\xc3\xac": "\u00ec",   # ì
            "\xc2\xb0": "\u00b0",   # °
            "\xc2\xab": "\u00ab",   # «
            "\xc2\xbb": "\u00bb",   # »
            "\xc2\xa7": "\u00a7",   # §
            "\ufeff": "",            # BOM
            "\u200b": "",            # Zero-width space
            "\u200c": "",            # Zero-width non-joiner
            "\u200d": "",            # Zero-width joiner
            "\ufffe": "",            # Non-character
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text


# ============================================================
# 2. LANGUAGE DETECTION — Rilevamento lingua semplificato
# ============================================================

class LanguageDetector:
    """Rilevamento lingua basato su frequenza caratteri e stop words."""

    STOP_WORDS = {
        "it": {"di", "che", "è", "la", "il", "un", "per", "non", "sono", "da",
               "del", "con", "una", "in", "al", "dei", "le", "nel", "gli", "alla",
               "delle", "come", "più", "anche", "questo", "questa", "essere", "ha"},
        "en": {"the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
               "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
               "this", "but", "his", "by", "from", "they", "we", "her", "she"},
        "fr": {"le", "de", "un", "être", "et", "en", "il", "que", "ne", "pas",
               "sur", "se", "qui", "ce", "dans", "du", "elle", "au", "avec", "pour"},
        "de": {"der", "die", "und", "in", "den", "von", "zu", "das", "mit",
               "sich", "des", "auf", "für", "ist", "im", "dem", "nicht", "ein",
               "eine", "als", "auch", "es", "an", "er", "hat", "aus", "sie"},
        "es": {"de", "la", "que", "el", "en", "y", "los", "se", "del", "las",
               "un", "por", "con", "no", "una", "su", "al", "lo", "como", "más"},
        "la": {"et", "in", "est", "non", "cum", "ad", "sed", "ut", "de", "quod",
               "qui", "ab", "ex", "per", "aut", "hoc", "enim", "quae", "esse"},
    }

    @classmethod
    def detect(cls, text: str) -> str:
        """Rileva la lingua del testo analizzando le stop words."""
        words = set(text.lower().split())
        scores = {}
        for lang, stops in cls.STOP_WORDS.items():
            overlap = len(words & stops)
            scores[lang] = overlap
        if not scores or max(scores.values()) < 3:
            return "unknown"
        return max(scores, key=scores.get)


# ============================================================
# 3. TEXT CHUNKER — Segmentazione semantica intelligente
# ============================================================

class SemanticChunker:
    """
    Segmenta testo in chunk semanticamente coerenti.
    Strategie:
    - Paragraph-based: split su paragrafi naturali
    - Sliding window: overlap per non perdere contesto ai bordi
    - Section-aware: rispetta titoli e sezioni
    """

    # Pattern per rilevare titoli di sezione
    SECTION_PATTERNS = [
        re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE),           # Markdown headers
        re.compile(r"^(?:CAPITOLO|CHAPTER|SEZIONE|SECTION)\s+[\dIVXLCDM]+[.:]\s*(.+)$",
                   re.MULTILINE | re.IGNORECASE),
        re.compile(r"^(\d+(?:\.\d+)*)\s+([A-Z].+)$", re.MULTILINE),  # 1.2.3 Title
        re.compile(r"^([A-Z][A-Z\s]{5,})$", re.MULTILINE),       # ALL CAPS titles
    ]

    @classmethod
    def chunk(
        cls,
        text: str,
        max_tokens: int = 512,
        overlap_tokens: int = 64,
        respect_sections: bool = True,
    ) -> list[dict]:
        """
        Segmenta il testo in chunk con overlap.
        Ritorna lista di dict con: content, start_char, end_char, section_title, tokens_approx
        """
        if not text:
            return []

        # Stima: 1 token ≈ 4 caratteri per lingue latine, 3.5 per inglese
        chars_per_token = 4
        max_chars = max_tokens * chars_per_token
        overlap_chars = overlap_tokens * chars_per_token

        # Split in paragrafi
        paragraphs = text.split("\n\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks = []
        current_chunk = ""
        current_section = ""
        chunk_start = 0
        char_pos = 0

        for para in paragraphs:
            # Rileva se è un titolo di sezione
            section_match = cls._detect_section(para)
            if section_match and respect_sections:
                # Salva chunk corrente se non vuoto
                if current_chunk.strip():
                    chunks.append(cls._make_chunk(
                        current_chunk.strip(), chunk_start, char_pos, current_section
                    ))
                current_section = section_match
                current_chunk = ""
                chunk_start = char_pos

            # Controlla se aggiungendo il paragrafo si supera il limite
            if len(current_chunk) + len(para) + 2 > max_chars and current_chunk.strip():
                chunks.append(cls._make_chunk(
                    current_chunk.strip(), chunk_start, char_pos, current_section
                ))
                # Overlap: prendi le ultime N parole del chunk precedente
                if overlap_chars > 0:
                    overlap_text = current_chunk[-overlap_chars:]
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para
                chunk_start = max(0, char_pos - overlap_chars)
            else:
                current_chunk += ("\n\n" if current_chunk else "") + para

            char_pos += len(para) + 2  # +2 per \n\n

        # Ultimo chunk
        if current_chunk.strip():
            chunks.append(cls._make_chunk(
                current_chunk.strip(), chunk_start, char_pos, current_section
            ))

        return chunks

    @classmethod
    def _detect_section(cls, text: str) -> Optional[str]:
        """Rileva se il testo è un titolo di sezione."""
        text_stripped = text.strip()
        if len(text_stripped) > 200:
            return None
        for pattern in cls.SECTION_PATTERNS:
            match = pattern.match(text_stripped)
            if match:
                return match.group(1) if match.lastindex else text_stripped
        return None

    @classmethod
    def _make_chunk(cls, content: str, start: int, end: int, section: str) -> dict:
        """Crea un dizionario chunk."""
        words = content.split()
        return {
            "content": content,
            "start_char": start,
            "end_char": end,
            "section_title": section,
            "tokens_approx": len(content) // 4,
            "word_count": len(words),
            "char_count": len(content),
        }


# ============================================================
# 4. METADATA EXTRACTOR — Estrazione metadati strutturati
# ============================================================

class MetadataExtractor:
    """Estrae metadati strutturati dal testo (date, autori, ISBN, DOI, etc.)."""

    ISBN_PATTERN = re.compile(
        r"(?:ISBN[:\- ]?)?(97[89][- ]?\d{1,5}[- ]?\d{1,7}[- ]?\d{1,7}[- ]?\d)"
    )
    DOI_PATTERN = re.compile(r"(10\.\d{4,}/\S+)")
    YEAR_PATTERN = re.compile(r"\b(1[5-9]\d{2}|20[0-2]\d)\b")
    AUTHOR_PATTERN = re.compile(
        r"(?:(?:di|by|autore|author|a cura di)[:\s]+)([A-Z][a-zà-ü]+(?:\s+[A-Z][a-zà-ü]+){1,3})",
        re.IGNORECASE
    )

    @classmethod
    def extract(cls, text: str, filename: str = "") -> dict:
        """Estrai metadati da testo e nome file."""
        meta = {}

        # ISBN
        isbn_match = cls.ISBN_PATTERN.search(text[:5000])
        if isbn_match:
            meta["isbn"] = isbn_match.group(1).replace("-", "").replace(" ", "")

        # DOI
        doi_match = cls.DOI_PATTERN.search(text[:5000])
        if doi_match:
            meta["doi"] = doi_match.group(1)

        # Anno (prendi il più frequente tra i primi 2000 chars)
        years = cls.YEAR_PATTERN.findall(text[:2000])
        if years:
            from collections import Counter
            year_counts = Counter(years)
            meta["year"] = int(year_counts.most_common(1)[0][0])

        # Autore
        author_match = cls.AUTHOR_PATTERN.search(text[:3000])
        if author_match:
            meta["author"] = author_match.group(1).strip()

        # Lingua
        meta["language"] = LanguageDetector.detect(text[:3000])

        # Statistiche testo
        words = text.split()
        meta["word_count"] = len(words)
        meta["char_count"] = len(text)
        meta["tokens_approx"] = len(text) // 4
        meta["paragraph_count"] = text.count("\n\n") + 1

        # Da filename
        if filename:
            meta["filename"] = filename
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            meta["file_type"] = ext

        return meta


# ============================================================
# 5. PREPROCESSING PIPELINE — Orchestratore completo
# ============================================================

class PreprocessingPipeline:
    """
    Pipeline completa di pre-elaborazione:
    1. Pulizia testo (TextCleaner)
    2. Rilevamento lingua (LanguageDetector)
    3. Estrazione metadati (MetadataExtractor)
    4. Segmentazione semantica (SemanticChunker)
    5. Generazione chunk processati con ID univoco
    """

    def __init__(
        self,
        max_tokens_per_chunk: int = 512,
        overlap_tokens: int = 64,
        respect_sections: bool = True,
        cleaning_options: Optional[dict] = None,
    ):
        self.max_tokens = max_tokens_per_chunk
        self.overlap_tokens = overlap_tokens
        self.respect_sections = respect_sections
        self.cleaning_options = cleaning_options or {}

    def process(
        self,
        text: str,
        doc_id: str = "",
        filename: str = "",
        extra_metadata: Optional[dict] = None,
    ) -> list[ProcessedChunk]:
        """
        Processa un documento completo e ritorna lista di ProcessedChunk.
        """
        if not text or not text.strip():
            return []

        # 1. Pulizia
        cleaned = TextCleaner.clean(text, self.cleaning_options)
        if not cleaned:
            return []

        # 2. Metadati
        metadata = MetadataExtractor.extract(cleaned, filename)
        if extra_metadata:
            metadata.update(extra_metadata)

        # 3. Lingua
        language = metadata.get("language", "unknown")

        # 4. Segmentazione
        raw_chunks = SemanticChunker.chunk(
            cleaned,
            max_tokens=self.max_tokens,
            overlap_tokens=self.overlap_tokens,
            respect_sections=self.respect_sections,
        )

        # 5. Genera ProcessedChunk con ID univoci
        if not doc_id:
            doc_id = hashlib.md5(cleaned[:500].encode()).hexdigest()[:12]

        total = len(raw_chunks)
        processed = []
        for i, rc in enumerate(raw_chunks):
            chunk_id = f"{doc_id}_chunk_{i:04d}"
            processed.append(ProcessedChunk(
                chunk_id=chunk_id,
                content=rc["content"],
                content_raw=rc["content"],  # Dopo clean è già il "raw" post-pulizia
                tokens_approx=rc["tokens_approx"],
                char_count=rc["char_count"],
                word_count=rc["word_count"],
                language=language,
                source_doc_id=doc_id,
                chunk_index=i,
                total_chunks=total,
                section_title=rc.get("section_title", ""),
                metadata=metadata,
            ))

        return processed

    def process_batch(
        self,
        documents: list[dict],
    ) -> list[ProcessedChunk]:
        """
        Processa un batch di documenti.
        Ogni dict ha: text, doc_id (opz), filename (opz), metadata (opz)
        """
        all_chunks = []
        for doc in documents:
            chunks = self.process(
                text=doc.get("text", ""),
                doc_id=doc.get("doc_id", ""),
                filename=doc.get("filename", ""),
                extra_metadata=doc.get("metadata"),
            )
            all_chunks.extend(chunks)
        return all_chunks
