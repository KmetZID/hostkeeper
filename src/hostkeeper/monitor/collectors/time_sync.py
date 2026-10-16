"""Collector status sinkronisasi waktu (NTP)."""

from __future__ import annotations

from hostkeeper.monitor.collector import CollectContext, Metric


def collect_time_sync(ctx: CollectContext) -> list[Metric]:
    res = ctx.runner.run(["timedatectl", "show"], mutates=False)
    if not res.ok:
        return [
            Metric(
                name="time.ntp_synchronized",
                value=False,
                unit="",
                status_hint="unknown",
            )
        ]

    is_sync = False
    for line in res.stdout.splitlines():
        if line.startswith("NTPSynchronized="):
            val = line.split("=", 1)[1].strip().lower()
            if val in ("yes", "true", "1"):
                is_sync = True
            break

    status = "ok" if is_sync else "warn"
    return [
        Metric(
            name="time.ntp_synchronized",
            value=is_sync,
            unit="",
            status_hint=status,
        )
    ]
