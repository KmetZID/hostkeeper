"""Engine planner: pengurutan dependensi Step dan perencanaan perubahan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from hostkeeper import messages
from hostkeeper.engine.step import Change, CheckResult, Risk, Step
from hostkeeper.profile import Profile
from hostkeeper.system.fileops import FileOps
from hostkeeper.system.runner import Runner


class PlannerError(Exception):
    """Kesalahan umum pada engine planner."""


class DependencyCycleError(PlannerError):
    """Siklus dependensi antar langkah terdeteksi."""


class MissingDependencyError(PlannerError):
    """Langkah membutuhkan dependensi yang tidak terdaftar."""


def sort_step_classes(step_classes: Sequence[type[Step]]) -> list[type[Step]]:
    """Mengurutkan kelas Step berdasarkan requires secara topologis.

    Memastikan setiap prasyarat (requires) dijalankan sebelum
    langkah yang membutuhkannya.
    Mendeteksi siklus dependensi dan dependensi yang hilang.
    """

    by_name = {cls.name: cls for cls in step_classes}

    # Periksa apakah ada dependensi yang tidak terdaftar
    for cls in step_classes:
        for dep in cls.requires:
            if dep not in by_name:
                raise MissingDependencyError(
                    messages.MISSING_DEPENDENCY.format(step=cls.name, dep=dep)
                )

    # 0 = belum dikunjungi, 1 = sedang dalam lintasan rekursif, 2 = selesai
    state: dict[str, int] = {cls.name: 0 for cls in step_classes}
    ordered: list[type[Step]] = []
    path: list[str] = []

    def visit(name: str) -> None:
        if state[name] == 1:
            cycle_path = " -> ".join(path + [name])
            raise DependencyCycleError(
                messages.DEPENDENCY_CYCLE.format(cycle=cycle_path)
            )
        if state[name] == 2:
            return

        state[name] = 1
        path.append(name)

        cls = by_name[name]
        for dep in cls.requires:
            visit(dep)

        path.pop()
        state[name] = 2
        ordered.append(cls)

    for cls in step_classes:
        if state[cls.name] == 0:
            visit(cls.name)

    return ordered


@dataclass(frozen=True)
class PlanItem:
    """Hasil perencanaan untuk satu Step."""

    step: Step
    check_result: CheckResult
    changes: list[Change]


@dataclass(frozen=True)
class PlanReport:
    """Laporan keseluruhan dari proses plan."""

    items: list[PlanItem]

    @property
    def total_changes(self) -> int:
        return sum(1 for item in self.items if len(item.changes) > 0)

    @property
    def total_compliant(self) -> int:
        return sum(1 for item in self.items if item.check_result.compliant)

    @property
    def total_high_risk(self) -> int:
        return sum(
            1
            for item in self.items
            if len(item.changes) > 0 and item.step.risk == Risk.HIGH
        )


class Planner:
    """Mengelola pengurutan langkah dan pemanggilan check/plan."""

    def __init__(
        self,
        profile: Profile,
        runner: Runner,
        fs: FileOps,
        registry: Sequence[type[Step]] | None = None,
    ) -> None:
        self.profile = profile
        self.runner = runner
        self.fs = fs
        self.registry = registry

    def get_ordered_steps(self) -> list[Step]:
        """Mengembalikan instance Step yang diurutkan dan hanya yang enabled."""
        reg = self.registry
        if reg is None:
            from hostkeeper.steps import REGISTRY

            reg = REGISTRY

        sorted_classes = sort_step_classes(reg)
        steps: list[Step] = []
        for cls in sorted_classes:
            instance = cls(self.profile, self.runner, self.fs)
            if instance.enabled():
                steps.append(instance)
        return steps

    def plan(self) -> PlanReport:
        """Menjalankan check() dan plan() untuk semua Step yang aktif."""
        items: list[PlanItem] = []
        for step in self.get_ordered_steps():
            chk = step.check()
            changes = [] if chk.compliant else step.plan()
            items.append(PlanItem(step=step, check_result=chk, changes=changes))
        return PlanReport(items=items)
