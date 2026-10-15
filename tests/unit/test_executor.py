"""Unit test untuk Executor (kebijakan fail-fast dan undo mundur)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import ClassVar

from hostkeeper.engine.audit import AuditWriter
from hostkeeper.engine.executor import Executor, make_run_id
from hostkeeper.engine.journal import JournalWriter
from hostkeeper.engine.step import Change, CheckResult, Risk, Step
from hostkeeper.profile import Profile
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


class MockStep(Step):
    """Step tiruan untuk menguji kebijakan Executor."""

    name: ClassVar[str] = "mock"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ()
    reversible: ClassVar[bool] = True

    def __init__(
        self,
        name: str,
        reversible: bool = True,
        fail_apply: bool = False,
        fail_verify: bool = False,
    ) -> None:
        super().__init__(Profile(version=1), FakeRunner(), FakeFileOps())
        self.name = name
        self.reversible = reversible
        self.fail_apply = fail_apply
        self.fail_verify = fail_verify
        self.applied_changes: list[Change] = []
        self.undone_changes: list[Change] = []

    def enabled(self) -> bool:
        return True

    def check(self) -> CheckResult:
        return CheckResult(compliant=False, current="drift")

    def plan(self) -> list[Change]:
        return [
            Change(
                step=self.name,
                action="set",
                target="item",
                before="old",
                after="new",
            )
        ]

    def apply(self, changes: list[Change]) -> None:
        if self.fail_apply:
            raise RuntimeError(f"Gagal apply {self.name}")
        self.applied_changes.extend(changes)

    def undo(self, changes: list[Change]) -> None:
        self.undone_changes.extend(changes)

    def verify(self) -> CheckResult:
        if self.fail_verify:
            return CheckResult(compliant=False, current="verify failed")
        return CheckResult(compliant=True, current="ok")


def test_executor_successful_run(tmp_path: Path) -> None:
    audit = AuditWriter(tmp_path / "audit.jsonl", run_id="run-1")
    journal = JournalWriter("run-1", "hash1", journal_dir=tmp_path / "journal")
    out = io.StringIO()

    step1 = MockStep("step1", reversible=True)
    step2 = MockStep("step2", reversible=False)

    ch1 = step1.plan()
    ch2 = step2.plan()

    executor = Executor(
        steps_with_changes=[(step1, ch1), (step2, ch2)],
        run_id="run-1",
        profile_path=tmp_path / "profile.yml",
        audit=audit,
        journal=journal,
        out=out,
        yes=True,
    )

    report = executor.run()
    assert report.n_applied == 2
    assert report.n_failed == 0
    assert len(step1.applied_changes) == 1
    assert len(step2.applied_changes) == 1
    assert len(step1.undone_changes) == 0
    assert report.journal_path is not None
    assert report.journal_path.exists()


def test_executor_confirmation_aborted(tmp_path: Path) -> None:
    audit = AuditWriter(tmp_path / "audit.jsonl", run_id="run-2")
    journal = JournalWriter("run-2", "hash2", journal_dir=tmp_path / "journal")
    out = io.StringIO()

    step = MockStep("step1")
    ch = step.plan()

    executor = Executor(
        steps_with_changes=[(step, ch)],
        run_id="run-2",
        profile_path=tmp_path / "profile.yml",
        audit=audit,
        journal=journal,
        out=out,
        yes=False,
        confirm_fn=lambda prompt: "n",
    )

    report = executor.run()
    assert report.aborted is True
    assert report.n_applied == 0
    assert len(step.applied_changes) == 0
    assert "Apply dibatalkan" in out.getvalue()


def test_executor_dry_run_mode(tmp_path: Path) -> None:
    audit = AuditWriter(tmp_path / "audit.jsonl", run_id="run-3")
    journal = JournalWriter("run-3", "hash3", journal_dir=tmp_path / "journal")
    out = io.StringIO()

    step = MockStep("step1")
    ch = step.plan()

    executor = Executor(
        steps_with_changes=[(step, ch)],
        run_id="run-3",
        profile_path=tmp_path / "profile.yml",
        audit=audit,
        journal=journal,
        out=out,
        dry_run=True,
    )

    report = executor.run()
    assert report.n_applied == 0
    assert len(step.applied_changes) == 0
    assert "[dry-run]" in out.getvalue()


def test_executor_fail_fast_and_undo_reversible_only(tmp_path: Path) -> None:
    audit = AuditWriter(tmp_path / "audit.jsonl", run_id="run-4")
    journal = JournalWriter("run-4", "hash4", journal_dir=tmp_path / "journal")
    out = io.StringIO()

    step1 = MockStep("step1", reversible=True)
    step2 = MockStep("step2", reversible=False)
    step3 = MockStep("step3", reversible=True, fail_apply=True)
    step4 = MockStep("step4", reversible=True)

    ch1 = step1.plan()
    ch2 = step2.plan()
    ch3 = step3.plan()
    ch4 = step4.plan()

    executor = Executor(
        steps_with_changes=[
            (step1, ch1),
            (step2, ch2),
            (step3, ch3),
            (step4, ch4),
        ],
        run_id="run-4",
        profile_path=tmp_path / "profile.yml",
        audit=audit,
        journal=journal,
        out=out,
        yes=True,
    )

    report = executor.run()
    assert report.n_failed == 1

    # step1 di-apply lalu di-undo karena reversible
    assert len(step1.applied_changes) == 1
    assert len(step1.undone_changes) == 1

    # step2 di-apply tetapi TIDAK di-undo karena NOT reversible
    assert len(step2.applied_changes) == 1
    assert len(step2.undone_changes) == 0

    # step3 gagal saat apply
    assert len(step3.applied_changes) == 0

    # step4 dilewati (skipped)
    assert len(step4.applied_changes) == 0

    output_str = out.getvalue()
    assert "Kegagalan: Step step3" in output_str
    assert "step1 dikembalikan" in output_str


def test_executor_verify_failure_triggers_undo(tmp_path: Path) -> None:
    audit = AuditWriter(tmp_path / "audit.jsonl", run_id="run-5")
    journal = JournalWriter("run-5", "hash5", journal_dir=tmp_path / "journal")
    out = io.StringIO()

    step1 = MockStep("step1", reversible=True)
    step2 = MockStep("step2", reversible=True, fail_verify=True)

    ch1 = step1.plan()
    ch2 = step2.plan()

    executor = Executor(
        steps_with_changes=[(step1, ch1), (step2, ch2)],
        run_id="run-5",
        profile_path=tmp_path / "profile.yml",
        audit=audit,
        journal=journal,
        out=out,
        yes=True,
    )

    report = executor.run()
    assert report.n_failed == 1
    # step1 harus di-undo
    assert len(step1.undone_changes) == 1


def test_make_run_id_format() -> None:
    run_id = make_run_id()
    assert "T" in run_id
    assert "Z-" in run_id
