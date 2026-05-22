# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (uv recommended)
uv venv && uv pip install -e .

# Run all benchmarks
cli-benchmark        # or: python bench.py

# Common flags
cli-benchmark --quick                  # 10x smaller workloads, smoke-test
cli-benchmark --only cpu,memory        # subset of categories
cli-benchmark --output /tmp/report.json
cli-benchmark --no-color
cli-benchmark --delay 32               # per-line print delay in ms (default: off)
```

No test suite or linter is configured.

## Architecture

The entry point is `bench.py` (`main()`), which parses args, displays a progress UI via `rich`, and delegates to per-category `run_all(quick)` functions.

**`benchmarks/runner.py`** — core execution engine. `TimedRunner` wraps a callable with timeout (120s via `ThreadPoolExecutor`) and, when `quick=False`, loops the callable until at least `MIN_DURATION_S` (0.5s) has elapsed, then averages the metric across iterations. Each benchmark function returns either a `(metric, extra_dict)` tuple or a scalar; `TimedRunner.run()` normalizes these into a `BenchmarkResult`.

**`benchmarks/{cpu,disk,memory,database,git}.py`** — one file per category. Each exposes a `run_all(quick: bool) -> List[BenchmarkResult]` function and individual `bench_*` functions. Benchmarks generate their own temp files/dirs and clean up in `finally` blocks. Git benchmarks skip gracefully if `git` is not on `PATH`.

**`benchmarks/reporter.py`** — rendering and scoring. `HIGHER_IS_BETTER`, `SCORE_REFERENCE`, and `CATEGORY_WEIGHTS` define benchmark semantics. Each benchmark is scored 0–100 via `_bench_score()` (log2 scale, 1× ref = 50 pts). Category scores are simple averages; the overall score is a weighted average across categories. `save_report()` writes JSON to `results/bench_<hostname>_<timestamp>.json`.

**`benchmarks/sysinfo.py`** — collects hostname, OS, CPU, RAM, and disk info into a `SystemInfo` dataclass.

## Adding a New Benchmark

1. Add a `bench_*` function to the appropriate category file, using `TimedRunner` and returning `(metric, extra_dict)`.
2. Add it to `run_all()` in that file.
3. Register the benchmark name in `reporter.py`'s `HIGHER_IS_BETTER` and `SCORE_REFERENCE` dicts.
