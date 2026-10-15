from __future__ import annotations

from typing import ClassVar

import pytest

from hostkeeper.engine.step import Change, CheckResult, Risk, Step
from hostkeeper.profile import Profile
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


class DummyStep(Step):
    name: ClassVar[str] = "dummy"
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


def test_risk_values() -> None:
    assert Risk.LOW == "rendah"
    assert Risk.MEDIUM == "sedang"
    assert Risk.HIGH == "tinggi"


def test_change_and_checkresult() -> None:
    c = Change(
        step="test",
        action="set",
        target="hostname",
        before="old",
        after="new",
    )
    assert c.step == "test"
    assert c.action == "set"
    assert c.target == "hostname"
    assert c.before == "old"
    assert c.after == "new"

    res = CheckResult(compliant=True, current="val", detail="info")
    assert res.compliant is True
    assert res.current == "val"
    assert res.detail == "info"


def test_step_defaults() -> None:
    prof = Profile(version=1)
    runner = FakeRunner()
    fs = FakeFileOps()

    step = DummyStep(prof, runner, fs)
    assert step.name == "dummy"
    assert step.risk == Risk.LOW
    assert step.requires == ()
    assert step.reversible is True

    # Default verify calls check
    verify_res = step.verify()
    assert verify_res.compliant is True
    assert verify_res.current == "ok"

    # Default undo does not raise
    step.undo([])


def test_step_abstract_cannot_instantiate() -> None:
    class IncompleteStep(Step):
        name: ClassVar[str] = "incomplete"
        risk: ClassVar[Risk] = Risk.LOW

    prof = Profile(version=1)
    runner = FakeRunner()
    fs = FakeFileOps()

    with pytest.raises(TypeError):
        IncompleteStep(prof, runner, fs)  # type: ignore[abstract]
