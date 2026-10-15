"""Unit test untuk PackagesStep (SPEC 5.3)."""

from __future__ import annotations

import pytest

from hostkeeper.engine.step import Change
from hostkeeper.profile import Profile
from hostkeeper.steps.packages import PackagesStep
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


def test_packages_step_enabled() -> None:
    fs = FakeFileOps()
    runner = FakeRunner()

    step_empty = PackagesStep(Profile(version=1), runner, fs)
    assert step_empty.enabled() is False

    step_with_pkgs = PackagesStep(
        Profile(version=1, packages=("htop", "vim")), runner, fs
    )
    assert step_with_pkgs.enabled() is True


def test_packages_step_check_all_installed() -> None:
    fs = FakeFileOps()
    runner = FakeRunner(
        responses={
            ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "curl", "vim"): (
                "curl install ok installed\nvim install ok installed\n"
            ),
        }
    )
    step = PackagesStep(Profile(version=1, packages=("curl", "vim")), runner, fs)
    chk = step.check()
    assert chk.compliant is True
    assert "curl, vim terpasang" in chk.current


def test_packages_step_check_missing_packages() -> None:
    fs = FakeFileOps()
    runner = FakeRunner(
        responses={
            ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "curl", "vim"): (
                "curl install ok installed\nvim deinstall ok config-files\n"
            ),
        }
    )
    step = PackagesStep(Profile(version=1, packages=("curl", "vim")), runner, fs)
    chk = step.check()
    assert chk.compliant is False
    assert "belum terpasang: vim" in chk.current


def test_packages_step_plan_candidate_none_raises() -> None:
    fs = FakeFileOps()
    runner = FakeRunner(
        responses={
            ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "unknown-pkg"): "",
            ("apt-cache", "policy", "unknown-pkg"): (
                "unknown-pkg:\n  Installed: (none)\n  Candidate: (none)\n"
            ),
        }
    )
    step = PackagesStep(Profile(version=1, packages=("unknown-pkg",)), runner, fs)
    with pytest.raises(RuntimeError) as exc_info:
        step.plan()
    assert "tidak tersedia di apt" in str(exc_info.value)


def test_packages_step_apply_success() -> None:
    fs = FakeFileOps()
    runner = FakeRunner(
        responses={
            ("apt-get", "update"): "",
            ("apt-get", "install", "-y", "--no-install-recommends", "htop", "vim"): "",
        }
    )
    step = PackagesStep(Profile(version=1, packages=("htop", "vim")), runner, fs)
    changes = [
        Change(
            step="packages",
            action="install",
            target="pkg:htop",
            before=None,
            after="htop",
        ),
        Change(
            step="packages",
            action="install",
            target="pkg:vim",
            before=None,
            after="vim",
        ),
    ]
    step.apply(changes)

    cmds = [cmd.argv for cmd in runner.calls]
    assert ("apt-get", "update") in cmds
    assert (
        "apt-get",
        "install",
        "-y",
        "--no-install-recommends",
        "htop",
        "vim",
    ) in cmds


def test_packages_step_apply_update_failed() -> None:
    fs = FakeFileOps()
    runner = FakeRunner()
    runner.register(["apt-get", "update"], "", returncode=100, stderr="E: Some error")
    step = PackagesStep(Profile(version=1, packages=("htop",)), runner, fs)
    changes = [
        Change(
            step="packages",
            action="install",
            target="pkg:htop",
            before=None,
            after="htop",
        ),
    ]

    with pytest.raises(RuntimeError) as exc_info:
        step.apply(changes)
    assert "apt-get update gagal" in str(exc_info.value)


def test_packages_step_verify() -> None:
    fs = FakeFileOps()
    runner = FakeRunner(
        responses={
            ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "htop"): (
                "htop install ok installed\n"
            ),
        }
    )
    step = PackagesStep(Profile(version=1, packages=("htop",)), runner, fs)
    chk = step.verify()
    assert chk.compliant is True
