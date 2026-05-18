from __future__ import annotations

import os
import random
import shutil
import string
import subprocess
import tempfile
import time
from typing import List

from .runner import BenchmarkResult, TimedRunner


def _git_available() -> bool:
    return shutil.which("git") is not None


def _tmpdir() -> str:
    return os.path.join(tempfile.gettempdir(), f"serverbench_{os.getpid()}_git")


def _run_git(args: List[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        check=True,
    )


def bench_large_commit(quick: bool = False) -> BenchmarkResult:
    n_files = 50 if quick else 500
    file_size_kb = 10
    runner = TimedRunner("git.large_commit", "git", "files/s", quick)

    def _run():
        base = _tmpdir()
        repo = os.path.join(base, "large_commit")
        os.makedirs(repo, exist_ok=True)
        try:
            _run_git(["init", "-b", "main"], repo)
            _run_git(["config", "user.email", "bench@serverbench"], repo)
            _run_git(["config", "user.name", "Serverbench"], repo)

            data = os.urandom(file_size_kb * 1024)
            for i in range(n_files):
                path = os.path.join(repo, f"file_{i:04d}.dat")
                with open(path, "wb") as f:
                    f.write(data)

            t0 = time.perf_counter()
            _run_git(["add", "."], repo)
            _run_git(["commit", "-m", "initial commit"], repo)
            elapsed = time.perf_counter() - t0

            return n_files / elapsed, {"n_files": n_files, "file_size_kb": file_size_kb}
        finally:
            shutil.rmtree(base, ignore_errors=True)

    return runner.run(_run)


def bench_local_clone(quick: bool = False) -> BenchmarkResult:
    n_files = 50 if quick else 500
    file_size_kb = 10
    runner = TimedRunner("git.local_clone", "git", "MB/s", quick)

    def _run():
        base = _tmpdir()
        src = os.path.join(base, "src_repo")
        dst = os.path.join(base, "clone_repo")
        os.makedirs(src, exist_ok=True)
        try:
            _run_git(["init", "-b", "main"], src)
            _run_git(["config", "user.email", "bench@serverbench"], src)
            _run_git(["config", "user.name", "Serverbench"], src)

            data = os.urandom(file_size_kb * 1024)
            for i in range(n_files):
                path = os.path.join(src, f"file_{i:04d}.dat")
                with open(path, "wb") as f:
                    f.write(data)
            _run_git(["add", "."], src)
            _run_git(["commit", "-m", "initial"], src)

            repo_size_mb = sum(
                os.path.getsize(os.path.join(root, f))
                for root, _, files in os.walk(src)
                for f in files
            ) / (1024 * 1024)

            t0 = time.perf_counter()
            subprocess.run(
                ["git", "clone", src, dst],
                capture_output=True,
                check=True,
            )
            elapsed = time.perf_counter() - t0

            return repo_size_mb / elapsed, {"repo_size_mb": round(repo_size_mb, 2)}
        finally:
            shutil.rmtree(base, ignore_errors=True)

    return runner.run(_run)


def bench_log_traversal(quick: bool = False) -> BenchmarkResult:
    n_commits = 20 if quick else 200
    runner = TimedRunner("git.log_traversal", "git", "ms", quick)

    def _run():
        base = _tmpdir()
        repo = os.path.join(base, "log_repo")
        os.makedirs(repo, exist_ok=True)
        try:
            _run_git(["init", "-b", "main"], repo)
            _run_git(["config", "user.email", "bench@serverbench"], repo)
            _run_git(["config", "user.name", "Serverbench"], repo)

            for i in range(n_commits):
                path = os.path.join(repo, "file.txt")
                with open(path, "w") as f:
                    f.write(f"commit {i}\n" + "".join(random.choices(string.ascii_letters, k=100)))
                _run_git(["add", "file.txt"], repo)
                _run_git(["commit", "-m", f"commit {i}"], repo)

            t0 = time.perf_counter()
            _run_git(["log", "--oneline"], repo)
            elapsed = time.perf_counter() - t0

            return elapsed * 1000, {"n_commits": n_commits}
        finally:
            shutil.rmtree(base, ignore_errors=True)

    return runner.run(_run)


def bench_diff(quick: bool = False) -> BenchmarkResult:
    n_commits = 20 if quick else 200
    runner = TimedRunner("git.diff", "git", "ms", quick)

    def _run():
        base = _tmpdir()
        repo = os.path.join(base, "diff_repo")
        os.makedirs(repo, exist_ok=True)
        try:
            _run_git(["init", "-b", "main"], repo)
            _run_git(["config", "user.email", "bench@serverbench"], repo)
            _run_git(["config", "user.name", "Serverbench"], repo)

            first_hash = None
            for i in range(n_commits):
                path = os.path.join(repo, f"file_{i % 10}.txt")
                with open(path, "w") as f:
                    f.write(f"version {i}\n" + "".join(random.choices(string.ascii_letters, k=200)))
                _run_git(["add", "."], repo)
                result = subprocess.run(
                    ["git", "commit", "-m", f"commit {i}"],
                    cwd=repo, capture_output=True, check=True,
                )
                if first_hash is None:
                    proc = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=repo, capture_output=True, check=True,
                    )
                    first_hash = proc.stdout.decode().strip()

            t0 = time.perf_counter()
            _run_git(["diff", first_hash, "HEAD"], repo)
            elapsed = time.perf_counter() - t0

            return elapsed * 1000, {"n_commits": n_commits}
        finally:
            shutil.rmtree(base, ignore_errors=True)

    return runner.run(_run)


def run_all(quick: bool = False) -> List[BenchmarkResult]:
    if not _git_available():
        return [
            TimedRunner.skipped(name, "git", "files/s", "git binary not found")
            for name in ["git.large_commit", "git.local_clone", "git.log_traversal", "git.diff"]
        ]
    return [
        bench_large_commit(quick),
        bench_local_clone(quick),
        bench_log_traversal(quick),
        bench_diff(quick),
    ]
