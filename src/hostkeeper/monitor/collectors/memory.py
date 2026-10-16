"""Collector memori dan swap dari /proc/meminfo."""

from __future__ import annotations

from hostkeeper.monitor.collector import CollectContext, Metric


def collect_memory(ctx: CollectContext) -> list[Metric]:
    meminfo_file = ctx.proc_path / "meminfo"
    if not meminfo_file.is_file():
        return [
            Metric(name="mem.total_mb", value=0.0, unit="MB", status_hint="unknown"),
            Metric(
                name="mem.available_mb", value=0.0, unit="MB", status_hint="unknown"
            ),
            Metric(name="mem.used_percent", value=0.0, unit="%", status_hint="unknown"),
            Metric(name="swap.total_mb", value=0.0, unit="MB", status_hint="unknown"),
            Metric(name="swap.free_mb", value=0.0, unit="MB", status_hint="unknown"),
            Metric(
                name="swap.used_percent", value=0.0, unit="%", status_hint="unknown"
            ),
        ]

    data: dict[str, int] = {}
    try:
        for line in meminfo_file.read_text(encoding="utf-8").splitlines():
            parts = line.split(":")
            if len(parts) >= 2:
                key = parts[0].strip()
                val_parts = parts[1].strip().split()
                if val_parts:
                    try:
                        data[key] = int(val_parts[0])
                    except ValueError:
                        pass
    except OSError:
        pass

    mem_total_kb = data.get("MemTotal", 0)
    mem_avail_kb = data.get("MemAvailable", data.get("MemFree", 0))
    swap_total_kb = data.get("SwapTotal", 0)
    swap_free_kb = data.get("SwapFree", 0)

    mem_total_mb = round(mem_total_kb / 1024, 1)
    mem_avail_mb = round(mem_avail_kb / 1024, 1)

    if mem_total_kb > 0:
        mem_used_pct = round((1.0 - (mem_avail_kb / mem_total_kb)) * 100, 1)
    else:
        mem_used_pct = 0.0

    swap_total_mb = round(swap_total_kb / 1024, 1)
    swap_free_mb = round(swap_free_kb / 1024, 1)

    if swap_total_kb > 0:
        swap_used_pct = round((1.0 - (swap_free_kb / swap_total_kb)) * 100, 1)
    else:
        swap_used_pct = 0.0

    return [
        Metric(name="mem.total_mb", value=mem_total_mb, unit="MB", status_hint="ok"),
        Metric(
            name="mem.available_mb", value=mem_avail_mb, unit="MB", status_hint="ok"
        ),
        Metric(name="mem.used_percent", value=mem_used_pct, unit="%", status_hint="ok"),
        Metric(name="swap.total_mb", value=swap_total_mb, unit="MB", status_hint="ok"),
        Metric(name="swap.free_mb", value=swap_free_mb, unit="MB", status_hint="ok"),
        Metric(
            name="swap.used_percent", value=swap_used_pct, unit="%", status_hint="ok"
        ),
    ]
