from __future__ import annotations

from pathlib import Path

import pytest

from hostkeeper.engine.step import Change, Risk
from hostkeeper.profile import Profile
from hostkeeper.steps import REGISTRY, HostnameStep, TimezoneStep
from hostkeeper.system.fakes import FakeFileOps, FakeRunner
from hostkeeper.system.fileops import ReadOnlyFileOps
from hostkeeper.system.runner import ReadOnlyRunner


def test_registry_steps() -> None:
    names = [s.name for s in REGISTRY]
    assert "hostname" in names
    assert "timezone" in names


@pytest.mark.parametrize("step_cls", REGISTRY)
def test_generic_step_check_is_pure_and_readonly(step_cls: type) -> None:
    """Memastikan check() murni dan tidak pernah memanggil perintah mutating."""
    prof = Profile(
        version=1,
        hostname="target-host",
        timezone="Asia/Jakarta",
    )
    fake_runner = FakeRunner(
        responses={
            ("hostnamectl", "--static"): "current-host\n",
            ("timedatectl", "show", "-p", "Timezone", "--value"): "UTC\n",
        }
    )
    ro_runner = ReadOnlyRunner(fake_runner)
    ro_fs = ReadOnlyFileOps(FakeFileOps())

    step = step_cls(prof, ro_runner, ro_fs)
    if step.enabled():
        res = step.check()
        assert isinstance(res.compliant, bool)
        # plan() juga tidak boleh memanggil mutating
        changes = step.plan()
        assert isinstance(changes, list)


@pytest.mark.parametrize("step_cls", REGISTRY)
def test_generic_step_idempotency(step_cls: type) -> None:
    """Tes idempotency generik: apply lalu plan ulang harus menghasilkan 0 perubahan."""
    prof = Profile(
        version=1,
        hostname="web-01",
        timezone="Asia/Jakarta",
        packages=("htop",),
    )
    # Runner awal dengan kondisi drift
    runner = FakeRunner(
        responses={
            ("hostnamectl", "--static"): "web-old\n",
            ("hostnamectl", "set-hostname", "web-01"): "",
            ("timedatectl", "show", "-p", "Timezone", "--value"): "UTC\n",
            ("timedatectl", "set-timezone", "Asia/Jakarta"): "",
            ("getent", "hosts", "web-01"): "127.0.0.1 web-01\n",
            ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "htop"): (
                "htop deinstall ok config-files\n"
            ),
            ("apt-cache", "policy", "htop"): "htop:\n  Candidate: 3.2.2\n",
            ("apt-get", "update"): "",
            ("apt-get", "install", "-y", "--no-install-recommends", "htop"): "",
        }
    )
    fs = FakeFileOps()
    step = step_cls(prof, runner, fs)
    assert step.enabled()

    # Periksa drift awal
    chk1 = step.check()
    assert chk1.compliant is False
    changes1 = step.plan()
    assert len(changes1) > 0

    # Terapkan perubahan
    step.apply(changes1)

    # Simulasikan kondisi sistem sudah berubah sesuai target
    if step.name == "hostname":
        runner.register(["hostnamectl", "--static"], "web-01\n")
    elif step.name == "timezone":
        runner.register(
            ["timedatectl", "show", "-p", "Timezone", "--value"],
            "Asia/Jakarta\n",
        )
    elif step.name == "packages":
        runner.register(
            ["dpkg-query", "-W", "-f=${Package} ${Status}\\n", "htop"],
            "htop install ok installed\n",
        )

    # Periksa ulang (check dan plan kedua)
    chk2 = step.check()
    assert chk2.compliant is True
    changes2 = step.plan()
    assert changes2 == []  # 0 perubahan di kali kedua!


def test_hostname_step_full_lifecycle() -> None:
    prof = Profile(version=1, hostname="web-01")
    runner = FakeRunner(
        responses={
            ("hostnamectl", "--static"): "web-old\n",
            ("hostnamectl", "set-hostname", "web-01"): "",
            ("hostnamectl", "set-hostname", "web-old"): "",
            ("getent", "hosts", "web-01"): "127.0.1.1 web-01\n",
        }
    )
    fs = FakeFileOps()

    step = HostnameStep(prof, runner, fs)
    assert step.name == "hostname"
    assert step.risk == Risk.LOW
    assert step.requires == ()
    assert step.reversible is True
    assert step.enabled() is True

    # Check drift
    chk = step.check()
    assert chk.compliant is False
    assert chk.current == "web-old"

    # Plan
    changes = step.plan()
    assert len(changes) == 1
    assert changes[0] == Change(
        step="hostname",
        action="set",
        target="hostname",
        before="web-old",
        after="web-01",
    )

    # Apply
    step.apply(changes)
    assert runner.calls[-1].argv == ("hostnamectl", "set-hostname", "web-01")
    assert runner.calls[-1].mutates is True

    # Verify
    runner.register(["hostnamectl", "--static"], "web-01\n")
    verify_res = step.verify()
    assert verify_res.compliant is True
    assert verify_res.current == "web-01"

    # Undo
    step.undo(changes)
    assert runner.calls[-1].argv == ("hostnamectl", "set-hostname", "web-old")
    assert runner.calls[-1].mutates is True


def test_hostname_step_disabled() -> None:
    prof = Profile(version=1, hostname=None)
    runner = FakeRunner()
    fs = FakeFileOps()
    step = HostnameStep(prof, runner, fs)
    assert step.enabled() is False


def test_hostname_step_verify_warnings() -> None:
    prof = Profile(version=1, hostname="web-01")
    runner = FakeRunner(
        responses={
            ("hostnamectl", "--static"): "web-01\n",
        }
    )
    # getent gagal (returncode 2)
    runner.register(["getent", "hosts", "web-01"], "", returncode=2)

    # FileOps dengan /etc/cloud/cloud.cfg tanpa preserve_hostname: true
    fs = FakeFileOps(
        files={
            Path("/etc/cloud/cloud.cfg"): "manage_etc_hosts: true\n",
        }
    )

    step = HostnameStep(prof, runner, fs)
    v_res = step.verify()
    assert v_res.compliant is True
    assert "getent hosts gagal" in v_res.detail
    assert "preserve_hostname" in v_res.detail


def test_timezone_step_full_lifecycle() -> None:
    prof = Profile(version=1, timezone="Asia/Jakarta")
    runner = FakeRunner(
        responses={
            ("timedatectl", "show", "-p", "Timezone", "--value"): "UTC\n",
            ("timedatectl", "set-timezone", "Asia/Jakarta"): "",
            ("timedatectl", "set-timezone", "UTC"): "",
        }
    )
    fs = FakeFileOps()

    step = TimezoneStep(prof, runner, fs)
    assert step.name == "timezone"
    assert step.risk == Risk.LOW
    assert step.requires == ()
    assert step.reversible is True
    assert step.enabled() is True

    # Check drift
    chk = step.check()
    assert chk.compliant is False
    assert chk.current == "UTC"

    # Plan
    changes = step.plan()
    assert len(changes) == 1
    assert changes[0] == Change(
        step="timezone",
        action="set",
        target="timezone",
        before="UTC",
        after="Asia/Jakarta",
    )

    # Apply
    step.apply(changes)
    assert runner.calls[-1].argv == ("timedatectl", "set-timezone", "Asia/Jakarta")
    assert runner.calls[-1].mutates is True

    # Verify
    runner.register(
        ["timedatectl", "show", "-p", "Timezone", "--value"],
        "Asia/Jakarta\n",
    )
    verify_res = step.verify()
    assert verify_res.compliant is True
    assert verify_res.current == "Asia/Jakarta"

    # Undo
    step.undo(changes)
    assert runner.calls[-1].argv == ("timedatectl", "set-timezone", "UTC")
    assert runner.calls[-1].mutates is True


def test_timezone_step_disabled() -> None:
    prof = Profile(version=1, timezone=None)
    runner = FakeRunner()
    fs = FakeFileOps()
    step = TimezoneStep(prof, runner, fs)
    assert step.enabled() is False


def test_hostname_step_apply_failure() -> None:
    prof = Profile(version=1, hostname="web-01")
    runner = FakeRunner()
    runner.register(
        ["hostnamectl", "set-hostname", "web-01"],
        "",
        returncode=1,
        stderr="Failed to set hostname",
    )
    fs = FakeFileOps()
    step = HostnameStep(prof, runner, fs)
    with pytest.raises(RuntimeError, match="hostnamectl set-hostname gagal"):
        step.apply(
            [
                Change(
                    step="hostname",
                    action="set",
                    target="hostname",
                    before="old",
                    after="web-01",
                )
            ]
        )


def test_timezone_step_apply_failure() -> None:
    prof = Profile(version=1, timezone="Asia/Jakarta")
    runner = FakeRunner()
    runner.register(
        ["timedatectl", "set-timezone", "Asia/Jakarta"],
        "",
        returncode=1,
        stderr="Failed to set timezone",
    )
    fs = FakeFileOps()
    step = TimezoneStep(prof, runner, fs)
    with pytest.raises(RuntimeError, match="timedatectl set-timezone gagal"):
        step.apply(
            [
                Change(
                    step="timezone",
                    action="set",
                    target="timezone",
                    before="UTC",
                    after="Asia/Jakarta",
                )
            ]
        )


def test_hostname_step_apply_none_noop() -> None:
    prof = Profile(version=1, hostname=None)
    runner = FakeRunner()
    fs = FakeFileOps()
    step = HostnameStep(prof, runner, fs)
    step.apply([])
    assert len(runner.calls) == 0


def test_timezone_step_apply_none_noop() -> None:
    prof = Profile(version=1, timezone=None)
    runner = FakeRunner()
    fs = FakeFileOps()
    step = TimezoneStep(prof, runner, fs)
    step.apply([])
    assert len(runner.calls) == 0
