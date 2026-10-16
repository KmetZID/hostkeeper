"""Unit test untuk hostkeeper.cli (argparse, dispatch, exit codes)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from hostkeeper.cli import (
    EXIT_DRIFT,
    EXIT_ENV,
    EXIT_LOCK,
    EXIT_OK,
    EXIT_USAGE,
    main,
)
from hostkeeper.engine.lock import LockConflict


def test_cli_version() -> None:
    out = io.StringIO()
    code = main(["version"], out=out)
    assert code == EXIT_OK
    text = out.getvalue()
    assert "hostkeeper" in text
    assert "OS      :" in text
    assert "Python  :" in text


def test_cli_watch_requires_subcommand() -> None:
    out = io.StringIO()
    code = main(["watch"], out=out)
    assert code == EXIT_USAGE


def test_cli_rollback_non_root_returns_exit_5() -> None:
    out = io.StringIO()
    with patch("os.geteuid", return_value=1000):
        code = main(["rollback"], out=out)
        assert code == EXIT_ENV


def test_cli_apply_non_root_returns_exit_5() -> None:
    out = io.StringIO()
    with patch("os.geteuid", return_value=1000):
        code = main(["apply"], out=out)
        assert code == EXIT_ENV


def test_cli_apply_lock_conflict_returns_exit_4(tmp_path: Path) -> None:
    prof_file = tmp_path / "profile.yml"
    prof_file.write_text("version: 1\nhostname: web-01\n", encoding="utf-8")

    out = io.StringIO()
    with patch("os.geteuid", return_value=0):
        with patch("hostkeeper.cli.LockManager.acquire", side_effect=LockConflict):
            code = main(["apply", "-c", str(prof_file)], out=out)
            assert code == EXIT_LOCK


def test_cli_invalid_profile_returns_exit_2(tmp_path: Path) -> None:
    bad_prof = tmp_path / "bad.yml"
    bad_prof.write_text("version: 1\nhostname: Web_01\n", encoding="utf-8")

    out = io.StringIO()
    code = main(["plan", "-c", str(bad_prof)], out=out)
    assert code == EXIT_USAGE


def test_cli_plan_check_returns_exit_3_on_drift(tmp_path: Path) -> None:
    prof_file = tmp_path / "profile.yml"
    prof_file.write_text("version: 1\nhostname: web-target\n", encoding="utf-8")

    out = io.StringIO()
    # Fake runner returns drift for hostname
    with patch(
        "hostkeeper.cli.SubprocessRunner.run",
        return_value=type(
            "Res",
            (),
            {"ok": True, "returncode": 0, "stdout": "web-old\n", "stderr": ""},
        ),
    ):
        code = main(["plan", "-c", str(prof_file), "--check"], out=out)
        assert code == EXIT_DRIFT


def test_cli_verify_drift_returns_exit_3(tmp_path: Path) -> None:
    prof_file = tmp_path / "profile.yml"
    prof_file.write_text("version: 1\nhostname: web-target\n", encoding="utf-8")

    out = io.StringIO()
    with patch(
        "hostkeeper.cli.SubprocessRunner.run",
        return_value=type(
            "Res",
            (),
            {"ok": True, "returncode": 0, "stdout": "web-old\n", "stderr": ""},
        ),
    ):
        code = main(["verify", "-c", str(prof_file)], out=out)
        assert code == EXIT_DRIFT


def test_cli_verify_all_ok_returns_exit_0(tmp_path: Path) -> None:
    prof_file = tmp_path / "profile.yml"
    prof_file.write_text("version: 1\nhostname: web-ok\n", encoding="utf-8")

    out = io.StringIO()
    with patch(
        "hostkeeper.cli.SubprocessRunner.run",
        return_value=type(
            "Res",
            (),
            {"ok": True, "returncode": 0, "stdout": "web-ok\n", "stderr": ""},
        ),
    ):
        code = main(["verify", "-c", str(prof_file)], out=out)
        assert code == EXIT_OK


def test_cli_plan_never_mutates(tmp_path: Path) -> None:
    """Plan wajib memakai ReadOnlyRunner dan ReadOnlyFileOps (SPEC 10)."""
    prof_file = tmp_path / "profile.yml"
    prof_file.write_text(
        "version: 1\nhostname: web-01\ntimezone: UTC\n",
        encoding="utf-8",
    )
    out = io.StringIO()
    with patch(
        "hostkeeper.cli.SubprocessRunner.run",
        return_value=type(
            "Res",
            (),
            {"ok": True, "returncode": 0, "stdout": "web-old\n", "stderr": ""},
        ),
    ) as mock_run:
        code = main(["plan", "-c", str(prof_file)], out=out)
        assert code == EXIT_OK
        # Semua pemanggilan runner dari plan harus mutates=False
        for call_args in mock_run.call_args_list:
            kwargs = call_args.kwargs
            if "mutates" in kwargs:
                assert kwargs["mutates"] is False


def test_cli_error_without_verbose_has_no_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prof_file = tmp_path / "profile.yml"
    prof_file.write_text("version: 1\n", encoding="utf-8")
    err_stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", err_stream)

    with patch(
        "hostkeeper.cli.Planner.plan", side_effect=RuntimeError("Simulasi crash")
    ):
        code = main(["plan", "-c", str(prof_file)])
        assert code == 1
        err = err_stream.getvalue()
        assert "ERROR: Kesalahan tidak terduga: Simulasi crash" in err
        assert "Traceback" not in err


def test_cli_error_with_verbose_shows_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prof_file = tmp_path / "profile.yml"
    prof_file.write_text("version: 1\n", encoding="utf-8")
    err_stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", err_stream)

    with patch(
        "hostkeeper.cli.Planner.plan", side_effect=RuntimeError("Simulasi crash")
    ):
        code = main(["plan", "-c", str(prof_file), "-v"])
        assert code == 1
        err = err_stream.getvalue()
        assert "Traceback (most recent call last):" in err


def test_cli_plan_hostnamectl_not_found_exits_5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prof_file = tmp_path / "profile.yml"
    prof_file.write_text("version: 1\nhostname: web-01\n", encoding="utf-8")
    err_stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", err_stream)

    from hostkeeper.system.runner import CmdResult

    with patch(
        "hostkeeper.cli.SubprocessRunner.run",
        return_value=CmdResult(
            argv=("hostnamectl", "--static"),
            returncode=127,
            stdout="",
            stderr="perintah tidak ditemukan: hostnamectl",
            duration=0.01,
        ),
    ):
        code = main(["plan", "-c", str(prof_file)])
        assert code == EXIT_ENV
        err = err_stream.getvalue()
        assert (
            "Perintah 'hostnamectl' tidak ditemukan. Step hostname membutuhkan systemd."
        ) in err


def test_cli_plan_timedatectl_not_found_exits_5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prof_file = tmp_path / "profile.yml"
    prof_file.write_text("version: 1\ntimezone: UTC\n", encoding="utf-8")
    err_stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", err_stream)

    from hostkeeper.system.runner import CmdResult

    with patch(
        "hostkeeper.cli.SubprocessRunner.run",
        return_value=CmdResult(
            argv=("timedatectl", "show", "-p", "Timezone", "--value"),
            returncode=127,
            stdout="",
            stderr="perintah tidak ditemukan: timedatectl",
            duration=0.01,
        ),
    ):
        code = main(["plan", "-c", str(prof_file)])
        assert code == EXIT_ENV
        err = err_stream.getvalue()
        assert (
            "Perintah 'timedatectl' tidak ditemukan. Step timezone membutuhkan systemd."
        ) in err
