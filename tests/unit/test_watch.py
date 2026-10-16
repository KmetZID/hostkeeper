"""Unit test untuk perintah hostkeeper watch (Tahap 3.3)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from hostkeeper.cli import EXIT_OK, EXIT_USAGE, main
from hostkeeper.engine.lock import LockConflict


def test_watch_run_lock_conflict_skips_cycle_cleanly() -> None:
    out = io.StringIO()
    lock_patch = patch(
        "hostkeeper.cli.LockManager.acquire",
        side_effect=LockConflict("Lock conflict"),
    )
    with lock_patch:
        code = main(["watch", "run"], out=out)
        assert code == EXIT_OK
        assert "dilewati" in out.getvalue().lower()


def test_watch_run_normal_cycle(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    watch_cfg = tmp_path / "watch.yml"
    watch_cfg.write_text(
        yaml.safe_dump(
            {
                "webhook_url": "https://example.invalid/hook",
                "webhook_format": "slack",
            }
        ),
        encoding="utf-8",
    )
    watch_cfg.chmod(0o600)

    out = io.StringIO()
    with patch("hostkeeper.cli.send_webhook", return_value=True):
        code = main(
            [
                "watch",
                "run",
                "--state-db",
                str(db_path),
                "--watch-config",
                str(watch_cfg),
                "--lock-path",
                str(tmp_path / "hostkeeper.lock"),
            ],
            out=out,
        )
        assert code == EXIT_OK
        assert db_path.exists()


def test_watch_test_notify_no_url(tmp_path: Path) -> None:
    cfg = tmp_path / "watch_empty.yml"
    cfg.write_text("thresholds: {}\n", encoding="utf-8")
    cfg.chmod(0o600)

    err = io.StringIO()
    with patch("sys.stderr", err):
        code = main(["watch", "test-notify", "--watch-config", str(cfg)])
        assert code == EXIT_USAGE


def test_watch_test_notify_success(tmp_path: Path) -> None:
    cfg = tmp_path / "watch.yml"
    cfg.write_text(
        "webhook_url: https://hooks.slack.com/services/T00/B00/SECRET\n",
        encoding="utf-8",
    )
    cfg.chmod(0o600)

    out = io.StringIO()
    with patch("hostkeeper.cli.send_webhook", return_value=True):
        code = main(["watch", "test-notify", "--watch-config", str(cfg)], out=out)
        assert code == EXIT_OK
        # Memastikan URL rahasia dimaskir di output
        assert "SECRET" not in out.getvalue()
        assert "******" in out.getvalue()


def test_watch_enable_and_disable() -> None:
    with patch("hostkeeper.cli.SubprocessRunner.run") as mock_run:
        mock_run.return_value = MagicMock(ok=True, returncode=0, stdout="", stderr="")

        out_enable = io.StringIO()
        code_enable = main(["watch", "enable"], out=out_enable)
        assert code_enable == EXIT_OK
        assert "diaktifkan" in out_enable.getvalue()

        out_disable = io.StringIO()
        code_disable = main(["watch", "disable"], out=out_disable)
        assert code_disable == EXIT_OK
        assert "dinonaktifkan" in out_disable.getvalue()
