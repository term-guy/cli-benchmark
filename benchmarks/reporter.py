from __future__ import annotations

import dataclasses
import json
import math
import os
from datetime import datetime
from typing import Dict, List, Optional

from rich.console import Console, Group
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

# Calibrated reference values: geometric mean across 5 real machines
# (Apple M5 laptop, AMD EPYC-Rome VPS, Intel Haswell VPS,
#  AMD EPYC-Genoa VPS, AMD EPYC 7601 server)
# A machine exactly matching all references scores 50 / 100 overall.
SCORE_REFERENCE: Dict[str, float] = {
    "cpu.hashing":        1191.0,    # MB/s
    "cpu.compression":      61.3,    # MB/s
    "cpu.prime_sieve":      97.2,    # ms  (lower=better)
    "cpu.multicore":       350.8,    # MB/s
    "disk.seq_write":     1297.0,    # MB/s
    "disk.seq_read":      3944.0,    # MB/s
    "disk.random_read":  113157.0,   # IOPS
    "disk.small_write":   22178.0,   # ops/s
    "disk.small_delete":  66301.0,   # ops/s
    "memory.write_bw":       7.15,   # GB/s
    "memory.read_bw":       13.39,   # GB/s
    "memory.latency":      140.3,    # ns/access  (lower=better)
    "db.bulk_insert":   1141183.0,   # rows/s
    "db.indexed_select":  97495.0,   # queries/s
    "db.nonindexed_select": 1767.0,  # queries/s
    "db.bulk_update":   1026270.0,   # rows/s
    "db.delete_vacuum":      1.78,   # ms  (lower=better)
    "git.large_commit":   7253.0,    # files/s
    "git.local_clone":      76.6,    # MB/s
    "git.log_traversal":    11.3,    # ms  (lower=better)
    "git.diff":              3.99,   # ms  (lower=better)
}

# Weights for the weighted-average overall score (must sum to 1.0)
CATEGORY_WEIGHTS: Dict[str, float] = {
    "cpu":      0.25,
    "disk":     0.25,
    "memory":   0.20,
    "database": 0.20,
    "git":      0.10,
}


def _bench_score(metric: float, ref: float, higher_is_better: bool) -> float:
    """Score one benchmark on a 0–100 scale.

    Scoring scale relative to reference:
      1× reference  →  50 pts
      2× reference  →  75 pts
      4× reference  → 100 pts  (capped)
      ½× reference  →  25 pts
      ¼× reference  →   0 pts  (capped)
    """
    if metric <= 0 or ref <= 0:
        return 0.0
    normalized = metric / ref if higher_is_better else ref / metric
    if normalized <= 0:
        return 0.0
    return max(0.0, min(100.0, 50.0 + 25.0 * math.log2(normalized)))


def _score_bar(score: float, width: int = 8) -> Text:
    ratio = score / 100.0
    filled = round(ratio * width)
    if score >= 75:
        style = "bold green"
    elif score >= 45:
        style = "bold yellow"
    else:
        style = "bold red"
    bar = Text()
    bar.append("█" * filled, style=style)
    bar.append("░" * (width - filled), style="dim")
    return bar


def _format_metric(metric: float, unit: str) -> str:
    if metric >= 1000:
        return f"{metric:,.0f}"
    elif metric >= 10:
        return f"{metric:.1f}"
    else:
        return f"{metric:.3f}"


def _score_color(score: float) -> str:
    if score >= 75:
        return "green"
    elif score >= 45:
        return "yellow"
    else:
        return "red"


def _grade(score: float) -> str:
    if score >= 75:
        return "S"
    elif score >= 60:
        return "A"
    elif score >= 45:
        return "B"
    elif score >= 30:
        return "C"
    elif score >= 15:
        return "D"
    else:
        return "F"


def _grade_label(score: float) -> str:
    descriptions = {
        "S": "\U0001f7e3 Exceptional",
        "A": "\U0001f7e2 Fast",
        "B": "\U0001f535 Above Average",
        "C": "\U0001f7e1 Average",
        "D": "\U0001f7e0 Below Average",
        "F": "\U0001f534 Slow",
    }
    g = _grade(score)
    return f"{g}  {descriptions[g]}"


def compute_category_scores(results: List[BenchmarkResult]) -> Dict[str, float]:
    by_cat: Dict[str, List[float]] = {}
    for r in results:
        if r.skipped or r.error or r.metric <= 0:
            continue
        ref = SCORE_REFERENCE.get(r.name)
        hib = HIGHER_IS_BETTER.get(r.name, True)
        if not ref:
            continue
        s = _bench_score(r.metric, ref, hib)
        by_cat.setdefault(r.category, []).append(s)
    return {
        cat: round(sum(scores) / len(scores), 1)
        for cat, scores in by_cat.items()
        if scores
    }


def compute_score(results: List[BenchmarkResult]) -> float:
    cat_scores = compute_category_scores(results)
    if not cat_scores:
        return 0.0
    default_w = 1.0 / len(CATEGORY_ORDER)
    weighted_sum = 0.0
    total_weight = 0.0
    for cat, score in cat_scores.items():
        w = CATEGORY_WEIGHTS.get(cat, default_w)
        weighted_sum += w * score
        total_weight += w
    return round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0


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

        table = Table(title=f"[bold]{cat.upper()}[/bold]", border_style="dim")
        table.add_column("Benchmark", style="cyan", no_wrap=True)
        table.add_column("Result", justify="right")
        table.add_column("Unit")
        table.add_column("Duration", justify="right")
        table.add_column("Score", justify="right")
        table.add_column("Rating")

        bench_scores: List[float] = []
        for r in cat_results:
            if r.skipped:
                table.add_row(r.name, "[yellow]SKIP[/yellow]", r.unit, "-", "-", Text(""))
                continue
            if r.error:
                table.add_row(r.name, "[red]ERROR[/red]", r.unit, f"{r.duration_s:.2f}s", "-", Text(""))
                continue

            ref = SCORE_REFERENCE.get(r.name)
            hib = HIGHER_IS_BETTER.get(r.name, True)
            if ref and r.metric > 0:
                s = _bench_score(r.metric, ref, hib)
                bench_scores.append(s)
                color = _score_color(s)
                score_cell = f"[{color}]{s:.0f}[/{color}]"
                bar = _score_bar(s)
            else:
                score_cell = "-"
                bar = Text("")

            table.add_row(
                r.name,
                _format_metric(r.metric, r.unit),
                r.unit,
                f"{r.duration_s:.2f}s",
                score_cell,
                bar,
            )

        if bench_scores:
            cat_avg = sum(bench_scores) / len(bench_scores)
            color = _score_color(cat_avg)
            table.add_section()
            table.add_row(
                "",
                "",
                "",
                f"[bold]Category avg[/bold]",
                f"[bold {color}]{cat_avg:.0f}[/bold {color}]",
                _score_bar(cat_avg),
            )

        console.print(table)
        console.print()


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

    stats = "\n".join([
        f"[bold]Total time:[/bold]  {wall_time:.1f}s",
        f"[bold]Benchmarks:[/bold] [green]{passed} passed[/green]  [yellow]{skipped} skipped[/yellow]  [red]{errored} errored[/red]",
        f"[bold]Report:[/bold]     {report_path}",
        f"[bold]Score:[/bold]      {score:.1f} / 100  —  {_grade_label(score)}",
    ])

    cat_scores = compute_category_scores(results)
    cat_table = Table(show_header=True, box=None, padding=(0, 2))
    cat_table.add_column("Category", style="bold")
    cat_table.add_column("Score", justify="right")
    cat_table.add_column("Grade", justify="center")
    cat_table.add_column("Weight", justify="right", style="dim")
    cat_table.add_column("", no_wrap=True)

    for cat in CATEGORY_ORDER:
        s = cat_scores.get(cat)
        if s is None:
            continue
        g = _grade(s)
        color = _score_color(s)
        w = CATEGORY_WEIGHTS.get(cat, 0.0)
        cat_table.add_row(
            cat.upper(),
            f"[{color}]{s:.1f}[/{color}]",
            f"[{color}]{g}[/{color}]",
            f"{w:.0%}",
            _score_bar(s, width=12),
        )

    console.print(Panel(
        Group(stats, "", cat_table),
        title="[bold]Summary[/bold]",
        border_style="green",
    ))


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
        "category_scores": compute_category_scores(results),
    }

    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)

    return output_path
