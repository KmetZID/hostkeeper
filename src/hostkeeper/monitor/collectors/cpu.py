"""Collector CPU: loadavg dan jumlah core."""

from __future__ import annotations

from hostkeeper.monitor.collector import CollectContext, Metric


def collect_cpu(ctx: CollectContext) -> list[Metric]:
    loadavg_file = ctx.proc_path / "loadavg"
    cpuinfo_file = ctx.proc_path / "cpuinfo"

    if not loadavg_file.is_file():
        return [
            Metric(name="cpu.load1", value=0.0, unit="", status_hint="unknown"),
            Metric(name="cpu.load5", value=0.0, unit="", status_hint="unknown"),
            Metric(name="cpu.load15", value=0.0, unit="", status_hint="unknown"),
            Metric(name="cpu.cores", value=1, unit="cores", status_hint="unknown"),
            Metric(
                name="cpu.load1_per_core", value=0.0, unit="", status_hint="unknown"
            ),
        ]

    try:
        load_parts = loadavg_file.read_text(encoding="utf-8").split()
        load1 = float(load_parts[0])
        load5 = float(load_parts[1])
        load15 = float(load_parts[2])
    except (IndexError, ValueError, OSError):
        return [
            Metric(name="cpu.load1", value=0.0, unit="", status_hint="unknown"),
            Metric(name="cpu.load5", value=0.0, unit="", status_hint="unknown"),
            Metric(name="cpu.load15", value=0.0, unit="", status_hint="unknown"),
            Metric(name="cpu.cores", value=1, unit="cores", status_hint="unknown"),
            Metric(
                name="cpu.load1_per_core", value=0.0, unit="", status_hint="unknown"
            ),
        ]

    cores = 1
    if cpuinfo_file.is_file():
        try:
            content = cpuinfo_file.read_text(encoding="utf-8")
            count = sum(
                1
                for line in content.splitlines()
                if line.startswith("processor\t:") or line.startswith("processor :")
            )
            if count > 0:
                cores = count
        except OSError:
            pass

    load1_per_core = round(load1 / cores, 2)

    return [
        Metric(name="cpu.load1", value=load1, unit="", status_hint="ok"),
        Metric(name="cpu.load5", value=load5, unit="", status_hint="ok"),
        Metric(name="cpu.load15", value=load15, unit="", status_hint="ok"),
        Metric(name="cpu.cores", value=cores, unit="cores", status_hint="ok"),
        Metric(
            name="cpu.load1_per_core", value=load1_per_core, unit="", status_hint="ok"
        ),
    ]
