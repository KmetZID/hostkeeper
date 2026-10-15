"""Unit test untuk AuditWriter (SPEC 4.5)."""

from __future__ import annotations

import json
import stat
from pathlib import Path

from hostkeeper.engine.audit import AuditWriter


def test_audit_writer_events_and_format(tmp_path: Path) -> None:
    audit_file = tmp_path / "audit.jsonl"
    writer = AuditWriter(path=audit_file, run_id="run-123")

    writer.log_run_start("/etc/hostkeeper/profile.yml")
    writer.log_plan("hostname", 1)
    writer.log_command(("hostnamectl", "set-hostname", "web-01"), 0)
    writer.log_step_applied("hostname", 1)
    writer.log_step_verified("hostname")
    writer.log_step_failed("packages", "apt failed")
    writer.log_undo("hostname")
    writer.log_run_end("ok")

    assert audit_file.exists()

    # Periksa permission mode 640 (rw-r-----)
    mode = stat.S_IMODE(audit_file.stat().st_mode)
    assert mode == 0o640

    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 8

    records = [json.loads(line) for line in lines]
    events = [r["event"] for r in records]
    assert events == [
        "run_start",
        "plan",
        "command",
        "step_applied",
        "step_verified",
        "step_failed",
        "undo",
        "run_end",
    ]

    for r in records:
        assert r["run_id"] == "run-123"
        assert "ts" in r
