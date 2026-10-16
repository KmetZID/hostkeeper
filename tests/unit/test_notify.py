"""Unit test untuk monitor/notify.py (Tahap 3.3)."""

from __future__ import annotations

import io
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from hostkeeper.monitor.notify import (
    check_watch_config_permissions,
    format_payload,
    mask_url,
    send_webhook,
)


def test_mask_url() -> None:
    assert (
        mask_url("https://hooks.slack.com/services/T00/B00/X12345")
        == "https://hooks.slack.com/services/******"
    )
    assert (
        mask_url("https://discord.com/api/webhooks/123456/abcdef-gh")
        == "https://discord.com/api/webhooks/******"
    )
    assert (
        mask_url("http://example.com/webhook?token=secret")
        == "http://example.com/webhook?******"
    )
    assert mask_url("invalid-url") == "******"


def test_format_payload_slack() -> None:
    data = format_payload(
        fmt="slack",
        hostname="web-01",
        messages=["Disk hampir penuh: 92%"],
        level="crit",
    )
    assert "text" in data
    assert "[CRIT]" in data["text"]
    assert "web-01" in data["text"]
    assert "Disk hampir penuh: 92%" in data["text"]


def test_format_payload_discord() -> None:
    data = format_payload(
        fmt="discord",
        hostname="web-01",
        messages=["Layanan nginx gagal"],
        level="crit",
    )
    assert "content" in data
    assert "[CRIT]" in data["content"]
    assert "web-01" in data["content"]


def test_format_payload_json() -> None:
    data = format_payload(
        fmt="json",
        hostname="web-01",
        messages=["Update keamanan tersedia"],
        level="warn",
    )
    assert data["hostname"] == "web-01"
    assert data["level"] == "warn"
    assert "Update keamanan tersedia" in data["alerts"]


@patch("urllib.request.urlopen")
def test_send_webhook_success(mock_urlopen: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    ok = send_webhook("https://example.invalid/hook", {"text": "hello"})
    assert ok is True
    assert mock_urlopen.called


@patch("urllib.request.urlopen")
def test_send_webhook_failure_is_non_fatal_and_masked(mock_urlopen: MagicMock) -> None:
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

    err_buf = io.StringIO()
    # Webhook gagal TIDAK boleh melempar exception crash, harus mengembalikan False
    ok = send_webhook(
        "https://secret-domain.com/token-12345",
        {"text": "hello"},
        out_err=err_buf,
    )
    assert ok is False

    err_output = err_buf.getvalue()
    # URL rahasia TIDAK boleh bocor di output error
    assert "token-12345" not in err_output
    assert "******" in err_output


def test_check_watch_config_permissions(tmp_path: Path) -> None:
    cfg = tmp_path / "watch.yml"
    cfg.write_text("webhook_url: https://example.invalid/hook\n", encoding="utf-8")
    cfg.chmod(0o644)  # bukan 0600

    err_buf = io.StringIO()
    warning = check_watch_config_permissions(cfg, out_err=err_buf)
    assert warning is True
    assert "0600" in err_buf.getvalue()

    cfg.chmod(0o600)
    err_buf2 = io.StringIO()
    warning2 = check_watch_config_permissions(cfg, out_err=err_buf2)
    assert warning2 is False
    assert err_buf2.getvalue() == ""
