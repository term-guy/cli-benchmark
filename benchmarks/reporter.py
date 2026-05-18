from __future__ import annotations

import dataclasses
import json
import math
import os
from datetime import datetime
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .runner import BenchmarkResult
from .sysinfo import SystemInfo


CATEGORY_ORDER = ["cpu", "disk", "memory", "database", "git"]

# For each benchmark, True = higher is better, False = lower is better
HIGHER_IS_BETTER: Dict[str, bool] = {
    "cpu.hashing": True,
    "cpu.compression": True,
    "cpu.prime_sieve": False,
    "cpu.multicore": True,
    "disk.seq_write": True,
    "disk.seq_read": True,
    "disk.random_read": True,
    "disk.small_write": True,
    "disk.small_delete": True,
    "memory.write_bw": True,
    "memory.read_bw": True,
    "memory.latency": False,
    "db.bulk_insert": True,
    "db.indexed_select": True,
    "db.nonindexed_select": True,
    "db.bulk_update": True,
    "db.delete_vacuum": False,
    "git.large_commit": True,
    "git.local_clone": True,
    "git.log_traversal": False,
    "git.diff": False,
}

SCORE_REFERENCE: Dict[str, float] = {
    "cpu.hashing": 2000.0,
    "cpu.compression": 400.0,
    "cpu.prime_sieve": 800.0,
    "cpu.multicore": 8000.0,
    "disk.seq_write": 500.0,
    "disk.seq_read": 1000.0,
    "disk.random_read": 5000.0,
    "disk.small_write": 2000.0,
    "disk.small_delete": 5000.0,
    "memory.write_bw": 20.0,
    "memory.read_bw": 25.0,
    "memory.latency": 50.0,
    "db.bulk_insert": 200000.0,
    "db.indexed_select": 100000.0,
    "db.nonindexed_select": 5000.0,
    "db.bulk_update": 50000.0,
    "db.delete_vacuum": 200.0,
    "git.large_commit": 200.0,
    "git.local_clone": 50.0,
    "git.log_traversal": 50.0,
    "git.diff": 30.0,
}


def _rating_bar(value: float, best: float, higher_is_better: bool, width: int = 8) -> Text:
    if best == 0:
        ratio = 0.0
    elif higher_is_better:
        ratio = min(value / best, 1.0)
    else:
        ratio = min(best / value, 1.0) if value > 0 else 0.0

    filled = round(ratio * width)
    bar_text = Text()

    if ratio > 0.66:
        style = "bold green"
    elif ratio > 0.33:
        style = "bold yellow"
    else:
        style = "bold red"

    bar_text.append("█" * filled, style=style)
    bar_text.append("░" * (width - filled), style="dim")
    return bar_text


def _format_metric(metric: float, unit: str) -> str:
    if metric >= 1000:
        return f"{metric:,.0f}"
    elif metric >= 10:
        return f"{metric:.1f}"
    else:
        return f"{metric:.3f}"


def print_sysinfo(console: Console, info: SystemInfo) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Value")

    table.add_row("Hostname", info.hostname)
    table.add_row("OS", info.distro)
    table.add_row("Kernel", info.kernel)
    table.add_row("CPU", info.cpu_model)
    table.add_row("Cores", f"{info.cpu_logical} logical / {info.cpu_physical} physical")
    table.add_row("RAM", f"{info.ram_total_mb:,} MB total / {info.ram_available_mb:,} MB available")
    table.add_row("Disk", f"{info.disk_mount}  {info.disk_total_gb:.1f} GB total / {info.disk_free_gb:.1f} GB free")
    table.add_row("Python", info.python_version)
    table.add_row("Rich", info.rich_version)

    console.print(Panel(table, title="[bold]System Info[/bold]", border_style="blue"))


def print_results(console: Console, results: List[BenchmarkResult]) -> None:
    by_category: Dict[str, List[BenchmarkResult]] = {}
    for r in results:
        by_category.setdefault(r.category, []).append(r)

    for cat in CATEGORY_ORDER:
        cat_results = by_category.get(cat, [])
        if not cat_results:
            continue

        valid = [r for r in cat_results if not r.skipped and r.error is None and r.metric > 0]
        best_map: Dict[str, float] = {}
        for r in valid:
            hib = HIGHER_IS_BETTER.get(r.name, True)
            cur_best = best_map.get(r.name)
            if cur_best is None:
                best_map[r.name] = r.metric
            elif hib and r.metric > cur_best:
                best_map[r.name] = r.metric
            elif not hib and r.metric < cur_best:
                best_map[r.name] = r.metric

        cat_best = max((r.metric for r in valid), default=0.0)
        if valid:
            hib_list = [HIGHER_IS_BETTER.get(r.name, True) for r in valid]
            if all(hib_list):
                cat_best = max(r.metric for r in valid)
            elif not any(hib_list):
                cat_best = min(r.metric for r in valid)

        table = Table(title=f"[bold]{cat.upper()}[/bold]", border_style="dim")
        table.add_column("Benchmark", style="cyan", no_wrap=True)
        table.add_column("Result", justify="right")
        table.add_column("Unit")
        table.add_column("Duration", justify="right")
        table.add_column("Rating")

        for r in cat_results:
            if r.skipped:
                table.add_row(r.name, "[yellow]SKIP[/yellow]", r.unit, "-", Text(""))
                continue
            if r.error:
                table.add_row(r.name, "[red]ERROR[/red]", r.unit, f"{r.duration_s:.2f}s", Text(""))
                continue

            hib = HIGHER_IS_BETTER.get(r.name, True)
            best_in_cat = cat_best if len(set(HIGHER_IS_BETTER.get(rr.name, True) for rr in valid)) == 1 else best_map.get(r.name, r.metric)
            rating = _rating_bar(r.metric, best_in_cat, hib)

            table.add_row(
                r.name,
                _format_metric(r.metric, r.unit),
                r.unit,
                f"{r.duration_s:.2f}s",
                rating,
            )

        console.print(table)
        console.print()


def compute_score(results: List[BenchmarkResult]) -> float:
    log_scores = []
    for r in results:
        if r.skipped or r.error or r.metric <= 0:
            continue
        ref = SCORE_REFERENCE.get(r.name)
        if ref is None or ref <= 0:
            continue
        hib = HIGHER_IS_BETTER.get(r.name, True)
        if hib:
            normalized = r.metric / ref
        else:
            normalized = ref / r.metric
        if normalized > 0:
            log_scores.append(math.log(normalized))

    if not log_scores:
        return 0.0

    geo_mean = math.exp(sum(log_scores) / len(log_scores))
    score = max(0.0, min(100.0, geo_mean * 50.0))
    return round(score, 1)


def _grade_label(score: float) -> str:
    if score >= 65:
        return "\U0001f7e2 Fast"
    elif score >= 35:
        return "\U0001f7e1 Average"
    else:
        return "\U0001f534 Slow"


def print_summary(
    console: Console,
    results: List[BenchmarkResult],
    wall_time: float,
    report_path: str,
    score: float,
) -> None:
    passed = sum(1 for r in results if not r.skipped and r.error is None)
    skipped = sum(1 for r in results if r.skipped)
    errored = sum(1 for r in results if r.error and not r.skipped)
    grade = _grade_label(score)

    lines = [
        f"[bold]Total time:[/bold]  {wall_time:.1f}s",
        f"[bold]Benchmarks:[/bold] [green]{passed} passed[/green]  [yellow]{skipped} skipped[/yellow]  [red]{errored} errored[/red]",
        f"[bold]Report:[/bold]     {report_path}",
        f"[bold]Score:[/bold]      {score:.1f} / 100  —  {grade}",
    ]

    console.print(Panel("\n".join(lines), title="[bold]Summary[/bold]", border_style="green"))


def save_report(
    results: List[BenchmarkResult],
    sysinfo: SystemInfo,
    score: float,
    output_path: Optional[str] = None,
) -> str:
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("results", exist_ok=True)
        output_path = os.path.join("results", f"bench_{sysinfo.hostname}_{ts}.json")

    payload = {
        "timestamp": datetime.now().isoformat(),
        "system": dataclasses.asdict(sysinfo),
        "results": [dataclasses.asdict(r) for r in results],
        "score": score,
    }

    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)

    return output_path
