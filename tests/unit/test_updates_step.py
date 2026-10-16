"""Unit test untuk UpdatesStep (Tahap 2.5)."""

from __future__ import annotations

from pathlib import Path

from hostkeeper.engine.step import Change, Risk
from hostkeeper.profile import Profile
from hostkeeper.steps.updates import UpdatesStep
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


def test_updates_step_metadata() -> None:
    step = UpdatesStep(Profile(), FakeRunner(), FakeFileOps())
    assert step.name == "updates"
    assert step.risk == Risk.LOW
    assert step.requires == ()
    assert step.reversible is True


def test_updates_step_disabled_when_none() -> None:
    step = UpdatesStep(Profile(), FakeRunner(), FakeFileOps())
    assert step.enabled() is False


def test_updates_step_plan_and_apply(tmp_path: Path) -> None:
    profile = Profile(unattended_upgrades=True)
    runner = FakeRunner(
        {
            ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "unattended-upgrades"): (
                "unattended-upgrades install ok installed\n"
            ),
        }
    )
    fs = FakeFileOps()
    step = UpdatesStep(profile, runner, fs)
    assert step.enabled() is True

    chk = step.check()
    assert chk.compliant is False

    changes = step.plan()
    assert len(changes) == 1
    assert changes[0].action == "write"
    assert "20auto-upgrades" in changes[0].target

    step.apply(changes)
    cfg_path = Path("/etc/apt/apt.conf.d/20auto-upgrades")
    content = fs.read_text(cfg_path)
    assert content is not None
    assert 'APT::Periodic::Update-Package-Lists "1";' in content
    assert 'APT::Periodic::Unattended-Upgrade "1";' in content


def test_updates_step_undo_removes_config() -> None:
    profile = Profile(unattended_upgrades=True)
    cfg_path = Path("/etc/apt/apt.conf.d/20auto-upgrades")
    fs = FakeFileOps({cfg_path: 'APT::Periodic::Update-Package-Lists "1";\n'})
    runner = FakeRunner()
    step = UpdatesStep(profile, runner, fs)

    changes = [
        Change(
            step="updates",
            action="write",
            target=str(cfg_path),
            before=None,
            after="content",
        )
    ]
    step.undo(changes)
    assert fs.read_text(cfg_path) is None
