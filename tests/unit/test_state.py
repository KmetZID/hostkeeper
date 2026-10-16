"""Unit test untuk monitor/state.py (Tahap 3.2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hostkeeper.monitor.collector import Metric
from hostkeeper.monitor.state import StateManager


def test_state_manager_init_and_wal_mode(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    StateManager(db_path=db_file)
    assert db_file.exists()

    with sqlite3.connect(db_file) as conn:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"


def test_state_manager_metrics_save_and_latest(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    state = StateManager(db_path=db_file)

    now = 1000.0
    metrics1 = [
        Metric(name="mem.used_percent", value=50.0, unit="%"),
        Metric(name="cpu.load1", value=0.5, unit=""),
    ]
    state.save_metrics(metrics1, ts=now)

    metrics2 = [
        Metric(name="mem.used_percent", value=55.0, unit="%"),
    ]
    state.save_metrics(metrics2, ts=now + 60.0)

    latest = state.get_latest_metrics()
    assert latest["mem.used_percent"].value == 55.0
    assert latest["cpu.load1"].value == 0.5


def test_state_manager_alerts_save_and_get(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    state = StateManager(db_path=db_file)

    state.set_alert("mem.used_percent", status="warn", since=100.0, last_notified=100.0)
    alerts = state.get_alerts()
    assert "mem.used_percent" in alerts
    assert alerts["mem.used_percent"].status == "warn"
    assert alerts["mem.used_percent"].since == 100.0

    # Ubah status
    state.set_alert("mem.used_percent", status="crit", since=100.0, last_notified=200.0)
    alerts = state.get_alerts()
    assert alerts["mem.used_percent"].status == "crit"
    assert alerts["mem.used_percent"].last_notified == 200.0

    # Hapus alert saat ok
    state.clear_alert("mem.used_percent")
    alerts = state.get_alerts()
    assert "mem.used_percent" not in alerts


def test_state_manager_retention_prune(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    state = StateManager(db_path=db_file)

    now = 1000000.0
    fifteen_days_ago = now - (15 * 86400)
    five_days_ago = now - (5 * 86400)

    state.save_metrics([Metric(name="old", value=1)], ts=fifteen_days_ago)
    state.save_metrics([Metric(name="recent", value=2)], ts=five_days_ago)

    pruned = state.prune_retention(now=now, max_days=14)
    assert pruned == 1

    latest = state.get_latest_metrics()
    assert "old" not in latest
    assert "recent" in latest


def test_state_manager_corrupted_db_recovery(tmp_path: Path) -> None:
    db_file = tmp_path / "corrupted.db"
    # Tulis biner acak/rusak ke file db
    db_file.write_bytes(b"BOGUS SQLITE HEADER CORRUPTED FILE CONTENT THAT BREAKS")

    # StateManager harus menangani tanpa melempar exception,
    # melainkan membuat ulang DB
    state = StateManager(db_path=db_file)
    # Operasi baca/tulis harus tetap berjalan normal
    state.save_metrics([Metric(name="test", value=123)], ts=100.0)
    latest = state.get_latest_metrics()
    assert latest["test"].value == 123.0 or latest["test"].value == 123
