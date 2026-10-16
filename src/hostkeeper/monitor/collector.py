"""Definisi Metric, CollectContext, dan fungsi collect_all."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from hostkeeper.system.fileops import FileOps, ReadOnlyFileOps
from hostkeeper.system.runner import ReadOnlyRunner, Runner, SubprocessRunner


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | int | str | bool
    unit: str = ""
    status_hint: str = "ok"  # "ok", "warn", "crit", "unknown"


@dataclass
class CollectContext:
    proc_path: Path = field(default_factory=lambda: Path("/proc"))
    runner: Runner = field(default_factory=lambda: ReadOnlyRunner(SubprocessRunner()))
    fileops: FileOps = field(default_factory=ReadOnlyFileOps)
    mount_points: list[str] = field(default_factory=lambda: ["/"])
    statvfs_fn: Callable[[str], Any] = os.statvfs
    reboot_required_path: Path = field(
        default_factory=lambda: Path("/var/run/reboot-required")
    )


def collect_all(ctx: CollectContext) -> list[Metric]:
    """Menjalankan semua collector dan mengembalikan daftar metrik gabungan."""
    from hostkeeper.monitor.collectors.cpu import collect_cpu
    from hostkeeper.monitor.collectors.disk import collect_disk
    from hostkeeper.monitor.collectors.memory import collect_memory
    from hostkeeper.monitor.collectors.psi import collect_psi
    from hostkeeper.monitor.collectors.services import collect_services
    from hostkeeper.monitor.collectors.ssh_failed import collect_ssh_failed
    from hostkeeper.monitor.collectors.time_sync import collect_time_sync
    from hostkeeper.monitor.collectors.updates import collect_updates

    metrics: list[Metric] = []
    metrics.extend(collect_cpu(ctx))
    metrics.extend(collect_memory(ctx))
    metrics.extend(collect_psi(ctx))
    metrics.extend(collect_disk(ctx))
    metrics.extend(collect_time_sync(ctx))
    metrics.extend(collect_services(ctx))
    metrics.extend(collect_updates(ctx))
    metrics.extend(collect_ssh_failed(ctx))
    return metrics
