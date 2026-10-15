from __future__ import annotations

from typing import ClassVar

import pytest

from hostkeeper.engine.planner import (
    DependencyCycleError,
    MissingDependencyError,
    Planner,
    sort_step_classes,
)
from hostkeeper.engine.step import Change, CheckResult, Risk, Step
from hostkeeper.profile import Profile
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


class StepA(Step):
    name: ClassVar[str] = "step_a"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ()

    def enabled(self) -> bool:
        return True

    def check(self) -> CheckResult:
        return CheckResult(compliant=True, current="ok")

    def plan(self) -> list[Change]:
        return []

    def apply(self, changes: list[Change]) -> None:
        pass


class StepB(Step):
    name: ClassVar[str] = "step_b"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ("step_a",)

    def enabled(self) -> bool:
        return True

    def check(self) -> CheckResult:
        return CheckResult(compliant=False, current="drift")

    def plan(self) -> list[Change]:
        return [
            Change(
                step="step_b",
                action="set",
                target="b",
                before="drift",
                after="ok",
            )
        ]

    def apply(self, changes: list[Change]) -> None:
        pass


class StepC(Step):
    name: ClassVar[str] = "step_c"
    risk: ClassVar[Risk] = Risk.HIGH
    requires: ClassVar[tuple[str, ...]] = ("step_b",)

    def enabled(self) -> bool:
        return False  # Disabled

    def check(self) -> CheckResult:
        return CheckResult(compliant=True, current="ok")

    def plan(self) -> list[Change]:
        return []

    def apply(self, changes: list[Change]) -> None:
        pass


class CycleA(Step):
    name: ClassVar[str] = "cycle_a"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ("cycle_b",)

    def enabled(self) -> bool:
        return True

    def check(self) -> CheckResult:
        return CheckResult(compliant=True, current="ok")

    def plan(self) -> list[Change]:
        return []

    def apply(self, changes: list[Change]) -> None:
        pass


class CycleB(Step):
    name: ClassVar[str] = "cycle_b"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ("cycle_a",)

    def enabled(self) -> bool:
        return True

    def check(self) -> CheckResult:
        return CheckResult(compliant=True, current="ok")

    def plan(self) -> list[Change]:
        return []

    def apply(self, changes: list[Change]) -> None:
        pass


class MissingDepStep(Step):
    name: ClassVar[str] = "missing_dep"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ("non_existent",)

    def enabled(self) -> bool:
        return True

    def check(self) -> CheckResult:
        return CheckResult(compliant=True, current="ok")

    def plan(self) -> list[Change]:
        return []

    def apply(self, changes: list[Change]) -> None:
        pass


def test_sort_step_classes_ordering() -> None:
    # When passed StepB before StepA, StepA should be ordered first
    ordered = sort_step_classes([StepB, StepA])
    assert [cls.name for cls in ordered] == ["step_a", "step_b"]


def test_sort_step_classes_cycle_detected() -> None:
    with pytest.raises(DependencyCycleError):
        sort_step_classes([CycleA, CycleB])


def test_sort_step_classes_missing_dependency() -> None:
    with pytest.raises(MissingDependencyError):
        sort_step_classes([MissingDepStep])


def test_planner_filtering_and_plan() -> None:
    prof = Profile(version=1)
    runner = FakeRunner()
    fs = FakeFileOps()

    planner = Planner(prof, runner, fs, registry=[StepA, StepB, StepC])

    # StepC is disabled, so only StepA and StepB should be in ordered steps
    ordered_steps = planner.get_ordered_steps()
    assert len(ordered_steps) == 2
    assert ordered_steps[0].name == "step_a"
    assert ordered_steps[1].name == "step_b"

    report = planner.plan()
    assert len(report.items) == 2
    # StepA is compliant
    assert report.items[0].check_result.compliant is True
    assert report.items[0].changes == []
    # StepB has 1 change
    assert report.items[1].check_result.compliant is False
    assert len(report.items[1].changes) == 1

    assert report.total_changes == 1
    assert report.total_compliant == 1
    assert report.total_high_risk == 0


def test_planner_default_registry() -> None:
    prof = Profile(version=1, hostname="web-01")
    runner = FakeRunner(
        responses={
            ("hostnamectl", "--static"): "web-01\n",
        }
    )
    fs = FakeFileOps()
    planner = Planner(prof, runner, fs)
    steps = planner.get_ordered_steps()
    assert len(steps) == 1
    assert steps[0].name == "hostname"
