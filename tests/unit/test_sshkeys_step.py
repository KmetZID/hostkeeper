"""Unit test untuk SshKeysStep (Tahap 2.2)."""

from __future__ import annotations

from pathlib import Path

from hostkeeper.engine.step import Change
from hostkeeper.profile import Profile
from hostkeeper.steps.sshkeys import SshKeysStep
from hostkeeper.system.fakes import FakeFileOps, FakeRunner

TEST_KEY_1 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleValidKey1234567890 key1@host"
TEST_KEY_2 = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC0 valid-rsa-key key2@host"
OLD_USER_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOldUserKeyNotManagedByHostkeeper"


def test_sshkeys_step_disabled() -> None:
    # Tanpa admin_user
    step = SshKeysStep(
        Profile(ssh_authorized_keys=(TEST_KEY_1,)),
        FakeRunner(),
        FakeFileOps(),
    )
    assert step.enabled() is False

    # Tanpa ssh_authorized_keys
    step2 = SshKeysStep(Profile(admin_user="deploy"), FakeRunner(), FakeFileOps())
    assert step2.enabled() is False


def test_sshkeys_step_plan() -> None:
    profile = Profile(
        admin_user="deploy",
        ssh_authorized_keys=(TEST_KEY_1,),
    )
    runner = FakeRunner(
        {
            (
                "getent",
                "passwd",
                "deploy",
            ): "deploy:x:1001:1001::/home/deploy:/bin/bash\n",
        }
    )
    fs = FakeFileOps()
    step = SshKeysStep(profile, runner, fs)
    assert step.enabled() is True

    chk = step.check()
    assert chk.compliant is False

    changes = step.plan()
    assert len(changes) == 1
    assert changes[0].action == "write"
    assert "/home/deploy/.ssh/authorized_keys" in changes[0].target


def test_sshkeys_step_apply_preserves_old_user_keys() -> None:
    profile = Profile(
        admin_user="deploy",
        ssh_authorized_keys=(TEST_KEY_1,),
    )
    auth_file = Path("/home/deploy/.ssh/authorized_keys")
    fs = FakeFileOps(
        {
            auth_file: f"{OLD_USER_KEY}\n",
        }
    )
    runner = FakeRunner(
        {
            (
                "getent",
                "passwd",
                "deploy",
            ): "deploy:x:1001:1001::/home/deploy:/bin/bash\n",
            (
                "install",
                "-d",
                "-m",
                "700",
                "-o",
                "deploy",
                "-g",
                "deploy",
                "/home/deploy/.ssh",
            ): "",
        }
    )
    step = SshKeysStep(profile, runner, fs)

    changes = step.plan()
    assert len(changes) == 1
    step.apply(changes)

    new_content = fs.read_text(auth_file)
    assert new_content is not None
    # Kunci lama pengguna TIDAK hilang
    assert OLD_USER_KEY in new_content
    # Kunci hostkeeper ada di dalam blok
    assert "# BEGIN hostkeeper" in new_content
    assert TEST_KEY_1 in new_content
    assert "# END hostkeeper" in new_content
    assert fs.modes.get(auth_file) == 0o600


def test_sshkeys_step_undo_removes_only_hostkeeper_block() -> None:
    profile = Profile(
        admin_user="deploy",
        ssh_authorized_keys=(TEST_KEY_1,),
    )
    auth_file = Path("/home/deploy/.ssh/authorized_keys")
    content_with_block = (
        f"{OLD_USER_KEY}\n# BEGIN hostkeeper\n{TEST_KEY_1}\n# END hostkeeper\n"
    )
    fs = FakeFileOps({auth_file: content_with_block})
    runner = FakeRunner(
        {
            (
                "getent",
                "passwd",
                "deploy",
            ): "deploy:x:1001:1001::/home/deploy:/bin/bash\n",
        }
    )
    step = SshKeysStep(profile, runner, fs)

    changes = [
        Change(
            step="sshkeys",
            action="write",
            target=str(auth_file),
            before=None,
            after=TEST_KEY_1,
        )
    ]
    step.undo(changes)

    new_content = fs.read_text(auth_file)
    assert new_content is not None
    # Blok hostkeeper dihapus
    assert "# BEGIN hostkeeper" not in new_content
    assert TEST_KEY_1 not in new_content
    # Kunci lama tetap bertahan utuh
    assert OLD_USER_KEY in new_content
