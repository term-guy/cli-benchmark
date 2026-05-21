from __future__ import annotations

import gzip
import hashlib
import math
import multiprocessing
import os
import struct
import time
from typing import List

from .runner import BenchmarkResult, TimedRunner


def _hash_worker(size_mb: int) -> float:
    data = os.urandom(size_mb * 1024 * 1024)
    start = time.perf_counter()
    hashlib.sha256(data).digest()
    elapsed = time.perf_counter() - start
    return size_mb / elapsed  # MB/s


def bench_hashing(quick: bool = False) -> BenchmarkResult:
    size_mb = 6 if quick else 64
    runner = TimedRunner("cpu.hashing", "cpu", "MB/s", quick)

    def _run():
        data = os.urandom(size_mb * 1024 * 1024)
        t0 = time.perf_counter()
        hashlib.sha256(data).digest()
        elapsed = time.perf_counter() - t0
        return size_mb / elapsed, {"size_mb": size_mb}

    return runner.run(_run)


def bench_compression(quick: bool = False) -> BenchmarkResult:
    size_mb = 1 if quick else 10
    runner = TimedRunner("cpu.compression", "cpu", "MB/s", quick)

    def _run():
        data = os.urandom(size_mb * 1024 * 1024)
        t0 = time.perf_counter()
        compressed = gzip.compress(data, compresslevel=1)
        gzip.decompress(compressed)
        elapsed = time.perf_counter() - t0
        mb_processed = size_mb * 2  # compress + decompress
        return mb_processed / elapsed, {"size_mb": size_mb}

    return runner.run(_run)


def bench_prime_sieve(quick: bool = False) -> BenchmarkResult:
    limit = 100_000 if quick else 10_000_000
    runner = TimedRunner("cpu.prime_sieve", "cpu", "ms", quick)

    def _run():
        t0 = time.perf_counter()
        sieve = bytearray([1]) * (limit + 1)
        sieve[0] = sieve[1] = 0
        for i in range(2, int(limit ** 0.5) + 1):
            if sieve[i]:
                sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
        count = sum(sieve)
        elapsed = time.perf_counter() - t0
        return elapsed * 1000, {"limit": limit, "prime_count": count}

    return runner.run(_run)


def _multicore_worker(args):
    size_mb, _ = args
    data = os.urandom(size_mb * 1024 * 1024)
    t0 = time.perf_counter()
    hashlib.sha256(data).digest()
    elapsed = time.perf_counter() - t0
    return size_mb / elapsed


def bench_multicore(quick: bool = False) -> BenchmarkResult:
    size_mb = 4 if quick else 16
    n_cores = max(2, os.cpu_count() or 2)
    runner = TimedRunner("cpu.multicore", "cpu", "MB/s", quick)

    def _run():
        # Single-core baseline
        single_result = _multicore_worker((size_mb, 0))

        # Multi-core run
        t0 = time.perf_counter()
        with multiprocessing.Pool(processes=n_cores) as pool:
            results = pool.map(_multicore_worker, [(size_mb, i) for i in range(n_cores)])
        elapsed = time.perf_counter() - t0

        total_mb = size_mb * n_cores
        multi_throughput = total_mb / elapsed
        efficiency = (multi_throughput / (single_result * n_cores)) * 100

        return multi_throughput, {
            "single_core_mbs": round(single_result, 1),
            "multi_core_mbs": round(multi_throughput, 1),
            "cores_used": n_cores,
            "scaling_efficiency_pct": round(efficiency, 1),
        }

    return runner.run(_run)


def _multicore_compression_worker(args):
    size_mb, _ = args
    data = os.urandom(size_mb * 1024 * 1024)
    t0 = time.perf_counter()
    compressed = gzip.compress(data, compresslevel=1)
    gzip.decompress(compressed)
    elapsed = time.perf_counter() - t0
    return (size_mb * 2) / elapsed  # compress + decompress counted


def bench_multicore_compression(quick: bool = False) -> BenchmarkResult:
    size_mb = 2 if quick else 8
    n_cores = max(2, os.cpu_count() or 2)
    runner = TimedRunner("cpu.multicore_compression", "cpu", "MB/s", quick)

    def _run():
        t0 = time.perf_counter()
        with multiprocessing.Pool(processes=n_cores) as pool:
            pool.map(_multicore_compression_worker, [(size_mb, i) for i in range(n_cores)])
        elapsed = time.perf_counter() - t0
        total_mb = size_mb * 2 * n_cores
        throughput = total_mb / elapsed
        return throughput, {"cores_used": n_cores, "chunk_mb": size_mb}

    return runner.run(_run)


def _multicore_sort_worker(args):
    n_items, _ = args
    raw = os.urandom(n_items * 4)
    data = list(struct.unpack(f"{n_items}f", raw))
    t0 = time.perf_counter()
    data.sort()
    elapsed = time.perf_counter() - t0
    return n_items / elapsed / 1e6  # Mops/s per core


def bench_multicore_sort(quick: bool = False) -> BenchmarkResult:
    n_items = 200_000 if quick else 1_000_000
    n_cores = max(2, os.cpu_count() or 2)
    runner = TimedRunner("cpu.multicore_sort", "cpu", "Mops/s", quick)

    def _run():
        t0 = time.perf_counter()
        with multiprocessing.Pool(processes=n_cores) as pool:
            pool.map(_multicore_sort_worker, [(n_items, i) for i in range(n_cores)])
        elapsed = time.perf_counter() - t0
        total_items = n_items * n_cores
        throughput = total_items / elapsed / 1e6
        return throughput, {"cores_used": n_cores, "items_per_core": n_items}

    return runner.run(_run)


def run_all(quick: bool = False) -> List[BenchmarkResult]:
    return [
        bench_hashing(quick),
        bench_compression(quick),
        bench_prime_sieve(quick),
        bench_multicore(quick),
        bench_multicore_compression(quick),
        bench_multicore_sort(quick),
    ]
