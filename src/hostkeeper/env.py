"""Deteksi lingkungan: OS, root, systemd, versi Python."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_OS: frozenset[str] = frozenset(
    {
        "debian:12",
        "debian:13",
        "ubuntu:22.04",
        "ubuntu:24.04",
    }
)


@dataclass(frozen=True)
class EnvInfo:
    """Informasi lingkungan sistem saat hostkeeper dijalankan."""

    os_name: str  # misal 'Debian GNU/Linux 12 (bookworm)'
    os_id: str  # 'debian' atau 'ubuntu'
    os_version: str  # '12', '13', '22.04', '24.04'
    python_version: str  # '3.11.2'
    is_root: bool
    systemd_active: bool
    profile_path: Path

    @property
    def os_key(self) -> str:
        """Menghasilkan kunci OS untuk pengecekan dukungan (misal 'debian:12')."""
        return f"{self.os_id}:{self.os_version}"

    @property
    def is_supported(self) -> bool:
        """True jika OS ini didukung hostkeeper."""
        return self.os_key in SUPPORTED_OS


def _parse_os_release(path: Path = Path("/etc/os-release")) -> tuple[str, str, str]:
    """Membaca /etc/os-release dan mengembalikan (os_name, os_id, os_version_id)."""
    os_name = "Linux"
    os_id = "linux"
    os_version = "unknown"

    if not path.is_file():
        return os_name, os_id, os_version

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("PRETTY_NAME="):
            os_name = line.split("=", 1)[1].strip('"')
        elif line.startswith("ID="):
            os_id = line.split("=", 1)[1].strip('"').lower()
        elif line.startswith("VERSION_ID="):
            os_version = line.split("=", 1)[1].strip('"')

    return os_name, os_id, os_version


def detect_env(profile_path: Path | None = None) -> EnvInfo:
    """Mendeteksi informasi lingkungan sistem."""
    if profile_path is None:
        profile_path = Path("/etc/hostkeeper/profile.yml")

    os_name, os_id, os_version = _parse_os_release()
    python_version = platform.python_version()
    is_root = os.geteuid() == 0
    systemd_active = Path("/run/systemd/system").exists()

    return EnvInfo(
        os_name=os_name,
        os_id=os_id,
        os_version=os_version,
        python_version=python_version,
        is_root=is_root,
        systemd_active=systemd_active,
        profile_path=profile_path,
    )
