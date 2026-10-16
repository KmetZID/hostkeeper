"""Collector update tertunda dan status reboot-required."""

from __future__ import annotations

from pathlib import Path

from hostkeeper.monitor.collector import CollectContext, Metric


def collect_updates(ctx: CollectContext) -> list[Metric]:
    res = ctx.runner.run(["apt-get", "-s", "upgrade"], mutates=False)

    pending_count = 0
    security_count = 0

    if res.ok:
        for line in res.stdout.splitlines():
            if line.startswith("Inst "):
                pending_count += 1
                if (
                    "-security" in line
                    or "Debian-Security" in line
                    or "Ubuntu:*-security" in line
                ):
                    security_count += 1

    # Cek reboot-required di path yang diinjeksi atau path sistem standar
    reboot_required = False
    if ctx.reboot_required_path.is_file():
        reboot_required = True
    elif (
        Path("/run/reboot-required").is_file()
        or Path("/var/run/reboot-required").is_file()
    ):
        reboot_required = True

    status = "warn" if (security_count > 0 or reboot_required) else "ok"

    return [
        Metric(
            name="updates.pending",
            value=pending_count,
            unit="packages",
            status_hint="ok" if pending_count == 0 else "warn",
        ),
        Metric(
            name="updates.security",
            value=security_count,
            unit="packages",
            status_hint="ok" if security_count == 0 else "warn",
        ),
        Metric(
            name="updates.reboot_required",
            value=reboot_required,
            unit="",
            status_hint=status,
        ),
    ]
