"""Unit test untuk UserStep (Tahap 2.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hostkeeper.engine.step import Change
from hostkeeper.profile import Profile
from hostkeeper.steps.user import UserStep
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


def test_user_step_disabled_when_no_admin_user() -> None:
    step = UserStep(Profile(), FakeRunner(), FakeFileOps())
    assert step.enabled() is False


def test_user_step_plan_when_user_not_exists() -> None:
    profile = Profile(admin_user="deploy", admin_sudo_nopasswd=True)
    runner = FakeRunner()
    runner.register(["id", "deploy"], "", returncode=1, stderr="no such user")
    fs = FakeFileOps()
    step = UserStep(profile, runner, fs)
    assert step.enabled() is True

    chk = step.check()
    assert chk.compliant is False

    changes = step.plan()
    assert any(c.action == "create" and c.target == "user:deploy" for c in changes)
    assert any(
        c.action == "write" and "90-hostkeeper-deploy" in c.target for c in changes
    )


def test_user_step_apply_creates_user_and_validates_sudoers() -> None:
    profile = Profile(admin_user="deploy", admin_sudo_nopasswd=True)
    runner = FakeRunner(
        {
            ("useradd", "-m", "-s", "/bin/bash", "deploy"): "",
            ("id", "-Gn", "deploy"): "deploy sudo\n",
            ("visudo", "-cf", "/tmp/.visudo_test.tmp"): "",  # visudo check passed
        }
    )
    runner.register(["id", "deploy"], "", returncode=1, stderr="no such user")
    fs = FakeFileOps()
    step = UserStep(profile, runner, fs)
    step._visudo_tmp_file = Path("/tmp/.visudo_test.tmp")

    changes = [
        Change(
            step="user",
            action="create",
            target="user:deploy",
            before=None,
            after="deploy",
        ),
        Change(
            step="user",
            action="write",
            target="/etc/sudoers.d/90-hostkeeper-deploy",
            before=None,
            after="deploy ALL=(ALL:ALL) NOPASSWD:ALL\n",
        ),
    ]
    step.apply(changes)

    # Pastikan useradd dipanggil
    assert any(
        c.argv == ("useradd", "-m", "-s", "/bin/bash", "deploy") for c in runner.calls
    )
    # Pastikan visudo dipanggil sebelum menyentuh file tujuan
    assert any("visudo" in c.argv for c in runner.calls)
    # File sudoers ditulis dengan mode 0440
    sudoers_path = Path("/etc/sudoers.d/90-hostkeeper-deploy")
    assert fs.read_text(sudoers_path) == "deploy ALL=(ALL:ALL) NOPASSWD:ALL\n"
    assert fs.modes.get(sudoers_path) == 0o440


def test_user_step_invalid_sudoers_rejected_before_writing() -> None:
    profile = Profile(admin_user="deploy")
    runner = FakeRunner()
    runner.register(
        ["visudo", "-cf", "/tmp/.visudo_test.tmp"],
        "",
        returncode=1,
        stderr="syntax error in sudoers",
    )
    fs = FakeFileOps()
    step = UserStep(profile, runner, fs)
    step._visudo_tmp_file = Path("/tmp/.visudo_test.tmp")

    changes = [
        Change(
            step="user",
            action="write",
            target="/etc/sudoers.d/90-hostkeeper-deploy",
            before=None,
            after="INVALID SYNTAX\n",
        )
    ]
    with pytest.raises(RuntimeError, match="visudo"):
        step.apply(changes)

    # File sudoers asli tidak boleh dibuat
    assert fs.read_text(Path("/etc/sudoers.d/90-hostkeeper-deploy")) is None


def test_user_step_undo_removes_sudoers_but_keeps_user() -> None:
    profile = Profile(admin_user="deploy")
    fs = FakeFileOps(
        {
            Path("/etc/sudoers.d/90-hostkeeper-deploy"): "deploy ALL=(ALL:ALL) ALL\n",
        }
    )
    runner = FakeRunner()
    step = UserStep(profile, runner, fs)

    changes = [
        Change(
            step="user",
            action="create",
            target="user:deploy",
            before=None,
            after="deploy",
        ),
        Change(
            step="user",
            action="write",
            target="/etc/sudoers.d/90-hostkeeper-deploy",
            before=None,
            after="deploy ALL=(ALL:ALL) ALL\n",
        ),
    ]
    step.undo(changes)

    # Sudoers dihapus
    assert fs.read_text(Path("/etc/sudoers.d/90-hostkeeper-deploy")) is None
    # Useradd/del TIDAK dipanggil saat undo
    assert not any("userdel" in c.argv for c in runner.calls)
