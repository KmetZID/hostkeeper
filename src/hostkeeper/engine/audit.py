"""Audit log append-only untuk hostkeeper (audit.jsonl, mode 640)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class AuditWriter:
    """Menulis event ke audit.jsonl secara append-only.

    Format: satu objek JSON per baris.
    File mode 640 sesuai SPEC 4.5.
    Path injectable untuk tes.
    """

    DEFAULT_PATH: Path = Path("/var/log/hostkeeper/audit.jsonl")

    def __init__(self, path: Path | None = None, run_id: str = "") -> None:
        self.path = path if path is not None else self.DEFAULT_PATH
        self.run_id = run_id

    def _write(self, record: dict[str, object]) -> None:
        """Menulis satu baris JSON ke audit log."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        # append-only, mode 640
        fd = os.open(
            str(self.path),
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o640,
        )
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def log_run_start(self, profile_path: str) -> None:
        self._write(
            {
                "ts": self._ts(),
                "run_id": self.run_id,
                "event": "run_start",
                "profile": profile_path,
            }
        )

    def log_plan(self, step: str, changes: int) -> None:
        self._write(
            {
                "ts": self._ts(),
                "run_id": self.run_id,
                "event": "plan",
                "step": step,
                "changes": changes,
            }
        )

    def log_command(self, argv: tuple[str, ...], returncode: int) -> None:
        self._write(
            {
                "ts": self._ts(),
                "run_id": self.run_id,
                "event": "command",
                "argv": list(argv),
                "returncode": returncode,
            }
        )

    def log_step_applied(self, step: str, changes: int) -> None:
        self._write(
            {
                "ts": self._ts(),
                "run_id": self.run_id,
                "event": "step_applied",
                "step": step,
                "changes": changes,
                "result": "ok",
            }
        )

    def log_step_verified(self, step: str) -> None:
        self._write(
            {
                "ts": self._ts(),
                "run_id": self.run_id,
                "event": "step_verified",
                "step": step,
                "result": "ok",
            }
        )

    def log_step_failed(self, step: str, detail: str) -> None:
        self._write(
            {
                "ts": self._ts(),
                "run_id": self.run_id,
                "event": "step_failed",
                "step": step,
                "detail": detail,
            }
        )

    def log_undo(self, step: str, reason: str | None = None) -> None:
        rec: dict[str, object] = {
            "ts": self._ts(),
            "run_id": self.run_id,
            "event": "undo",
            "step": step,
        }
        if reason is not None:
            rec["reason"] = reason
        self._write(rec)

    def log_run_end(self, result: str) -> None:
        self._write(
            {
                "ts": self._ts(),
                "run_id": self.run_id,
                "event": "run_end",
                "result": result,
            }
        )
