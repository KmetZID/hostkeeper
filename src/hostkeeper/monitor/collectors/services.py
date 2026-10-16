"""Collector service sistem yang gagal."""

from __future__ import annotations

from hostkeeper.monitor.collector import CollectContext, Metric


def collect_services(ctx: CollectContext) -> list[Metric]:
    res = ctx.runner.run(["systemctl", "--failed", "--no-legend"], mutates=False)
    if not res.ok:
        return [
            Metric(
                name="services.failed_count",
                value=0,
                unit="",
                status_hint="unknown",
            ),
            Metric(
                name="services.failed_list",
                value="",
                unit="",
                status_hint="unknown",
            ),
        ]

    failed_units: list[str] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if parts:
            failed_units.append(parts[0])

    count = len(failed_units)
    status = "crit" if count > 0 else "ok"
    failed_str = ", ".join(failed_units)

    return [
        Metric(
            name="services.failed_count",
            value=count,
            unit="",
            status_hint=status,
        ),
        Metric(
            name="services.failed_list",
            value=failed_str,
            unit="",
            status_hint=status,
        ),
    ]
