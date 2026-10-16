"""Penyimpanan status dan metrik SQLite (/var/lib/hostkeeper/state.db)."""

from __future__ import annotations

import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from hostkeeper.monitor.collector import Metric


@dataclass(frozen=True)
class AlertRecord:
    name: str
    status: str
    since: float
    last_notified: float


class StateManager:
    """Mengelola SQLite state.db untuk metrik deret waktu dan status alert."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path("/var/lib/hostkeeper/state.db")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics (
                        ts REAL NOT NULL,
                        name TEXT NOT NULL,
                        value TEXT NOT NULL
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name);"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alerts (
                        name TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        since REAL NOT NULL,
                        last_notified REAL NOT NULL
                    );
                    """
                )
                conn.commit()
        except sqlite3.DatabaseError as err:
            # Penanganan DB rusak: buat ulang database bersih
            sys.stderr.write(
                f"Peringatan: state.db rusak ({err}), membuat ulang database.\n"
            )
            try:
                backup_path = self.db_path.with_suffix(f".corrupt.{int(time.time())}")
                if self.db_path.exists():
                    self.db_path.rename(backup_path)
            except OSError:
                if self.db_path.exists():
                    self.db_path.unlink(missing_ok=True)

            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics (
                        ts REAL NOT NULL,
                        name TEXT NOT NULL,
                        value TEXT NOT NULL
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name);"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alerts (
                        name TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        since REAL NOT NULL,
                        last_notified REAL NOT NULL
                    );
                    """
                )
                conn.commit()

    def save_metrics(
        self,
        metrics: list[Metric],
        ts: float | None = None,
    ) -> None:
        current_ts = time.time() if ts is None else ts
        rows = [(current_ts, m.name, str(m.value)) for m in metrics]
        try:
            with self._get_connection() as conn:
                conn.executemany(
                    "INSERT INTO metrics (ts, name, value) VALUES (?, ?, ?);",
                    rows,
                )
                conn.commit()
        except sqlite3.DatabaseError:
            self._init_db()
            with self._get_connection() as conn:
                conn.executemany(
                    "INSERT INTO metrics (ts, name, value) VALUES (?, ?, ?);",
                    rows,
                )
                conn.commit()

    def get_latest_metrics(self) -> dict[str, Metric]:
        res: dict[str, Metric] = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT m.name, m.value
                    FROM metrics m
                    INNER JOIN (
                        SELECT name, MAX(ts) as max_ts
                        FROM metrics
                        GROUP BY name
                    ) latest ON m.name = latest.name AND m.ts = latest.max_ts;
                    """
                )
                for name, val_str in cursor.fetchall():
                    val: float | int | str | bool = val_str
                    try:
                        if "." in val_str:
                            val = float(val_str)
                        else:
                            val = int(val_str)
                    except ValueError:
                        if val_str.lower() in ("true", "yes"):
                            val = True
                        elif val_str.lower() in ("false", "no"):
                            val = False
                    res[name] = Metric(name=name, value=val)
        except sqlite3.DatabaseError:
            self._init_db()
        return res

    def get_alerts(self) -> dict[str, AlertRecord]:
        alerts: dict[str, AlertRecord] = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT name, status, since, last_notified FROM alerts;"
                )
                for name, status, since, last_notified in cursor.fetchall():
                    alerts[name] = AlertRecord(
                        name=name,
                        status=status,
                        since=float(since),
                        last_notified=float(last_notified),
                    )
        except sqlite3.DatabaseError:
            self._init_db()
        return alerts

    def set_alert(
        self,
        name: str,
        status: str,
        since: float,
        last_notified: float,
    ) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO alerts (name, status, since, last_notified)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        status = excluded.status,
                        since = excluded.since,
                        last_notified = excluded.last_notified;
                    """,
                    (name, status, since, last_notified),
                )
                conn.commit()
        except sqlite3.DatabaseError:
            self._init_db()
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO alerts (name, status, since, last_notified)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        status = excluded.status,
                        since = excluded.since,
                        last_notified = excluded.last_notified;
                    """,
                    (name, status, since, last_notified),
                )
                conn.commit()

    def clear_alert(self, name: str) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM alerts WHERE name = ?;", (name,))
                conn.commit()
        except sqlite3.DatabaseError:
            self._init_db()

    def prune_retention(
        self,
        now: float | None = None,
        max_days: int = 14,
    ) -> int:
        cutoff = (time.time() if now is None else now) - (max_days * 86400)
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM metrics WHERE ts < ?;",
                    (cutoff,),
                )
                conn.commit()
                return int(cursor.rowcount)
        except sqlite3.DatabaseError:
            self._init_db()
            return 0
