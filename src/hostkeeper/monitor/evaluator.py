"""Evaluator metrik terhadap ambang batas watch.yml dengan hysteresis dan cooldown."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hostkeeper.monitor.collector import Metric
from hostkeeper.monitor.state import AlertRecord


@dataclass(frozen=True)
class ThresholdConfig:
    warn: float | int | bool
    crit: float | int | bool | None = None
    recover: float | int | bool | None = None


@dataclass(frozen=True)
class EvaluationResult:
    metric_name: str
    status: str  # "ok", "warn", "crit", "unknown"
    message: str
    value: Any
    is_transition: bool
    previous_status: str
    alert_needed: bool


DEFAULT_THRESHOLDS: dict[str, ThresholdConfig] = {
    "mem_used_percent": ThresholdConfig(warn=80.0, crit=90.0, recover=75.0),
    "swap_used_percent": ThresholdConfig(warn=50.0, crit=80.0, recover=40.0),
    "disk_used_percent": ThresholdConfig(warn=80.0, crit=90.0, recover=75.0),
    "disk_inodes_used_percent": ThresholdConfig(warn=80.0, crit=90.0, recover=75.0),
    "cpu_load_per_core": ThresholdConfig(warn=2.0, crit=4.0, recover=1.5),
    "psi_cpu_some_avg10": ThresholdConfig(warn=25.0, crit=50.0, recover=15.0),
    "psi_memory_some_avg10": ThresholdConfig(warn=25.0, crit=50.0, recover=15.0),
    "psi_io_some_avg10": ThresholdConfig(warn=25.0, crit=50.0, recover=15.0),
    "services_failed_count": ThresholdConfig(warn=1, crit=1, recover=0),
    "updates_security": ThresholdConfig(warn=1, crit=5, recover=0),
    "updates_reboot_required": ThresholdConfig(warn=True, recover=False),
    "ssh_failed_logins": ThresholdConfig(warn=10, crit=50, recover=5),
    "time_ntp_synchronized": ThresholdConfig(warn=False, recover=True),
}


def _metric_to_threshold_key(name: str) -> str | None:
    if name == "mem.used_percent":
        return "mem_used_percent"
    if name == "swap.used_percent":
        return "swap_used_percent"
    if name.startswith("disk.") and name.endswith(".used_percent"):
        return "disk_used_percent"
    if name.startswith("disk.") and name.endswith(".inodes_used_percent"):
        return "disk_inodes_used_percent"
    if name == "cpu.load1_per_core":
        return "cpu_load_per_core"
    if name == "psi.cpu.some_avg10":
        return "psi_cpu_some_avg10"
    if name == "psi.memory.some_avg10":
        return "psi_memory_some_avg10"
    if name == "psi.io.some_avg10":
        return "psi_io_some_avg10"
    if name == "services.failed_count":
        return "services_failed_count"
    if name == "updates.security":
        return "updates_security"
    if name == "updates.reboot_required":
        return "updates_reboot_required"
    if name == "ssh.failed_logins_10m":
        return "ssh_failed_logins"
    if name == "time.ntp_synchronized":
        return "time_ntp_synchronized"
    return None


class Evaluator:
    """Mengevaluasi metrik terhadap konfigurasi ambang batas watch.yml."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or Path("/etc/hostkeeper/watch.yml")
        self.thresholds: dict[str, ThresholdConfig] = dict(DEFAULT_THRESHOLDS)
        self.cooldown_seconds: float = 3600.0
        self._load_config()

    def _load_config(self) -> None:
        if not self.config_path.is_file():
            return

        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return

            if "cooldown_seconds" in raw and isinstance(
                raw["cooldown_seconds"], (int, float)
            ):
                self.cooldown_seconds = float(raw["cooldown_seconds"])

            custom_th = raw.get("thresholds")
            if isinstance(custom_th, dict):
                for k, v in custom_th.items():
                    if isinstance(v, dict) and "warn" in v:
                        self.thresholds[k] = ThresholdConfig(
                            warn=v["warn"],
                            crit=v.get("crit"),
                            recover=v.get("recover"),
                        )
        except Exception:
            # Fallback ke default aman jika file watch.yml cacat
            pass

    def evaluate(
        self,
        metrics: list[Metric],
        previous_alerts: dict[str, AlertRecord],
        now: float | None = None,
    ) -> list[EvaluationResult]:
        _ = now
        results: list[EvaluationResult] = []

        for m in metrics:
            th_key = _metric_to_threshold_key(m.name)
            prev = previous_alerts.get(m.name)
            old_status = prev.status if prev else "ok"

            if m.status_hint == "unknown":
                results.append(
                    EvaluationResult(
                        metric_name=m.name,
                        status="unknown",
                        message=f"{m.name}: nilai tidak dapat ditentukan",
                        value=m.value,
                        is_transition=old_status != "unknown",
                        previous_status=old_status,
                        alert_needed=(old_status != "unknown"),
                    )
                )
                continue

            if not th_key or th_key not in self.thresholds:
                # Tanpa ambang khusus, ikuti status_hint
                status = m.status_hint
                results.append(
                    EvaluationResult(
                        metric_name=m.name,
                        status=status,
                        message=f"{m.name}: {m.value}{m.unit}",
                        value=m.value,
                        is_transition=(status != old_status),
                        previous_status=old_status,
                        alert_needed=(status != old_status and status != "ok"),
                    )
                )
                continue

            th = self.thresholds[th_key]
            new_status = self._evaluate_single(m.value, th, old_status)
            is_transition = new_status != old_status

            # Alert hanya saat transisi!
            alert_needed = is_transition

            msg = f"{m.name} = {m.value}{m.unit} (status: {new_status})"
            if is_transition and new_status == "ok":
                msg = f"{m.name} telah pulih kembali normal ({m.value}{m.unit})"

            results.append(
                EvaluationResult(
                    metric_name=m.name,
                    status=new_status,
                    message=msg,
                    value=m.value,
                    is_transition=is_transition,
                    previous_status=old_status,
                    alert_needed=alert_needed,
                )
            )

        return results

    def _evaluate_single(
        self,
        val: Any,
        th: ThresholdConfig,
        old_status: str,
    ) -> str:
        # Boolean check (misal time.ntp_synchronized, updates.reboot_required)
        if isinstance(th.warn, bool):
            if val == th.warn:
                return "warn"
            if th.recover is not None and val == th.recover:
                return "ok"
            return "ok" if not val else "warn"

        # Numeric check
        try:
            num = float(val)
        except (ValueError, TypeError):
            return "unknown"

        warn_val = float(th.warn)
        crit_val = float(th.crit) if th.crit is not None else None
        recover_val = float(th.recover) if th.recover is not None else warn_val

        # Hysteresis: jika sebelumnya warn atau crit
        if old_status in ("warn", "crit"):
            # Jika turun di bawah atau sama dengan batas recover -> pulih ke ok
            if num <= recover_val:
                return "ok"
            # Jika sebelumnya crit dan sekarang di bawah crit
            # tetapi masih di atas warn -> turun ke warn
            if old_status == "crit" and crit_val is not None and num < crit_val:
                return "warn"
            # Jika sebelumnya warn dan sekarang naik ke crit -> naik ke crit
            if old_status == "warn" and crit_val is not None and num >= crit_val:
                return "crit"
            return old_status

        # Status sebelumnya ok
        if crit_val is not None and num >= crit_val:
            return "crit"
        if num >= warn_val:
            return "warn"
        return "ok"
