"""Unit test untuk SafetyTimer (Tahap 2.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hostkeeper.engine.executor import Executor
from hostkeeper.engine.safety_timer import SafetyTimer
from hostkeeper.engine.step import Change, CheckResult, Risk, Step
from hostkeeper.profile import Profile
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


def test_safety_timer_start_and_stop() -> None:
    runner = FakeRunner(
        {
            (
                "systemd-run",
                "--on-active=90s",
                "--unit=hostkeeper-rollback-run-test",
                "hostkeeper",
                "rollback",
                "run-test",
                "--yes",
                "--reason",
                "timer",
            ): "",
            ("systemctl", "stop", "hostkeeper-rollback-run-test.timer"): "",
        }
    )
    printed: list[str] = []
    timer = SafetyTimer(
        runner=runner,
        run_id="run-test",
        timeout_seconds=90,
        print_fn=printed.append,
    )

    timer.start()
    assert any("Safety timer aktif" in p for p in printed)
    assert any("systemd-run" in c.argv for c in runner.calls)

    timer.stop()
    assert any("Safety timer dibatalkan" in p for p in printed)
    assert any("systemctl" in c.argv and "stop" in c.argv for c in runner.calls)


def test_safety_timer_start_failure_raises() -> None:
    runner = FakeRunner()
    runner.register(
        [
            "systemd-run",
            "--on-active=90s",
            "--unit=hostkeeper-rollback-run-fail",
            "hostkeeper",
            "rollback",
            "run-fail",
            "--yes",
            "--reason",
            "timer",
        ],
        "",
        returncode=1,
        stderr="Failed to connect to bus",
    )
    timer = SafetyTimer(runner=runner, run_id="run-fail", timeout_seconds=90)
    with pytest.raises(RuntimeError, match="Safety timer gagal"):
        timer.start()


def test_executor_integrates_safety_timer_for_high_risk_step(tmp_path: Path) -> None:
    calls_sequence: list[str] = []

    class HighRiskStep(Step):
        name = "mock_high"
        risk = Risk.HIGH
        requires = ()
        reversible = True

        def enabled(self) -> bool:
            return True

        def check(self) -> CheckResult:
            return CheckResult(compliant=False, current="drift")

        def plan(self) -> list[Change]:
            return [
                Change(
                    step=self.name,
                    action="set",
                    target="high",
                    before=None,
                    after="val",
                )
            ]

        def apply(self, changes: list[Change]) -> None:
            calls_sequence.append("apply")

        def verify(self) -> CheckResult:
            calls_sequence.append("verify")
            return CheckResult(compliant=True, current="ok")

        def undo(self, changes: list[Change]) -> None:
            pass

    runner = FakeRunner(
        {
            (
                "systemd-run",
                "--on-active=90s",
                "--unit=hostkeeper-rollback-run-hr",
                "hostkeeper",
                "rollback",
                "run-hr",
                "--yes",
                "--reason",
                "timer",
            ): "",
            ("systemctl", "stop", "hostkeeper-rollback-run-hr.timer"): "",
        }
    )

    from hostkeeper.engine.audit import AuditWriter
    from hostkeeper.engine.journal import JournalWriter

    audit = AuditWriter(path=tmp_path / "audit.jsonl", run_id="run-hr")
    journal = JournalWriter(
        run_id="run-hr", profile_sha256="", journal_dir=tmp_path / "journal"
    )

    step = HighRiskStep(Profile(), runner, FakeFileOps())
    executor = Executor(
        steps_with_changes=[(step, step.plan())],
        runner=runner,
        yes=True,
        run_id="run-hr",
        confirm_timeout=90,
        audit=audit,
        journal=journal,
    )

    report = executor.run()
    assert report.n_applied == 1

    # Periksa urutan: systemd-run -> apply -> verify -> systemctl stop
    op_names = []
    for c in runner.calls:
        if "systemd-run" in c.argv:
            op_names.append("start_timer")
        elif "systemctl" in c.argv and "stop" in c.argv:
            op_names.append("stop_timer")

    assert "start_timer" in op_names
    assert "apply" in calls_sequence
    assert "verify" in calls_sequence
    assert "stop_timer" in op_names


def test_executor_aborts_high_risk_step_if_timer_fails(tmp_path: Path) -> None:
    class HighRiskStep(Step):
        name = "mock_high_fail"
        risk = Risk.HIGH
        requires = ()
        reversible = True

        def enabled(self) -> bool:
            return True

        def check(self) -> CheckResult:
            return CheckResult(compliant=False, current="drift")

        def plan(self) -> list[Change]:
            return [
                Change(
                    step=self.name,
                    action="set",
                    target="high",
                    before=None,
                    after="val",
                )
            ]

        def apply(self, changes: list[Change]) -> None:
            raise AssertionError("Apply TIDAK boleh dijalankan jika timer gagal!")

        def verify(self) -> CheckResult:
            return CheckResult(compliant=True, current="ok")

        def undo(self, changes: list[Change]) -> None:
            pass

    runner = FakeRunner()
    runner.register(
        [
            "systemd-run",
            "--on-active=90s",
            "--unit=hostkeeper-rollback-run-err",
            "hostkeeper",
            "rollback",
            "run-err",
            "--yes",
            "--reason",
            "timer",
        ],
        "",
        returncode=1,
        stderr="systemd-run failed",
    )

    from hostkeeper.engine.audit import AuditWriter
    from hostkeeper.engine.journal import JournalWriter

    audit = AuditWriter(path=tmp_path / "audit.jsonl", run_id="run-err")
    journal = JournalWriter(
        run_id="run-err", profile_sha256="", journal_dir=tmp_path / "journal"
    )

    step = HighRiskStep(Profile(), runner, FakeFileOps())
    executor = Executor(
        steps_with_changes=[(step, step.plan())],
        runner=runner,
        yes=True,
        run_id="run-err",
        confirm_timeout=90,
        audit=audit,
        journal=journal,
    )

    report = executor.run()
    # Apply gagal dan step tidak dijalankan
    assert report.n_failed == 1
    assert not any(r.applied for r in report.results)
