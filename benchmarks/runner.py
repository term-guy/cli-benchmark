from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Optional


TIMEOUT_SECONDS = 120
MIN_DURATION_S = 0.5


@dataclass
class BenchmarkResult:
    name: str
    category: str
    metric: float
    unit: str
    duration_s: float
    extra: dict = field(default_factory=dict)
    error: Optional[str] = None
    skipped: bool = False


class TimedRunner:
    """Context manager that runs a benchmark with timeout and exception handling."""

    def __init__(self, name: str, category: str, unit: str, quick: bool = False):
        self.name = name
        self.category = category
        self.unit = unit
        self.quick = quick
        self._start = 0.0
        self.result: Optional[BenchmarkResult] = None

    def run(self, fn, *args, **kwargs) -> BenchmarkResult:
        self._start = time.perf_counter()
        metrics = []
        last_outcome = None

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                while True:
                    future = executor.submit(fn, *args, **kwargs)
                    try:
                        outcome = future.result(timeout=TIMEOUT_SECONDS)
                    except FuturesTimeoutError:
                        duration = time.perf_counter() - self._start
                        return BenchmarkResult(
                            name=self.name,
                            category=self.category,
                            metric=0.0,
                            unit=self.unit,
                            duration_s=duration,
                            error=f"timed out after {TIMEOUT_SECONDS}s",
                        )

                    last_outcome = outcome
                    if isinstance(outcome, BenchmarkResult):
                        metrics.append(outcome.metric)
                    else:
                        m = outcome[0] if isinstance(outcome, tuple) else outcome
                        metrics.append(float(m))

                    elapsed = time.perf_counter() - self._start
                    if self.quick or elapsed >= MIN_DURATION_S:
                        break
        except Exception as exc:
            duration = time.perf_counter() - self._start
            return BenchmarkResult(
                name=self.name,
                category=self.category,
                metric=0.0,
                unit=self.unit,
                duration_s=duration,
                error=str(exc),
            )

        duration = time.perf_counter() - self._start
        avg_metric = sum(metrics) / len(metrics)

        if isinstance(last_outcome, BenchmarkResult):
            last_outcome.metric = avg_metric
            last_outcome.duration_s = duration
            return last_outcome

        _, extra = last_outcome if isinstance(last_outcome, tuple) else (last_outcome, {})
        return BenchmarkResult(
            name=self.name,
            category=self.category,
            metric=avg_metric,
            unit=self.unit,
            duration_s=duration,
            extra=extra,
        )

    @staticmethod
    def skipped(name: str, category: str, unit: str, reason: str = "") -> BenchmarkResult:
        return BenchmarkResult(
            name=name,
            category=category,
            metric=0.0,
            unit=unit,
            duration_s=0.0,
            skipped=True,
            error=reason or None,
        )
