"""Profil hostkeeper: pemuatan, validasi skema v1, dan representasi data."""

from __future__ import annotations

import base64
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
ADMIN_USER_REGEX: re.Pattern[str] = re.compile(r"^[a-z_][a-z0-9_-]*[$]?$")

SSH_KNOWN_KEYS: frozenset[str] = frozenset(
    {"port", "permit_root_login", "password_auth"}
)
VALID_PERMIT_ROOT: frozenset[str] = frozenset(
    {"yes", "no", "prohibit-password", "forced-commands-only"}
)
SSH_ALLOWED_KEY_TYPES: tuple[str, ...] = (
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
)

FIREWALL_KNOWN_KEYS: frozenset[str] = frozenset({"allow"})
FIREWALL_RULE_REGEX: re.Pattern[str] = re.compile(r"^([0-9]{1,5})/(tcp|udp)$")


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


def validate_admin_user(user: Any) -> str:
    """Validasi nama admin_user."""
    if not isinstance(user, str) or not user or len(user) > 32:
        raise ProfileValidationError(messages.ADMIN_USER_INVALID.format(user=user))
    if user == "root" or not ADMIN_USER_REGEX.match(user):
        raise ProfileValidationError(messages.ADMIN_USER_INVALID.format(user=user))
    return user


def validate_ssh_authorized_keys(keys: Any) -> tuple[str, ...]:
    """Validasi daftar kunci publik SSH."""
    if not isinstance(keys, (list, tuple)):
        raise ProfileValidationError(messages.SSH_KEYS_INVALID_TYPE)

    validated: list[str] = []
    for k in keys:
        if not isinstance(k, str) or not k.strip():
            raise ProfileValidationError(messages.SSH_KEY_INVALID.format(key=str(k)))
        parts = k.strip().split()
        if len(parts) < 2:
            raise ProfileValidationError(messages.SSH_KEY_INVALID.format(key=k))
        key_type, b64_blob = parts[0], parts[1]
        if key_type not in SSH_ALLOWED_KEY_TYPES:
            raise ProfileValidationError(messages.SSH_KEY_INVALID.format(key=k))
        if not re.match(r"^[A-Za-z0-9+/]+={0,2}$", b64_blob):
            raise ProfileValidationError(messages.SSH_KEY_INVALID.format(key=k))
        try:
            padded = b64_blob + "=" * ((4 - len(b64_blob) % 4) % 4)
            decoded = base64.b64decode(padded, validate=True)
            if not decoded:
                raise ProfileValidationError(messages.SSH_KEY_INVALID.format(key=k))
        except Exception:
            raise ProfileValidationError(messages.SSH_KEY_INVALID.format(key=k))
        validated.append(k.strip())

    return tuple(validated)


def validate_ssh(ssh_conf: Any) -> dict[str, Any]:
    """Validasi opsi konfigurasi SSH."""
    if not isinstance(ssh_conf, dict):
        raise ProfileValidationError(messages.SSH_CONFIG_INVALID_TYPE)

    unknown = sorted(set(ssh_conf.keys()) - SSH_KNOWN_KEYS)
    if unknown:
        raise ProfileValidationError(
            messages.SSH_CONFIG_UNKNOWN_KEYS.format(keys=", ".join(unknown))
        )

    validated: dict[str, Any] = {}
    if "port" in ssh_conf:
        port = ssh_conf["port"]
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not (1 <= port <= 65535)
        ):
            raise ProfileValidationError(messages.SSH_PORT_INVALID)
        validated["port"] = port

    if "permit_root_login" in ssh_conf:
        prl = ssh_conf["permit_root_login"]
        if isinstance(prl, bool):
            prl_val = "yes" if prl else "no"
        elif isinstance(prl, str):
            prl_val = prl.lower()
        else:
            raise ProfileValidationError(
                messages.SSH_PERMIT_ROOT_INVALID.format(val=prl)
            )
        if prl_val not in VALID_PERMIT_ROOT:
            raise ProfileValidationError(
                messages.SSH_PERMIT_ROOT_INVALID.format(val=prl)
            )
        validated["permit_root_login"] = prl_val

    if "password_auth" in ssh_conf:
        pwa = ssh_conf["password_auth"]
        if not isinstance(pwa, bool):
            raise ProfileValidationError(messages.SSH_PASSWORD_AUTH_INVALID)
        validated["password_auth"] = pwa

    return validated


def validate_firewall(fw_conf: Any) -> dict[str, Any]:
    """Validasi opsi konfigurasi firewall."""
    if not isinstance(fw_conf, dict):
        raise ProfileValidationError(messages.FIREWALL_CONFIG_INVALID_TYPE)

    unknown = sorted(set(fw_conf.keys()) - FIREWALL_KNOWN_KEYS)
    if unknown:
        raise ProfileValidationError(
            messages.FIREWALL_CONFIG_UNKNOWN_KEYS.format(keys=", ".join(unknown))
        )

    validated: dict[str, Any] = {}
    if "allow" in fw_conf:
        allow = fw_conf["allow"]
        if not isinstance(allow, (list, tuple)):
            raise ProfileValidationError(messages.FIREWALL_ALLOW_INVALID_TYPE)
        valid_rules: list[str] = []
        for rule in allow:
            if not isinstance(rule, str):
                raise ProfileValidationError(
                    messages.FIREWALL_RULE_INVALID.format(rule=str(rule))
                )
            m = FIREWALL_RULE_REGEX.match(rule.strip())
            if not m:
                raise ProfileValidationError(
                    messages.FIREWALL_RULE_INVALID.format(rule=rule)
                )
            port = int(m.group(1))
            if not (1 <= port <= 65535):
                raise ProfileValidationError(
                    messages.FIREWALL_RULE_INVALID.format(rule=rule)
                )
            valid_rules.append(rule.strip())
        validated["allow"] = tuple(valid_rules)

    return validated


def validate_unattended_upgrades(uu: Any) -> bool:
    """Validasi pengaturan unattended_upgrades."""
    if not isinstance(uu, bool):
        raise ProfileValidationError(messages.UNATTENDED_UPGRADES_INVALID)
    return uu


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

    admin_user: str | None = None
    if "admin_user" in data:
        admin_user = validate_admin_user(data["admin_user"])

    admin_sudo_nopasswd = bool(data.get("admin_sudo_nopasswd", False))

    ssh_auth_keys: tuple[str, ...] = ()
    if "ssh_authorized_keys" in data:
        ssh_auth_keys = validate_ssh_authorized_keys(data["ssh_authorized_keys"])

    ssh: Mapping[str, Any] | None = None
    if "ssh" in data:
        ssh = validate_ssh(data["ssh"])

    firewall: Mapping[str, Any] | None = None
    if "firewall" in data:
        firewall = validate_firewall(data["firewall"])

    unattended_upgrades: bool | None = None
    if "unattended_upgrades" in data:
        unattended_upgrades = validate_unattended_upgrades(data["unattended_upgrades"])

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
