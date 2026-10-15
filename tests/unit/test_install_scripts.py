"""Unit test untuk skrip install.sh, uninstall.sh, launcher, dan contoh profil."""

from __future__ import annotations

import subprocess
from pathlib import Path

from hostkeeper.profile import load_profile

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_example_profile_yaml_validity() -> None:
    example_path = REPO_ROOT / "docs" / "example-profile.yml"
    assert example_path.is_file()
    prof = load_profile(example_path)
    assert prof.version == 1
    assert prof.hostname == "web-01"
    assert prof.timezone == "Asia/Jakarta"
    assert "curl" in prof.packages
    assert "htop" in prof.packages
    assert "vim" in prof.packages


def test_test_data_example_profile_validity() -> None:
    test_data_path = REPO_ROOT / "tests" / "data" / "profile.example.yml"
    assert test_data_path.is_file()
    prof = load_profile(test_data_path)
    assert prof.version == 1
    assert prof.hostname == "web-01"
    assert prof.timezone == "Asia/Jakarta"
    assert len(prof.packages) == 3


def test_hostkeeper_launcher_exists_and_executable() -> None:
    launcher = REPO_ROOT / "packaging" / "hostkeeper.launcher"
    assert launcher.is_file()
    content = launcher.read_text(encoding="utf-8")
    assert "PYTHONPATH=" in content
    assert "exec python3 -m hostkeeper" in content


def test_install_script_dry_run() -> None:
    script = REPO_ROOT / "install.sh"
    res = subprocess.run(
        [str(script), "--dry-run", "--prefix", "/tmp/nonexistent-prefix"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "hostkeeper 0.1.0 terpasang." in res.stdout
    assert "[dry-run]" in res.stdout
    # Tidak boleh membuat direktori tersebut saat dry-run
    assert not Path("/tmp/nonexistent-prefix").exists()


def test_install_script_unknown_option_exits_2() -> None:
    script = REPO_ROOT / "install.sh"
    res = subprocess.run(
        [str(script), "--bad-flag"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 2
    assert "ERROR: Opsi tidak dikenal" in res.stderr


def test_uninstall_script_idempotent_when_not_installed() -> None:
    script = REPO_ROOT / "uninstall.sh"
    res = subprocess.run(
        [str(script), "--prefix", "/tmp/nonexistent-prefix", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "tidak terpasang" in res.stdout
