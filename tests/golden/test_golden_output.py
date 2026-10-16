"""Golden tests untuk format output SPEC bagian 8."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

from hostkeeper import __version__
from hostkeeper.cli import EXIT_DRIFT, EXIT_ENV, EXIT_LOCK, EXIT_OK, EXIT_USAGE, main
from hostkeeper.engine.lock import LockConflict
from hostkeeper.engine.step import CheckResult
from hostkeeper.monitor.collector import Metric


def _make_res(stdout: str) -> object:
    return type(
        "Res",
        (),
        {"ok": True, "returncode": 0, "stdout": stdout, "stderr": ""},
    )()


def test_golden_version_output() -> None:
    out = io.StringIO()
    with patch(
        "hostkeeper.cli.detect_env",
        return_value=type(
            "Env",
            (),
            {
                "os_name": "Debian GNU/Linux 12 (bookworm)",
                "is_supported": True,
                "python_version": "3.11.2",
                "systemd_active": True,
            },
        )(),
    ):
        code = main(["version"], out=out)
        assert code == EXIT_OK
        lines = [line.strip() for line in out.getvalue().splitlines() if line.strip()]
        assert lines[0] == f"hostkeeper {__version__}"
        assert lines[1] == "OS      : Debian GNU/Linux 12 (bookworm)  [didukung]"
        assert lines[2] == "Python  : 3.11.2"
        assert lines[3] == "systemd : aktif"


def test_golden_plan_text_output(tmp_path: Path) -> None:
    prof = tmp_path / "profile.yml"
    prof.write_text(
        "version: 1\n"
        "hostname: web-01\n"
        "timezone: Asia/Jakarta\n"
        "packages:\n  - curl\n  - htop\n  - vim\n",
        encoding="utf-8",
    )
    out = io.StringIO()
    responses = {
        ("hostnamectl", "--static"): "web-old\n",
        ("timedatectl", "show", "-p", "Timezone", "--value"): "Asia/Jakarta\n",
        ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "curl", "htop", "vim"): (
            "curl install ok installed\n"
            "htop deinstall ok config-files\n"
            "vim deinstall ok config-files\n"
        ),
        ("apt-cache", "policy", "htop"): "htop:\n  Candidate: 3.2.2\n",
        ("apt-cache", "policy", "vim"): "vim:\n  Candidate: 9.0\n",
    }

    def fake_run(argv: list[str], mutates: bool = False, **kwargs: object) -> object:
        key = tuple(argv)
        return _make_res(responses.get(key, ""))

    with patch("hostkeeper.cli.SubprocessRunner.run", side_effect=fake_run):
        code = main(["plan", "-c", str(prof)], out=out)
        assert code == EXIT_OK
        output = out.getvalue()
        assert f"hostkeeper {__version__} plan" in output
        assert (
            "STATUS  STEP       PERUBAHAN                                   RISIKO"
            in output
        )
        assert (
            "[~]     hostname   web-old -> web-01                           rendah"
            in output
        )
        assert (
            "[=]     timezone   Asia/Jakarta (sudah sesuai)                 -" in output
        )
        assert (
            "[+]     packages   pasang: htop, vim (curl sudah terpasang)    rendah"
            in output
        )
        assert "Ringkasan: 2 perubahan, 1 sudah sesuai, 0 berisiko tinggi." in output
        assert (
            "Mode plan: tidak ada yang diubah. Jalankan `sudo hostkeeper apply`"
            in output
        )


def test_golden_plan_json_output(tmp_path: Path) -> None:
    prof = tmp_path / "profile.yml"
    prof.write_text(
        "version: 1\nhostname: web-01\ntimezone: Asia/Jakarta\n",
        encoding="utf-8",
    )
    out = io.StringIO()
    responses = {
        ("hostnamectl", "--static"): "web-old\n",
        ("timedatectl", "show", "-p", "Timezone", "--value"): "Asia/Jakarta\n",
    }

    def fake_run(argv: list[str], mutates: bool = False, **kwargs: object) -> object:
        key = tuple(argv)
        return _make_res(responses.get(key, ""))

    with patch("hostkeeper.cli.SubprocessRunner.run", side_effect=fake_run):
        code = main(["plan", "-c", str(prof), "--json"], out=out)
        assert code == EXIT_OK
        json_lines = [
            line
            for line in out.getvalue().splitlines()
            if line.strip().startswith("{") and line.strip().endswith("}")
        ]
        assert len(json_lines) > 0
        data = json.loads(json_lines[-1])
        assert data["version"] == __version__
        assert data["summary"]["changes"] == 1
        assert data["summary"]["ok"] == 1
        assert len(data["steps"]) == 2


def test_golden_verify_output_compliant(tmp_path: Path) -> None:
    prof = tmp_path / "profile.yml"
    prof.write_text(
        "version: 1\n"
        "hostname: web-01\n"
        "timezone: Asia/Jakarta\n"
        "packages:\n  - curl\n  - htop\n  - vim\n",
        encoding="utf-8",
    )
    out = io.StringIO()
    responses = {
        ("hostnamectl", "--static"): "web-01\n",
        ("timedatectl", "show", "-p", "Timezone", "--value"): "Asia/Jakarta\n",
        ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "curl", "htop", "vim"): (
            "curl install ok installed\n"
            "htop install ok installed\n"
            "vim install ok installed\n"
        ),
    }

    def fake_run(argv: list[str], mutates: bool = False, **kwargs: object) -> object:
        key = tuple(argv)
        return _make_res(responses.get(key, ""))

    with patch("hostkeeper.cli.SubprocessRunner.run", side_effect=fake_run):
        code = main(["verify", "-c", str(prof)], out=out)
        assert code == EXIT_OK
        output = out.getvalue()
        assert "[=] hostname   web-01" in output
        assert "[=] timezone   Asia/Jakarta" in output
        assert "[=] packages   curl, htop, vim terpasang" in output
        assert "Semua Step sesuai profil." in output


def test_golden_verify_output_drift(tmp_path: Path, monkeypatch: object) -> None:
    prof = tmp_path / "profile.yml"
    prof.write_text(
        "version: 1\nhostname: web-01\ntimezone: Asia/Jakarta\npackages:\n  - htop\n",
        encoding="utf-8",
    )
    out = io.StringIO()
    responses = {
        ("hostnamectl", "--static"): "web-old\n",
        ("timedatectl", "show", "-p", "Timezone", "--value"): "Asia/Jakarta\n",
        ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "htop"): (
            "htop deinstall ok config-files\n"
        ),
    }

    def fake_run(argv: list[str], mutates: bool = False, **kwargs: object) -> object:
        key = tuple(argv)
        return _make_res(responses.get(key, ""))

    with patch("hostkeeper.cli.SubprocessRunner.run", side_effect=fake_run):
        code = main(["verify", "-c", str(prof)], out=out)
        assert code == EXIT_DRIFT
        output = out.getvalue()
        assert "[~] hostname   diharapkan web-01, sekarang web-old" in output
        assert "[=] timezone   Asia/Jakarta" in output
        assert "[~] packages   belum terpasang: htop" in output


def test_golden_errors_section_8_5(tmp_path: Path, monkeypatch: object) -> None:
    # 1. apply bukan root
    out1 = io.StringIO()
    err1 = io.StringIO()
    with patch("sys.stderr", err1):
        with patch("os.geteuid", return_value=1000):
            code1 = main(["apply"], out=out1)
            assert code1 == EXIT_ENV
            err_msg = err1.getvalue()
            assert "ERROR: apply membutuhkan root." in err_msg

    # 2. profile invalid
    bad_prof = tmp_path / "bad.yml"
    bad_prof.write_text("version: 1\nhostname: Web_01\n", encoding="utf-8")
    out2 = io.StringIO()
    err2 = io.StringIO()
    with patch("sys.stderr", err2):
        code2 = main(["plan", "-c", str(bad_prof)], out=out2)
        assert code2 == EXIT_USAGE
        assert "ERROR: profil tidak valid:" in err2.getvalue()
        assert "hostname 'web_01' tidak sah" in err2.getvalue().lower()

    # 3. lock conflict
    good_prof = tmp_path / "good.yml"
    good_prof.write_text("version: 1\nhostname: web-01\n", encoding="utf-8")
    out3 = io.StringIO()
    err3 = io.StringIO()
    with patch("sys.stderr", err3):
        with patch("os.geteuid", return_value=0):
            with patch("hostkeeper.cli.LockManager.acquire", side_effect=LockConflict):
                code3 = main(["apply", "-c", str(good_prof)], out=out3)
                assert code3 == EXIT_LOCK
                assert "ERROR: hostkeeper lain sedang berjalan" in err3.getvalue()


def test_golden_status_table_and_json(tmp_path: Path) -> None:
    prof = tmp_path / "profile.yml"
    prof.write_text("version: 1\nhostname: web-01\n", encoding="utf-8")

    out_table = io.StringIO()
    with patch(
        "hostkeeper.cli.collect_all",
        return_value=[
            Metric(name="cpu.load1", value=0.15, unit="", status_hint="ok"),
            Metric(name="mem.used_percent", value=50.0, unit="%", status_hint="ok"),
        ],
    ):
        hn_res = CheckResult(
            compliant=True,
            current="web-01",
        )
        with patch(
            "hostkeeper.steps.hostname.HostnameStep.check",
            return_value=hn_res,
        ):
            code = main(
                ["status", "-c", str(prof), "--no-color"],
                out=out_table,
            )
            assert code == EXIT_OK
            table = out_table.getvalue()
            tgt = f"hostkeeper {__version__} status"
            assert tgt in table
            assert "METRIK SISTEM:" in table
            assert "KESESUAIAN PROFIL:" in table
            assert "[OK]" in table
            assert "cpu.load1" in table
            msg = "Semua metrik dan profil dalam kondisi OK"
            assert msg in table

    out_json = io.StringIO()
    with patch(
        "hostkeeper.cli.collect_all",
        return_value=[
            Metric(name="cpu.load1", value=0.15, unit="", status_hint="ok"),
        ],
    ):
        hn_res = CheckResult(
            compliant=True,
            current="web-01",
        )
        with patch(
            "hostkeeper.steps.hostname.HostnameStep.check",
            return_value=hn_res,
        ):
            code_json = main(
                ["status", "-c", str(prof), "--json"],
                out=out_json,
            )
            assert code_json == EXIT_OK
            data = json.loads(out_json.getvalue())
            assert data["version"] == __version__
            assert data["status"] == "ok"
            assert data["summary"]["warn"] == 0
            assert data["summary"]["crit"] == 0
            assert data["summary"]["drift"] == 0
