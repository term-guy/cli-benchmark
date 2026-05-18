from __future__ import annotations

import os
import random
import shutil
import tempfile
import time
from typing import List

from .runner import BenchmarkResult, TimedRunner


def _get_tmpdir() -> str:
    return tempfile.mkdtemp(prefix=f"serverbench_{os.getpid()}_disk_")


def bench_seq_write(quick: bool = False) -> BenchmarkResult:
    size_mb = 64 if quick else 512
    chunk_mb = 1
    chunk = os.urandom(chunk_mb * 1024 * 1024)
    runner = TimedRunner("disk.seq_write", "disk", "MB/s", quick)

    def _run():
        tmpdir = _get_tmpdir()
        path = os.path.join(tmpdir, "seq_write.bin")
        try:
            t0 = time.perf_counter()
            with open(path, "wb") as f:
                for _ in range(size_mb // chunk_mb):
                    f.write(chunk)
                f.flush()
                os.fsync(f.fileno())
            elapsed = time.perf_counter() - t0
            return size_mb / elapsed, {"size_mb": size_mb}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def bench_seq_read(quick: bool = False) -> BenchmarkResult:
    size_mb = 64 if quick else 512
    chunk_size = 1024 * 1024
    runner = TimedRunner("disk.seq_read", "disk", "MB/s", quick)

    def _run():
        tmpdir = _get_tmpdir()
        path = os.path.join(tmpdir, "seq_read.bin")
        chunk = os.urandom(chunk_size)
        try:
            with open(path, "wb") as f:
                for _ in range(size_mb):
                    f.write(chunk)
                f.flush()
                os.fsync(f.fileno())

            t0 = time.perf_counter()
            with open(path, "rb") as f:
                while f.read(chunk_size):
                    pass
            elapsed = time.perf_counter() - t0
            return size_mb / elapsed, {"size_mb": size_mb}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def bench_random_read(quick: bool = False) -> BenchmarkResult:
    file_mb = 64 if quick else 512
    n_reads = 100 if quick else 1000
    block_size = 4096
    runner = TimedRunner("disk.random_read", "disk", "IOPS", quick)

    def _run():
        tmpdir = _get_tmpdir()
        path = os.path.join(tmpdir, "rand_read.bin")
        chunk = os.urandom(1024 * 1024)
        try:
            with open(path, "wb") as f:
                for _ in range(file_mb):
                    f.write(chunk)
                f.flush()
                os.fsync(f.fileno())

            file_size = os.path.getsize(path)
            max_offset = file_size - block_size
            offsets = [random.randint(0, max_offset) for _ in range(n_reads)]

            t0 = time.perf_counter()
            with open(path, "rb") as f:
                for offset in offsets:
                    f.seek(offset)
                    f.read(block_size)
            elapsed = time.perf_counter() - t0
            iops = n_reads / elapsed
            return iops, {"n_reads": n_reads, "block_size_kb": 4}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def bench_small_files_write(quick: bool = False) -> BenchmarkResult:
    n_files = 100 if quick else 1000
    file_size = 1024
    runner = TimedRunner("disk.small_write", "disk", "ops/s", quick)

    def _run():
        tmpdir = _get_tmpdir()
        try:
            data = os.urandom(file_size)
            t0 = time.perf_counter()
            for i in range(n_files):
                path = os.path.join(tmpdir, f"small_{i}.dat")
                with open(path, "wb") as f:
                    f.write(data)
            elapsed = time.perf_counter() - t0
            return n_files / elapsed, {"n_files": n_files, "file_size_kb": 1}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def bench_small_files_delete(quick: bool = False) -> BenchmarkResult:
    n_files = 100 if quick else 1000
    file_size = 1024
    runner = TimedRunner("disk.small_delete", "disk", "ops/s", quick)

    def _run():
        tmpdir = _get_tmpdir()
        try:
            data = os.urandom(file_size)
            paths = []
            for i in range(n_files):
                path = os.path.join(tmpdir, f"small_{i}.dat")
                with open(path, "wb") as f:
                    f.write(data)
                paths.append(path)

            t0 = time.perf_counter()
            for path in paths:
                os.unlink(path)
            elapsed = time.perf_counter() - t0
            return n_files / elapsed, {"n_files": n_files}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def run_all(quick: bool = False) -> List[BenchmarkResult]:
    return [
        bench_seq_write(quick),
        bench_seq_read(quick),
        bench_random_read(quick),
        bench_small_files_write(quick),
        bench_small_files_delete(quick),
    ]
