"""Collector Pressure Stall Information (PSI): cpu, memory, io."""

from __future__ import annotations

from hostkeeper.monitor.collector import CollectContext, Metric


def _parse_psi_avg10(content: str) -> float | None:
    for line in content.splitlines():
        if line.startswith("some "):
            parts = line.split()
            for part in parts[1:]:
                if part.startswith("avg10="):
                    try:
                        return float(part.split("=")[1])
                    except (ValueError, IndexError):
                        return None
    return None


def collect_psi(ctx: CollectContext) -> list[Metric]:
    metrics: list[Metric] = []
    pressure_dir = ctx.proc_path / "pressure"

    for resource in ("cpu", "memory", "io"):
        pfile = pressure_dir / resource
        metric_name = f"psi.{resource}.some_avg10"
        if not pfile.is_file():
            metrics.append(
                Metric(
                    name=metric_name,
                    value="tidak tersedia",
                    unit="%",
                    status_hint="unknown",
                )
            )
            continue

        try:
            val = _parse_psi_avg10(pfile.read_text(encoding="utf-8"))
            if val is not None:
                metrics.append(
                    Metric(name=metric_name, value=val, unit="%", status_hint="ok")
                )
            else:
                metrics.append(
                    Metric(
                        name=metric_name,
                        value="tidak tersedia",
                        unit="%",
                        status_hint="unknown",
                    )
                )
        except OSError:
            metrics.append(
                Metric(
                    name=metric_name,
                    value="tidak tersedia",
                    unit="%",
                    status_hint="unknown",
                )
            )

    return metrics
