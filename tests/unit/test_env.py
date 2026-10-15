"""Unit test untuk deteksi lingkungan (env.py)."""

from __future__ import annotations

from pathlib import Path

from hostkeeper.env import EnvInfo, _parse_os_release, detect_env


def test_parse_os_release_custom(tmp_path: Path) -> None:
    os_rel = tmp_path / "os-release"
    os_rel.write_text(
        'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n'
        'NAME="Debian GNU/Linux"\n'
        'VERSION_ID="12"\n'
        'VERSION="12 (bookworm)"\n'
        "ID=debian\n",
        encoding="utf-8",
    )
    name, os_id, version = _parse_os_release(os_rel)
    assert name == "Debian GNU/Linux 12 (bookworm)"
    assert os_id == "debian"
    assert version == "12"


def test_parse_os_release_missing(tmp_path: Path) -> None:
    name, os_id, version = _parse_os_release(tmp_path / "nonexistent")
    assert name == "Linux"
    assert os_id == "linux"
    assert version == "unknown"


def test_env_info_supported() -> None:
    info = EnvInfo(
        os_name="Debian GNU/Linux 12",
        os_id="debian",
        os_version="12",
        python_version="3.11.2",
        is_root=False,
        systemd_active=True,
        profile_path=Path("/etc/hostkeeper/profile.yml"),
    )
    assert info.os_key == "debian:12"
    assert info.is_supported is True


def test_env_info_unsupported() -> None:
    info = EnvInfo(
        os_name="Arch Linux",
        os_id="arch",
        os_version="rolling",
        python_version="3.11.2",
        is_root=False,
        systemd_active=True,
        profile_path=Path("/etc/hostkeeper/profile.yml"),
    )
    assert info.os_key == "arch:rolling"
    assert info.is_supported is False


def test_detect_env_current() -> None:
    env = detect_env()
    assert isinstance(env.os_name, str)
    assert isinstance(env.is_root, bool)
    assert isinstance(env.systemd_active, bool)
