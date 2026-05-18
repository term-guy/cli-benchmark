from __future__ import annotations

import os
import random
import shutil
import sqlite3
import string
import tempfile
import time
from typing import List

from .runner import BenchmarkResult, TimedRunner


def _get_tmpdir() -> str:
    return tempfile.mkdtemp(prefix=f"serverbench_{os.getpid()}_db_")


def bench_bulk_insert(quick: bool = False) -> BenchmarkResult:
    n_rows = 10_000 if quick else 100_000
    runner = TimedRunner("db.bulk_insert", "database", "rows/s", quick)

    def _run():
        tmpdir = _get_tmpdir()
        db_path = os.path.join(tmpdir, "bench.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT, score REAL)")
            rows = [
                (i, "".join(random.choices(string.ascii_letters, k=20)), random.random())
                for i in range(n_rows)
            ]
            t0 = time.perf_counter()
            with conn:
                conn.executemany("INSERT INTO items VALUES (?, ?, ?)", rows)
            elapsed = time.perf_counter() - t0
            conn.close()
            return n_rows / elapsed, {"n_rows": n_rows}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def bench_indexed_select(quick: bool = False) -> BenchmarkResult:
    n_queries = 1_000 if quick else 10_000
    n_rows = 10_000 if quick else 100_000
    runner = TimedRunner("db.indexed_select", "database", "queries/s", quick)

    def _run():
        tmpdir = _get_tmpdir()
        db_path = os.path.join(tmpdir, "bench.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT, score REAL)")
            conn.execute("CREATE INDEX idx_id ON items(id)")
            rows = [(i, str(i), random.random()) for i in range(n_rows)]
            with conn:
                conn.executemany("INSERT INTO items VALUES (?, ?, ?)", rows)

            ids = [random.randint(0, n_rows - 1) for _ in range(n_queries)]
            t0 = time.perf_counter()
            cur = conn.cursor()
            for row_id in ids:
                cur.execute("SELECT * FROM items WHERE id = ?", (row_id,))
                cur.fetchone()
            elapsed = time.perf_counter() - t0
            conn.close()
            return n_queries / elapsed, {"n_queries": n_queries}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def bench_nonindexed_select(quick: bool = False) -> BenchmarkResult:
    n_queries = 100 if quick else 1_000
    n_rows = 1_000 if quick else 10_000
    runner = TimedRunner("db.nonindexed_select", "database", "queries/s", quick)

    def _run():
        tmpdir = _get_tmpdir()
        db_path = os.path.join(tmpdir, "bench.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE items (id INTEGER, value TEXT, score REAL)")
            words = ["".join(random.choices(string.ascii_lowercase, k=8)) for _ in range(n_rows)]
            rows = [(i, words[i], random.random()) for i in range(n_rows)]
            with conn:
                conn.executemany("INSERT INTO items VALUES (?, ?, ?)", rows)

            targets = random.choices(words, k=n_queries)
            t0 = time.perf_counter()
            cur = conn.cursor()
            for target in targets:
                cur.execute("SELECT * FROM items WHERE value = ?", (target,))
                cur.fetchone()
            elapsed = time.perf_counter() - t0
            conn.close()
            return n_queries / elapsed, {"n_queries": n_queries}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def bench_bulk_update(quick: bool = False) -> BenchmarkResult:
    n_rows = 1_000 if quick else 10_000
    runner = TimedRunner("db.bulk_update", "database", "rows/s", quick)

    def _run():
        tmpdir = _get_tmpdir()
        db_path = os.path.join(tmpdir, "bench.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT, score REAL)")
            rows = [(i, str(i), random.random()) for i in range(n_rows)]
            with conn:
                conn.executemany("INSERT INTO items VALUES (?, ?, ?)", rows)

            updates = [(random.random(), i) for i in range(n_rows)]
            t0 = time.perf_counter()
            with conn:
                conn.executemany("UPDATE items SET score = ? WHERE id = ?", updates)
            elapsed = time.perf_counter() - t0
            conn.close()
            return n_rows / elapsed, {"n_rows": n_rows}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def bench_delete_vacuum(quick: bool = False) -> BenchmarkResult:
    n_rows = 1_000 if quick else 10_000
    runner = TimedRunner("db.delete_vacuum", "database", "ms", quick)

    def _run():
        tmpdir = _get_tmpdir()
        db_path = os.path.join(tmpdir, "bench.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT, score REAL)")
            rows = [(i, str(i), random.random()) for i in range(n_rows)]
            with conn:
                conn.executemany("INSERT INTO items VALUES (?, ?, ?)", rows)

            t0 = time.perf_counter()
            with conn:
                conn.execute("DELETE FROM items")
            conn.execute("VACUUM")
            conn.commit()
            elapsed = time.perf_counter() - t0
            conn.close()
            return elapsed * 1000, {"n_rows": n_rows}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return runner.run(_run)


def run_all(quick: bool = False) -> List[BenchmarkResult]:
    return [
        bench_bulk_insert(quick),
        bench_indexed_select(quick),
        bench_nonindexed_select(quick),
        bench_bulk_update(quick),
        bench_delete_vacuum(quick),
    ]
