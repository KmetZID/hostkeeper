"""Collector login SSH gagal dari journalctl."""

from __future__ import annotations

from hostkeeper.monitor.collector import CollectContext, Metric


def collect_ssh_failed(ctx: CollectContext) -> list[Metric]:
    res = ctx.runner.run(
        ["journalctl", "-u", "ssh", "--since", "-10min"],
        mutates=False,
    )
    if not res.ok:
        # Layanan sshd di beberapa distro mungkin sshd.service atau journalctl tidak ada
        return [
            Metric(
                name="ssh.failed_logins_10m",
                value=0,
                unit="attempts",
                status_hint="unknown",
            )
        ]

    failed_count = 0
    for line in res.stdout.splitlines():
        if "Failed password" in line or "Invalid user" in line:
            failed_count += 1

    status = "warn" if failed_count > 10 else "ok"

    return [
        Metric(
            name="ssh.failed_logins_10m",
            value=failed_count,
            unit="attempts",
            status_hint=status,
        )
    ]
