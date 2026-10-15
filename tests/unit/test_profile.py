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
        "ssh_authorized_keys": ["ssh-ed25519 AAAA..."],
    }
    prof = parse_profile_dict(data, zoneinfo_dir=zoneinfo)
    assert prof.admin_user == "admin"
    assert prof.admin_sudo_nopasswd is True
    assert prof.ssh_authorized_keys == ("ssh-ed25519 AAAA...",)
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
