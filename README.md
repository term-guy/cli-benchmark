# cli-benchmark

A cross-platform performance benchmark tool that measures real-world performance across CPU, disk I/O, memory, database, and git operations. Runs on Linux and macOS.

## Install

### Using uv (recommended)

```bash
uv venv && uv pip install -e .
source .venv/bin/activate
```

### Using pip

```bash
pip install -e .
```

## Usage

```bash
# Run all benchmarks
cli-benchmark

# Or run directly
python bench.py

# Quick smoke-test (10x smaller workloads)
cli-benchmark --quick

# Run only specific categories
cli-benchmark --only cpu,memory

# Save report to a specific path
cli-benchmark --output /tmp/my_report.json

# Disable color output
cli-benchmark --no-color
```

## Example Output

```
╭──────────────────────────── System Info ──────-──────────────────────╮
│  Hostname  myserver                                                  │
│  OS        Ubuntu 22.04 / macOS 14.4                                 │
│  Kernel    5.15.0-89-generic / Darwin 23.4.0                         │
│  CPU       Intel(R) Xeon(R) E5-2680 v4 @ 2.40GHz / Apple M3 Pro      │
│  Cores     8 logical / 4 physical                                    │
│  RAM       16,384 MB total / 12,048 MB available                     │
│  Disk      /home/user  200.0 GB total / 120.5 GB free                │
│  Python    3.11.5                                                    │
│  Rich      13.7.0                                                    │
╰───────-──────────────────────────────────────────────────────────────╯

⠋ CPU benchmarks      0:00:03  running…
⠙ Disk I/O benchmarks 0:00:00  waiting…
...

                          CPU
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┓
┃ Benchmark          ┃   Result ┃ Unit ┃    Duration ┃ Score ┃  Rating  ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━┩
│ cpu.hashing        │  2,341.5 │ MB/s │      0.03s  │    97 │ ████████ │
│ cpu.compression    │    412.3 │ MB/s │      0.05s  │    89 │ ███████░ │
│ cpu.prime_sieve    │     82.3 │   ms │      0.82s  │    74 │ ██████░░ │
│ cpu.multicore      │  1,418.0 │ MB/s │      1.12s  │    91 │ ████████ │
├────────────────────┼──────────┼──────┼─────────────┼───────┼──────────┤
│                    │          │      │ Category avg│    88 │ ███████░ │
└────────────────────┴──────────┴──────┴─────────────┴───────┴──────────┘

╭──────────────────────────── Summary ───────────────────────-─────╮
│ Total time:  47.3s                                               │
│ Benchmarks: 21 passed  0 skipped  0 errored                      │
│ Report:     results/bench_myserver_20240115_103047.json          │
│ Score:      78.2 / 100  —  A  🟢 Fast                            │
│                                                                  │
│ Category   Score  Grade  Weight                                  │
│ CPU         88.0      A     25%  ████████████                    │
│ DISK        81.5      A     25%  ██████████░░                    │
│ MEMORY      74.2      B     20%  █████████░░░                    │
│ DATABASE    71.8      B     20%  █████████░░░                    │
│ GIT         65.3      A     10%  ████████░░░░                    │
╰──────────────────────────────────────────────────────────────────╯
```

## CLI Flags

| Flag | Description |
|------|-------------|
| `--only CATEGORIES` | Comma-separated list of categories: `cpu`, `disk`, `memory`, `database`, `git` |
| `--output PATH` | Override the default JSON report path (`results/bench_<host>_<timestamp>.json`) |
| `--quick` | Use reduced workloads (~10x smaller) for a fast smoke test |
| `--no-color` | Disable rich color output (useful for CI or log capture) |

## What Each Benchmark Measures

### CPU

| Benchmark | Workload | Metric |
|-----------|----------|--------|
| `cpu.hashing` | SHA-256 of 64 MB buffer | MB/s |
| `cpu.compression` | gzip compress+decompress 10 MB | MB/s |
| `cpu.prime_sieve` | Sieve of Eratosthenes to 10,000,000 | ms |
| `cpu.multicore` | Parallel SHA-256 across all logical cores | MB/s + efficiency % |

### Disk I/O

| Benchmark | Workload | Metric |
|-----------|----------|--------|
| `disk.seq_write` | 512 MB sequential write with fsync | MB/s |
| `disk.seq_read` | 512 MB sequential read | MB/s |
| `disk.random_read` | 1000 random 4 KB seeks | IOPS |
| `disk.small_write` | Create 1000 × 1 KB files | ops/s |
| `disk.small_delete` | Delete 1000 × 1 KB files | ops/s |

### Memory

| Benchmark | Workload | Metric |
|-----------|----------|--------|
| `memory.write_bw` | Overwrite 256 MB bytearray | GB/s |
| `memory.read_bw` | Read through 256 MB bytearray | GB/s |
| `memory.latency` | Pointer-chase traversal (random access) | ns/access |

### Database (SQLite)

| Benchmark | Workload | Metric |
|-----------|----------|--------|
| `db.bulk_insert` | 100,000 rows in one transaction | rows/s |
| `db.indexed_select` | 10,000 lookups on indexed int column | queries/s |
| `db.nonindexed_select` | 1,000 full-scan text lookups | queries/s |
| `db.bulk_update` | Update 10,000 rows | rows/s |
| `db.delete_vacuum` | Delete all rows + VACUUM | ms |

### Git

| Benchmark | Workload | Metric |
|-----------|----------|--------|
| `git.large_commit` | 500 × 10 KB files, add + commit | files/s |
| `git.local_clone` | Clone a local repo | MB/s |
| `git.log_traversal` | `git log --oneline` across 200 commits | ms |
| `git.diff` | Diff between first and last of 200 commits | ms |

Git benchmarks are skipped gracefully if `git` is not found on `PATH`.

## Results and Scoring

Results are saved to `results/bench_<hostname>_<YYYYMMDD_HHMMSS>.json` after every run.

### Score Calculation

Each benchmark is scored 0–100 against calibrated reference values. A machine matching all references scores 50. The scale is logarithmic: 2× the reference → 75 pts, 4× → 100 pts, ½× → 25 pts.

Per-benchmark scores are averaged within each category, then combined into an overall score using weighted categories (CPU 25%, Disk 25%, Memory 20%, Database 20%, Git 10%).

| Grade | Score | Label |
|-------|-------|-------|
| S | ≥ 75 | 🟣 Exceptional |
| A | 60–74 | 🟢 Fast |
| B | 45–59 | 🔵 Above Average |
| C | 30–44 | 🟡 Average |
| D | 15–29 | 🟠 Below Average |
| F | < 15 | 🔴 Slow |

Rating bars (█████░░░) and colors reflect the score: green ≥ 75, yellow ≥ 45, red below.

### JSON Report Format

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "system": {
    "hostname": "myserver",
    "distro": "Ubuntu 22.04 / macOS 14.4",
    "kernel": "5.15.0-89-generic / Darwin 23.4.0",
    "cpu_model": "Intel(R) Xeon(R) E5-2680 v4 / Apple M3 Pro",
    "cpu_logical": 8,
    "cpu_physical": 4,
    "ram_total_mb": 16384,
    "ram_available_mb": 12048,
    "python_version": "3.11.5",
    "rich_version": "13.7.0",
    "disk_mount": "/home/user/project",
    "disk_total_gb": 200.0,
    "disk_free_gb": 120.5
  },
  "results": [
    {
      "name": "cpu.hashing",
      "category": "cpu",
      "metric": 2341.5,
      "unit": "MB/s",
      "duration_s": 0.027,
      "extra": {"size_mb": 64},
      "error": null,
      "skipped": false
    }
  ],
  "score": 72.4,
  "category_scores": {
    "cpu": 88.0,
    "disk": 81.5,
    "memory": 74.2,
    "database": 71.8,
    "git": 65.3
  }
}
```
