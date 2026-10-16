"""Unit test untuk SshdStep (Tahap 2.3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from hostkeeper.engine.step import Change, Risk
from hostkeeper.profile import Profile
from hostkeeper.steps.sshd import SshdStep
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


def test_sshd_step_metadata() -> None:
    step = SshdStep(Profile(), FakeRunner(), FakeFileOps())
    assert step.name == "sshd"
    assert step.risk == Risk.HIGH
    assert step.requires == ("user", "sshkeys")
    assert step.reversible is True


def test_sshd_step_disabled_when_no_ssh_config() -> None:
    step = SshdStep(Profile(), FakeRunner(), FakeFileOps())
    assert step.enabled() is False


def test_sshd_step_socket_active_rejects_non_22_port() -> None:
    profile = Profile(
        admin_user="deploy",
        ssh={"port": 2222, "password_auth": False},
    )
    runner = FakeRunner(
        {
            ("systemctl", "is-active", "ssh.socket"): "active\n",
        }
    )
    step = SshdStep(profile, runner, FakeFileOps())
    with pytest.raises(RuntimeError, match="ssh.socket aktif"):
        step.apply(
            [Change(step="sshd", action="write", target="sshd", before=None, after="")]
        )


def test_sshd_step_gate_failure_aborts_without_writing() -> None:
    profile = Profile(
        admin_user="deploy",
        ssh={"password_auth": False},
    )
    runner = FakeRunner(
        {
            ("systemctl", "is-active", "ssh.socket"): ("inactive\n", 3, "inactive"),
        }
    )
    runner.register(["systemctl", "is-active", "ssh.socket"], "", returncode=3)
    fs = FakeFileOps()
    # Mock confirm_fn mengembalikan "tidak"
    step = SshdStep(profile, runner, fs, confirm_fn=lambda _: "tidak")
    # Gerbang mekanisme login pura-pura lolos
    with patch.object(step, "_test_ssh_login_mechanism", return_value=True):
        with pytest.raises(RuntimeError, match="dibatalkan"):
            step.apply(
                [
                    Change(
                        step="sshd",
                        action="write",
                        target="sshd",
                        before=None,
                        after="",
                    )
                ]
            )

    # Drop-in TIDAK boleh ditulis
    drop_in = Path("/etc/ssh/sshd_config.d/00-hostkeeper.conf")
    assert fs.read_text(drop_in) is None


def test_sshd_step_sshd_t_failure_removes_dropin() -> None:
    profile = Profile(
        admin_user="deploy",
        ssh={"permit_root_login": "no"},
    )
    runner = FakeRunner(
        {
            ("systemctl", "is-active", "ssh.socket"): "inactive\n",
        }
    )
    runner.register(["systemctl", "is-active", "ssh.socket"], "", returncode=3)
    runner.register(["sshd", "-t"], "", returncode=1, stderr="Bad configuration option")
    fs = FakeFileOps()
    step = SshdStep(profile, runner, fs, bypass_human_gate=True)

    with patch.object(step, "_test_ssh_login_mechanism", return_value=True):
        with pytest.raises(RuntimeError, match="sshd -t gagal"):
            step.apply(
                [
                    Change(
                        step="sshd",
                        action="write",
                        target="sshd",
                        before=None,
                        after="",
                    )
                ]
            )

    # File drop-in harus dihapus jika sshd -t gagal
    drop_in = Path("/etc/ssh/sshd_config.d/00-hostkeeper.conf")
    assert fs.read_text(drop_in) is None


def test_sshd_step_temporary_key_always_cleaned_up() -> None:
    profile = Profile(admin_user="deploy", ssh={"password_auth": False})
    fs = FakeFileOps(
        {
            Path("/home/deploy/.ssh/authorized_keys"): "initial_key\n",
        }
    )
    runner = FakeRunner(
        {
            (
                "getent",
                "passwd",
                "deploy",
            ): "deploy:x:1001:1001::/home/deploy:/bin/bash\n",
            ("ssh-keygen", "-t", "ed25519", "-N", "", "-f", "/tmp/test_key"): "",
        }
    )
    # Pura-pura ssh gagal
    runner.register(
        ["ssh", "-o", "BatchMode=yes"], "", returncode=255, stderr="connection refused"
    )
    step = SshdStep(profile, runner, fs)

    # Uji _test_ssh_login_mechanism membersihkan kunci sementara dalam finally
    with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
        mock_dir = Path("/tmp/mock_ssh_test")
        mock_tmpdir.return_value.__enter__.return_value = str(mock_dir)
        # Jalankan tes mekanisme
        try:
            step._test_ssh_login_mechanism(user="deploy", port=22)
        except Exception:
            pass

    # Kunci di authorized_keys harus kembali ke isi semula tanpa meninggalkan sisa
    auth_content = fs.read_text(Path("/home/deploy/.ssh/authorized_keys"))
    assert auth_content is not None
    assert "mock_ssh_test" not in auth_content
    assert "# TEMP hostkeeper" not in auth_content
