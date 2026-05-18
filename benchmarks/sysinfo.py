from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class SystemInfo:
    hostname: str
    distro: str
    kernel: str
    cpu_model: str
    cpu_logical: int
    cpu_physical: int
    ram_total_mb: int
    ram_available_mb: int
    python_version: str
    rich_version: str
    disk_mount: str
    disk_total_gb: float
    disk_free_gb: float


def _parse_os_release() -> str:
    try:
        with open("/etc/os-release") as f:
            data = {}
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    data[k] = v.strip('"')
        name = data.get("NAME", "")
        version = data.get("VERSION_ID", "")
        return f"{name} {version}".strip() or "Unknown"
    except OSError:
        return platform.system()


def _sysctl_str(key: str) -> str:
    try:
        return subprocess.check_output(["sysctl", "-n", key], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def _sysctl_int(key: str) -> int:
    val = _sysctl_str(key)
    try:
        return int(val)
    except ValueError:
        return 0


def _parse_cpu_info() -> tuple:
    model = "Unknown"
    physical_ids = set()
    cores_per_socket = 1
    try:
        with open("/proc/cpuinfo") as f:
            current_physical_id = None
            current_cores = 1
            for line in f:
                line = line.strip()
                if line.startswith("model name") and model == "Unknown":
                    model = line.split(":", 1)[1].strip()
                elif line.startswith("physical id"):
                    current_physical_id = line.split(":", 1)[1].strip()
                    physical_ids.add(current_physical_id)
                elif line.startswith("cpu cores"):
                    current_cores = int(line.split(":", 1)[1].strip())
                    cores_per_socket = current_cores
    except OSError:
        pass

    if model == "Unknown" and platform.system() == "Darwin":
        model = _sysctl_str("machdep.cpu.brand_string") or _sysctl_str("hw.model") or "Unknown"

    physical = len(physical_ids) * cores_per_socket if physical_ids else 1
    logical = os.cpu_count() or 1

    if platform.system() == "Darwin":
        mac_physical = _sysctl_int("hw.physicalcpu") or _sysctl_int("hw.physicalcpu_max")
        if mac_physical:
            physical = mac_physical

    return model, logical, physical


def _parse_meminfo() -> tuple:
    total_kb = 0
    available_kb = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    available_kb = int(line.split()[1])
    except OSError:
        pass

    if total_kb == 0 and platform.system() == "Darwin":
        total_bytes = _sysctl_int("hw.memsize")
        total_kb = total_bytes // 1024
        # vm_stat reports page counts; page size is typically 16384 on Apple Silicon, 4096 on Intel
        try:
            page_size = _sysctl_int("hw.pagesize") or 4096
            vm_out = subprocess.check_output(["vm_stat"], stderr=subprocess.DEVNULL).decode()
            free_pages = 0
            inactive_pages = 0
            for line in vm_out.splitlines():
                if line.startswith("Pages free:"):
                    free_pages += int(line.split(":")[1].strip().rstrip("."))
                elif line.startswith("Pages inactive:"):
                    inactive_pages += int(line.split(":")[1].strip().rstrip("."))
            available_kb = (free_pages + inactive_pages) * page_size // 1024
        except Exception:
            available_kb = total_kb // 2  # rough fallback

    return total_kb // 1024, available_kb // 1024


def _rich_version() -> str:
    try:
        from importlib.metadata import version
        return version("rich")
    except Exception:
        try:
            import rich
            return getattr(rich, "__version__", "unknown")
        except Exception:
            return "unknown"


def collect(bench_dir: str) -> SystemInfo:
    cpu_model, cpu_logical, cpu_physical = _parse_cpu_info()
    ram_total, ram_available = _parse_meminfo()

    try:
        usage = shutil.disk_usage(bench_dir)
        disk_mount = bench_dir
        disk_total_gb = usage.total / (1024 ** 3)
        disk_free_gb = usage.free / (1024 ** 3)
    except OSError:
        disk_mount = bench_dir
        disk_total_gb = 0.0
        disk_free_gb = 0.0

    return SystemInfo(
        hostname=socket.gethostname(),
        distro=_parse_os_release(),
        kernel=platform.release(),
        cpu_model=cpu_model,
        cpu_logical=cpu_logical,
        cpu_physical=cpu_physical,
        ram_total_mb=ram_total,
        ram_available_mb=ram_available,
        python_version=sys.version.split()[0],
        rich_version=_rich_version(),
        disk_mount=disk_mount,
        disk_total_gb=round(disk_total_gb, 1),
        disk_free_gb=round(disk_free_gb, 1),
    )
