"""Unit test untuk perintah hostkeeper status dan profile compliance (Tahap 3.4)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hostkeeper.cli import EXIT_DRIFT, EXIT_OK, main
from hostkeeper.engine.step import CheckResult
from hostkeeper.monitor.collector import Metric
from hostkeeper.system.fileops import ReadOnlyFileOps
from hostkeeper.system.runner import ReadOnlyRunner, ReadOnlyViolation


def test_profile_checker_read_only_violation() -> None:
    ro_runner = ReadOnlyRunner(MagicMock())
    with pytest.raises(ReadOnlyViolation):
        ro_runner.run(["touch", "/tmp/forbidden"], mutates=True)

    ro_fs = ReadOnlyFileOps()
    with pytest.raises(ReadOnlyViolation):
        ro_fs.write_atomic(Path("/tmp/forbidden"), "content", mode=0o644)


def test_status_all_ok(tmp_path: Path) -> None:
    prof = tmp_path / "profile.yml"
    prof.write_text(
        "version: 1\nhostname: web-01\ntimezone: Asia/Jakarta\n",
        encoding="utf-8",
    )

    out = io.StringIO()
    with patch(
        "hostkeeper.cli.collect_all",
        return_value=[
            Metric(name="cpu.load1", value=0.1, unit="", status_hint="ok"),
            Metric(name="mem.used_percent", value=40.0, unit="%", status_hint="ok"),
            Metric(name="disk./.used_percent", value=50.0, unit="%", status_hint="ok"),
            Metric(name="services.failed_count", value=0, unit="", status_hint="ok"),
            Metric(name="time.ntp_synchronized", value=True, unit="", status_hint="ok"),
        ],
    ):
        hn_res = CheckResult(
            compliant=True,
            current="web-01",
        )
        tz_res = CheckResult(
            compliant=True,
            current="Asia/Jakarta",
        )
        hn_patch = patch(
            "hostkeeper.steps.hostname.HostnameStep.check",
            return_value=hn_res,
        )
        tz_patch = patch(
            "hostkeeper.steps.timezone.TimezoneStep.check",
            return_value=tz_res,
        )
        with hn_patch, tz_patch:
            code = main(
                ["status", "-c", str(prof)],
                out=out,
            )
            assert code == EXIT_OK
            output = out.getvalue()
            assert "status" in output
            assert "METRIK SISTEM:" in output
            assert "KESESUAIAN PROFIL:" in output
            msg = "Semua metrik dan profil dalam kondisi OK"
            assert msg in output


def test_status_drift_detected_exits_3(tmp_path: Path) -> None:
    prof = tmp_path / "profile.yml"
    prof.write_text("version: 1\nhostname: web-01\n", encoding="utf-8")

    out = io.StringIO()
    with patch(
        "hostkeeper.cli.collect_all",
        return_value=[
            Metric(name="cpu.load1", value=0.1, unit="", status_hint="ok"),
        ],
    ):
        # Server punya hostname web-different -> drift!
        hn_res = CheckResult(
            compliant=False,
            current="web-different",
        )
        with patch(
            "hostkeeper.steps.hostname.HostnameStep.check",
            return_value=hn_res,
        ):
            code = main(
                ["status", "-c", str(prof)],
                out=out,
            )
            assert code == EXIT_DRIFT
            assert "[WARN]" in out.getvalue()
            assert "web-different" in out.getvalue()


def test_status_json_output(tmp_path: Path) -> None:
    prof = tmp_path / "profile.yml"
    prof.write_text("version: 1\nhostname: web-01\n", encoding="utf-8")

    out = io.StringIO()
    with patch(
        "hostkeeper.cli.collect_all",
        return_value=[
            Metric(name="mem.used_percent", value=95.0, unit="%", status_hint="crit"),
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
                ["status", "-c", str(prof), "--json"],
                out=out,
            )
            assert code == EXIT_DRIFT
            raw = json.loads(out.getvalue())
            assert raw["status"] == "crit"
            assert raw["summary"]["crit"] == 1
            assert len(raw["metrics"]) >= 1
            assert len(raw["profile"]) >= 1
