"""Collector ruang dan inode disk via statvfs."""

from __future__ import annotations

from hostkeeper.monitor.collector import CollectContext, Metric


def collect_disk(ctx: CollectContext) -> list[Metric]:
    metrics: list[Metric] = []
    for mount in ctx.mount_points:
        try:
            stat = ctx.statvfs_fn(mount)
            total_bytes = stat.f_blocks * stat.f_frsize
            avail_bytes = stat.f_bavail * stat.f_frsize
            free_bytes = stat.f_bfree * stat.f_frsize
            used_bytes = total_bytes - free_bytes

            total_gb = round(total_bytes / (1024**3), 1)
            free_gb = round(avail_bytes / (1024**3), 1)

            if total_bytes > 0:
                used_pct = round((used_bytes / total_bytes) * 100, 1)
            else:
                used_pct = 0.0

            total_inodes = stat.f_files
            free_inodes = stat.f_ffree
            used_inodes = total_inodes - free_inodes

            if total_inodes > 0:
                inodes_used_pct = round((used_inodes / total_inodes) * 100, 1)
            else:
                inodes_used_pct = 0.0

            metrics.append(
                Metric(
                    name=f"disk.{mount}.used_percent",
                    value=used_pct,
                    unit="%",
                    status_hint="ok",
                )
            )
            metrics.append(
                Metric(
                    name=f"disk.{mount}.total_gb",
                    value=total_gb,
                    unit="GB",
                    status_hint="ok",
                )
            )
            metrics.append(
                Metric(
                    name=f"disk.{mount}.free_gb",
                    value=free_gb,
                    unit="GB",
                    status_hint="ok",
                )
            )
            metrics.append(
                Metric(
                    name=f"disk.{mount}.inodes_used_percent",
                    value=inodes_used_pct,
                    unit="%",
                    status_hint="ok",
                )
            )
        except OSError:
            metrics.append(
                Metric(
                    name=f"disk.{mount}.used_percent",
                    value=0.0,
                    unit="%",
                    status_hint="unknown",
                )
            )
            metrics.append(
                Metric(
                    name=f"disk.{mount}.inodes_used_percent",
                    value=0.0,
                    unit="%",
                    status_hint="unknown",
                )
            )

    return metrics
