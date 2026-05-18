from __future__ import annotations

import array
import random
import time
from typing import List

from .runner import BenchmarkResult, TimedRunner


def bench_write_bandwidth(quick: bool = False) -> BenchmarkResult:
    size_mb = 32 if quick else 256
    chunk_size = 4 * 1024 * 1024  # 4MB chunks
    runner = TimedRunner("memory.write_bw", "memory", "GB/s", quick)

    def _run():
        total_bytes = size_mb * 1024 * 1024
        buf = bytearray(total_bytes)
        chunk = bytes(chunk_size)

        t0 = time.perf_counter()
        for offset in range(0, total_bytes, chunk_size):
            end = min(offset + chunk_size, total_bytes)
            buf[offset:end] = chunk[:end - offset]
        elapsed = time.perf_counter() - t0

        gb_s = (size_mb / 1024) / elapsed
        return gb_s, {"size_mb": size_mb}

    return runner.run(_run)


def bench_read_bandwidth(quick: bool = False) -> BenchmarkResult:
    size_mb = 32 if quick else 256
    chunk_size = 4 * 1024 * 1024
    runner = TimedRunner("memory.read_bw", "memory", "GB/s", quick)

    def _run():
        total_bytes = size_mb * 1024 * 1024
        buf = bytearray(total_bytes)

        t0 = time.perf_counter()
        total_read = 0
        for offset in range(0, total_bytes, chunk_size):
            end = min(offset + chunk_size, total_bytes)
            _ = buf[offset:end]
            total_read += end - offset
        elapsed = time.perf_counter() - t0

        gb_s = (size_mb / 1024) / elapsed
        return gb_s, {"size_mb": size_mb}

    return runner.run(_run)


def bench_latency(quick: bool = False) -> BenchmarkResult:
    # Pointer-chase walk with 64-byte stride to measure memory latency
    n_elements = 512 * 1024 if quick else 4 * 1024 * 1024
    stride = 16  # 64 bytes / 4 bytes per int32
    runner = TimedRunner("memory.latency", "memory", "ns/access", quick)

    def _run():
        # Build a shuffled pointer-chase array
        arr = array.array("l", range(n_elements))

        # Fisher-Yates shuffle to create random traversal order
        indices = list(range(n_elements))
        for i in range(n_elements - 1, 0, -1):
            j = random.randint(0, i)
            indices[i], indices[j] = indices[j], indices[i]

        # Build linked list in array: arr[i] = next index to visit
        chase = array.array("l", [0] * n_elements)
        for i in range(n_elements - 1):
            chase[indices[i]] = indices[i + 1]
        chase[indices[-1]] = indices[0]

        n_accesses = min(100_000, n_elements)
        t0 = time.perf_counter()
        idx = 0
        for _ in range(n_accesses):
            idx = chase[idx]
        elapsed = time.perf_counter() - t0

        ns_per_access = (elapsed / n_accesses) * 1e9
        return ns_per_access, {"n_accesses": n_accesses, "array_size_mb": round(n_elements * 8 / (1024 * 1024), 1)}

    return runner.run(_run)


def run_all(quick: bool = False) -> List[BenchmarkResult]:
    return [
        bench_write_bandwidth(quick),
        bench_read_bandwidth(quick),
        bench_latency(quick),
    ]
