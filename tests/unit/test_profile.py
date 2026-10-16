from __future__ import annotations

from pathlib import Path

import pytest

from hostkeeper.profile import (
    ProfileValidationError,
    load_profile,
    parse_profile_dict,
    validate_hostname,
    validate_packages,
    validate_timezone,
)


def test_validate_hostname_valid() -> None:
    for h in ["web-01", "a", "srv1.example.com", "node-1.sub-domain.org", "x" * 63]:
        validate_hostname(h)


def test_validate_hostname_invalid() -> None:
    invalid_cases = [
        "",
        "a;b",  # shell meta / malicious
        "Web_01",  # uppercase and underscore
        "web_01",  # underscore
        "-start",  # starts with hyphen
        "end-",  # ends with hyphen
        "a..b",  # consecutive dots
        ".start.com",
        "end.com.",
        "a" * 64,  # label > 63 chars
        "a" * 254,  # total > 253 chars
        "foo bar",  # whitespace
        "foo$bar",  # special char
    ]
    for h in invalid_cases:
        with pytest.raises(ProfileValidationError):
            validate_hostname(h)


def test_validate_timezone_valid(tmp_path: Path) -> None:
    zoneinfo = tmp_path / "zoneinfo"
    zoneinfo.mkdir()
    (zoneinfo / "Asia").mkdir()
    (zoneinfo / "Asia" / "Jakarta").write_text("dummy tz data")
    (zoneinfo / "UTC").symlink_to(zoneinfo / "Asia" / "Jakarta")

    validate_timezone("Asia/Jakarta", zoneinfo_dir=zoneinfo)
    validate_timezone("UTC", zoneinfo_dir=zoneinfo)


def test_validate_timezone_invalid(tmp_path: Path) -> None:
    zoneinfo = tmp_path / "zoneinfo"
    zoneinfo.mkdir()
    (zoneinfo / "Asia").mkdir()
    (zoneinfo / "Asia" / "Jakarta").write_text("dummy tz data")

    invalid_zones = [
        "../x",  # traversal attempt
        "../../etc/shadow",  # traversal attempt
        "/etc/passwd",  # absolute path
        "Asia/NonExistent",
        "Asia",  # directory, not file
        "",
        "NonExistent",
    ]
    for tz in invalid_zones:
        with pytest.raises(ProfileValidationError):
            validate_timezone(tz, zoneinfo_dir=zoneinfo)


def test_validate_packages_valid() -> None:
    pkgs = ["curl", "vim", "htop", "python3.11", "libssl-dev", "g++"]
    res = validate_packages(pkgs)
    assert res == tuple(pkgs)


def test_validate_packages_invalid() -> None:
    invalid_lists = [
        "not-a-list",
        ["curl", "foo; rm -rf /"],  # malicious
        ["curl", "Bad_Package"],  # uppercase / underscore
        ["-startwithhyphen"],
        [f"pkg{i}" for i in range(101)],  # > 100 packages
        [123],  # not str
    ]
    for pkgs in invalid_lists:
        with pytest.raises(ProfileValidationError):
            validate_packages(pkgs)  # type: ignore[arg-type]


def test_parse_profile_dict_valid(tmp_path: Path) -> None:
    zoneinfo = tmp_path / "zoneinfo"
    zoneinfo.mkdir()
    (zoneinfo / "UTC").write_text("tz")

    data = {
        "version": 1,
        "hostname": "srv-01",
        "timezone": "UTC",
        "packages": ["curl", "htop"],
    }
    prof = parse_profile_dict(data, zoneinfo_dir=zoneinfo)
    assert prof.version == 1
    assert prof.hostname == "srv-01"
    assert prof.timezone == "UTC"
    assert prof.packages == ("curl", "htop")


def test_parse_profile_dict_optional_fields_override(tmp_path: Path) -> None:
    zoneinfo = tmp_path / "zoneinfo"
    zoneinfo.mkdir()

    data = {
        "version": 1,
        "admin_user": "admin",
        "admin_sudo_nopasswd": True,
        "ssh_authorized_keys": [
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleValidKey1234567890 admin@host"
        ],
    }
    prof = parse_profile_dict(data, zoneinfo_dir=zoneinfo)
    assert prof.admin_user == "admin"
    assert prof.admin_sudo_nopasswd is True
    assert prof.ssh_authorized_keys == (
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleValidKey1234567890 admin@host",
    )
    assert prof.hostname is None


def test_parse_profile_dict_invalid_version() -> None:
    with pytest.raises(ProfileValidationError):
        parse_profile_dict({"version": 2})

    with pytest.raises(ProfileValidationError):
        parse_profile_dict({})  # missing version


def test_parse_profile_dict_unknown_keys() -> None:
    with pytest.raises(ProfileValidationError):
        parse_profile_dict({"version": 1, "unknown_field": "val"})


def test_load_profile_from_file(tmp_path: Path) -> None:
    zoneinfo = tmp_path / "zoneinfo"
    zoneinfo.mkdir()
    (zoneinfo / "UTC").write_text("tz")

    profile_file = tmp_path / "profile.yml"
    profile_file.write_text(
        "version: 1\nhostname: node-01\ntimezone: UTC\npackages:\n  - curl\n"
    )

    prof = load_profile(profile_file, zoneinfo_dir=zoneinfo)
    assert prof.hostname == "node-01"
    assert prof.timezone == "UTC"
    assert prof.packages == ("curl",)


def test_load_profile_file_not_found(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.yml"
    with pytest.raises(ProfileValidationError, match="tidak ditemukan"):
        load_profile(non_existent)


def test_load_profile_invalid_yaml(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yml"
    bad_yaml.write_text("version: 1\n  invalid: indentation: [")
    with pytest.raises(ProfileValidationError, match="Format YAML"):
        load_profile(bad_yaml)


def test_parse_profile_dict_not_a_mapping() -> None:
    with pytest.raises(ProfileValidationError, match="pemetaan YAML"):
        parse_profile_dict("not a dict")


def test_validate_admin_user_valid() -> None:
    from hostkeeper.profile import validate_admin_user

    for u in ["deploy", "admin", "alice", "user_01", "john-doe", "web1$", "a"]:
        assert validate_admin_user(u) == u


def test_validate_admin_user_invalid() -> None:
    from hostkeeper.profile import validate_admin_user

    invalid_users = [
        "root",  # forbidden
        "",
        "1user",  # starts with digit
        "-user",  # starts with dash
        "User",  # uppercase
        "user;rm",  # malicious char
        "user name",  # space
        "a" * 33,  # > 32 chars
        123,  # not str
    ]
    for u in invalid_users:
        with pytest.raises(ProfileValidationError):
            validate_admin_user(u)


def test_validate_ssh_authorized_keys_valid() -> None:
    from hostkeeper.profile import validate_ssh_authorized_keys

    valid_keys = [
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleValidKey1234567890 comment@host",
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC0 valid-rsa-key",
        "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABB",
    ]
    res = validate_ssh_authorized_keys(valid_keys)
    assert res == tuple(valid_keys)


def test_validate_ssh_authorized_keys_invalid() -> None:
    from hostkeeper.profile import validate_ssh_authorized_keys

    invalid_cases = [
        "not a list",
        [123],
        ["ssh-dss AAAAB3NzaC1kc3MAAA dummy"],  # unsupported/insecure type
        ["ssh-ed25519"],  # missing blob
        ["ssh-ed25519 !@#$invalidbase64!"],  # invalid base64
        ["completely invalid key text"],
    ]
    for case in invalid_cases:
        with pytest.raises(ProfileValidationError):
            validate_ssh_authorized_keys(case)


def test_validate_ssh_valid() -> None:
    from hostkeeper.profile import validate_ssh

    ssh_conf = {
        "port": 22,
        "permit_root_login": "no",
        "password_auth": False,
    }
    res = validate_ssh(ssh_conf)
    assert res["port"] == 22
    assert res["permit_root_login"] == "no"
    assert res["password_auth"] is False


def test_validate_ssh_invalid() -> None:
    from hostkeeper.profile import validate_ssh

    invalid_cases = [
        "not-a-dict",
        {"unknown": "val"},
        {"port": 0},
        {"port": 70000},
        {"port": "22"},
        {"permit_root_login": "invalid_value"},
        {"password_auth": "no"},  # not a bool
    ]
    for case in invalid_cases:
        with pytest.raises(ProfileValidationError):
            validate_ssh(case)


def test_validate_firewall_valid() -> None:
    from hostkeeper.profile import validate_firewall

    fw = {"allow": ["22/tcp", "80/tcp", "443/tcp", "53/udp"]}
    res = validate_firewall(fw)
    assert res["allow"] == ("22/tcp", "80/tcp", "443/tcp", "53/udp")


def test_validate_firewall_invalid() -> None:
    from hostkeeper.profile import validate_firewall

    invalid_cases = [
        "not-a-dict",
        {"unknown": 123},
        {"allow": "not-a-list"},
        {"allow": ["80"]},  # missing protocol
        {"allow": ["80/http"]},  # invalid proto
        {"allow": ["0/tcp"]},  # port out of range
        {"allow": ["70000/tcp"]},  # port out of range
        {"allow": ["22/tcp; rm -rf /"]},  # injection attempt
    ]
    for case in invalid_cases:
        with pytest.raises(ProfileValidationError):
            validate_firewall(case)


def test_validate_unattended_upgrades() -> None:
    from hostkeeper.profile import validate_unattended_upgrades

    assert validate_unattended_upgrades(True) is True
    assert validate_unattended_upgrades(False) is False
    with pytest.raises(ProfileValidationError):
        validate_unattended_upgrades("yes")
    with pytest.raises(ProfileValidationError):
        validate_unattended_upgrades(1)
