"""Unit test untuk JournalWriter."""

from __future__ import annotations

import json
from pathlib import Path

from hostkeeper.engine.journal import JournalWriter
from hostkeeper.engine.step import Change


def test_journal_writer_lifecycle(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    writer = JournalWriter(
        run_id="20260114T093000Z-ab12",
        profile_sha256="abcdef123456",
        journal_dir=journal_dir,
    )

    writer.record_step(
        name="hostname",
        status="applied",
        reversible=True,
        changes=[
            Change(
                step="hostname",
                action="set",
                target="hostname",
                before="web-old",
                after="web-01",
            )
        ],
    )
    writer.record_step(
        name="packages",
        status="skipped",
        reversible=False,
        changes=[],
    )

    path = writer.write()
    assert path.is_file()
    assert path.name == "20260114T093000Z-ab12.json"

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == "20260114T093000Z-ab12"
    assert data["profile_sha256"] == "abcdef123456"
    assert len(data["steps"]) == 2
    assert data["steps"][0]["name"] == "hostname"
    assert data["steps"][0]["status"] == "applied"
    assert data["steps"][0]["reversible"] is True
    assert len(data["steps"][0]["changes"]) == 1
    assert data["steps"][1]["name"] == "packages"
    assert data["steps"][1]["status"] == "skipped"
