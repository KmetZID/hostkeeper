"""Unit test untuk hostkeeper rollback (Tahap 2.1)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hostkeeper.cli import EXIT_OK, main
from hostkeeper.engine.rollback import RollbackError, RollbackManager
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


def _create_sample_journal(
    journal_dir: Path,
    run_id: str,
    steps: list[dict[str, object]],
    corrupt: bool = False,
) -> Path:
    journal_dir.mkdir(parents=True, exist_ok=True)
    jfile = journal_dir / f"{run_id}.json"
    if corrupt:
        jfile.write_text("{ corrupt json: [", encoding="utf-8")
    else:
        data = {
            "run_id": run_id,
            "hostkeeper": "0.2.0",
            "profile_sha256": "abc123",
            "steps": steps,
        }
        jfile.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return jfile


def test_rollback_restores_file_and_state(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    backup_dir = tmp_path / "backups"
    audit_file = tmp_path / "audit.jsonl"
    run_id = "20260114T093000Z-test1"

    # Buat backup file di backup_dir/<run_id>/etc/dummy.conf
    backup_file = backup_dir / run_id / "etc" / "dummy.conf"
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file.write_text("original content", encoding="utf-8")

    # File saat ini di sistem
    fs = FakeFileOps(
        {
            Path("/etc/dummy.conf"): "modified content",
            backup_file: "original content",
        }
    )
    runner = FakeRunner(
        {
            ("hostnamectl", "set-hostname", "srv-old"): "",
        }
    )

    steps = [
        {
            "name": "hostname",
            "status": "applied",
            "reversible": True,
            "changes": [
                {
                    "action": "set",
                    "target": "hostname",
                    "before": "srv-old",
                    "after": "srv-new",
                }
            ],
            "backups": [],
        },
        {
            "name": "dummy_step",
            "status": "applied",
            "reversible": True,
            "changes": [
                {
                    "action": "write",
                    "target": "/etc/dummy.conf",
                    "before": "original content",
                    "after": "modified content",
                }
            ],
            "backups": [str(backup_file)],
        },
    ]
    _create_sample_journal(journal_dir, run_id, steps)

    mgr = RollbackManager(
        journal_dir=journal_dir,
        backup_dir=backup_dir,
        audit_path=audit_file,
        runner=runner,
        fs=fs,
    )

    ok = mgr.rollback(run_id=run_id, yes=True, reason="manual")
    assert ok is True

    # 1. Hostname dikembalikan
    assert any(
        c.argv == ("hostnamectl", "set-hostname", "srv-old") for c in runner.calls
    )
    # 2. File dikembalikan persis
    assert fs.read_text(Path("/etc/dummy.conf")) == "original content"
    # 3. Audit tercatat
    audit_lines = [
        json.loads(line)
        for line in audit_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    undo_events = [e for e in audit_lines if e.get("event") == "undo"]
    assert len(undo_events) >= 1
    assert undo_events[0]["reason"] == "manual"


def test_rollback_reverse_order(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    backup_dir = tmp_path / "backups"
    run_id = "20260114T093000Z-order"

    order_called: list[str] = []

    class MockStepA:
        name = "step_a"
        reversible = True

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def undo(self, changes: object) -> None:
            order_called.append("step_a")

    class MockStepB:
        name = "step_b"
        reversible = True

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def undo(self, changes: object) -> None:
            order_called.append("step_b")

    steps = [
        {
            "name": "step_a",
            "status": "applied",
            "reversible": True,
            "changes": [],
            "backups": [],
        },
        {
            "name": "step_b",
            "status": "applied",
            "reversible": True,
            "changes": [],
            "backups": [],
        },
    ]
    _create_sample_journal(journal_dir, run_id, steps)

    fs = FakeFileOps()
    runner = FakeRunner()
    mgr = RollbackManager(
        journal_dir=journal_dir,
        backup_dir=backup_dir,
        runner=runner,
        fs=fs,
        step_registry=(MockStepA, MockStepB),  # type: ignore[arg-type]
    )

    mgr.rollback(run_id=run_id, yes=True)
    # Urutan harus mundur: step_b lalu step_a
    assert order_called == ["step_b", "step_a"]


def test_rollback_corrupt_journal(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    run_id = "20260114T093000Z-corrupt"
    _create_sample_journal(journal_dir, run_id, [], corrupt=True)

    mgr = RollbackManager(
        journal_dir=journal_dir, runner=FakeRunner(), fs=FakeFileOps()
    )
    with pytest.raises(RollbackError, match="rusak atau tidak valid"):
        mgr.rollback(run_id=run_id, yes=True)


def test_rollback_nonexistent_run(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    mgr = RollbackManager(
        journal_dir=journal_dir, runner=FakeRunner(), fs=FakeFileOps()
    )
    with pytest.raises(RollbackError, match="tidak ditemukan"):
        mgr.rollback(run_id="nonexistent-run", yes=True)


def test_rollback_no_runs(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    mgr = RollbackManager(
        journal_dir=journal_dir, runner=FakeRunner(), fs=FakeFileOps()
    )
    with pytest.raises(RollbackError, match="Tidak ada"):
        mgr.rollback(run_id=None, yes=True)


def test_rollback_idempotent(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    backup_dir = tmp_path / "backups"
    run_id = "20260114T093000Z-idem"

    backup_file = backup_dir / run_id / "etc" / "test.conf"
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file.write_text("v1", encoding="utf-8")

    fs = FakeFileOps(
        {
            Path("/etc/test.conf"): "v2",
            backup_file: "v1",
        }
    )
    steps = [
        {
            "name": "test_step",
            "status": "applied",
            "reversible": True,
            "changes": [],
            "backups": [str(backup_file)],
        }
    ]
    _create_sample_journal(journal_dir, run_id, steps)

    mgr = RollbackManager(
        journal_dir=journal_dir,
        backup_dir=backup_dir,
        runner=FakeRunner(),
        fs=fs,
    )

    # Rollback 1
    assert mgr.rollback(run_id=run_id, yes=True) is True
    assert fs.read_text(Path("/etc/test.conf")) == "v1"

    # Rollback 2 (idempotent, tidak error)
    assert mgr.rollback(run_id=run_id, yes=True) is True
    assert fs.read_text(Path("/etc/test.conf")) == "v1"


def test_rollback_irreversible_step_reported(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    run_id = "20260114T093000Z-irrev"

    messages_printed: list[str] = []
    steps = [
        {
            "name": "packages",
            "status": "applied",
            "reversible": False,
            "changes": [{"action": "install", "target": "curl", "after": "curl"}],
            "backups": [],
        }
    ]
    _create_sample_journal(journal_dir, run_id, steps)

    mgr = RollbackManager(
        journal_dir=journal_dir,
        runner=FakeRunner(),
        fs=FakeFileOps(),
        print_fn=messages_printed.append,
    )

    ok = mgr.rollback(run_id=run_id, yes=True)
    assert ok is True
    assert any("tidak dapat dibalik otomatis" in m for m in messages_printed)


def test_rollback_cli_integration(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    run_id = "20260114T093000Z-cli"
    _create_sample_journal(journal_dir, run_id, [])

    out = io.StringIO()
    with patch("os.geteuid", return_value=0):
        with patch(
            "hostkeeper.engine.rollback.RollbackManager.DEFAULT_JOURNAL_DIR",
            journal_dir,
        ):
            code = main(["rollback", "--list"], out=out)
            assert code == EXIT_OK
            assert run_id in out.getvalue()
