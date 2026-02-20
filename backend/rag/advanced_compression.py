"""
╔══════════════════════════════════════════════════════════════════════╗
║        VIO 83 AI ORCHESTRA — Advanced Compression Engine            ║
║                                                                      ║
║  Multi-algoritmo con selezione automatica:                           ║
║  • zlib    — default, bilanciato (stdlib)                            ║
║  • lz4     — velocissimo, per hot data (opzionale)                   ║
║  • zstd    — miglior rapporto compressione/velocità (opzionale)      ║
║  • bz2     — alta compressione, lento (stdlib)                       ║
║  • lzma/xz — massima compressione, molto lento (stdlib)              ║
║                                                                      ║
║  Features:                                                           ║
║  • Auto-detection algoritmo migliore per tipo dati                   ║
║  • Streaming compression per file enormi                             ║
║  • Dictionary compression (Zstd) per dati simili                     ║
║  • Benchmark integrato per confronto                                 ║
║  • Transparent decompression (header auto-detect)                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import bz2
import hashlib
import io
import lzma
import struct
import time
import zlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("vio83.compression")

# ═══════════════════════════════════════════════════════
# Disponibilità librerie opzionali
# ═══════════════════════════════════════════════════════

_HAS_LZ4 = False
_HAS_ZSTD = False

try:
    import lz4.frame as lz4_frame
    import lz4.block as lz4_block
    _HAS_LZ4 = True
except ImportError:
    pass

try:
    import zstandard as zstd
    _HAS_ZSTD = True
except ImportError:
    pass


# ═══════════════════════════════════════════════════════
# Tipi e Configurazione
# ═══════════════════════════════════════════════════════

class CompressionAlgo(Enum):
    NONE = "none"
    ZLIB = "zlib"
    LZ4 = "lz4"
    ZSTD = "zstd"
    BZ2 = "bz2"
    LZMA = "lzma"       # = xz
    AUTO = "auto"        # Selezione automatica


# Magic bytes per identificazione trasparente
_MAGIC = {
    CompressionAlgo.ZLIB: b"VZ01",
    CompressionAlgo.LZ4: b"VL01",
    CompressionAlgo.ZSTD: b"VS01",
    CompressionAlgo.BZ2: b"VB01",
    CompressionAlgo.LZMA: b"VX01",
    CompressionAlgo.NONE: b"VN01",
}

_MAGIC_REVERSE = {v: k for k, v in _MAGIC.items()}

# Header: 4 bytes magic + 4 bytes original size (uint32) + 4 bytes checksum
_HEADER_SIZE = 12
_HEADER_FMT = "4sII"  # magic(4) + original_size(4) + crc32(4)


@dataclass
class CompressionResult:
    """Risultato di un'operazione di compressione."""
    algo: CompressionAlgo
    original_size: int
    compressed_size: int
    ratio: float  # compressed / original (< 1.0 = buono)
    time_ms: float
    throughput_mbps: float  # MB/s


@dataclass
class CompressionProfile:
    """Profilo di compressione per tipo di dati."""
    name: str
    algo: CompressionAlgo
    level: int
    description: str


# Profili predefiniti
PROFILES: Dict[str, CompressionProfile] = {
    "fastest": CompressionProfile("fastest", CompressionAlgo.LZ4, 0, "Velocità massima, compressione leggera"),
    "fast": CompressionProfile("fast", CompressionAlgo.ZSTD, 1, "Veloce con buona compressione"),
    "balanced": CompressionProfile("balanced", CompressionAlgo.ZSTD, 3, "Bilanciato velocità/compressione"),
    "default": CompressionProfile("default", CompressionAlgo.ZLIB, 6, "Default stdlib, nessuna dipendenza"),
    "high": CompressionProfile("high", CompressionAlgo.ZSTD, 9, "Alta compressione, moderatamente lento"),
    "maximum": CompressionProfile("maximum", CompressionAlgo.LZMA, 6, "Massima compressione, lento"),
    "archive": CompressionProfile("archive", CompressionAlgo.LZMA, 9, "Archivio, massima compressione"),
    "text": CompressionProfile("text", CompressionAlgo.ZSTD, 5, "Ottimizzato per testo"),
    "embeddings": CompressionProfile("embeddings", CompressionAlgo.LZ4, 0, "Ottimizzato per vettori numerici"),
    "metadata": CompressionProfile("metadata", CompressionAlgo.ZLIB, 9, "Metadata JSON compatto"),
}


# ═══════════════════════════════════════════════════════
# Compressore Core
# ═══════════════════════════════════════════════════════

class Compressor:
    """
    Compressore multi-algoritmo con header trasparente.

    Uso base:
        comp = Compressor()
        compressed = comp.compress(data)              # auto-detect migliore
        original = comp.decompress(compressed)         # auto-detect algo da header

        compressed = comp.compress(data, algo=CompressionAlgo.ZSTD, level=5)
        compressed = comp.compress_profile(data, "text")
    """

    def __init__(self, default_algo: CompressionAlgo = CompressionAlgo.ZLIB, default_level: int = 6):
        self.default_algo = self._resolve_algo(default_algo)
        self.default_level = default_level

        # Zstd compressor/decompressor (riutilizzabili, thread-safe)
        self._zstd_compressors: Dict[int, Any] = {}
        self._zstd_decompressor = None
        if _HAS_ZSTD:
            self._zstd_decompressor = zstd.ZstdDecompressor()

    def _resolve_algo(self, algo: CompressionAlgo) -> CompressionAlgo:
        """Risolvi AUTO e verifica disponibilità."""
        if algo == CompressionAlgo.AUTO:
            if _HAS_ZSTD:
                return CompressionAlgo.ZSTD
            return CompressionAlgo.ZLIB

        if algo == CompressionAlgo.LZ4 and not _HAS_LZ4:
            logger.warning("LZ4 non disponibile, fallback a zlib")
            return CompressionAlgo.ZLIB
        if algo == CompressionAlgo.ZSTD and not _HAS_ZSTD:
            logger.warning("Zstd non disponibile, fallback a zlib")
            return CompressionAlgo.ZLIB
        return algo

    def _get_zstd_compressor(self, level: int) -> Any:
        if level not in self._zstd_compressors:
            self._zstd_compressors[level] = zstd.ZstdCompressor(level=level)
        return self._zstd_compressors[level]

    # ─────────────────────────────────────────────────
    # Compressione
    # ─────────────────────────────────────────────────

    def compress(
        self,
        data: bytes,
        algo: Optional[CompressionAlgo] = None,
        level: Optional[int] = None,
    ) -> bytes:
        """
        Comprime dati con header trasparente.

        Returns:
            bytes con header VIO83 (12 bytes) + payload compresso
        """
        if not data:
            return self._pack_header(CompressionAlgo.NONE, 0, 0) + b""

        algo = self._resolve_algo(algo or self.default_algo)
        level = level if level is not None else self.default_level
        original_size = len(data)
        crc = zlib.crc32(data) & 0xFFFFFFFF

        t0 = time.perf_counter()

        if algo == CompressionAlgo.NONE:
            compressed = data
        elif algo == CompressionAlgo.ZLIB:
            compressed = zlib.compress(data, level)
        elif algo == CompressionAlgo.LZ4:
            compressed = lz4_frame.compress(data, compression_level=level)
        elif algo == CompressionAlgo.ZSTD:
            cctx = self._get_zstd_compressor(level)
            compressed = cctx.compress(data)
        elif algo == CompressionAlgo.BZ2:
            compressed = bz2.compress(data, compresslevel=max(1, min(9, level)))
        elif algo == CompressionAlgo.LZMA:
            compressed = lzma.compress(data, preset=max(0, min(9, level)))
        else:
            compressed = zlib.compress(data, level)

        elapsed = time.perf_counter() - t0

        # Se la compressione non aiuta, salva non compresso
        if len(compressed) >= original_size:
            return self._pack_header(CompressionAlgo.NONE, original_size, crc) + data

        return self._pack_header(algo, original_size, crc) + compressed

    def decompress(self, data: bytes) -> bytes:
        """
        Decomprime automaticamente (legge algo dall'header).

        Returns:
            bytes originali decompresse
        """
        if len(data) < _HEADER_SIZE:
            return data  # Nessun header, restituisci raw

        algo, original_size, stored_crc = self._unpack_header(data[:_HEADER_SIZE])
        payload = data[_HEADER_SIZE:]

        if algo == CompressionAlgo.NONE:
            result = payload
        elif algo == CompressionAlgo.ZLIB:
            result = zlib.decompress(payload)
        elif algo == CompressionAlgo.LZ4:
            if not _HAS_LZ4:
                raise ImportError("lz4 richiesto per decomprimere dati LZ4")
            result = lz4_frame.decompress(payload)
        elif algo == CompressionAlgo.ZSTD:
            if not _HAS_ZSTD:
                raise ImportError("zstandard richiesto per decomprimere dati Zstd")
            result = self._zstd_decompressor.decompress(payload)
        elif algo == CompressionAlgo.BZ2:
            result = bz2.decompress(payload)
        elif algo == CompressionAlgo.LZMA:
            result = lzma.decompress(payload)
        else:
            raise ValueError(f"Algoritmo sconosciuto nell'header: {algo}")

        # Verifica integrità
        actual_crc = zlib.crc32(result) & 0xFFFFFFFF
        if stored_crc != 0 and actual_crc != stored_crc:
            raise ValueError(
                f"Checksum CRC32 non valido: atteso {stored_crc:#x}, ottenuto {actual_crc:#x}"
            )

        return result

    def compress_profile(self, data: bytes, profile_name: str) -> bytes:
        """Comprimi usando un profilo predefinito."""
        profile = PROFILES.get(profile_name, PROFILES["default"])
        algo = self._resolve_algo(profile.algo)
        return self.compress(data, algo=algo, level=profile.level)

    # ─────────────────────────────────────────────────
    # Streaming
    # ─────────────────────────────────────────────────

    def compress_stream(
        self,
        input_stream: io.RawIOBase,
        output_stream: io.RawIOBase,
        algo: Optional[CompressionAlgo] = None,
        level: Optional[int] = None,
        chunk_size: int = 1024 * 1024,
    ) -> CompressionResult:
        """
        Compressione streaming per file enormi.
        Non tiene tutto in memoria.
        """
        algo = self._resolve_algo(algo or self.default_algo)
        level = level if level is not None else self.default_level
        total_in = 0
        total_out = 0
        t0 = time.perf_counter()

        if algo == CompressionAlgo.ZLIB:
            compressor = zlib.compressobj(level)
            while True:
                chunk = input_stream.read(chunk_size)
                if not chunk:
                    break
                total_in += len(chunk)
                compressed = compressor.compress(chunk)
                if compressed:
                    output_stream.write(compressed)
                    total_out += len(compressed)
            tail = compressor.flush()
            if tail:
                output_stream.write(tail)
                total_out += len(tail)

        elif algo == CompressionAlgo.ZSTD and _HAS_ZSTD:
            cctx = zstd.ZstdCompressor(level=level)
            with cctx.stream_writer(output_stream) as writer:
                while True:
                    chunk = input_stream.read(chunk_size)
                    if not chunk:
                        break
                    total_in += len(chunk)
                    writer.write(chunk)
            total_out = output_stream.tell() if hasattr(output_stream, 'tell') else 0

        elif algo == CompressionAlgo.LZ4 and _HAS_LZ4:
            ctx = lz4_frame.create_compression_context()
            header = lz4_frame.compress_begin(ctx)
            output_stream.write(header)
            total_out += len(header)
            while True:
                chunk = input_stream.read(chunk_size)
                if not chunk:
                    break
                total_in += len(chunk)
                compressed = lz4_frame.compress_chunk(ctx, chunk)
                output_stream.write(compressed)
                total_out += len(compressed)
            tail = lz4_frame.compress_flush(ctx)
            output_stream.write(tail)
            total_out += len(tail)

        else:
            # Fallback: leggi tutto e comprimi in blocco
            all_data = input_stream.read()
            total_in = len(all_data)
            compressed = self.compress(all_data, algo=algo, level=level)
            output_stream.write(compressed)
            total_out = len(compressed)

        elapsed = time.perf_counter() - t0
        ratio = total_out / total_in if total_in > 0 else 1.0
        throughput = (total_in / (1024 * 1024)) / elapsed if elapsed > 0 else 0

        return CompressionResult(
            algo=algo,
            original_size=total_in,
            compressed_size=total_out,
            ratio=round(ratio, 4),
            time_ms=round(elapsed * 1000, 2),
            throughput_mbps=round(throughput, 2),
        )

    # ─────────────────────────────────────────────────
    # Dictionary Compression (Zstd)
    # ─────────────────────────────────────────────────

    def train_dictionary(self, samples: List[bytes], dict_size: int = 1024 * 1024) -> Optional[bytes]:
        """
        Addestra un dizionario Zstd da campioni simili.
        Perfetto per comprimere metadata/JSON con struttura ripetitiva.

        Compressione con dizionario: fino a 5-10x meglio su dati piccoli simili.
        """
        if not _HAS_ZSTD:
            logger.warning("Zstd non disponibile, dizionario non creato")
            return None

        dict_data = zstd.train_dictionary(dict_size, samples)
        return dict_data.as_bytes()

    def compress_with_dict(self, data: bytes, dict_data: bytes, level: int = 3) -> bytes:
        """Comprimi usando un dizionario pre-addestrato."""
        if not _HAS_ZSTD:
            return self.compress(data, algo=CompressionAlgo.ZLIB)

        d = zstd.ZstdCompressionDict(dict_data)
        cctx = zstd.ZstdCompressor(dict_data=d, level=level)
        compressed = cctx.compress(data)
        return self._pack_header(CompressionAlgo.ZSTD, len(data), zlib.crc32(data) & 0xFFFFFFFF) + compressed

    def decompress_with_dict(self, data: bytes, dict_data: bytes) -> bytes:
        """Decomprimi usando un dizionario."""
        if not _HAS_ZSTD:
            return self.decompress(data)

        algo, original_size, stored_crc = self._unpack_header(data[:_HEADER_SIZE])
        payload = data[_HEADER_SIZE:]

        d = zstd.ZstdCompressionDict(dict_data)
        dctx = zstd.ZstdDecompressor(dict_data=d)
        result = dctx.decompress(payload)

        actual_crc = zlib.crc32(result) & 0xFFFFFFFF
        if stored_crc != 0 and actual_crc != stored_crc:
            raise ValueError("Checksum CRC32 non valido")

        return result

    # ─────────────────────────────────────────────────
    # Header pack/unpack
    # ─────────────────────────────────────────────────

    def _pack_header(self, algo: CompressionAlgo, original_size: int, crc: int) -> bytes:
        magic = _MAGIC.get(algo, _MAGIC[CompressionAlgo.NONE])
        # Tronca a uint32 se necessario
        original_size = min(original_size, 0xFFFFFFFF)
        crc = crc & 0xFFFFFFFF
        return struct.pack(_HEADER_FMT, magic, original_size, crc)

    def _unpack_header(self, header: bytes) -> Tuple[CompressionAlgo, int, int]:
        magic, original_size, crc = struct.unpack(_HEADER_FMT, header)
        algo = _MAGIC_REVERSE.get(magic, CompressionAlgo.NONE)
        return algo, original_size, crc

    # ─────────────────────────────────────────────────
    # Auto-selection
    # ─────────────────────────────────────────────────

    def select_best_algo(
        self,
        sample: bytes,
        candidates: Optional[List[CompressionAlgo]] = None,
        prefer: str = "balanced",
    ) -> Tuple[CompressionAlgo, int]:
        """
        Testa diversi algoritmi su un campione e restituisce il migliore.

        prefer:
            "speed"     — minimizza tempo
            "ratio"     — minimizza dimensione
            "balanced"  — equilibrio (default)
        """
        if candidates is None:
            candidates = [CompressionAlgo.ZLIB, CompressionAlgo.BZ2]
            if _HAS_LZ4:
                candidates.append(CompressionAlgo.LZ4)
            if _HAS_ZSTD:
                candidates.append(CompressionAlgo.ZSTD)

        results: List[Tuple[CompressionAlgo, int, float, float]] = []  # algo, level, ratio, time

        for algo in candidates:
            resolved = self._resolve_algo(algo)
            if resolved != algo:
                continue

            levels = self._get_test_levels(algo)
            for lvl in levels:
                t0 = time.perf_counter()
                compressed = self.compress(sample, algo=algo, level=lvl)
                elapsed = time.perf_counter() - t0
                ratio = len(compressed) / len(sample) if len(sample) > 0 else 1.0
                results.append((algo, lvl, ratio, elapsed))

        if not results:
            return CompressionAlgo.ZLIB, 6

        if prefer == "speed":
            results.sort(key=lambda x: x[3])
        elif prefer == "ratio":
            results.sort(key=lambda x: x[2])
        else:
            # Balanced: score = ratio * 0.6 + normalized_time * 0.4
            max_time = max(r[3] for r in results) or 1.0
            results.sort(key=lambda x: x[2] * 0.6 + (x[3] / max_time) * 0.4)

        best = results[0]
        logger.info(f"Algoritmo migliore per {prefer}: {best[0].value} livello {best[1]} "
                     f"(ratio={best[2]:.3f}, tempo={best[3]*1000:.1f}ms)")
        return best[0], best[1]

    def _get_test_levels(self, algo: CompressionAlgo) -> List[int]:
        if algo == CompressionAlgo.LZ4:
            return [0, 3, 9]
        if algo == CompressionAlgo.ZSTD:
            return [1, 3, 7]
        if algo == CompressionAlgo.ZLIB:
            return [1, 6, 9]
        if algo == CompressionAlgo.BZ2:
            return [1, 5, 9]
        if algo == CompressionAlgo.LZMA:
            return [0, 3, 6]
        return [6]

    # ─────────────────────────────────────────────────
    # Benchmark
    # ─────────────────────────────────────────────────

    def benchmark(
        self,
        data: bytes,
        algos: Optional[List[CompressionAlgo]] = None,
        levels: Optional[Dict[CompressionAlgo, List[int]]] = None,
        iterations: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Benchmark completo di tutti gli algoritmi su dati reali.

        Returns:
            Lista ordinata per score complessivo
        """
        if algos is None:
            algos = [CompressionAlgo.ZLIB, CompressionAlgo.BZ2, CompressionAlgo.LZMA]
            if _HAS_LZ4:
                algos.append(CompressionAlgo.LZ4)
            if _HAS_ZSTD:
                algos.append(CompressionAlgo.ZSTD)

        results: List[Dict[str, Any]] = []
        original_size = len(data)

        for algo in algos:
            resolved = self._resolve_algo(algo)
            if resolved != algo:
                continue

            test_levels = (levels or {}).get(algo) or self._get_test_levels(algo)

            for lvl in test_levels:
                compress_times = []
                decompress_times = []
                compressed_size = 0

                for _ in range(iterations):
                    # Compressione
                    t0 = time.perf_counter()
                    compressed = self.compress(data, algo=algo, level=lvl)
                    compress_times.append(time.perf_counter() - t0)
                    compressed_size = len(compressed)

                    # Decompressione
                    t0 = time.perf_counter()
                    self.decompress(compressed)
                    decompress_times.append(time.perf_counter() - t0)

                avg_compress = sum(compress_times) / len(compress_times)
                avg_decompress = sum(decompress_times) / len(decompress_times)
                ratio = compressed_size / original_size if original_size > 0 else 1.0

                results.append({
                    "algo": algo.value,
                    "level": lvl,
                    "original_bytes": original_size,
                    "compressed_bytes": compressed_size,
                    "ratio": round(ratio, 4),
                    "savings_pct": round((1 - ratio) * 100, 1),
                    "compress_ms": round(avg_compress * 1000, 2),
                    "decompress_ms": round(avg_decompress * 1000, 2),
                    "compress_mbps": round((original_size / (1024 * 1024)) / avg_compress, 1) if avg_compress > 0 else 0,
                    "decompress_mbps": round((compressed_size / (1024 * 1024)) / avg_decompress, 1) if avg_decompress > 0 else 0,
                })

        # Ordina per rapporto compressione
        results.sort(key=lambda x: x["ratio"])
        return results


# ═══════════════════════════════════════════════════════
# Batch Compressor (per distillazione massiva)
# ═══════════════════════════════════════════════════════

class BatchCompressor:
    """
    Compressore ottimizzato per batch di documenti simili.
    Usa dictionary compression quando disponibile.
    """

    def __init__(self, algo: CompressionAlgo = CompressionAlgo.AUTO, level: int = 3):
        self.compressor = Compressor(default_algo=algo, default_level=level)
        self._dict_data: Optional[bytes] = None
        self._batch_buffer: List[bytes] = []
        self._dict_trained = False

    def add_sample(self, data: bytes) -> None:
        """Aggiungi campione per training dizionario."""
        if len(self._batch_buffer) < 1000:
            self._batch_buffer.append(data)

    def train(self, dict_size: int = 256 * 1024) -> bool:
        """Addestra dizionario dai campioni raccolti."""
        if not self._batch_buffer:
            return False

        self._dict_data = self.compressor.train_dictionary(
            self._batch_buffer[:500],
            dict_size=dict_size,
        )
        self._dict_trained = self._dict_data is not None
        self._batch_buffer.clear()
        if self._dict_trained:
            logger.info(f"Dizionario Zstd addestrato: {len(self._dict_data)} bytes")
        return self._dict_trained

    def compress(self, data: bytes) -> bytes:
        """Comprimi usando dizionario se disponibile."""
        if self._dict_trained and self._dict_data:
            return self.compressor.compress_with_dict(data, self._dict_data)
        return self.compressor.compress(data)

    def decompress(self, data: bytes) -> bytes:
        """Decomprimi usando dizionario se disponibile."""
        if self._dict_trained and self._dict_data:
            try:
                return self.compressor.decompress_with_dict(data, self._dict_data)
            except Exception:
                pass
        return self.compressor.decompress(data)

    def get_dictionary(self) -> Optional[bytes]:
        """Restituisci dizionario per salvataggio."""
        return self._dict_data

    def load_dictionary(self, dict_data: bytes) -> None:
        """Carica dizionario pre-addestrato."""
        self._dict_data = dict_data
        self._dict_trained = True


# ═══════════════════════════════════════════════════════
# Singleton & Helper
# ═══════════════════════════════════════════════════════

_default_compressor: Optional[Compressor] = None


def get_compressor() -> Compressor:
    """Singleton del compressore default."""
    global _default_compressor
    if _default_compressor is None:
        _default_compressor = Compressor()
    return _default_compressor


def compress(data: bytes, profile: str = "default") -> bytes:
    """Shortcut: comprimi con profilo."""
    return get_compressor().compress_profile(data, profile)


def decompress(data: bytes) -> bytes:
    """Shortcut: decomprimi (auto-detect)."""
    return get_compressor().decompress(data)


def available_algorithms() -> Dict[str, bool]:
    """Lista algoritmi disponibili."""
    return {
        "zlib": True,
        "bz2": True,
        "lzma": True,
        "lz4": _HAS_LZ4,
        "zstd": _HAS_ZSTD,
    }
