"""Pemeriksaan kesesuaian sistem dengan profil untuk monitoring dan status."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hostkeeper.engine.step import Step
from hostkeeper.monitor.collector import Metric
from hostkeeper.profile import Profile, load_profile
from hostkeeper.steps import REGISTRY
from hostkeeper.system.fileops import FileOps, ReadOnlyFileOps
from hostkeeper.system.runner import ReadOnlyRunner, Runner


@dataclass(frozen=True)
class StepCompliance:
    name: str
    compliant: bool
    current: str
    status: str  # "ok" | "warn"
    detail: str = ""


def check_profile_compliance(
    profile: Profile,
    runner: Runner,
    fs: FileOps,
) -> tuple[list[Metric], list[StepCompliance]]:
    """Memeriksa semua Step aktif dalam profil.

    Menggunakan ReadOnlyRunner dan ReadOnlyFileOps.
    """
    ro_runner = runner if isinstance(runner, ReadOnlyRunner) else ReadOnlyRunner(runner)
    ro_fs = fs if isinstance(fs, ReadOnlyFileOps) else ReadOnlyFileOps(fs)

    metrics: list[Metric] = []
    compliances: list[StepCompliance] = []

    for step_cls in REGISTRY:
        step: Step = step_cls(profile, ro_runner, ro_fs)
        if not step.enabled():
            continue

        check_res = step.check()
        metric_name = f"profile.{step.name}"

        if not check_res.compliant:
            status = "warn"
            val = f"tidak sesuai: {check_res.current}"
            compliances.append(
                StepCompliance(
                    name=step.name,
                    compliant=False,
                    current=check_res.current,
                    status=status,
                    detail=(
                        f"Step {step.name} tidak lagi sesuai profil "
                        f"({check_res.current})"
                    ),
                )
            )
        else:
            status = "ok"
            val = check_res.current
            compliances.append(
                StepCompliance(
                    name=step.name,
                    compliant=True,
                    current=check_res.current,
                    status=status,
                    detail=f"{check_res.current} (sesuai)",
                )
            )

        metrics.append(
            Metric(
                name=metric_name,
                value=val,
                unit="",
                status_hint=status,
            )
        )

    return metrics, compliances


def load_profile_if_exists(
    profile_path: Path,
) -> Profile | None:
    """Membaca file profil jika ada dan valid; mengembalikan None jika tidak ada."""
    if not profile_path.is_file():
        return None
    try:
        return load_profile(profile_path)
    except Exception:
        return None
