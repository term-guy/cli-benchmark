#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import List, Optional

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    BarColumn,
    TaskID,
)

from benchmarks import cpu, disk, memory, database, git
from benchmarks.reporter import (
    compute_score,
    print_results,
    print_summary,
    print_sysinfo,
    save_report,
)
from benchmarks.runner import BenchmarkResult
from benchmarks import sysinfo as sysinfo_mod


ALL_CATEGORIES = ["cpu", "disk", "memory", "database", "git"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cli-benchmark",
        description="Linux server performance benchmark tool",
    )
    parser.add_argument(
        "--only",
        metavar="CATEGORIES",
        help="Comma-separated list of categories to run (cpu,disk,memory,database,git)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Override default JSON report output path",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use 10x smaller workloads for a fast smoke-test run",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable color output",
    )
    return parser.parse_args()


def _make_progress(console: Console) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        TextColumn("{task.fields[status]}"),
        console=console,
        transient=False,
    )


def _run_category(
    name: str,
    runner_fn,
    quick: bool,
    progress: Progress,
    task_id: TaskID,
    results: List[BenchmarkResult],
) -> None:
    progress.update(task_id, status="[cyan]running…[/cyan]")
    try:
        cat_results = runner_fn(quick)
        results.extend(cat_results)
        errors = [r for r in cat_results if r.error and not r.skipped]
        skips = [r for r in cat_results if r.skipped]
        if errors:
            progress.update(task_id, total=1, completed=1, status=f"[red]done ({len(errors)} error(s))[/red]")
        elif skips and len(skips) == len(cat_results):
            progress.update(task_id, total=1, completed=1, status="[yellow]SKIP[/yellow]")
        else:
            progress.update(task_id, total=1, completed=1, status="[green]done[/green]")
    except Exception as exc:
        progress.update(task_id, total=1, completed=1, status=f"[red]error: {exc}[/red]")


def main() -> int:
    args = _parse_args()
    console = Console(no_color=args.no_color)

    categories: List[str] = ALL_CATEGORIES
    if args.only:
        requested = [c.strip().lower() for c in args.only.split(",")]
        unknown = [c for c in requested if c not in ALL_CATEGORIES]
        if unknown:
            console.print(f"[red]Unknown categories: {', '.join(unknown)}[/red]")
            console.print(f"Valid categories: {', '.join(ALL_CATEGORIES)}")
            return 1
        categories = requested

    bench_dir = os.getcwd()
    info = sysinfo_mod.collect(bench_dir)
    print_sysinfo(console, info)

    if args.quick:
        console.print("[yellow]Quick mode: using reduced workloads[/yellow]\n")

    results: List[BenchmarkResult] = []
    wall_start = time.perf_counter()

    category_map = {
        "cpu": ("CPU benchmarks", cpu.run_all),
        "disk": ("Disk I/O benchmarks", disk.run_all),
        "memory": ("Memory benchmarks", memory.run_all),
        "database": ("Database benchmarks", database.run_all),
        "git": ("Git benchmarks", git.run_all),
    }

    try:
        with _make_progress(console) as progress:
            tasks = {}
            for cat in categories:
                label, _ = category_map[cat]
                task_id = progress.add_task(label, status="[dim]waiting…[/dim]")
                tasks[cat] = task_id

            for cat in categories:
                task_id = tasks[cat]
                _, runner_fn = category_map[cat]
                _run_category(cat, runner_fn, args.quick, progress, task_id, results)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        return 130
    except Exception:
        console.print_exception()
        return 1

    wall_time = time.perf_counter() - wall_start

    console.print()
    print_results(console, results)

    score = compute_score(results)

    try:
        report_path = save_report(results, info, score, args.output)
    except Exception as exc:
        console.print(f"[red]Failed to save report: {exc}[/red]")
        report_path = "(not saved)"

    print_summary(console, results, wall_time, report_path, score)
    return 0


if __name__ == "__main__":
    sys.exit(main())
