"""Profil hostkeeper: pemuatan, validasi skema v1, dan representasi data."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from hostkeeper import messages

KNOWN_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "hostname",
        "timezone",
        "packages",
        "admin_user",
        "admin_sudo_nopasswd",
        "ssh_authorized_keys",
        "ssh",
        "firewall",
        "unattended_upgrades",
    }
)

PACKAGE_NAME_REGEX: re.Pattern[str] = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
HOSTNAME_LABEL_REGEX: re.Pattern[str] = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


class ProfileValidationError(Exception):
    """Kesalahan saat validasi konfigurasi profil."""


@dataclass(frozen=True)
class Profile:
    """Representasi profil yang sudah divalidasi."""

    version: int = 1
    hostname: str | None = None
    timezone: str | None = None
    packages: tuple[str, ...] = ()
    admin_user: str | None = None
    admin_sudo_nopasswd: bool = False
    ssh_authorized_keys: tuple[str, ...] = ()
    ssh: Mapping[str, Any] | None = None
    firewall: Mapping[str, Any] | None = None
    unattended_upgrades: bool | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)


def validate_hostname(hostname: str) -> None:
    """Validasi hostname sesuai RFC 1123."""
    if not isinstance(hostname, str) or not hostname or len(hostname) > 253:
        raise ProfileValidationError(
            messages.HOSTNAME_INVALID.format(hostname=hostname)
        )

    labels = hostname.split(".")
    for label in labels:
        if not (1 <= len(label) <= 63):
            raise ProfileValidationError(
                messages.HOSTNAME_INVALID.format(hostname=hostname)
            )
        if not HOSTNAME_LABEL_REGEX.match(label):
            raise ProfileValidationError(
                messages.HOSTNAME_INVALID.format(hostname=hostname)
            )


def validate_timezone(
    tz: str,
    zoneinfo_dir: Path | str = Path("/usr/share/zoneinfo"),
) -> None:
    """Validasi timezone terhadap direktori zoneinfo."""
    zoneinfo_path = Path(zoneinfo_dir)
    if not isinstance(tz, str) or not tz:
        raise ProfileValidationError(
            messages.TIMEZONE_INVALID.format(timezone=tz, zoneinfo_dir=zoneinfo_path)
        )

    # Larang path traversal dan path absolut
    if ".." in tz or ".." in tz.split("/") or tz.startswith(("/", "\\")):
        raise ProfileValidationError(
            messages.TIMEZONE_INVALID.format(timezone=tz, zoneinfo_dir=zoneinfo_path)
        )

    target = zoneinfo_path / tz
    # Periksa traversal via resolve jika zoneinfo_path ada
    if zoneinfo_path.exists():
        try:
            target.resolve().relative_to(zoneinfo_path.resolve())
        except ValueError:
            raise ProfileValidationError(
                messages.TIMEZONE_INVALID.format(
                    timezone=tz, zoneinfo_dir=zoneinfo_path
                )
            )

    if not target.is_file():
        raise ProfileValidationError(
            messages.TIMEZONE_INVALID.format(timezone=tz, zoneinfo_dir=zoneinfo_path)
        )


def validate_packages(packages: Any) -> tuple[str, ...]:
    """Validasi daftar nama paket."""
    if not isinstance(packages, (list, tuple)):
        raise ProfileValidationError(messages.PACKAGES_INVALID_TYPE)

    if len(packages) > 100:
        raise ProfileValidationError(
            messages.PACKAGES_TOO_MANY.format(count=len(packages))
        )

    validated: list[str] = []
    for pkg in packages:
        if not isinstance(pkg, str) or not PACKAGE_NAME_REGEX.match(pkg):
            raise ProfileValidationError(
                messages.PACKAGE_INVALID_NAME.format(package=pkg)
            )
        validated.append(pkg)

    return tuple(validated)


def parse_profile_dict(
    data: Any,
    zoneinfo_dir: Path | str = Path("/usr/share/zoneinfo"),
) -> Profile:
    """Validasi dan parsing kamus konfigurasi profil."""
    if not isinstance(data, dict):
        raise ProfileValidationError(messages.PROFILE_NOT_A_MAPPING)

    # Validasi versi
    version = data.get("version")
    if version != 1:
        raise ProfileValidationError(
            messages.PROFILE_INVALID_VERSION.format(version=version)
        )

    # Validasi kunci tak dikenal
    unknown = sorted(set(data.keys()) - KNOWN_KEYS)
    if unknown:
        raise ProfileValidationError(
            messages.PROFILE_UNKNOWN_KEYS.format(keys=", ".join(unknown))
        )

    hostname: str | None = None
    if "hostname" in data:
        raw_hostname = data["hostname"]
        validate_hostname(raw_hostname)
        hostname = raw_hostname

    timezone: str | None = None
    if "timezone" in data:
        raw_timezone = data["timezone"]
        validate_timezone(raw_timezone, zoneinfo_dir=zoneinfo_dir)
        timezone = raw_timezone

    packages: tuple[str, ...] = ()
    if "packages" in data:
        packages = validate_packages(data["packages"])

    admin_user = data.get("admin_user")
    admin_sudo_nopasswd = bool(data.get("admin_sudo_nopasswd", False))
    ssh_auth_keys_raw = data.get("ssh_authorized_keys")
    ssh_auth_keys = (
        tuple(ssh_auth_keys_raw) if isinstance(ssh_auth_keys_raw, (list, tuple)) else ()
    )
    ssh = data.get("ssh")
    firewall = data.get("firewall")
    unattended_upgrades = data.get("unattended_upgrades")

    return Profile(
        version=version,
        hostname=hostname,
        timezone=timezone,
        packages=packages,
        admin_user=admin_user,
        admin_sudo_nopasswd=admin_sudo_nopasswd,
        ssh_authorized_keys=ssh_auth_keys,
        ssh=ssh,
        firewall=firewall,
        unattended_upgrades=unattended_upgrades,
        raw=data,
    )


def load_profile(
    path: Path | str,
    zoneinfo_dir: Path | str = Path("/usr/share/zoneinfo"),
) -> Profile:
    """Membaca file YAML profil dan memvalidasinya."""
    profile_path = Path(path)
    if not profile_path.is_file():
        raise ProfileValidationError(
            messages.PROFILE_FILE_NOT_FOUND.format(path=profile_path)
        )

    try:
        content = profile_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ProfileValidationError(
            messages.PROFILE_INVALID_YAML.format(detail=str(exc))
        ) from exc

    return parse_profile_dict(data, zoneinfo_dir=zoneinfo_dir)
