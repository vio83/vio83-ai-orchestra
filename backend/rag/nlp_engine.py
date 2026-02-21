# ============================================================
# VIO 83 AI ORCHESTRA — Copyright (c) 2026 Viorica Porcu (vio83)
# DUAL LICENSE: Proprietary + AGPL-3.0 — See LICENSE files
# ALL RIGHTS RESERVED — https://github.com/vio83/vio83-ai-orchestra
# ============================================================
"""
╔══════════════════════════════════════════════════════════════════════╗
║           VIO 83 AI ORCHESTRA — NLP Processing Engine               ║
║                                                                      ║
║  Pipeline NLP multi-livello con fallback progressivo:                ║
║  • Livello 3: spaCy     — NER, POS, dependency parse (opzionale)    ║
║  • Livello 2: NLTK      — tokenization, stemming, NER (opzionale)   ║
║  • Livello 1: Regex     — base, zero dipendenze (sempre disponibile)║
║                                                                      ║
║  Features:                                                           ║
║  • Named Entity Recognition (NER) multi-livello                      ║
║  • Keyword extraction (TF-IDF, TextRank, RAKE)                      ║
║  • Language detection (statistico)                                   ║
║  • Text summarization (extractive)                                   ║
║  • Sentiment analysis (lexicon-based)                                ║
║  • Topic classification                                              ║
║  • Text cleaning e normalization                                     ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import collections
import logging
import math
import os
import re
import string
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Counter, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("vio83.nlp_engine")

# ═══════════════════════════════════════════════════════
# Rilevamento librerie
# ═══════════════════════════════════════════════════════

_HAS_SPACY = False
_HAS_NLTK = False

try:
    import spacy
    _HAS_SPACY = True
except ImportError:
    pass

try:
    import nltk
    _HAS_NLTK = True
except ImportError:
    pass


class NLPLevel(Enum):
    REGEX = 1
    NLTK = 2
    SPACY = 3


def detect_nlp_level() -> NLPLevel:
    if _HAS_SPACY:
        return NLPLevel.SPACY
    if _HAS_NLTK:
        return NLPLevel.NLTK
    return NLPLevel.REGEX


# ═══════════════════════════════════════════════════════
# Tipi
# ═══════════════════════════════════════════════════════

@dataclass
class Entity:
    text: str
    label: str  # PERSON, ORG, GPE, DATE, etc.
    start: int = 0
    end: int = 0
    confidence: float = 1.0


@dataclass
class Keyword:
    word: str
    score: float
    frequency: int = 0


@dataclass
class NLPResult:
    """Risultato completo dell'analisi NLP."""
    text_cleaned: str = ""
    language: str = ""
    language_confidence: float = 0.0
    entities: List[Entity] = field(default_factory=list)
    keywords: List[Keyword] = field(default_factory=list)
    summary: str = ""
    sentiment_score: float = 0.0  # -1.0 (neg) a +1.0 (pos)
    sentiment_label: str = ""     # "positive", "negative", "neutral"
    word_count: int = 0
    sentence_count: int = 0
    topics: List[str] = field(default_factory=list)
    nlp_level: str = ""


# ═══════════════════════════════════════════════════════
# 1. REGEX NLP (Livello 1 — sempre disponibile)
# ═══════════════════════════════════════════════════════

# Stopwords minimali per le lingue principali
_STOPWORDS: Dict[str, Set[str]] = {
    "en": {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "more", "most", "other", "some", "such", "no",
        "not", "only", "own", "same", "so", "than", "too", "very", "just",
        "because", "but", "and", "or", "if", "while", "that", "this", "it",
        "its", "he", "she", "they", "them", "his", "her", "their", "we", "you",
        "i", "me", "my", "your", "our", "which", "what", "who", "whom",
    },
    "it": {
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "del",
        "dello", "della", "dei", "degli", "delle", "a", "al", "allo", "alla",
        "ai", "agli", "alle", "da", "dal", "dallo", "dalla", "dai", "dagli",
        "dalle", "in", "nel", "nello", "nella", "nei", "negli", "nelle", "con",
        "su", "sul", "sullo", "sulla", "sui", "sugli", "sulle", "per", "tra",
        "fra", "e", "o", "ma", "che", "non", "si", "come", "anche", "questo",
        "questa", "questi", "queste", "quello", "quella", "quelli", "quelle",
        "sono", "essere", "avere", "fare", "dire", "potere", "volere", "dovere",
        "stato", "stata", "stati", "state", "ho", "hai", "ha", "abbiamo",
        "hanno", "era", "sono", "sei", "siamo", "siete", "pi\xf9", "molto",
        "tutto", "tutti", "ogni", "suo", "sua", "suoi", "sue", "mio", "mia",
        "nostro", "loro", "quando", "dove", "perch\xe9", "come", "se", "chi",
    },
    "es": {
        "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
        "al", "a", "en", "con", "por", "para", "sin", "sobre", "entre",
        "y", "o", "pero", "que", "no", "se", "es", "son", "fue", "ser",
        "estar", "haber", "tener", "hacer", "como", "este", "esta", "esto",
    },
    "fr": {
        "le", "la", "les", "un", "une", "des", "de", "du", "au", "aux",
        "et", "ou", "mais", "que", "qui", "ne", "pas", "est", "sont",
        "a", "en", "dans", "pour", "par", "sur", "avec", "ce", "cette",
    },
    "de": {
        "der", "die", "das", "ein", "eine", "und", "oder", "aber", "nicht",
        "ist", "sind", "war", "haben", "sein", "werden", "von", "zu", "mit",
        "in", "auf", "an", "bei", "nach", "aus", "um", "als", "wenn",
    },
}

# Language detection: character frequency profiles
_LANG_PROFILES: Dict[str, Dict[str, float]] = {
    "en": {"the": 0.07, "and": 0.03, "of": 0.035, "to": 0.025, "is": 0.02, "that": 0.015, "for": 0.012, "with": 0.01, "this": 0.01, "was": 0.01},
    "it": {"della": 0.015, "che": 0.03, "il": 0.025, "nel": 0.008, "sono": 0.01, "questo": 0.008, "degli": 0.005, "nella": 0.006, "anche": 0.008, "essere": 0.006},
    "es": {"que": 0.028, "el": 0.025, "los": 0.015, "del": 0.012, "las": 0.012, "una": 0.012, "por": 0.01, "como": 0.008, "pero": 0.005, "este": 0.005},
    "fr": {"le": 0.025, "les": 0.018, "des": 0.015, "est": 0.012, "une": 0.01, "dans": 0.008, "pour": 0.008, "avec": 0.006, "pas": 0.008, "sont": 0.005},
    "de": {"der": 0.035, "die": 0.035, "und": 0.03, "den": 0.02, "ist": 0.015, "das": 0.015, "ein": 0.012, "nicht": 0.01, "auf": 0.008, "werden": 0.005},
    "pt": {"que": 0.025, "do": 0.02, "da": 0.02, "em": 0.018, "um": 0.015, "os": 0.012, "uma": 0.012, "como": 0.008, "mais": 0.008, "pelo": 0.005},
}

# Sentiment lexicon minimale
_SENTIMENT_POS = {
    "good", "great", "excellent", "amazing", "wonderful", "fantastic", "brilliant",
    "outstanding", "superb", "love", "best", "perfect", "beautiful", "happy",
    "positive", "success", "successful", "innovative", "advanced", "powerful",
    "buono", "ottimo", "eccellente", "fantastico", "brillante", "amore",
    "perfetto", "bello", "felice", "successo", "innovativo", "avanzato",
}

_SENTIMENT_NEG = {
    "bad", "terrible", "awful", "horrible", "poor", "worst", "hate", "ugly",
    "failure", "failed", "negative", "problem", "error", "wrong", "broken",
    "cattivo", "terribile", "orribile", "pessimo", "odio", "brutto",
    "fallimento", "negativo", "problema", "errore", "sbagliato", "rotto",
}


class RegexNLP:
    """NLP basato su regex — zero dipendenze."""

    _SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')
    _WORD_RE = re.compile(r'\b\w+\b', re.UNICODE)
    _EMAIL_RE = re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b')
    _URL_RE = re.compile(r'https?://\S+|www\.\S+')
    _DATE_RE = re.compile(
        r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b'
    )
    _NUMBER_RE = re.compile(r'\b\d[\d,.]*\b')
    _PERSON_RE = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
    _ORG_RE = re.compile(
        r'\b([A-Z][A-Za-z]*(?:\s+(?:Inc|Corp|Ltd|LLC|GmbH|SpA|SA|AG|Co|Group|Foundation|Institute|University))\b\.?)'
    )
    _ACRONYM_RE = re.compile(r'\b[A-Z]{2,6}\b')

    def clean_text(self, text: str) -> str:
        text = self._URL_RE.sub(' ', text)
        text = self._EMAIL_RE.sub(' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = ''.join(c for c in text if unicodedata.category(c)[0] != 'C' or c in '\n\t')
        return text

    def detect_language(self, text: str) -> Tuple[str, float]:
        words = self._WORD_RE.findall(text.lower())
        if len(words) < 5:
            return "unknown", 0.0

        word_set = set(words)
        word_freq: Counter[str] = collections.Counter(words)
        total = sum(word_freq.values())

        best_lang = "en"
        best_score = -1.0

        for lang, profile in _LANG_PROFILES.items():
            score = 0.0
            matches = 0
            for word, weight in profile.items():
                if word in word_set:
                    # Parola presente: punteggio proporzionale a frequenza e peso
                    actual_freq = word_freq[word] / total
                    score += actual_freq * 100 + weight * 10
                    matches += 1
                else:
                    # Parola assente: penalità leggera
                    score -= weight * 2

            if matches == 0:
                score = -10.0

            if score > best_score:
                best_score = score
                best_lang = lang

        confidence = min(1.0, max(0.0, best_score / 5.0))
        return best_lang, round(confidence, 3)

    def extract_entities(self, text: str) -> List[Entity]:
        entities: List[Entity] = []

        for match in self._DATE_RE.finditer(text):
            entities.append(Entity(text=match.group(), label="DATE", start=match.start(), end=match.end()))

        for match in self._EMAIL_RE.finditer(text):
            entities.append(Entity(text=match.group(), label="EMAIL", start=match.start(), end=match.end()))

        for match in self._URL_RE.finditer(text):
            entities.append(Entity(text=match.group(), label="URL", start=match.start(), end=match.end()))

        for match in self._ORG_RE.finditer(text):
            entities.append(Entity(text=match.group(), label="ORG", start=match.start(), end=match.end(), confidence=0.7))

        for match in self._PERSON_RE.finditer(text):
            name = match.group()
            if not any(e.start <= match.start() <= e.end for e in entities):
                entities.append(Entity(text=name, label="PERSON", start=match.start(), end=match.end(), confidence=0.5))

        return entities

    def extract_keywords(self, text: str, lang: str = "en", top_n: int = 20) -> List[Keyword]:
        """TF-based keyword extraction."""
        words = self._WORD_RE.findall(text.lower())
        stopwords = _STOPWORDS.get(lang, _STOPWORDS["en"])

        filtered = [w for w in words if len(w) > 2 and w not in stopwords and not w.isdigit()]
        if not filtered:
            return []

        freq: Counter[str] = collections.Counter(filtered)
        max_freq = freq.most_common(1)[0][1] if freq else 1

        keywords = []
        for word, count in freq.most_common(top_n * 2):
            tf = 0.5 + 0.5 * (count / max_freq)
            keywords.append(Keyword(word=word, score=round(tf, 4), frequency=count))

        keywords.sort(key=lambda k: k.score, reverse=True)
        return keywords[:top_n]

    def extract_keyphrases(self, text: str, lang: str = "en", top_n: int = 10) -> List[Keyword]:
        """RAKE-like keyphrase extraction."""
        stopwords = _STOPWORDS.get(lang, _STOPWORDS["en"])
        sentences = self._SENTENCE_RE.split(text)
        phrases: Counter[str] = collections.Counter()

        for sent in sentences:
            words = self._WORD_RE.findall(sent.lower())
            current_phrase: List[str] = []

            for word in words:
                if word in stopwords or len(word) <= 2:
                    if current_phrase:
                        phrase = " ".join(current_phrase)
                        if len(current_phrase) >= 2:
                            phrases[phrase] += 1
                        current_phrase = []
                else:
                    current_phrase.append(word)

            if current_phrase and len(current_phrase) >= 2:
                phrases[" ".join(current_phrase)] += 1

        results = []
        for phrase, count in phrases.most_common(top_n):
            word_count = len(phrase.split())
            score = count * math.log(1 + word_count)
            results.append(Keyword(word=phrase, score=round(score, 3), frequency=count))

        results.sort(key=lambda k: k.score, reverse=True)
        return results[:top_n]

    def summarize(self, text: str, max_sentences: int = 3) -> str:
        """Extractive summarization basata su TF."""
        sentences = self._SENTENCE_RE.split(text)
        if len(sentences) <= max_sentences:
            return text

        words = self._WORD_RE.findall(text.lower())
        freq: Counter[str] = collections.Counter(words)
        max_freq = freq.most_common(1)[0][1] if freq else 1

        scored = []
        for i, sent in enumerate(sentences):
            sent_words = self._WORD_RE.findall(sent.lower())
            if not sent_words:
                continue
            score = sum(freq.get(w, 0) / max_freq for w in sent_words) / len(sent_words)
            # Bonus per posizione (prima/ultima frase importanti)
            if i == 0:
                score *= 1.5
            elif i == len(sentences) - 1:
                score *= 1.2
            scored.append((i, sent, score))

        scored.sort(key=lambda x: x[2], reverse=True)
        selected = sorted(scored[:max_sentences], key=lambda x: x[0])
        return " ".join(s[1].strip() for s in selected)

    def sentiment(self, text: str) -> Tuple[float, str]:
        """Sentiment analysis basata su lexicon."""
        words = set(self._WORD_RE.findall(text.lower()))
        pos_count = len(words & _SENTIMENT_POS)
        neg_count = len(words & _SENTIMENT_NEG)
        total = pos_count + neg_count

        if total == 0:
            return 0.0, "neutral"

        score = (pos_count - neg_count) / total
        if score > 0.1:
            label = "positive"
        elif score < -0.1:
            label = "negative"
        else:
            label = "neutral"

        return round(score, 3), label

    def analyze(self, text: str) -> NLPResult:
        """Analisi NLP completa."""
        cleaned = self.clean_text(text)
        lang, lang_conf = self.detect_language(cleaned)
        entities = self.extract_entities(text)
        keywords = self.extract_keywords(cleaned, lang)
        summary = self.summarize(cleaned)
        sent_score, sent_label = self.sentiment(cleaned)
        words = self._WORD_RE.findall(cleaned)
        sentences = self._SENTENCE_RE.split(cleaned)

        return NLPResult(
            text_cleaned=cleaned,
            language=lang,
            language_confidence=lang_conf,
            entities=entities,
            keywords=keywords,
            summary=summary,
            sentiment_score=sent_score,
            sentiment_label=sent_label,
            word_count=len(words),
            sentence_count=len(sentences),
            nlp_level="regex",
        )


# ═══════════════════════════════════════════════════════
# 2. NLTK NLP (Livello 2)
# ═══════════════════════════════════════════════════════

class NLTKNLP:
    """NLP con NLTK — richiede pip install nltk."""

    def __init__(self):
        if not _HAS_NLTK:
            raise ImportError("NLTK richiesto. Installa con: pip install nltk")

        # Download risorse se necessario
        self._ensure_data()
        self._regex_nlp = RegexNLP()

    def _ensure_data(self) -> None:
        resources = ["punkt", "punkt_tab", "averaged_perceptron_tagger",
                     "averaged_perceptron_tagger_eng", "maxent_ne_chunker",
                     "maxent_ne_chunker_tab", "words", "stopwords"]
        for res in resources:
            try:
                nltk.data.find(f"tokenizers/{res}" if "punkt" in res else f"corpora/{res}" if res in ("words", "stopwords") else f"taggers/{res}" if "tagger" in res else f"chunkers/{res}")
            except LookupError:
                try:
                    nltk.download(res, quiet=True)
                except Exception:
                    pass

    def extract_entities(self, text: str) -> List[Entity]:
        """NER con NLTK ne_chunk."""
        entities: List[Entity] = []
        try:
            from nltk import word_tokenize, pos_tag, ne_chunk
            from nltk.tree import Tree

            tokens = word_tokenize(text)
            tagged = pos_tag(tokens)
            chunks = ne_chunk(tagged)

            for chunk in chunks:
                if isinstance(chunk, Tree):
                    entity_text = " ".join(c[0] for c in chunk)
                    entity_label = chunk.label()
                    entities.append(Entity(text=entity_text, label=entity_label, confidence=0.75))
        except Exception as e:
            logger.warning(f"NLTK NER fallback a regex: {e}")
            return self._regex_nlp.extract_entities(text)

        # Aggiungi entità regex che NLTK potrebbe aver mancato
        regex_entities = self._regex_nlp.extract_entities(text)
        entity_texts = {e.text for e in entities}
        for re_ent in regex_entities:
            if re_ent.text not in entity_texts:
                entities.append(re_ent)

        return entities

    def extract_keywords(self, text: str, lang: str = "en", top_n: int = 20) -> List[Keyword]:
        """TF-IDF-like con NLTK stopwords."""
        try:
            from nltk.corpus import stopwords as nltk_stopwords
            from nltk.tokenize import word_tokenize
            from nltk.stem import PorterStemmer

            lang_map = {"en": "english", "it": "italian", "es": "spanish",
                        "fr": "french", "de": "german", "pt": "portuguese"}
            nltk_lang = lang_map.get(lang, "english")

            try:
                stop = set(nltk_stopwords.words(nltk_lang))
            except OSError:
                stop = _STOPWORDS.get(lang, _STOPWORDS["en"])

            tokens = word_tokenize(text.lower())
            stemmer = PorterStemmer()

            filtered = [t for t in tokens if t.isalpha() and len(t) > 2 and t not in stop]
            stemmed = [(stemmer.stem(t), t) for t in filtered]

            stem_freq: Counter[str] = collections.Counter(s[0] for s in stemmed)
            stem_to_word: Dict[str, str] = {}
            for stem, word in stemmed:
                if stem not in stem_to_word or len(word) > len(stem_to_word[stem]):
                    stem_to_word[stem] = word

            max_freq = stem_freq.most_common(1)[0][1] if stem_freq else 1
            keywords = []
            for stem, count in stem_freq.most_common(top_n):
                tf = 0.5 + 0.5 * (count / max_freq)
                keywords.append(Keyword(
                    word=stem_to_word.get(stem, stem),
                    score=round(tf, 4),
                    frequency=count,
                ))

            return keywords

        except Exception:
            return self._regex_nlp.extract_keywords(text, lang, top_n)

    def analyze(self, text: str) -> NLPResult:
        cleaned = self._regex_nlp.clean_text(text)
        lang, lang_conf = self._regex_nlp.detect_language(cleaned)
        entities = self.extract_entities(text)
        keywords = self.extract_keywords(cleaned, lang)
        summary = self._regex_nlp.summarize(cleaned)
        sent_score, sent_label = self._regex_nlp.sentiment(cleaned)

        try:
            from nltk.tokenize import word_tokenize, sent_tokenize
            word_count = len(word_tokenize(cleaned))
            sent_count = len(sent_tokenize(cleaned))
        except Exception:
            word_count = len(cleaned.split())
            sent_count = len(RegexNLP._SENTENCE_RE.split(cleaned))

        return NLPResult(
            text_cleaned=cleaned,
            language=lang,
            language_confidence=lang_conf,
            entities=entities,
            keywords=keywords,
            summary=summary,
            sentiment_score=sent_score,
            sentiment_label=sent_label,
            word_count=word_count,
            sentence_count=sent_count,
            nlp_level="nltk",
        )


# ═══════════════════════════════════════════════════════
# 3. SPACY NLP (Livello 3)
# ═══════════════════════════════════════════════════════

class SpacyNLP:
    """NLP con spaCy — massima qualità. Richiede pip install spacy."""

    # Modelli per lingua
    _MODELS: Dict[str, List[str]] = {
        "en": ["en_core_web_sm", "en_core_web_md", "en_core_web_lg"],
        "it": ["it_core_news_sm", "it_core_news_md", "it_core_news_lg"],
        "es": ["es_core_news_sm", "es_core_news_md"],
        "fr": ["fr_core_news_sm", "fr_core_news_md"],
        "de": ["de_core_news_sm", "de_core_news_md"],
        "pt": ["pt_core_news_sm", "pt_core_news_md"],
        "xx": ["xx_ent_wiki_sm"],  # multilingue
    }

    def __init__(self, default_model: str = ""):
        if not _HAS_SPACY:
            raise ImportError("spaCy richiesto. Installa con: pip install spacy")

        self._nlp_models: Dict[str, Any] = {}
        self._regex_nlp = RegexNLP()

        if default_model:
            try:
                self._nlp_models["default"] = spacy.load(default_model)
                logger.info(f"SpacyNLP: modello {default_model} caricato")
            except OSError:
                logger.warning(f"Modello {default_model} non trovato, tentativo auto-load")

    def _get_model(self, lang: str = "en") -> Any:
        if lang in self._nlp_models:
            return self._nlp_models[lang]
        if "default" in self._nlp_models:
            return self._nlp_models["default"]

        # Prova a caricare modello per lingua
        models = self._MODELS.get(lang, self._MODELS.get("xx", []))
        for model_name in models:
            try:
                nlp = spacy.load(model_name)
                self._nlp_models[lang] = nlp
                logger.info(f"SpacyNLP: modello {model_name} caricato per {lang}")
                return nlp
            except OSError:
                continue

        # Ultimo tentativo: modello multilingue
        for model_name in self._MODELS.get("xx", []):
            try:
                nlp = spacy.load(model_name)
                self._nlp_models["xx"] = nlp
                return nlp
            except OSError:
                continue

        logger.warning(f"Nessun modello spaCy per {lang}, fallback a regex")
        return None

    def extract_entities(self, text: str, lang: str = "en") -> List[Entity]:
        nlp = self._get_model(lang)
        if nlp is None:
            return self._regex_nlp.extract_entities(text)

        doc = nlp(text[:100000])  # Limita per performance
        entities = []
        for ent in doc.ents:
            entities.append(Entity(
                text=ent.text,
                label=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
                confidence=0.9,
            ))
        return entities

    def extract_keywords(self, text: str, lang: str = "en", top_n: int = 20) -> List[Keyword]:
        nlp = self._get_model(lang)
        if nlp is None:
            return self._regex_nlp.extract_keywords(text, lang, top_n)

        doc = nlp(text[:100000])

        # Usa noun chunks + named entities
        candidates: Counter[str] = collections.Counter()

        for chunk in doc.noun_chunks:
            lemma = chunk.root.lemma_.lower()
            if len(lemma) > 2 and not chunk.root.is_stop:
                candidates[lemma] += 1

        for token in doc:
            if (token.pos_ in ("NOUN", "PROPN", "ADJ")
                    and not token.is_stop
                    and len(token.lemma_) > 2):
                candidates[token.lemma_.lower()] += 1

        max_freq = candidates.most_common(1)[0][1] if candidates else 1
        keywords = []
        for word, count in candidates.most_common(top_n):
            tf = 0.5 + 0.5 * (count / max_freq)
            keywords.append(Keyword(word=word, score=round(tf, 4), frequency=count))

        return keywords

    def analyze(self, text: str) -> NLPResult:
        cleaned = self._regex_nlp.clean_text(text)
        lang, lang_conf = self._regex_nlp.detect_language(cleaned)

        nlp = self._get_model(lang)
        if nlp is None:
            return self._regex_nlp.analyze(text)

        doc = nlp(cleaned[:100000])

        entities = self.extract_entities(text, lang)
        keywords = self.extract_keywords(cleaned, lang)
        summary = self._regex_nlp.summarize(cleaned)
        sent_score, sent_label = self._regex_nlp.sentiment(cleaned)

        return NLPResult(
            text_cleaned=cleaned,
            language=lang,
            language_confidence=lang_conf,
            entities=entities,
            keywords=keywords,
            summary=summary,
            sentiment_score=sent_score,
            sentiment_label=sent_label,
            word_count=len(doc),
            sentence_count=len(list(doc.sents)),
            nlp_level="spacy",
        )


# ═══════════════════════════════════════════════════════
# Unified NLP Pipeline
# ═══════════════════════════════════════════════════════

class NLPPipeline:
    """
    Pipeline NLP unificata con fallback automatico.

    Uso:
        nlp = NLPPipeline()  # auto-detect livello migliore
        result = nlp.analyze("Your text here...")
        print(result.entities, result.keywords, result.summary)
    """

    def __init__(self, preferred_level: Optional[NLPLevel] = None):
        self._level = preferred_level or detect_nlp_level()
        self._engine: Any = None
        self._init_engine()

    def _init_engine(self) -> None:
        if self._level == NLPLevel.SPACY:
            try:
                self._engine = SpacyNLP()
                logger.info("NLPPipeline: usando spaCy (Livello 3)")
                return
            except Exception as e:
                logger.warning(f"spaCy non disponibile: {e}, fallback NLTK")
                self._level = NLPLevel.NLTK

        if self._level == NLPLevel.NLTK:
            try:
                self._engine = NLTKNLP()
                logger.info("NLPPipeline: usando NLTK (Livello 2)")
                return
            except Exception as e:
                logger.warning(f"NLTK non disponibile: {e}, fallback regex")
                self._level = NLPLevel.REGEX

        self._engine = RegexNLP()
        logger.info("NLPPipeline: usando Regex (Livello 1)")

    def analyze(self, text: str) -> NLPResult:
        """Analisi NLP completa con il miglior motore disponibile."""
        return self._engine.analyze(text)

    def clean_text(self, text: str) -> str:
        if hasattr(self._engine, 'clean_text'):
            return self._engine.clean_text(text)
        return RegexNLP().clean_text(text)

    def detect_language(self, text: str) -> Tuple[str, float]:
        if hasattr(self._engine, 'detect_language'):
            return self._engine.detect_language(text)
        return RegexNLP().detect_language(text)

    def extract_entities(self, text: str) -> List[Entity]:
        return self._engine.extract_entities(text) if hasattr(self._engine, 'extract_entities') else []

    def extract_keywords(self, text: str, lang: str = "en", top_n: int = 20) -> List[Keyword]:
        return self._engine.extract_keywords(text, lang, top_n)

    def summarize(self, text: str, max_sentences: int = 3) -> str:
        if hasattr(self._engine, 'summarize'):
            return self._engine.summarize(text, max_sentences)
        return RegexNLP().summarize(text, max_sentences)

    @property
    def level(self) -> NLPLevel:
        return self._level

    @property
    def level_name(self) -> str:
        return self._level.name


# ═══════════════════════════════════════════════════════
# Singleton & Helper
# ═══════════════════════════════════════════════════════

_pipeline: Optional[NLPPipeline] = None


def get_nlp_pipeline(preferred_level: Optional[NLPLevel] = None) -> NLPPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = NLPPipeline(preferred_level)
    return _pipeline


def reset_nlp_pipeline() -> None:
    global _pipeline
    _pipeline = None


def available_nlp_levels() -> Dict[str, bool]:
    return {
        "regex": True,
        "nltk": _HAS_NLTK,
        "spacy": _HAS_SPACY,
    }
