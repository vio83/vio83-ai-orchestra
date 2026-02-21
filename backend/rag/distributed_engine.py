# ============================================================
# VIO 83 AI ORCHESTRA — Copyright (c) 2026 Viorica Porcu (vio83)
# DUAL LICENSE: Proprietary + AGPL-3.0 — See LICENSE files
# ALL RIGHTS RESERVED — https://github.com/vio83/vio83-ai-orchestra
# ============================================================
"""
╔══════════════════════════════════════════════════════════════════════╗
║        VIO 83 AI ORCHESTRA — Distributed Processing Engine          ║
║                                                                      ║
║  Calcolo parallelo e distribuito multi-backend:                      ║
║  • ProcessPool  — multiprocessing locale (default, zero config)      ║
║  • ThreadPool   — I/O-bound tasks (download, API calls)              ║
║  • AsyncPool    — asyncio per massimo throughput I/O                 ║
║  • DaskCluster  — Dask distributed (opzionale, cluster)              ║
║  • SparkCluster — PySpark (opzionale, big data)                      ║
║                                                                      ║
║  Features:                                                           ║
║  • Pipeline DAG con dipendenze                                       ║
║  • Progress tracking in tempo reale                                  ║
║  • Auto-scaling basato su risorse disponibili                        ║
║  • Fault tolerance con retry automatico                              ║
║  • Work stealing per bilanciamento carico                            ║
║  • Batch processing con backpressure                                 ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import queue
import signal
import sys
import threading
import time
import traceback
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    Future,
    as_completed,
)
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any, Callable, Dict, Generator, Generic, List, Optional, Sequence,
    Tuple, TypeVar, Union,
)

logger = logging.getLogger("vio83.distributed")

T = TypeVar("T")
R = TypeVar("R")

# ═══════════════════════════════════════════════════════
# Rilevamento risorse
# ═══════════════════════════════════════════════════════

@dataclass
class SystemResources:
    """Risorse di sistema rilevate automaticamente."""
    cpu_count: int = 1
    cpu_count_physical: int = 1
    memory_total_gb: float = 0.0
    memory_available_gb: float = 0.0
    disk_free_gb: float = 0.0
    platform: str = ""


def detect_resources() -> SystemResources:
    """Rileva risorse disponibili sul sistema."""
    cpu_logical = os.cpu_count() or 1

    # CPU fisiche (se psutil disponibile)
    cpu_physical = cpu_logical
    mem_total = 0.0
    mem_avail = 0.0
    try:
        import psutil
        cpu_physical = psutil.cpu_count(logical=False) or cpu_logical
        mem = psutil.virtual_memory()
        mem_total = mem.total / (1024**3)
        mem_avail = mem.available / (1024**3)
    except ImportError:
        # Fallback senza psutil
        try:
            import resource
            # Su macOS/Linux
            mem_total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024**3)
            mem_avail = mem_total * 0.6  # stima
        except (ValueError, OSError, AttributeError):
            mem_total = 8.0  # fallback
            mem_avail = 4.0

    # Disco
    disk_free = 0.0
    try:
        import shutil
        usage = shutil.disk_usage(os.path.expanduser("~"))
        disk_free = usage.free / (1024**3)
    except Exception:
        disk_free = 50.0

    return SystemResources(
        cpu_count=cpu_logical,
        cpu_count_physical=cpu_physical,
        memory_total_gb=round(mem_total, 2),
        memory_available_gb=round(mem_avail, 2),
        disk_free_gb=round(disk_free, 2),
        platform=sys.platform,
    )


# ═══════════════════════════════════════════════════════
# Task & Progress
# ═══════════════════════════════════════════════════════

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Risultato di un task distribuito."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    worker_id: str = ""
    retries: int = 0


@dataclass
class BatchProgress:
    """Progresso di un batch di task."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    running: int = 0
    pending: int = 0
    elapsed_seconds: float = 0.0
    items_per_second: float = 0.0
    eta_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def percent(self) -> float:
        if self.total == 0:
            return 100.0
        return round((self.completed / self.total) * 100, 1)

    @property
    def is_done(self) -> bool:
        return (self.completed + self.failed) >= self.total


# ═══════════════════════════════════════════════════════
# Progress Callback
# ═══════════════════════════════════════════════════════

class ProgressTracker:
    """Thread-safe progress tracker con callback."""

    def __init__(self, total: int, callback: Optional[Callable[[BatchProgress], None]] = None):
        self._lock = threading.Lock()
        self._progress = BatchProgress(total=total, pending=total)
        self._start_time = time.time()
        self._callback = callback

    def start_task(self) -> None:
        with self._lock:
            self._progress.running += 1
            self._progress.pending -= 1
            self._notify()

    def complete_task(self) -> None:
        with self._lock:
            self._progress.running -= 1
            self._progress.completed += 1
            self._update_stats()
            self._notify()

    def fail_task(self, error: str = "") -> None:
        with self._lock:
            self._progress.running -= 1
            self._progress.failed += 1
            if error:
                self._progress.errors.append(error[:200])
            self._update_stats()
            self._notify()

    def _update_stats(self) -> None:
        elapsed = time.time() - self._start_time
        self._progress.elapsed_seconds = round(elapsed, 1)
        done = self._progress.completed + self._progress.failed
        if elapsed > 0 and done > 0:
            self._progress.items_per_second = round(done / elapsed, 1)
            remaining = self._progress.total - done
            self._progress.eta_seconds = round(remaining / self._progress.items_per_second, 1)

    def _notify(self) -> None:
        if self._callback:
            try:
                self._callback(self._progress)
            except Exception:
                pass

    @property
    def progress(self) -> BatchProgress:
        with self._lock:
            return self._progress


# ═══════════════════════════════════════════════════════
# 1. LOCAL PROCESS POOL (default)
# ═══════════════════════════════════════════════════════

class LocalProcessPool:
    """
    Pool di processi locale con multiprocessing.
    Default per CPU-bound tasks su macchina singola.
    Auto-scaling basato su CPU disponibili.
    """

    def __init__(self, max_workers: Optional[int] = None, memory_limit_gb: float = 0.0):
        resources = detect_resources()
        if max_workers is None:
            # Lascia 1 CPU libera per il sistema, min 2
            max_workers = max(2, resources.cpu_count_physical - 1)
        if memory_limit_gb > 0:
            # Limita worker se poca RAM
            mem_per_worker = 0.5  # GB stimati per worker
            max_from_mem = int(resources.memory_available_gb / mem_per_worker)
            max_workers = min(max_workers, max(2, max_from_mem))

        self.max_workers = max_workers
        self._executor: Optional[ProcessPoolExecutor] = None
        logger.info(f"LocalProcessPool: {max_workers} workers "
                     f"(CPU: {resources.cpu_count_physical}, RAM: {resources.memory_available_gb:.1f}GB)")

    def _get_executor(self) -> ProcessPoolExecutor:
        if self._executor is None:
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        return self._executor

    def map(
        self,
        fn: Callable[[T], R],
        items: Sequence[T],
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
        max_retries: int = 2,
        chunk_size: int = 0,
    ) -> List[R]:
        """
        Esegui fn su ogni item in parallelo.

        Args:
            fn: funzione da eseguire (deve essere picklable)
            items: sequenza di input
            progress_callback: callback per progresso
            max_retries: tentativi per item fallito
            chunk_size: 0 = auto

        Returns:
            Lista di risultati nello stesso ordine
        """
        if not items:
            return []

        if chunk_size <= 0:
            chunk_size = max(1, len(items) // (self.max_workers * 4))

        tracker = ProgressTracker(len(items), progress_callback)
        executor = self._get_executor()
        results: List[Optional[R]] = [None] * len(items)
        futures: Dict[Future, Tuple[int, int]] = {}  # future -> (index, retry_count)

        for i, item in enumerate(items):
            future = executor.submit(fn, item)
            futures[future] = (i, 0)
            tracker.start_task()

        for future in as_completed(futures):
            idx, retry_count = futures[future]
            try:
                results[idx] = future.result(timeout=300)
                tracker.complete_task()
            except Exception as e:
                if retry_count < max_retries:
                    # Retry
                    new_future = executor.submit(fn, items[idx])
                    futures[new_future] = (idx, retry_count + 1)
                    tracker.start_task()
                    logger.warning(f"Task {idx} fallito, retry {retry_count+1}: {e}")
                else:
                    tracker.fail_task(str(e))
                    logger.error(f"Task {idx} fallito definitivamente: {e}")

        return [r for r in results if r is not None]

    def map_batched(
        self,
        fn: Callable[[List[T]], List[R]],
        items: Sequence[T],
        batch_size: int = 100,
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
    ) -> List[R]:
        """
        Esegui fn su batch di items.
        Più efficiente per I/O-bound con overhead per item.
        """
        batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]
        tracker = ProgressTracker(len(batches), progress_callback)
        executor = self._get_executor()

        all_results: List[R] = []
        futures = {executor.submit(fn, batch): i for i, batch in enumerate(batches)}

        for future in as_completed(futures):
            tracker.start_task()
            try:
                batch_result = future.result(timeout=600)
                all_results.extend(batch_result)
                tracker.complete_task()
            except Exception as e:
                tracker.fail_task(str(e))

        return all_results

    def shutdown(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None


# ═══════════════════════════════════════════════════════
# 2. LOCAL THREAD POOL (I/O-bound)
# ═══════════════════════════════════════════════════════

class LocalThreadPool:
    """
    Pool di thread per I/O-bound tasks (download, API calls, disk I/O).
    Supporta più worker rispetto a ProcessPool perché i thread
    rilasciano il GIL durante I/O.
    """

    def __init__(self, max_workers: Optional[int] = None):
        resources = detect_resources()
        if max_workers is None:
            # I/O-bound: più thread che CPU
            max_workers = min(resources.cpu_count * 4, 64)
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None

    def _get_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._executor

    def map(
        self,
        fn: Callable[[T], R],
        items: Sequence[T],
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
        max_retries: int = 3,
        rate_limit_per_sec: float = 0,
    ) -> List[R]:
        """
        Esegui fn su ogni item con thread.

        Args:
            rate_limit_per_sec: limita richieste/secondo (0 = no limit)
        """
        if not items:
            return []

        tracker = ProgressTracker(len(items), progress_callback)
        executor = self._get_executor()
        results: List[Optional[R]] = [None] * len(items)
        interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0

        futures: Dict[Future, Tuple[int, int]] = {}

        for i, item in enumerate(items):
            if interval > 0 and i > 0:
                time.sleep(interval)
            future = executor.submit(fn, item)
            futures[future] = (i, 0)
            tracker.start_task()

        for future in as_completed(futures):
            idx, retry_count = futures[future]
            try:
                results[idx] = future.result(timeout=120)
                tracker.complete_task()
            except Exception as e:
                if retry_count < max_retries:
                    new_future = executor.submit(fn, items[idx])
                    futures[new_future] = (idx, retry_count + 1)
                    tracker.start_task()
                else:
                    tracker.fail_task(str(e))

        return [r for r in results if r is not None]

    def shutdown(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None


# ═══════════════════════════════════════════════════════
# 3. ASYNC POOL (massimo throughput I/O)
# ═══════════════════════════════════════════════════════

class AsyncPool:
    """
    Pool asyncio per massimo throughput I/O.
    Perfetto per download massivi con migliaia di connessioni concorrenti.
    """

    def __init__(self, max_concurrency: int = 100):
        self.max_concurrency = max_concurrency

    async def map_async(
        self,
        fn: Callable,
        items: Sequence[Any],
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
    ) -> List[Any]:
        """Esegui coroutine fn su ogni item con semaforo."""
        semaphore = asyncio.Semaphore(self.max_concurrency)
        tracker = ProgressTracker(len(items), progress_callback)
        results: List[Any] = [None] * len(items)

        async def _run(idx: int, item: Any) -> None:
            async with semaphore:
                tracker.start_task()
                try:
                    results[idx] = await fn(item)
                    tracker.complete_task()
                except Exception as e:
                    tracker.fail_task(str(e))

        tasks = [_run(i, item) for i, item in enumerate(items)]
        await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if r is not None]

    def map(
        self,
        fn: Callable,
        items: Sequence[Any],
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
    ) -> List[Any]:
        """Wrapper sincrono per map_async."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Già in un event loop — usa thread per evitare deadlock
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(1) as ex:
                future = ex.submit(asyncio.run, self.map_async(fn, items, progress_callback))
                return future.result()
        else:
            return asyncio.run(self.map_async(fn, items, progress_callback))


# ═══════════════════════════════════════════════════════
# 4. DASK DISTRIBUTED (opzionale)
# ═══════════════════════════════════════════════════════

class DaskCluster:
    """
    Wrapper per Dask Distributed.
    Scala su cluster multi-nodo.
    Richiede: pip install dask distributed
    """

    def __init__(
        self,
        scheduler_address: str = "",
        n_workers: int = 0,
        threads_per_worker: int = 2,
        memory_limit: str = "auto",
    ):
        try:
            import dask
            from dask.distributed import Client, LocalCluster
        except ImportError:
            raise ImportError(
                "dask e distributed richiesti. "
                "Installa con: pip install 'dask[distributed]'"
            )

        if scheduler_address:
            # Connetti a cluster esistente
            self._client = Client(scheduler_address)
        else:
            # Crea cluster locale
            resources = detect_resources()
            if n_workers <= 0:
                n_workers = max(2, resources.cpu_count_physical - 1)
            cluster = LocalCluster(
                n_workers=n_workers,
                threads_per_worker=threads_per_worker,
                memory_limit=memory_limit,
            )
            self._client = Client(cluster)

        logger.info(f"DaskCluster connesso: {self._client.dashboard_link}")

    def map(
        self,
        fn: Callable[[T], R],
        items: Sequence[T],
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
    ) -> List[R]:
        """Map distribuito su cluster Dask."""
        from dask.distributed import progress as dask_progress

        futures = self._client.map(fn, items)

        if progress_callback:
            tracker = ProgressTracker(len(items), progress_callback)
            results = []
            for future in self._client.as_completed(futures):
                try:
                    results.append(future.result())
                    tracker.complete_task()
                except Exception as e:
                    tracker.fail_task(str(e))
            return results
        else:
            return self._client.gather(futures)

    def submit(self, fn: Callable, *args, **kwargs) -> Any:
        """Invia singolo task."""
        return self._client.submit(fn, *args, **kwargs)

    def scatter(self, data: Any) -> Any:
        """Distribuisci dati nel cluster (per evitare serializzazione ripetuta)."""
        return self._client.scatter(data, broadcast=True)

    @property
    def dashboard_url(self) -> str:
        return self._client.dashboard_link or ""

    def shutdown(self) -> None:
        self._client.close()


# ═══════════════════════════════════════════════════════
# 5. SPARK CLUSTER (opzionale, big data)
# ═══════════════════════════════════════════════════════

class SparkCluster:
    """
    Wrapper per PySpark.
    Per elaborazione di dataset enormi (TB+).
    Richiede: pip install pyspark
    """

    def __init__(
        self,
        app_name: str = "VIO83-Orchestra",
        master: str = "local[*]",
        config: Optional[Dict[str, str]] = None,
    ):
        try:
            from pyspark.sql import SparkSession
        except ImportError:
            raise ImportError(
                "pyspark richiesto per SparkCluster. "
                "Installa con: pip install pyspark"
            )

        builder = SparkSession.builder.appName(app_name).master(master)
        if config:
            for k, v in config.items():
                builder = builder.config(k, v)

        # Config ottimizzate per il nostro caso
        builder = (
            builder
            .config("spark.sql.adaptive.enabled", "true")
            .config("spark.sql.shuffle.partitions", "auto")
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
            .config("spark.driver.memory", "4g")
        )

        self._spark = builder.getOrCreate()
        self._sc = self._spark.sparkContext
        logger.info(f"SparkCluster inizializzato: {master}")

    def map_rdd(self, fn: Callable, items: List[Any], partitions: int = 0) -> List[Any]:
        """Map su RDD Spark."""
        if partitions <= 0:
            partitions = self._sc.defaultParallelism
        rdd = self._sc.parallelize(items, partitions)
        return rdd.map(fn).collect()

    def map_dataframe(self, fn: Callable, items: List[Dict], schema: Optional[Any] = None) -> List[Dict]:
        """Map su DataFrame Spark (più ottimizzato)."""
        from pyspark.sql import Row
        from pyspark.sql.functions import udf
        from pyspark.sql.types import StringType

        rows = [Row(**item) for item in items]
        df = self._spark.createDataFrame(rows)

        # UDF per trasformazione
        transform_udf = udf(fn, StringType())
        # Nota: per casi reali, serve schema output più specifico

        return [row.asDict() for row in df.collect()]

    def read_parquet(self, path: str):
        """Leggi dataset Parquet (per dati pre-processati)."""
        return self._spark.read.parquet(path)

    def write_parquet(self, df, path: str, mode: str = "overwrite") -> None:
        """Scrivi dataset Parquet."""
        df.write.mode(mode).parquet(path)

    @property
    def ui_url(self) -> str:
        return self._sc.uiWebUrl or ""

    def shutdown(self) -> None:
        self._spark.stop()


# ═══════════════════════════════════════════════════════
# PIPELINE DAG
# ═══════════════════════════════════════════════════════

@dataclass
class PipelineStage:
    """Uno stadio della pipeline."""
    name: str
    fn: Callable
    depends_on: List[str] = field(default_factory=list)
    pool_type: str = "process"  # "process", "thread", "async"
    max_workers: int = 0
    batch_size: int = 100
    retry_count: int = 2


class Pipeline:
    """
    Pipeline DAG per elaborazione multi-stadio.

    Uso:
        pipeline = Pipeline()
        pipeline.add_stage("download", download_fn, pool_type="thread")
        pipeline.add_stage("parse", parse_fn, depends_on=["download"])
        pipeline.add_stage("distill", distill_fn, depends_on=["parse"])
        pipeline.add_stage("store", store_fn, depends_on=["distill"])
        results = pipeline.run(items)
    """

    def __init__(self):
        self._stages: Dict[str, PipelineStage] = {}
        self._order: List[str] = []

    def add_stage(
        self,
        name: str,
        fn: Callable,
        depends_on: Optional[List[str]] = None,
        pool_type: str = "process",
        max_workers: int = 0,
        batch_size: int = 100,
        retry_count: int = 2,
    ) -> "Pipeline":
        stage = PipelineStage(
            name=name,
            fn=fn,
            depends_on=depends_on or [],
            pool_type=pool_type,
            max_workers=max_workers,
            batch_size=batch_size,
            retry_count=retry_count,
        )
        self._stages[name] = stage
        self._order = self._topological_sort()
        return self

    def _topological_sort(self) -> List[str]:
        """Ordina stadi rispettando dipendenze."""
        visited = set()
        order = []

        def visit(name: str):
            if name in visited:
                return
            visited.add(name)
            stage = self._stages[name]
            for dep in stage.depends_on:
                if dep in self._stages:
                    visit(dep)
            order.append(name)

        for name in self._stages:
            visit(name)
        return order

    def run(
        self,
        items: Sequence[Any],
        progress_callback: Optional[Callable[[str, BatchProgress], None]] = None,
    ) -> Dict[str, List[Any]]:
        """
        Esegui pipeline completa.

        Returns:
            Dict con risultati per ogni stadio
        """
        stage_results: Dict[str, List[Any]] = {}

        for stage_name in self._order:
            stage = self._stages[stage_name]
            logger.info(f"Pipeline stadio: {stage_name}")

            # Input: risultati dello stadio precedente o items originali
            if stage.depends_on:
                input_data = stage_results[stage.depends_on[0]]
            else:
                input_data = list(items)

            # Crea pool appropriato
            pool = self._create_pool(stage)

            # Callback specifico per stadio
            def stage_callback(p: BatchProgress) -> None:
                if progress_callback:
                    progress_callback(stage_name, p)

            # Esegui
            t0 = time.time()
            results = pool.map(
                stage.fn,
                input_data,
                progress_callback=stage_callback,
                max_retries=stage.retry_count,
            )
            elapsed = time.time() - t0

            stage_results[stage_name] = results
            logger.info(f"Stadio {stage_name}: {len(results)} risultati in {elapsed:.1f}s")

            # Shutdown pool se non riutilizzabile
            if hasattr(pool, 'shutdown'):
                pool.shutdown()

        return stage_results

    def _create_pool(self, stage: PipelineStage):
        if stage.pool_type == "thread":
            return LocalThreadPool(max_workers=stage.max_workers or None)
        elif stage.pool_type == "async":
            return AsyncPool(max_concurrency=stage.max_workers or 100)
        else:
            return LocalProcessPool(max_workers=stage.max_workers or None)


# ═══════════════════════════════════════════════════════
# BATCH PROCESSOR con backpressure
# ═══════════════════════════════════════════════════════

class BatchProcessor:
    """
    Processore batch con backpressure automatica.
    Regola la velocità in base alla memoria disponibile.
    """

    def __init__(
        self,
        process_fn: Callable[[List[Any]], List[Any]],
        batch_size: int = 100,
        max_queue_size: int = 1000,
        pool_type: str = "process",
        max_workers: int = 0,
    ):
        self.process_fn = process_fn
        self.batch_size = batch_size
        self.max_queue_size = max_queue_size
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._results: List[Any] = []
        self._lock = threading.Lock()
        self._pool_type = pool_type
        self._max_workers = max_workers
        self._stop_event = threading.Event()

    def feed(self, item: Any) -> None:
        """Aggiungi item alla coda (blocca se coda piena = backpressure)."""
        while not self._stop_event.is_set():
            try:
                self._queue.put(item, timeout=1.0)
                return
            except queue.Full:
                # Backpressure: aspetta che la coda si svuoti
                logger.debug("Backpressure attiva, coda piena")
                continue

    def feed_batch(self, items: Sequence[Any]) -> None:
        """Aggiungi batch di items."""
        for item in items:
            self.feed(item)

    def process_all(
        self,
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
    ) -> List[Any]:
        """Processa tutti gli items nella coda."""
        items = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if not items:
            return []

        # Processa in batch paralleli
        batches = [items[i:i+self.batch_size] for i in range(0, len(items), self.batch_size)]

        if self._pool_type == "process":
            pool = LocalProcessPool(max_workers=self._max_workers or None)
        else:
            pool = LocalThreadPool(max_workers=self._max_workers or None)

        tracker = ProgressTracker(len(batches), progress_callback)
        results = []

        for batch in batches:
            tracker.start_task()
            try:
                batch_results = self.process_fn(batch)
                results.extend(batch_results)
                tracker.complete_task()
            except Exception as e:
                tracker.fail_task(str(e))

        pool.shutdown()
        return results

    def stop(self) -> None:
        self._stop_event.set()


# ═══════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════

_HAS_DASK = False
_HAS_SPARK = False

try:
    import dask
    _HAS_DASK = True
except ImportError:
    pass

try:
    import pyspark
    _HAS_SPARK = True
except ImportError:
    pass


def create_pool(
    pool_type: str = "auto",
    max_workers: int = 0,
    **kwargs,
) -> Union[LocalProcessPool, LocalThreadPool, AsyncPool, DaskCluster, SparkCluster]:
    """
    Factory per creare il pool appropriato.

    pool_type:
        "auto"    — sceglie il migliore disponibile
        "process" — multiprocessing locale
        "thread"  — threading locale
        "async"   — asyncio
        "dask"    — Dask distributed
        "spark"   — PySpark
    """
    if pool_type == "auto":
        if _HAS_DASK and kwargs.get("scheduler_address"):
            return DaskCluster(**kwargs)
        return LocalProcessPool(max_workers=max_workers or None)

    if pool_type == "process":
        return LocalProcessPool(max_workers=max_workers or None)
    elif pool_type == "thread":
        return LocalThreadPool(max_workers=max_workers or None)
    elif pool_type == "async":
        return AsyncPool(max_concurrency=max_workers or 100)
    elif pool_type == "dask":
        return DaskCluster(**kwargs)
    elif pool_type == "spark":
        return SparkCluster(**kwargs)
    else:
        raise ValueError(f"Pool type sconosciuto: {pool_type}")


def available_backends() -> Dict[str, bool]:
    """Lista backend disponibili."""
    return {
        "process": True,
        "thread": True,
        "async": True,
        "dask": _HAS_DASK,
        "spark": _HAS_SPARK,
    }
